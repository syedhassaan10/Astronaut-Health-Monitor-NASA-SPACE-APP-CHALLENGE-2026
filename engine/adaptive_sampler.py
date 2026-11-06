"""Battery saving: decide, frame by frame, whether to run the pose model.

- full:     every frame.
- adaptive: every `base_stride`-th frame, but every frame for `burst_ms` after the knee
            nearly stops moving (a turning point), so the exact top and bottom of each
            rep are still captured.

The turning-point trigger has two levels (a Schmitt trigger): it arms only after the knee
was clearly moving, and fires when the speed drops. Jitter while standing still therefore
never starts a burst.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SamplerConfig:
    # Run the model on every Nth frame. 7 clears the 75% saving target with the same rep count.
    base_stride: int = 7
    # After a turning point, run every frame for this long.
    burst_ms: float = 300
    # Knee speed (degrees/second) below which we are "near a turning point".
    velocity_thresh_deg_per_s: float = 8
    # Speed must first go above thresh x arm_factor to arm the trigger.
    arm_factor: float = 2
    # Speed is measured over at least this window (ms) to ignore landmark jitter.
    velocity_window_ms: float = 150


DEFAULT_SAMPLER = SamplerConfig()


class AdaptiveSampler:
    def __init__(self, mode="adaptive", cfg=DEFAULT_SAMPLER):
        self.mode = mode
        self.cfg = cfg
        self.reset()

    def set_mode(self, mode):
        self.mode = mode
        self.reset()

    def reset(self):
        self.since_run = 0
        self.burst_until = -math.inf
        self.history = []  # list of (knee, t_ms)
        self.armed = False

    def should_run(self, now_ms):
        """Call once per camera frame. True means: run the pose model on this frame."""
        if self.mode == "full":
            return True
        self.since_run += 1
        in_burst = now_ms < self.burst_until
        run = in_burst or self.since_run >= self.cfg.base_stride
        if run:
            self.since_run = 0
        return run

    def on_result(self, knee, t_ms):
        """Call after each model run with the knee angle (None if no person was found)."""
        if self.mode != "adaptive":
            return
        if knee is None:
            self.history = []
            self.armed = False
            return

        h = self.history
        h.append((knee, t_ms))
        while len(h) > 1 and t_ms - h[1][1] >= self.cfg.velocity_window_ms * 3:
            h.pop(0)

        # Reference = the newest earlier sample that is at least velocity_window_ms old.
        reference = None
        for i in range(len(h) - 2, -1, -1):
            if t_ms - h[i][1] >= self.cfg.velocity_window_ms:
                reference = h[i]
                break
        if reference is None:
            return

        ref_knee, ref_t = reference
        speed = abs(knee - ref_knee) / (t_ms - ref_t) * 1000
        threshold = self.cfg.velocity_thresh_deg_per_s
        if speed > threshold * self.cfg.arm_factor:
            self.armed = True
        elif self.armed and speed < threshold:
            # Turning point: capture every frame for a moment.
            self.armed = False
            self.burst_until = t_ms + self.cfg.burst_ms
