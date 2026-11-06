"""Vital-sign rules: heart rate, blood pressure, temperature, blood sugar, oxygen saturation.

Two kinds of rule:
1. Range: the latest reading is outside the normal band (limits in config/health_rules.py).
2. Trend: resting heart rate has risen above the person's own baseline.

Wording rule: say "estimate", "trend", "decision support"; never call anything a diagnosis.
All limits are demonstration values for a resting adult, not clinically validated.
"""

from dataclasses import dataclass

from config.health_rules import HEALTH_RULES
from engine.health_types import ACT, WATCH, Alert, AlertWhat, SeriesPoint, worst_status
from engine.session_metrics import median


@dataclass
class VitalReading:
    """One set of measurements on one mission day. None = not measured."""
    id: str
    crew_id: str
    day: int
    heart_rate: float | None = None     # resting, beats per minute
    systolic: float | None = None       # mmHg
    diastolic: float | None = None      # mmHg
    temperature_c: float | None = None
    glucose_mg_dl: float | None = None
    spo2_pct: float | None = None


# What each vital is called, its unit, why it matters in space and what to do.
VITALS = {
    "heart_rate": {
        "label": "Resting heart rate",
        "unit": "bpm",
        "source": "hrp-cardio",
        "why": "In weightlessness, body fluids shift towards the head and the heart and blood vessels adapt. "
               "Resting heart rate is a simple sign of that adaptation, of fitness loss, fever, dehydration, "
               "stress or poor sleep.",
        "high": "Resting heart rate is high",
        "low": "Resting heart rate is low",
    },
    "blood_pressure": {
        "label": "Blood pressure",
        "unit": "mmHg",
        "source": "hrp-cardio",
        "why": "Spaceflight changes how the heart and blood vessels control blood pressure. Low pressure can cause "
               "dizziness or fainting (especially after landing or in partial gravity); high pressure strains the "
               "heart and vessels over a long mission.",
        "high": "Blood pressure is high",
        "low": "Blood pressure is low",
    },
    "temperature_c": {
        "label": "Body temperature",
        "unit": "°C",
        "source": "hrp-immune",
        "why": "The immune system changes in spaceflight and dormant viruses can reactivate. A fever is an early "
               "sign of infection in a closed cabin where it can spread to the whole crew.",
        "high": "Body temperature is high",
        "low": "Body temperature is low",
    },
    "glucose_mg_dl": {
        "label": "Blood sugar",
        "unit": "mg/dL",
        "source": "hrp-nutrition",
        "why": "Diet, exercise load, stress and sleep all change blood sugar. Low blood sugar can cause confusion "
               "or fainting during critical tasks; high blood sugar over time harms health.",
        "high": "Blood sugar is high",
        "low": "Blood sugar is low",
    },
    "spo2_pct": {
        "label": "Oxygen saturation",
        "unit": "%",
        "source": "hrp-hypoxia",
        "why": "Oxygen saturation shows how well the lungs load oxygen into the blood. A drop can come from a lung "
               "or heart problem or from a problem with the cabin atmosphere (a hostile closed environment).",
        "high": "Oxygen saturation is high",
        "low": "Oxygen saturation is low",
    },
}

# Shared steps for an out-of-range reading. Specific advice lives in the guidance pages.
ACTIONS = {
    WATCH: [
        "Rest quietly for 5 minutes, then measure again the same way (see the how-to guide).",
        "If it is still outside the normal range, log it and tell the Crew Medical Officer today.",
    ],
    ACT: [
        "Stop exercise and strenuous tasks now, and measure again after 5 minutes of rest.",
        "Tell the Crew Medical Officer straight away. If you feel unwell, open the Emergency guide.",
    ],
}

HR_RISE_TEXT = {
    "title": "Resting heart rate is rising",
    "why": "A resting heart rate that climbs above your own normal can reflect loss of fitness from unloading, "
           "poor sleep, stress, dehydration or the start of an illness. Treat it as a trend estimate.",
    "actions": {
        WATCH: ["Measure each morning before getting up, in the same position, for the next 3 days.",
                "Check sleep, fluids and stress in the daily check-in; tell the Crew Medical Officer if it keeps rising."],
        ACT: ["Tell the Crew Medical Officer about the rising trend today.",
              "Keep exercise light until the Crew Medical Officer has reviewed it."],
    },
}


def f1(n):
    return f"{n:.1f}"


def range_level(value, r):
    """WATCH / ACT / None for one value, and which side ("high" or "low") it is on."""
    if r.act_high is not None and value > r.act_high:
        return ACT, "high"
    if r.act_low is not None and value < r.act_low:
        return ACT, "low"
    if r.watch_high is not None and value > r.watch_high:
        return WATCH, "high"
    if r.watch_low is not None and value < r.watch_low:
        return WATCH, "low"
    return None, None


def normal_band_text(r, unit):
    """e.g. "50-100 bpm" or "95 % or more"."""
    if r.watch_low is not None and r.watch_high is not None:
        return f"{r.watch_low:g}-{r.watch_high:g} {unit}"
    if r.watch_low is not None:
        return f"{r.watch_low:g} {unit} or more"
    return f"{r.watch_high:g} {unit} or less"


