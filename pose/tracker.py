"""The camera tracker: one call per video frame.

frame -> frame sampler (battery saving) -> pose model -> knee angles -> rep counter
      -> form score and plain feedback ("Good depth", "Go deeper")

The pose model is passed in as a function, so this file has no MediaPipe code and can be
tested with made-up poses.
"""

import time
from dataclasses import dataclass, field

from engine.adaptive_sampler import DEFAULT_SAMPLER, AdaptiveSampler
from engine.form_feedback import assess_rep, feedback_text, targets_for
from engine.gravity_engine import tempo_for_g
from engine.perf_stats import PerfStats
from engine.pose_math import joint_angles, mean_visibility
from engine.rep_detector import REP_CONFIGS, RepDetector, Sample

# A frame below this confidence is not given to the rep counter at all.
MIN_FRAME_CONF = 0.3
# Below this, the astronaut is told to move the camera.
UNRELIABLE_CONF = 0.5
# How long the "measurement unreliable" message stays after a rejected rep.
BANNER_MS = 5000


@dataclass
class LiveState:
    present: bool = False   # a person is in view
    knee: float | None = None
    confidence: float = 0.0
    level: str = "neutral"  # green / amber / red / neutral, for the overlay colour


@dataclass
class RepEvent:
    kind: str                  # "rep", "unreliable" or "partial"
    metrics: object = None     # RepMetrics (None for partial)
    assessment: object = None  # FormAssessment (only for "rep")
    feedback: str = ""         # e.g. "Good depth", "Go deeper"


@dataclass
class FrameResult:
    ran_model: bool
    pose: object = None        # PoseResult from the last model run (kept between runs for drawing)
    live: LiveState = field(default_factory=LiveState)
    event: RepEvent | None = None


def live_depth_level(knee, depth_target_deg):
    """Overlay colour while going down: green at depth, amber close to it."""
    if knee <= depth_target_deg + 5:
        return "green"
    if knee <= depth_target_deg + 20:
        return "amber"
    return "neutral"


class Tracker:
    def __init__(self, exercise, g, detect, mode="adaptive", sampler_cfg=DEFAULT_SAMPLER):
        self.exercise = exercise
        self.g = g
        self.detect = detect
        self.sampler = AdaptiveSampler(mode, sampler_cfg)
        self.perf = PerfStats()
        cfg = REP_CONFIGS.get(exercise)
        self.detector = RepDetector(cfg) if cfg else None
        self.last_pose = None
        self.last_level = "neutral"
        self.live = LiveState()
        self.reps = 0
        self.partials = 0
        self.rejected = 0
        self.banner_until = -1.0
        self.last_feedback = ""

    @property
    def mode(self):
        return self.sampler.mode

    def set_mode(self, mode):
        self.sampler.set_mode(mode)
        self.perf.reset()

    def set_conditions(self, exercise, g):
        """Change exercise or gravity without stopping the camera."""
        self.exercise = exercise
        self.g = g
        cfg = REP_CONFIGS.get(exercise)
        self.detector = RepDetector(cfg) if cfg else None

    def process(self, frame, t_ms):
        """Handle one video frame taken at time t_ms (milliseconds)."""
        self.perf.on_frame(t_ms)
        event = None
        ran = self.sampler.should_run(t_ms)
        if ran:
            started = time.perf_counter()
            pose = self.detect(frame, t_ms)
            self.perf.on_inference(t_ms, (time.perf_counter() - started) * 1000)
            event = self._handle_pose(pose, t_ms)

        cfg = REP_CONFIGS.get(self.exercise)
        moving = self.detector is not None and self.detector.phase == "moving"
        if cfg and moving and self.live.knee is not None:
            self.live.level = live_depth_level(self.live.knee, cfg.depth_target_deg)
        else:
            self.live.level = self.last_level
        return FrameResult(ran_model=ran, pose=self.last_pose, live=self.live, event=event)

    def _handle_pose(self, pose, t_ms):
        if pose is None:
            self.last_pose = None
            self.sampler.on_result(None, t_ms)
            self.live = LiveState(level=self.last_level)
            return None

        self.last_pose = pose
        angles = joint_angles(pose.world)
        confidence = mean_visibility(pose.landmarks)
        knee = angles.knee if angles else None
        self.sampler.on_result(knee, t_ms)
        self.live = LiveState(present=True, knee=knee, confidence=confidence, level=self.last_level)
        if angles is None or confidence < MIN_FRAME_CONF or self.detector is None:
            return None

        sample = Sample(t_ms=t_ms, knee=angles.knee, asymmetry_deg=abs(angles.knee_l - angles.knee_r),
                        confidence=confidence)
        result = self.detector.push(sample)
        if result is None:
            return None
        if result.kind == "partial":
            self.partials += 1
            return RepEvent(kind="partial", feedback="Go deeper")
        if result.kind == "unreliable":
            self.rejected += 1
            self.banner_until = t_ms + BANNER_MS
            return RepEvent(kind="unreliable", metrics=result.rep, feedback="Measurement unreliable")

        cfg = REP_CONFIGS[self.exercise]
        assessment = assess_rep(result.rep, targets_for(cfg, tempo_for_g(self.g)))
        self.last_level = assessment.overall
        self.reps += 1
        self.last_feedback = feedback_text(assessment)
        return RepEvent(kind="rep", metrics=result.rep, assessment=assessment, feedback=self.last_feedback)

    def message(self, t_ms):
        """The camera warning to show right now, or None."""
        if not self.live.present:
            return "No person detected. Step into the frame, hips to ankles in view."
        if self.live.confidence < UNRELIABLE_CONF or t_ms < self.banner_until:
            return "Measurement unreliable. Move the camera so your whole body is in view."
        return None
