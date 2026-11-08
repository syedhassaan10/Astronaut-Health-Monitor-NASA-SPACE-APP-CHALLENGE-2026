"""Deterministic demo data: 3 crew x 30 mission days of squat sessions at 0 g (LEO),
daily check-ins and daily vital signs. The same on every computer.

  c1 Rivera : slowly getting weaker (depth, speed, asymmetry, missed reps), sleeping worse,
              resting heart rate creeping up late in the mission
  c2 Okafor : normal (noise only)
  c3 Tanaka : left/right difference rising, with knee pain from day 9
"""

import math

from engine.health_types import CheckIn, RepSample, SessionRecord
from engine.vitals_rules import VitalReading
from data.nasa_evidence import ARED_STRENGTH_LOSS, UNTREATED_STRENGTH_LOSS, lifting_time

DEMO_DAYS = 30
PRESCRIBED_REPS = 24  # 3 sets x 8

_MASK = 0xFFFFFFFF


def _imul(a, b):
    """32-bit integer multiply, kept as an unsigned number."""
    return (a * b) & _MASK


def make_rng(seed):
    """Small seeded random generator (mulberry32), identical to the original app's."""
    state = [seed & _MASK]

    def next_value():
        state[0] = (state[0] + 0x6D2B79F5) & _MASK
        t = state[0]
        t = _imul(t ^ (t >> 15), t | 1)
        t = t ^ ((t + _imul(t ^ (t >> 7), t | 61)) & _MASK)
        return ((t ^ (t >> 14)) & _MASK) / 4294967296

    return next_value


def gauss(r):
    """Standard normal sample (Box-Muller)."""
    u = max(r(), 1e-9)
    return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * r())


def round_half_up(x):
    return math.floor(x + 0.5)


def after(day, start):
    return max(0, day - start)


# ---- exercise sessions -----------------------------------------------------------------------

def _c1_completion(d):
    if d <= 21:
        return 1
    return max(0.45, 1 - 0.07 * (d - 21))


# Strength lost so far, shaped by published NASA figures (data/nasa_evidence.py). The demo squeezes a
# long-duration mission into 30 days, so the loss NASA reports over a whole mission is reached by day 30.
def c1_strength_loss(d):
    """Rivera misses exercise from day 10: towards NASA's 'up to 30%' leg strength loss by day 30."""
    return UNTREATED_STRENGTH_LOSS.value * after(d, 10) / (DEMO_DAYS - 10)


def c2_strength_loss(d):
    """Okafor follows the plan: NASA's average 9% lower-body strength loss with ARED, spread over the mission."""
    return ARED_STRENGTH_LOSS.value * (d - 1) / (DEMO_DAYS - 1)


# Modelling assumption: a weaker squat is also a shallower one (60° deeper knee angle per 100% strength lost).
DEPTH_DEG_PER_STRENGTH_LOST = 60


PROFILES = [
    {
        "crew_id": "c1", "seed": 101,
        "depth": lambda d: 94 + DEPTH_DEG_PER_STRENGTH_LOST * c1_strength_loss(d),
        "concentric": lambda d: lifting_time(0.9, c1_strength_loss(d)),
        "asymmetry": lambda d: 2.5 + 0.12 * after(d, 12),
        "completion": _c1_completion,
    },
    {
        "crew_id": "c2", "seed": 202,
        "depth": lambda d: 92 + DEPTH_DEG_PER_STRENGTH_LOST * c2_strength_loss(d),
        "concentric": lambda d: lifting_time(0.85, c2_strength_loss(d)),
        "asymmetry": lambda d: 2.2,
        "completion": lambda d: 1,
    },
    {
        "crew_id": "c3", "seed": 303,
        "depth": lambda d: 96,
        "concentric": lambda d: 0.95,
        "asymmetry": lambda d: 2.8 + 0.4 * after(d, 12),
        "completion": lambda d: 1,
    },
]


def _make_session(p, day, r):
    completed = round_half_up(PRESCRIBED_REPS * p["completion"](day))
    reps = []
    for _ in range(completed):
        # Same order of random draws as the original app.
        depth = p["depth"](day) + gauss(r) * 2.5
        eccentric = max(1, 3.2 + gauss(r) * 0.2)
        concentric = max(0.3, p["concentric"](day) * (1 + gauss(r) * 0.04))
        asymmetry = max(0, p["asymmetry"](day) + gauss(r) * 1.0)
        # About 5% of reps are poor-confidence frames, which the rules must ignore.
        if r() < 0.05:
            confidence = 0.35 + r() * 0.15
        else:
            confidence = 0.86 + r() * 0.11
        reps.append(RepSample(depth, eccentric, concentric, asymmetry, confidence))
    return SessionRecord(id=f"{p['crew_id']}-d{day}", crew_id=p["crew_id"], exercise="squat", day=day,
                         gravity_g=0, prescribed_reps=PRESCRIBED_REPS, reps=reps)


