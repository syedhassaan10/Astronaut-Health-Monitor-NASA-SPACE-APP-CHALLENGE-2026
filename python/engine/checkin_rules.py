"""Daily check-in rules: pain, recovery, stress, and knee pain combined with rising asymmetry.

Wording rule: say "estimate", "trend", "decision support"; never call anything a diagnosis.
"""

from config.health_rules import HEALTH_RULES
from engine.health_types import ACT, WATCH, Alert, AlertWhat, SeriesPoint

LOCATION_LABEL = {
    "knee": "knee",
    "hip": "hip",
    "ankle-foot": "ankle / foot",
    "lower-back": "lower back",
    "upper-back-neck": "upper back / neck",
    "shoulder": "shoulder",
    "other": "other area",
}

TEXT = {
    "pain": {
        "title": "Reported pain",
        "metric": "Self-reported pain (0-10)",
        "why": "Pain during or after resistive exercise is an early signal worth acting on before it limits training "
               "or becomes an injury, and crews are far from a hospital.",
        "source": "hrp-muscle-bone",
        "actions": {
            WATCH: ["Keep the load and range of motion in the pain-free zone and log pain again tomorrow.",
                    "Tell the Crew Medical Officer if it persists or increases."],
            ACT: ["Consult the Crew Medical Officer before the next loaded session.",
                  "Pause the movement that provokes the pain and use a lighter, pain-free alternative."],
        },
    },
    "recovery": {
        "title": "Poor sleep and high fatigue",
        "metric": "Self-reported fatigue (0-10)",
        "why": "Sleep loss and fatigue are common on missions and reduce performance and recovery. They can also make "
               "exercise measurements look worse than they really are.",
        "source": "hrp-sleep",
        "actions": {
            WATCH: ["Prioritise sleep and recovery; consider a lighter session today.",
                    "Repeat measurements when rested before reading much into a trend."],
            ACT: ["Consult the Crew Medical Officer about sustained poor recovery."],
        },
    },
    "stress": {
        "title": "High stress reported",
        "metric": "Self-reported stress (0-10)",
        "why": "Isolation, confinement and workload can raise stress. Spotting a sustained rise early lets the crew and "
               "flight surgeon respond before it affects health and performance.",
        "source": "hrp-behavioral",
        "actions": {
            WATCH: ["Take a break, talk with a crewmate, or schedule a private call if comms allow.",
                    "Mention it to the Crew Medical Officer if it continues."],
            ACT: ["Consult the Crew Medical Officer about sustained high stress."],
        },
    },
    "pain-asymmetry": {
        "title": "Knee pain with rising left/right asymmetry",
        "metric": "Left/right knee-angle difference",
        "why": "Pain plus a growing left/right difference can mean you are unconsciously favouring one side. Together "
               "these two signals are more meaningful than either alone, so this is raised early.",
        "source": "hrp-muscle-bone",
        "actions": {
            WATCH: ["Repeat the measurement with the camera centred and watch weight shift and foot placement.",
                    "Reduce the simulated load and keep the knee pain-free; log pain again tomorrow."],
            ACT: ["Consult the Crew Medical Officer before the next loaded session.",
                  "Stop loaded squatting until the knee has been reviewed."],
        },
    },
}


def f1(n):
    return f"{n:.1f}"


def recent_checkins(checkins, crew_id, window):
    """The latest `window` check-ins for one crew member, oldest first."""
    mine = [c for c in checkins if c.crew_id == crew_id]
    mine.sort(key=lambda c: c.day)
    return mine[-window:]


def _count(checkins, test):
    n = 0
    for c in checkins:
        if test(c):
            n += 1
    return n


def _build(crew_id, rule, level, exercise, day, title, what):
    t = TEXT[rule]
    exercise_part = exercise if exercise is not None else "checkin"
    return Alert(
        id=f"{crew_id}:{exercise_part}:{rule}",
        crew_id=crew_id, exercise=exercise, rule=rule, level=level, title=title, what=what,
        why_text=t["why"], why_source_id=t["source"], actions=list(t["actions"][level]), day=day,
    )


def _series(checkins, pick):
    return [SeriesPoint(day=c.day, value=pick(c)) for c in checkins]


