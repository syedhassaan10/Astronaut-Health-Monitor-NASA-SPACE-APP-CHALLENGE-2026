"""Published NASA figures that shape the demo crew's data.

Each figure was read in the NASA document itself (page given) on 7 November 2026.
The demo is synthetic: it squeezes a long-duration mission (about 6 months) into 30 demo days,
so the trends that NASA reports over a whole mission appear within the demo.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Figure:
    id: str
    value: float
    statement: str    # what NASA reports, in plain words
    source_id: str    # see guidance/sources.py
    page: int
    used_for: str     # how the demo uses it


# Leg strength lost on a long-duration mission when exercise is not enough.
UNTREATED_STRENGTH_LOSS = Figure(
    "untreated-strength-loss", 0.30,
    "Extensor and flexor muscles may lose up to 30% isokinetic torque during long-duration missions.",
    "nasa-sp-2025-deconditioning", 5,
    "Rivera, who misses exercise from day 10, loses leg strength towards this 30% by day 30.")

# Lower-body strength lost on long-duration ISS missions with the ARED resistive exercise device.
ARED_STRENGTH_LOSS = Figure(
    "ared-strength-loss", 0.09,
    "With the ARED device on 180+ day ISS missions, lower-body strength fell by 9% on average (range 4-12%).",
    "nasa-sp-2025-deconditioning", 23,
    "Okafor, who follows the exercise plan, loses 9% over the demo mission and stays within normal limits.")

# NASA's standard: keep at least 80% of pre-flight strength.
STRENGTH_STANDARD = Figure(
    "strength-standard", 0.80,
    "NASA-STD-3001 requires crewmembers to keep skeletal muscle strength at or above 80% of baseline.",
    "nasa-sp-2025-deconditioning", 16,
    "Explains why a 30% loss (Rivera) needs action while a 9% loss (Okafor) does not.")

# Bone mineral density lost per month at the hip and spine.
BONE_LOSS_PER_MONTH = Figure(
    "bone-loss-per-month", 0.015,
    "Astronauts lose on average 1-1.5% of pre-flight bone mineral density per month at the hip and spine.",
    "hrp-bone-2024", 10,
    "Shown on the body map. OrbitFit does not measure bone; it tracks the exercise that protects it.")

ALL = [UNTREATED_STRENGTH_LOSS, ARED_STRENGTH_LOSS, STRENGTH_STANDARD, BONE_LOSS_PER_MONTH]

# The demo squeezes a long-duration mission into 30 days.
DEMO_MISSION_DAYS = 180


def strength_left(loss_so_far):
    """Share of baseline strength left (1.0 = all of it)."""
    return 1 - loss_so_far


def lifting_time(base_s, loss_so_far):
    """Modelling assumption: with less strength the same lift takes longer (time ~ 1 / strength)."""
    return base_s / strength_left(loss_so_far)
