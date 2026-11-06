"""Rolling performance numbers: camera fps, model calls, share of frames skipped."""

from dataclasses import dataclass

WINDOW_MS = 2000


@dataclass
class PerfSnapshot:
    camera_fps: float
    inference_per_sec: float
    avg_inference_ms: float
    frames: int
    inferences: int
    skipped_pct: float  # share of frames on which the model was skipped, 0..100
    saved_ms: float     # estimated model time saved compared with running every frame


def _trim(times, now):
    while times and now - times[0] > WINDOW_MS:
        times.pop(0)


def _rate(times):
    """Events per second over the rolling window."""
    if len(times) < 2:
        return 0.0
    span = times[-1] - times[0]
    if span == 0:
        span = 1
    return (len(times) - 1) * 1000 / span


class PerfStats:
    def __init__(self):
        self.reset()

    def reset(self):
        self.frame_times = []
        self.inf_times = []
        self.frames = 0
        self.inferences = 0
        self.inf_ms_total = 0.0
        self.timed = 0  # model calls included in the average (the first one is warm-up)

    def on_frame(self, now):
        self.frames += 1
        self.frame_times.append(now)
        _trim(self.frame_times, now)

    def on_inference(self, now, ms):
        self.inferences += 1
        # The first call after a reset pays a one-off warm-up cost; leave it out of the average.
        if self.inferences > 1:
            self.inf_ms_total += ms
            self.timed += 1
        self.inf_times.append(now)
        _trim(self.inf_times, now)

    def snapshot(self, now):
        _trim(self.frame_times, now)
        _trim(self.inf_times, now)
        avg = self.inf_ms_total / self.timed if self.timed else 0.0
        skipped = self.frames - self.inferences
        skipped_pct = 100 * skipped / self.frames if self.frames else 0.0
        return PerfSnapshot(
            camera_fps=_rate(self.frame_times),
            inference_per_sec=_rate(self.inf_times),
            avg_inference_ms=avg,
            frames=self.frames,
            inferences=self.inferences,
            skipped_pct=skipped_pct,
            saved_ms=skipped * avg,
        )
