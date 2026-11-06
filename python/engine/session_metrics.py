"""Small statistics helpers and the per-session summary."""

import math

from config.health_rules import HEALTH_RULES
from engine.health_types import SessionMetrics


def median(values):
    if not values:
        return math.nan
    s = sorted(values)
    middle = len(s) // 2
    if len(s) % 2 == 1:
        return s[middle]
    return (s[middle - 1] + s[middle]) / 2


def mean(values):
    if not values:
        return math.nan
    return sum(values) / len(values)


def std_dev(values):
    """Sample standard deviation (n - 1); 0 for fewer than two values."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    total = 0.0
    for v in values:
        total += (v - m) ** 2
    return math.sqrt(total / (len(values) - 1))


def summarize_session(rec, cfg=HEALTH_RULES):
    """Summarise one session.

    Low-confidence reps are dropped first, so they can never move a baseline or a rule.
    A session is usable only with at least min_valid_reps valid reps and a mean
    confidence at or above the threshold.
    """
    valid = [r for r in rec.reps if r.confidence >= cfg.min_confidence]
    mean_confidence = mean([r.confidence for r in rec.reps])
    usable = len(valid) >= cfg.min_valid_reps and mean_confidence >= cfg.min_confidence
    return SessionMetrics(
        id=rec.id,
        day=rec.day,
        gravity_g=rec.gravity_g,
        prescribed_reps=rec.prescribed_reps,
        completed_reps=len(rec.reps),
        valid_reps=len(valid),
        depth_deg=median([r.min_knee_angle for r in valid]),
        concentric_s=median([r.concentric_s for r in valid]),
        eccentric_s=median([r.eccentric_s for r in valid]),
        asymmetry_deg=mean([r.asymmetry_deg for r in valid]),
        variability_deg=std_dev([r.min_knee_angle for r in valid]),
        mean_confidence=mean_confidence,
        usable=usable,
    )


def slope_per_day(points):
    """Least-squares slope of value against day; 0 if it cannot be computed."""
    if len(points) < 2:
        return 0.0
    mean_day = mean([p.day for p in points])
    mean_value = mean([p.value for p in points])
    num = 0.0
    den = 0.0
    for p in points:
        num += (p.day - mean_day) * (p.value - mean_value)
        den += (p.day - mean_day) ** 2
    if den == 0:
        return 0.0
    return num / den
