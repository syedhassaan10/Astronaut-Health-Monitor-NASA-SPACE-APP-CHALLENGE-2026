"""Battery-saving benchmark: run the same clip with every frame analysed, then with the
adaptive frame sampler, and compare model calls and rep counts.

Run:  python -m pose.benchmark            (uses the bundled demo clip, 3 loops)
      python -m pose.benchmark my.mp4 5   (another clip, 5 loops)
"""

import sys
from dataclasses import dataclass

import cv2

from pose.landmarker import DEMO_VIDEO, PoseEstimator
from pose.tracker import Tracker
from pose.video_source import VideoSource


@dataclass
class BenchRow:
    mode: str
    frames: int
    inferences: int
    reps: int
    avg_inference_ms: float


@dataclass
class BenchResult:
    full: BenchRow
    adaptive: BenchRow

    @property
    def reduction_pct(self):
        """Share of model calls saved by the adaptive sampler, 0..100."""
        if self.full.inferences == 0:
            return 0.0
        return 100 * (1 - self.adaptive.inferences / self.full.inferences)

    @property
    def same_reps(self):
        return self.full.reps == self.adaptive.reps


def run_once(video_path, mode, loops, exercise="squat", g=0.0, estimator_factory=PoseEstimator):
    """Play the clip `loops` times in one mode and count frames, model calls and reps."""
    estimator = estimator_factory()
    tracker = Tracker(exercise, g, estimator.detect, mode=mode)
    source = VideoSource("video", path=video_path, loop=True)
    frame_count = int(source.capture.get(cv2.CAP_PROP_FRAME_COUNT))
    total_frames = frame_count * loops
    last_t = 0.0
    try:
        for _ in range(total_frames):
            item = source.read()
            if item is None:
                break
            frame, t_ms = item
            last_t = t_ms
            tracker.process(frame, t_ms)
    finally:
        source.close()
        estimator.close()
    snap = tracker.perf.snapshot(last_t)
    return BenchRow(mode=mode, frames=snap.frames, inferences=snap.inferences, reps=tracker.reps,
                    avg_inference_ms=snap.avg_inference_ms)


def run_benchmark(video_path=DEMO_VIDEO, loops=3, estimator_factory=PoseEstimator):
    full = run_once(video_path, "full", loops, estimator_factory=estimator_factory)
    adaptive = run_once(video_path, "adaptive", loops, estimator_factory=estimator_factory)
    return BenchResult(full=full, adaptive=adaptive)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEMO_VIDEO
    loops = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    r = run_benchmark(path, loops)
    for row in (r.full, r.adaptive):
        print(f"{row.mode:9} frames={row.frames:5} model calls={row.inferences:5} reps={row.reps:3} "
              f"avg model time={row.avg_inference_ms:.1f} ms")
    print(f"Model calls saved: {r.reduction_pct:.1f}%  |  same rep count: {'yes' if r.same_reps else 'NO'}")


if __name__ == "__main__":
    main()
