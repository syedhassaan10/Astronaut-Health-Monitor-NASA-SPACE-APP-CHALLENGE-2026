"""Rep counting from the knee angle: top -> bottom -> top.

There is a gap (hysteresis) between "leaving the top" and "back at the top",
so jitter around one value cannot create phantom reps.
All thresholds are demonstration values.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RepConfig:
    top_deg: float          # knee angle at/above which the body is "at the top" (standing)
    descend_deg: float      # below this, a descent has started
    bottom_deg: float       # must go below this for the rep to count (depth gate)
    depth_target_deg: float  # form feedback: green at or below this
    min_confidence: float   # mean landmark confidence needed to trust a rep


REP_CONFIGS = {
    "squat": RepConfig(top_deg=160, descend_deg=150, bottom_deg=120, depth_target_deg=100, min_confidence=0.6),
    "deadlift": RepConfig(top_deg=165, descend_deg=155, bottom_deg=145, depth_target_deg=130, min_confidence=0.6),
    # Heel raise has no rep config: the knee barely bends, so the camera cannot count it.
}


@dataclass
class Sample:
    t_ms: float
    knee: float
    asymmetry_deg: float  # |left knee - right knee|
    confidence: float     # mean landmark confidence 0..1


@dataclass
class RepMetrics:
    rep_no: int
    start_ms: float
    end_ms: float
    min_knee_angle: float
    eccentric_s: float   # time going down
    concentric_s: float  # time coming up
    hold_s: float        # time at the bottom
    asymmetry_deg: float
    confidence: float


@dataclass
class RepResult:
    kind: str  # "rep", "unreliable" (low confidence) or "partial" (never reached depth)
    rep: RepMetrics | None = None


def _cross_time(p, c, level):
    """Time at which the line from sample p to sample c crosses `level`."""
    d = c.knee - p.knee
    if abs(d) < 1e-9:
        return c.t_ms
    f = (level - p.knee) / d
    f = min(1.0, max(0.0, f))
    return p.t_ms + f * (c.t_ms - p.t_ms)


class RepDetector:
    # Gap (ms) between samples above which tracking counts as lost.
    MAX_GAP_MS = 1500
    # Samples within this many degrees of the minimum count as "at the bottom".
    BOTTOM_BAND_DEG = 4
    # Window (ms) over which the person's standing angle is learned.
    CALIB_WINDOW_MS = 8000
    # Need at least this much history before the top is adapted.
    CALIB_MIN_MS = 1500
    # The learned top sits this many degrees below the person's typical standing angle.
    TOP_MARGIN_DEG = 4
    # Never learn a top lower than bottom_deg + this (a deep hold must not count as standing).
    MIN_TOP_ABOVE_BOTTOM_DEG = 25

    def __init__(self, cfg):
        self.cfg = cfg
        self.rep_no = 0
        self.reset()

    def set_config(self, cfg):
        self.cfg = cfg
        self.reset()

    def reset(self):
        self.phase = "idle"  # "idle", "top" or "moving"
        self.prev = None
        self.last_at_top = None
        self.first_below_top = None
        self.last_below_top = None
        self.hist = []
        self.top = self.cfg.top_deg
        self.descend = self.cfg.descend_deg
        self.descent_start_ms = 0.0
        self.buf = []
        self.reached_bottom = False
        self.sum_conf = 0.0
        self.sum_asym = 0.0
        self.n = 0

    def _recalibrate(self, s):
        """Learn this person's own standing angle.

        Real people rarely straighten to a textbook 160-180 degrees, so "top" is the 90th
        percentile of recent knee angles minus a small margin. It never goes above the
        configured top, nor below bottom_deg + MIN_TOP_ABOVE_BOTTOM_DEG.
        """
        c = self.cfg
        self.hist.append(s)
        while len(self.hist) > 1 and s.t_ms - self.hist[0].t_ms > self.CALIB_WINDOW_MS:
            self.hist.pop(0)
        if s.t_ms - self.hist[0].t_ms < self.CALIB_MIN_MS:
            return
        knees = sorted(h.knee for h in self.hist)
        index = min(len(knees) - 1, math.floor(0.9 * len(knees)))
        reference = knees[index]
        floor = c.bottom_deg + self.MIN_TOP_ABOVE_BOTTOM_DEG
        self.top = min(c.top_deg, max(floor, reference - self.TOP_MARGIN_DEG))
        self.descend = self.top - (c.top_deg - c.descend_deg)

    def push(self, s):
        """Feed one sample. Returns a RepResult when a rep ends, otherwise None."""
        prev = self.prev
        self.prev = s
        if prev is not None and s.t_ms - prev.t_ms > self.MAX_GAP_MS:
            # The person left the frame or tracking was lost.
            self.phase = "idle"
            self.hist = []
        if self.phase != "moving":
            # Thresholds stay frozen while a rep is in progress.
            self._recalibrate(s)

        if self.phase == "idle":
            if s.knee >= self.top:
                self.phase = "top"
                self.last_at_top = s
                self.first_below_top = None
            return None

        if self.phase == "top":
            return self._push_at_top(s, prev)

        return self._push_moving(s)

    def _push_at_top(self, s, prev):
        if s.knee >= self.top:
            self.last_at_top = s
            self.first_below_top = None
        elif self.first_below_top is None:
            self.first_below_top = s

        if s.knee < self.descend and prev is not None:
            self.phase = "moving"
            if self.last_at_top is not None and self.first_below_top is not None:
                self.descent_start_ms = _cross_time(self.last_at_top, self.first_below_top, self.top)
            else:
                self.descent_start_ms = _cross_time(prev, s, self.descend)
            self.buf = [s]
            self.reached_bottom = s.knee < self.cfg.bottom_deg
            self.last_below_top = s
            self.sum_conf = s.confidence
            self.sum_asym = s.asymmetry_deg
            self.n = 1
        return None

    def _push_moving(self, s):
        c = self.cfg
        self.sum_conf += s.confidence
        self.sum_asym += s.asymmetry_deg
        self.n += 1
        self.buf.append(s)
        if s.knee < c.bottom_deg:
            self.reached_bottom = True

        if s.knee < self.top:
            self.last_below_top = s
            return None

        # Back at the top: the rep is complete.
        self.phase = "top"
        self.last_at_top = s
        self.first_below_top = None
        if not self.reached_bottom:
            return RepResult(kind="partial")

        if self.last_below_top is not None:
            end_ms = _cross_time(self.last_below_top, s, self.top)
        else:
            end_ms = s.t_ms

        # The bottom is a band within BOTTOM_BAND_DEG of the minimum. Going down ends when the
        # band is first entered; coming up starts when it is last left.
        min_knee = min(b.knee for b in self.buf)
        in_band = [b for b in self.buf if b.knee <= min_knee + self.BOTTOM_BAND_DEG]
        band_start_ms = in_band[0].t_ms
        band_end_ms = in_band[-1].t_ms

        self.rep_no += 1
        rep = RepMetrics(
            rep_no=self.rep_no,
            start_ms=self.descent_start_ms,
            end_ms=end_ms,
            min_knee_angle=min_knee,
            eccentric_s=max(0.0, (band_start_ms - self.descent_start_ms) / 1000),
            concentric_s=max(0.0, (end_ms - band_end_ms) / 1000),
            hold_s=max(0.0, (band_end_ms - band_start_ms) / 1000),
            asymmetry_deg=self.sum_asym / self.n,
            confidence=self.sum_conf / self.n,
        )
        if rep.confidence >= c.min_confidence:
            return RepResult(kind="rep", rep=rep)
        return RepResult(kind="unreliable", rep=rep)
