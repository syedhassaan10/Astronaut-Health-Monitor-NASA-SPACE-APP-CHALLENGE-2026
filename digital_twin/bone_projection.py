"""
analytics/bone_projection.py

Simple bone-mineral-density (BMD) loss projection for a spaceflight mission.

This is a deliberately SIMPLE projection, not a validated physiological model.

Background (NASA Digital Astronaut Project, NTRS 20140003236):
  astronauts lose roughly 1-2 % of bone mass per month in microgravity,
  especially in the proximal femur, and exercise is the main countermeasure.

Model:
  effective_rate = monthly_loss_rate * (1 - exercise_effectiveness)
  BMD(t)         = 100 * (1 - effective_rate/100) ** (t_days / 30)      [% of baseline]

Inputs:
  monthly_loss_rate_pct     : % bone loss per month with NO countermeasure
                              (e.g. the astronaut's bone_density_loss reading)
  exercise_effectiveness    : 0.0 (no exercise benefit) .. 1.0 (loss fully prevented)
"""

from typing import Dict, List

# Reference range reported by NASA's Digital Astronaut Project (no countermeasure)
NASA_RANGE_PCT_PER_MONTH = (1.0, 2.0)


def _bmd_curve(rate_pct_per_month: float, days: List[int]) -> List[float]:
    """BMD as % of baseline, compounded monthly (30-day month)."""
    keep = 1.0 - rate_pct_per_month / 100.0
    return [100.0 * (keep ** (d / 30.0)) for d in days]


def project_bone_loss(
    monthly_loss_rate_pct: float,
    mission_days: int,
    exercise_effectiveness: float = 0.0,
) -> Dict:
    """
    Project BMD over the mission.

    Returns a dict with:
      days, bmd_percent            : projection for this astronaut
      ref_low, ref_high            : NASA 1% and 2%/month reference curves (no exercise)
      effective_rate_pct_per_month : rate after exercise benefit
      total_loss_pct               : bone lost by end of mission (% of baseline)
      loss_avoided_pct             : loss avoided thanks to exercise (vs no exercise)
    """
    if mission_days <= 0:
        raise ValueError("mission_days must be positive")
    if monthly_loss_rate_pct < 0:
        raise ValueError("monthly_loss_rate_pct must be >= 0")

    e = min(max(float(exercise_effectiveness), 0.0), 1.0)
    effective = monthly_loss_rate_pct * (1.0 - e)

    days = list(range(0, int(mission_days) + 1))
    bmd = _bmd_curve(effective, days)
    bmd_no_ex = _bmd_curve(monthly_loss_rate_pct, days)

    return {
        "days": days,
        "bmd_percent": bmd,
        "ref_low": _bmd_curve(NASA_RANGE_PCT_PER_MONTH[0], days),
        "ref_high": _bmd_curve(NASA_RANGE_PCT_PER_MONTH[1], days),
        "effective_rate_pct_per_month": effective,
        "total_loss_pct": 100.0 - bmd[-1],
        "loss_avoided_pct": bmd[-1] - bmd_no_ex[-1],
    }