def assess_checkins(checkins, crew_id, exercises, cfg=HEALTH_RULES):
    """Alerts from the daily check-ins, alone and combined with the exercise trend.

    `exercises` are the exercise assessments already computed for the same crew member.
    """
    k = cfg.checkin
    all_mine = [c for c in checkins if c.crew_id == crew_id]
    all_mine.sort(key=lambda c: c.day)
    recent = all_mine[-k.window:]
    if not recent:
        return []
    last = recent[-1]
    alerts = []

    # 1. Pain: sustained at WATCH/ACT level, or a single acute report.
    sustained_act = _count(recent, lambda c: c.pain >= k.pain.act) >= k.min_sustained
    sustained_watch = _count(recent, lambda c: c.pain >= k.pain.watch) >= k.min_sustained
    acute = any(c.pain >= k.acute_pain for c in recent)
    pain_level = None
    if sustained_act:
        pain_level = ACT
    elif sustained_watch or acute:
        pain_level = WATCH
    if pain_level:
        where = None
        for c in reversed(recent):
            if c.pain > 0:
                where = c.pain_location
                break
        loc = LOCATION_LABEL[where] if where else "unspecified area"
        n = _count(recent, lambda c: c.pain >= k.pain.watch)
        alerts.append(_build(crew_id, "pain", pain_level, None, last.day, f"Pain reported: {loc}", AlertWhat(
            metric=TEXT["pain"]["metric"], unit="/10", baseline=None, now=last.pain, delta=last.pain,
            summary=f"Pain {last.pain}/10 ({loc}) on day {last.day}; {n} of the last {len(recent)} check-ins "
                    f"at {k.pain.watch}/10 or higher.",
            series=_series(all_mine, lambda c: c.pain),
        )))

    # 2. Recovery: low sleep AND high fatigue, sustained.
    def poor_recovery(c):
        return c.sleep <= k.sleep_low and c.fatigue >= k.fatigue_high

    poor_count = _count(recent, poor_recovery)
    if poor_count >= k.min_sustained:
        alerts.append(_build(crew_id, "recovery", WATCH, None, last.day, TEXT["recovery"]["title"], AlertWhat(
            metric=TEXT["recovery"]["metric"], unit="/10", baseline=None, now=last.fatigue, delta=last.fatigue,
            summary=f"Sleep {last.sleep}/10 and fatigue {last.fatigue}/10 on day {last.day}; poor recovery in "
                    f"{poor_count} of the last {len(recent)} check-ins.",
            series=_series(all_mine, lambda c: c.fatigue),
        )))

    # 3. Stress: sustained high.
    stressed = _count(recent, lambda c: c.stress >= k.stress_high)
    if stressed >= k.min_sustained:
        alerts.append(_build(crew_id, "stress", WATCH, None, last.day, TEXT["stress"]["title"], AlertWhat(
            metric=TEXT["stress"]["metric"], unit="/10", baseline=None, now=last.stress, delta=last.stress,
            summary=f"Stress {last.stress}/10 on day {last.day}; {stressed} of the last {len(recent)} check-ins "
                    f"at {k.stress_high}/10 or higher.",
            series=_series(all_mine, lambda c: c.stress),
        )))

    # 4. Combined: knee pain + rising asymmetry -> WATCH (ACT if severe).
    knee_pain = any(c.pain_location == "knee" and c.pain >= k.knee_pain_min for c in recent)
    if knee_pain:
        rising = [e for e in exercises if e.deltas is not None and e.deltas.asymmetry_deg >= k.combined_asymmetry_deg]
        rising.sort(key=lambda e: e.deltas.asymmetry_deg, reverse=True)
        if rising:
            top = rising[0]
            severe_pain = _count(recent, lambda c: c.pain_location == "knee" and c.pain >= k.pain.act) >= k.min_sustained
            asym_act = any(a.rule == "asymmetry" and a.level == ACT for a in top.alerts)
            level = ACT if (severe_pain or asym_act) else WATCH
            worst_knee = max(c.pain for c in recent if c.pain_location == "knee")
            base = top.baseline.asymmetry_deg if top.baseline else None
            alerts.append(_build(crew_id, "pain-asymmetry", level, top.exercise, last.day,
                                 TEXT["pain-asymmetry"]["title"], AlertWhat(
                metric=TEXT["pain-asymmetry"]["metric"], unit="°", baseline=base,
                now=(base or 0) + top.deltas.asymmetry_deg, delta=top.deltas.asymmetry_deg,
                summary=f"Knee pain up to {worst_knee}/10 reported, while left/right difference is "
                        f"+{f1(top.deltas.asymmetry_deg)}° above your baseline.",
                series=top.asymmetry_series,
            )))
    return alerts


def context_for(rule, checkins, crew_id, cfg=HEALTH_RULES):
    """Notes explaining that how the person feels may account for part of an exercise trend."""
    k = cfg.checkin
    if rule not in ("depth", "concentric", "variability"):
        return []
    recent = recent_checkins(checkins, crew_id, k.window)
    out = []
    if any(c.fatigue >= k.fatigue_high for c in recent):
        out.append("Recent check-ins report high fatigue, which can slow and loosen reps. Repeat the measurement when "
                   "rested before acting on this trend.")
    if any(c.sleep <= k.sleep_low for c in recent):
        out.append("Recent check-ins report poor sleep, which can affect performance.")
    if rule == "depth" and any(c.pain_location == "knee" and c.pain >= k.knee_pain_min for c in recent):
        out.append("Reported knee pain may be limiting depth.")
    return out
