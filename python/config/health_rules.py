"""All health thresholds in one place.

Every number here is a DEMONSTRATION value, not clinically validated.
They are kept in one file so reviewers can read and change them.
To try other values, copy the config with dataclasses.replace(...).
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Levels:
    """A deterioration at or above `watch` raises WATCH, at or above `act` raises ACT."""
    watch: float
    act: float


@dataclass(frozen=True)
class AdherenceRules:
    """Completed / prescribed volume. WATCH or ACT when the ratio drops BELOW these."""
    watch: float = 0.8
    act: float = 0.6
    window_days: int = 7


@dataclass(frozen=True)
class CheckinRules:
    """Daily check-in rules. All sliders are 0-10."""
    # Rules look at the latest N check-ins.
    window: int = 3
    # Pain is "sustained" when at least min_sustained of the window are at or above the level.
    pain: Levels = Levels(watch=4, act=7)
    min_sustained: int = 2
    # A single report at or above this raises WATCH straight away.
    acute_pain: int = 7
    # Knee pain at or above this counts for the combined knee pain + asymmetry rule.
    knee_pain_min: int = 3
    # Combined rule: asymmetry must have risen at least this many degrees above baseline.
    combined_asymmetry_deg: float = 2
    # Recovery: sleep at or below AND fatigue at or above these, sustained.
    sleep_low: int = 4
    fatigue_high: int = 7
    # Stress at or above this, sustained.
    stress_high: int = 8


@dataclass(frozen=True)
class Range:
    """A normal band for a vital sign.

    Below watch_low or above watch_high raises WATCH.
    Below act_low or above act_high raises ACT.
    None means "no limit on this side".
    """
    watch_low: float | None
    watch_high: float | None
    act_low: float | None
    act_high: float | None


@dataclass(frozen=True)
class VitalsRules:
    """Vital-sign limits for a resting adult. Demonstration values only."""
    heart_rate: Range = Range(watch_low=50, watch_high=100, act_low=40, act_high=120)        # beats per minute
    systolic: Range = Range(watch_low=90, watch_high=135, act_low=80, act_high=160)          # mmHg
    diastolic: Range = Range(watch_low=None, watch_high=85, act_low=None, act_high=100)      # mmHg
    temperature_c: Range = Range(watch_low=35.5, watch_high=37.8, act_low=35.0, act_high=38.5)
    glucose_mg_dl: Range = Range(watch_low=70, watch_high=180, act_low=54, act_high=250)
    spo2_pct: Range = Range(watch_low=95, watch_high=None, act_low=90, act_high=None)
    # Resting heart rate rising above the person's own baseline (median of the first readings).
    baseline_readings: int = 3
    recent_readings: int = 3
    heart_rate_rise_bpm: Levels = Levels(watch=10, act=20)


@dataclass(frozen=True)
class HealthRulesConfig:
    # Baseline = median of the first N usable sessions.
    baseline_sessions: int = 3
    # A session needs at least this many valid reps to be usable.
    min_valid_reps: int = 5
    # Reps (and sessions) below this mean confidence are never used.
    min_confidence: float = 0.6
    # Rules compare the median of up to this many latest usable sessions with the baseline.
    recent_sessions: int = 3
    # Need at least this many usable sessions after the baseline before any movement rule fires.
    min_recent_sessions: int = 2
    # Sessions at a gravity further than this (in g) from the baseline's are not comparable.
    gravity_tolerance: float = 0.1

    # Depth decline: bottom knee angle shallower than baseline by this many degrees.
    depth: Levels = Levels(watch=8, act=16)
    # Slower lifting phase (power proxy): % longer than baseline.
    concentric: Levels = Levels(watch=15, act=30)
    # Rising left/right difference: degrees above baseline.
    asymmetry: Levels = Levels(watch=4, act=8)
    # Rising rep-to-rep variability: degrees of standard deviation above baseline.
    variability: Levels = Levels(watch=3, act=6)
    adherence: AdherenceRules = AdherenceRules()

    # This many WATCH rules at the same time escalate the exercise to ACT.
    escalate_watch_count: int = 3

    checkin: CheckinRules = field(default_factory=CheckinRules)
    vitals: VitalsRules = field(default_factory=VitalsRules)


HEALTH_RULES = HealthRulesConfig()
