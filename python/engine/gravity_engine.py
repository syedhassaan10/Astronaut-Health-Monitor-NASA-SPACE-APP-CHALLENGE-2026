"""Simplified model of gravity-dependent resistance training.

The ARED-style target load is SIMULATED: we do not control any hardware, and every
constant here is a demonstration value, not clinically validated.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ExerciseSpec:
    id: str
    label: str
    exercise_factor: float        # share of the "missing" body weight the device should replace (0..1)
    base_training_load_kg: float  # load prescribed at 1 g, before gravity compensation


EXERCISES = {
    "squat": ExerciseSpec("squat", "Squat", 1.0, 40),
    "deadlift": ExerciseSpec("deadlift", "Deadlift", 0.6, 50),
    "heelRaise": ExerciseSpec("heelRaise", "Heel raise", 0.8, 20),
}

EXERCISE_IDS = list(EXERCISES.keys())

# Standard gravity (m/s2).
G0 = 9.81
# Approximate ARED maximum load, about 600 lb = 272 kg.
ARED_MAX_KG = 272


@dataclass
class Tempo:
    eccentric_s: float
    concentric_s: float
    hold_s: float


@dataclass
class VolumeGuidance:
    sessions_per_week: int
    sets: int
    reps: int
    minutes_per_day: int


@dataclass
class Plan:
    g: float
    effective_bodyweight_n: float
    target_load_kg: float
    capped: bool
    tempo: Tempo
    volume: VolumeGuidance


def clamp_g(g):
    """Gravity as a fraction of Earth, limited to 0..1. Not-a-number counts as Earth."""
    if not math.isfinite(g):
        return 1.0
    return min(1.0, max(0.0, g))


def lerp_by_g(g, at_zero, at_earth):
    """Straight line between the value at 0 g and the value at 1 g."""
    x = clamp_g(g)
    return at_zero + (at_earth - at_zero) * x


def effective_bodyweight_n(mass_kg, g):
    """Body weight the muscles and bones actually carry: mass x g x 9.81."""
    return mass_kg * clamp_g(g) * G0


def target_ared_load_kg(mass_kg, g, ex):
    """Simulated device load: replace the missing gravity load, plus the normal training load.

    target = mass x (1 - g) x exercise_factor + base_training_load, capped at ARED_MAX_KG.
    Returns (kg, capped).
    """
    raw = mass_kg * (1 - clamp_g(g)) * ex.exercise_factor + ex.base_training_load_kg
    return min(raw, ARED_MAX_KG), raw > ARED_MAX_KG


def tempo_for_g(g):
    """1 g: 2 s down / 1 s up / no hold. 0 g: 4 s down / 2 s up / 1 s hold.

    Lower gravity means slower, more controlled reps to keep tension on the muscle.
    """
    return Tempo(
        eccentric_s=lerp_by_g(g, 4, 2),
        concentric_s=lerp_by_g(g, 2, 1),
        hold_s=lerp_by_g(g, 1, 0),
    )


def round_half_up(x):
    """Round .5 upwards (Python's round() would round 4.5 to 4)."""
    return math.floor(x + 0.5)


def volume_for_g(g):
    """1 g: 3 sessions/week, 3 x 8, 30 min/day. 0 g: 6 sessions/week, 4 x 10, 120 min/day."""
    return VolumeGuidance(
        sessions_per_week=round_half_up(lerp_by_g(g, 6, 3)),
        sets=round_half_up(lerp_by_g(g, 4, 3)),
        reps=round_half_up(lerp_by_g(g, 10, 8)),
        minutes_per_day=round_half_up(lerp_by_g(g, 120, 30)),
    )


def build_plan(mass_kg, g, exercise_id):
    """Full exercise plan for one exercise at gravity g."""
    ex = EXERCISES[exercise_id]
    kg, capped = target_ared_load_kg(mass_kg, g, ex)
    return Plan(
        g=clamp_g(g),
        effective_bodyweight_n=effective_bodyweight_n(mass_kg, g),
        target_load_kg=kg,
        capped=capped,
        tempo=tempo_for_g(g),
        volume=volume_for_g(g),
    )