def _latest_with(readings, field_name):
    """The newest reading that has a value for this field, or None."""
    for reading in reversed(readings):
        if getattr(reading, field_name) is not None:
            return reading
    return None


def _series(readings, field_name):
    points = []
    for reading in readings:
        value = getattr(reading, field_name)
        if value is not None:
            points.append(SeriesPoint(day=reading.day, value=value))
    return points


def _alert(crew_id, rule, level, title, day, what, why, source, actions):
    return Alert(
        id=f"{crew_id}:vitals:{rule}", crew_id=crew_id, exercise=None, rule=rule, level=level, title=title,
        what=what, why_text=why, why_source_id=source, actions=list(actions), day=day,
    )


def _range_alert(crew_id, mine, key, rng):
    latest = _latest_with(mine, key)
    if latest is None:
        return None
    value = getattr(latest, key)
    level, side = range_level(value, rng)
    if level is None:
        return None
    info = VITALS[key]
    return _alert(crew_id, key, level, info[side], latest.day, AlertWhat(
        metric=info["label"], unit=info["unit"], baseline=None, now=value, delta=0,
        summary=f"{info['label']} {value:g} {info['unit']} on day {latest.day} "
                f"(normal range {normal_band_text(rng, info['unit'])}).",
        series=_series(mine, key),
    ), info["why"], info["source"], ACTIONS[level])


def _blood_pressure_alert(crew_id, mine, cfg):
    """One alert for blood pressure: the worse of systolic and diastolic."""
    latest = None
    for reading in reversed(mine):
        if reading.systolic is not None and reading.diastolic is not None:
            latest = reading
            break
    if latest is None:
        return None
    sys_level, sys_side = range_level(latest.systolic, cfg.vitals.systolic)
    dia_level, dia_side = range_level(latest.diastolic, cfg.vitals.diastolic)
    levels = [lv for lv in (sys_level, dia_level) if lv is not None]
    if not levels:
        return None
    level = worst_status(*levels)
    side = sys_side if sys_level == level else dia_side
    info = VITALS["blood_pressure"]
    bp = f"{latest.systolic:g}/{latest.diastolic:g}"
    normal = f"{cfg.vitals.systolic.watch_low:g}-{cfg.vitals.systolic.watch_high:g} over " \
             f"{cfg.vitals.diastolic.watch_high:g} or less"
    return _alert(crew_id, "blood_pressure", level, info[side], latest.day, AlertWhat(
        metric="Blood pressure (systolic)", unit=info["unit"], baseline=None, now=latest.systolic, delta=0,
        summary=f"Blood pressure {bp} mmHg on day {latest.day} (normal range {normal} mmHg).",
        series=_series(mine, "systolic"),
    ), info["why"], info["source"], ACTIONS[level])


def _heart_rate_trend_alert(crew_id, mine, cfg):
    """Resting heart rate: median of the latest readings vs the median of the first readings."""
    v = cfg.vitals
    with_hr = [r for r in mine if r.heart_rate is not None]
    if len(with_hr) < v.baseline_readings + v.recent_readings:
        return None
    baseline = median([r.heart_rate for r in with_hr[:v.baseline_readings]])
    after_baseline = with_hr[v.baseline_readings:]
    recent = after_baseline[-v.recent_readings:]
    now = median([r.heart_rate for r in recent])
    rise = now - baseline
    level = None
    if rise >= v.heart_rate_rise_bpm.act:
        level = ACT
    elif rise >= v.heart_rate_rise_bpm.watch:
        level = WATCH
    if level is None:
        return None
    return _alert(crew_id, "heart_rate_trend", level, HR_RISE_TEXT["title"], recent[-1].day, AlertWhat(
        metric="Resting heart rate (median)", unit="bpm", baseline=baseline, now=now, delta=rise,
        summary=f"Resting heart rate {f1(baseline)} bpm at baseline → {f1(now)} bpm now (+{f1(rise)} bpm).",
        series=_series(with_hr, "heart_rate"),
    ), HR_RISE_TEXT["why"], "hrp-cardio", HR_RISE_TEXT["actions"][level])


def assess_vitals(readings, crew_id, cfg=HEALTH_RULES):
    """All vital-sign alerts for one crew member."""
    mine = [r for r in readings if r.crew_id == crew_id]
    mine.sort(key=lambda r: r.day)
    if not mine:
        return []
    candidates = [
        _range_alert(crew_id, mine, "heart_rate", cfg.vitals.heart_rate),
        _heart_rate_trend_alert(crew_id, mine, cfg),
        _blood_pressure_alert(crew_id, mine, cfg),
        _range_alert(crew_id, mine, "temperature_c", cfg.vitals.temperature_c),
        _range_alert(crew_id, mine, "glucose_mg_dl", cfg.vitals.glucose_mg_dl),
        _range_alert(crew_id, mine, "spo2_pct", cfg.vitals.spo2_pct),
    ]
    return [a for a in candidates if a is not None]
