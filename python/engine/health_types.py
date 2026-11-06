"""Shared data shapes for the health rules."""

from dataclasses import dataclass, field

NOMINAL = "NOMINAL"
WATCH = "WATCH"
ACT = "ACT"

_RANK = {NOMINAL: 0, WATCH: 1, ACT: 2}

# Where it hurts (daily check-in).
BODY_LOCATIONS = ["knee", "hip", "ankle-foot", "lower-back", "upper-back-neck", "shoulder", "other"]


def worst_status(*statuses):
    """The worst of NOMINAL / WATCH / ACT."""
    result = NOMINAL
    for s in statuses:
        if _RANK[s] > _RANK[result]:
            result = s
    return result


@dataclass
class RepSample:
    """One counted rep, as the health rules need it."""
    min_knee_angle: float
    eccentric_s: float
    concentric_s: float
    asymmetry_deg: float
    confidence: float


@dataclass
class SessionRecord:
    """One prescribed training session. A skipped session has reps = []."""
    id: str
    crew_id: str
    exercise: str
    day: int  # mission day
    gravity_g: float
    prescribed_reps: int
    reps: list = field(default_factory=list)


@dataclass
class SessionMetrics:
    id: str
    day: int
    gravity_g: float
    prescribed_reps: int
    completed_reps: int   # reps counted at all
    valid_reps: int       # reps above the confidence threshold
    depth_deg: float      # median bottom knee angle; higher = shallower
    concentric_s: float
    eccentric_s: float
    asymmetry_deg: float  # mean left/right difference
    variability_deg: float  # standard deviation of the bottom knee angle across reps
    mean_confidence: float
    usable: bool          # trustworthy enough to feed baselines and rules


@dataclass
class CheckIn:
    """Daily 30-second self-check. All sliders are 0-10. One per crew member per mission day."""
    id: str
    crew_id: str
    day: int
    sleep: int    # 10 = slept very well
    fatigue: int  # 10 = exhausted
    pain: int     # 0 = no pain, 10 = worst imaginable
    pain_location: str | None  # None when pain is 0
    stress: int   # 10 = very stressed or low mood


@dataclass
class Baseline:
    depth_deg: float
    concentric_s: float
    asymmetry_deg: float
    variability_deg: float
    gravity_g: float
    days: list  # mission days the baseline was built from


@dataclass
class SeriesPoint:
    day: int
    value: float


@dataclass
class AlertWhat:
    metric: str
    unit: str
    baseline: float | None
    now: float
    delta: float  # now - baseline (or shortfall for adherence)
    summary: str
    series: list


@dataclass
class Alert:
    """Always three parts: what changed, why it matters in space, what to do."""
    id: str
    crew_id: str
    exercise: str | None  # None for crew-level alerts (check-in, vitals)
    rule: str
    level: str            # WATCH or ACT
    title: str
    what: AlertWhat
    why_text: str
    why_source_id: str
    actions: list
    day: int              # latest mission day contributing to the alert
    context: list = field(default_factory=list)  # notes from other signals, e.g. high fatigue


@dataclass
class Deltas:
    depth_deg: float
    concentric_pct: float
    asymmetry_deg: float
    variability_deg: float


@dataclass
class ExerciseAssessment:
    crew_id: str
    exercise: str
    status: str
    baseline: Baseline | None
    usable_sessions: int
    alerts: list
    asymmetry_series: list
    deltas: Deltas | None  # None until a comparable baseline exists
    notes: list            # e.g. "Building baseline (2/3)"


@dataclass
class CrewAssessment:
    crew_id: str
    status: str
    exercises: list
    alerts: list