def generate_demo_sessions():
    out = []
    for p in PROFILES:
        r = make_rng(p["seed"])
        for day in range(1, DEMO_DAYS + 1):
            out.append(_make_session(p, day, r))
    return out


# ---- daily check-ins -------------------------------------------------------------------------

CHECKIN_PROFILES = [
    {
        "crew_id": "c1", "seed": 11,
        "sleep": lambda d: 7.5 - 0.3 * after(d, 18),
        "fatigue": lambda d: 3 + 0.45 * after(d, 16),
        "pain": lambda d: 0,
        "pain_location": None,
        "stress": lambda d: 3 + 0.25 * after(d, 19),
    },
    {
        "crew_id": "c2", "seed": 22,
        "sleep": lambda d: 7.5, "fatigue": lambda d: 3, "pain": lambda d: 0,
        "pain_location": None, "stress": lambda d: 3,
    },
    {
        "crew_id": "c3", "seed": 33,
        "sleep": lambda d: 7, "fatigue": lambda d: 3.5,
        "pain": lambda d: 0.25 * after(d, 8),
        "pain_location": "knee",
        "stress": lambda d: 4,
    },
]


def clamp10(x):
    return max(0, min(10, round_half_up(x)))


def generate_demo_checkins():
    out = []
    for p in CHECKIN_PROFILES:
        r = make_rng(p["seed"])
        for day in range(1, DEMO_DAYS + 1):
            base_pain = p["pain"](day)
            if base_pain > 0:
                pain = clamp10(base_pain + gauss(r) * 0.4)
            else:
                pain = clamp10(base_pain)
            sleep = clamp10(p["sleep"](day) + gauss(r) * 0.7)
            fatigue = clamp10(p["fatigue"](day) + gauss(r) * 0.7)
            stress = clamp10(p["stress"](day) + gauss(r) * 0.7)
            location = p["pain_location"] if pain > 0 else None
            out.append(CheckIn(id=f"{p['crew_id']}-ci{day}", crew_id=p["crew_id"], day=day, sleep=sleep,
                               fatigue=fatigue, pain=pain, pain_location=location, stress=stress))
    return out


# ---- daily vital signs (new in the Python version) -------------------------------------------

VITAL_PROFILES = [
    {"crew_id": "c1", "seed": 1001, "heart_rate": lambda d: 62 + 1.2 * after(d, 18),
     "systolic": 118, "diastolic": 76, "temperature_c": 36.6, "glucose": 95, "spo2": 98},
    {"crew_id": "c2", "seed": 2002, "heart_rate": lambda d: 58,
     "systolic": 115, "diastolic": 74, "temperature_c": 36.5, "glucose": 92, "spo2": 98},
    {"crew_id": "c3", "seed": 3003, "heart_rate": lambda d: 64,
     "systolic": 120, "diastolic": 78, "temperature_c": 36.7, "glucose": 98, "spo2": 97.5},
]


DEMO_DAILY_DOSE_MSV = 1.8


def generate_demo_vitals():
    out = []
    for p in VITAL_PROFILES:
        r = make_rng(p["seed"])
        for day in range(1, DEMO_DAYS + 1):
            heart_rate = round(p["heart_rate"](day) + gauss(r) * 2)
            systolic = round(p["systolic"] + gauss(r) * 3)
            diastolic = round(p["diastolic"] + gauss(r) * 2)
            temperature = round(p["temperature_c"] + gauss(r) * 0.15, 1)
            glucose = round(p["glucose"] + gauss(r) * 5)
            spo2 = round(min(100, p["spo2"] + gauss(r) * 0.5))
            # Daily dosimeter reading around the deep-space background (1.8 mSv a day, MSL RAD).
            radiation = round(max(0.0, DEMO_DAILY_DOSE_MSV + gauss(r) * 0.15), 1)
            out.append(VitalReading(id=f"{p['crew_id']}-v{day}", crew_id=p["crew_id"], day=day,
                                    heart_rate=heart_rate, systolic=systolic, diastolic=diastolic,
                                    temperature_c=temperature, glucose_mg_dl=glucose, spo2_pct=spo2,
                                    radiation_msv=radiation))
    return out


DEMO_SESSIONS = generate_demo_sessions()
DEMO_CHECKINS = generate_demo_checkins()
DEMO_VITALS = generate_demo_vitals()
