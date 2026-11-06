"""Exercise trend rules: compare recent sessions with the person's own baseline.

Wording rule: say "estimate", "trend", "decision support"; never call anything a diagnosis.
"""

import math

from config.health_rules import HEALTH_RULES
from engine.checkin_rules import assess_checkins, context_for
from engine.health_types import (
    ACT, NOMINAL, WATCH, Alert, AlertWhat, Baseline, CrewAssessment, Deltas, ExerciseAssessment,
    SeriesPoint, worst_status,
)
from engine.session_metrics import median, summarize_session


def level_for(deterioration, t):
    """Map "how much worse than baseline" to WATCH / ACT / None (higher = worse)."""
    if not math.isfinite(deterioration):
        return None
    if deterioration >= t.act:
        return ACT
    if deterioration >= t.watch:
        return WATCH
    return None


def _adherence_level(ratio, t):
    """Adherence is "lower is worse"."""
    if ratio < t.act:
        return ACT
    if ratio < t.watch:
        return WATCH
    return None


def compute_baseline(usable, cfg=HEALTH_RULES):
    """Baseline = median of the first N usable sessions; None until there are N."""
    first = usable[:cfg.baseline_sessions]
    if len(first) < cfg.baseline_sessions:
        return None
    return Baseline(
        depth_deg=median([m.depth_deg for m in first]),
        concentric_s=median([m.concentric_s for m in first]),
        asymmetry_deg=median([m.asymmetry_deg for m in first]),
        variability_deg=median([m.variability_deg for m in first]),
        gravity_g=median([m.gravity_g for m in first]),
        days=[m.day for m in first],
    )


TEXT = {
    "depth": {
        "title": "Squat depth trend is getting shallower",
        "metric": "Bottom knee angle (median)",
        "unit": "°",
        "why": "Less depth can reflect reduced strength or range of motion as muscle is unloaded in microgravity. "
               "This is a camera-based movement estimate, not a measurement of muscle or bone.",
        "source": "hrp-muscle-bone",
        "actions": {
            WATCH: [
                "Repeat the measurement next session with the camera re-positioned (side or front, hips to ankles in view).",
                "Re-check the simulated target load and tempo for the current gravity.",
            ],
            ACT: [
                "Consult the Crew Medical Officer about the depth trend.",
                "Reduce the simulated load and restore full depth before progressing again.",
            ],
        },
    },
    "concentric": {
        "title": "Lifting phase is slowing",
        "metric": "Concentric duration (median)",
        "unit": "s",
        "why": "A slower lifting phase is a simple proxy for lower power output, which falls with muscle unloading "
               "and fatigue. Treat it as a trend estimate.",
        "source": "hrp-muscle-bone",
        "actions": {
            WATCH: ["Repeat the measurement and check sleep and fatigue in the daily check-in.",
                    "Keep load steady; avoid adding volume until the trend settles."],
            ACT: ["Consult the Crew Medical Officer about the power trend.",
                  "Lower the simulated load and rebuild tempo before increasing it."],
        },
    },
    "asymmetry": {
        "title": "Left/right asymmetry is rising",
        "metric": "Mean left/right knee-angle difference",
        "unit": "°",
        "why": "Growing left/right differences can point to compensation, discomfort or uneven loading, which "
               "matters when working under high resistive-exercise loads.",
        "source": "hrp-muscle-bone",
        "actions": {
            WATCH: ["Repeat the measurement with the camera centred, then watch foot placement and weight shift.",
                    "Log any pain or discomfort in the daily check-in."],
            ACT: ["Consult the Crew Medical Officer before the next loaded session.",
                  "Reduce the simulated load and use a slower, controlled tempo."],
        },
    },
    "variability": {
        "title": "Rep-to-rep consistency is dropping",
        "metric": "Depth variability (SD across reps)",
        "unit": "°",
        "why": "Less consistent reps can signal fatigue or reduced movement control, which raises the chance of "
               "poor form under load.",
        "source": "hrp-muscle-bone",
        "actions": {
            WATCH: ["Repeat the measurement and add a longer rest between sets.",
                    "Check sleep and fatigue in the daily check-in."],
            ACT: ["Consult the Crew Medical Officer about form consistency.",
                  "Cut volume until reps are consistent again."],
        },
    },
    "adherence": {
        "title": "Exercise volume is below the prescription",
        "metric": "Completed ÷ prescribed volume (recent days)",
        "unit": "%",
        "why": "Countermeasure exercise only works when it is done. Missed volume lets the effects of unloading "
               "accumulate on a mission where daily exercise is part of the plan.",
        "source": "iss-exercise",
        "actions": {
            WATCH: ["Schedule the missed volume over the next sessions.",
                    "If time or equipment is the problem, tell the Crew Medical Officer."],
            ACT: ["Consult the Crew Medical Officer about the sustained shortfall.",
                  "Agree a reduced but achievable plan and re-measure."],
        },
    },
}


def f1(n):
    return f"{n:.1f}"


def _series(metrics, pick):
    return [SeriesPoint(day=m.day, value=pick(m)) for m in metrics]


def _make_alert(crew_id, exercise, latest_day, rule, level, baseline, now, delta, summary, series):
    t = TEXT[rule]
    return Alert(
        id=f"{crew_id}:{exercise}:{rule}",
        crew_id=crew_id,
        exercise=exercise,
        rule=rule,
        level=level,
        title=t["title"],
        what=AlertWhat(metric=t["metric"], unit=t["unit"], baseline=baseline, now=now, delta=delta,
                       summary=summary, series=series),
        why_text=t["why"],
        why_source_id=t["source"],
        actions=list(t["actions"][level]),
        day=latest_day,
    )


def adherence_ratio(all_metrics, latest_day, window_days):
    """Completed / prescribed reps over the last `window_days` mission days."""
    in_window = [m for m in all_metrics if m.day > latest_day - window_days]
    prescribed = sum(m.prescribed_reps for m in in_window)
    if prescribed == 0:
        return None
    # Completed reps, not valid reps: low camera confidence is a measurement problem, not skipped exercise.
    completed = sum(m.completed_reps for m in in_window)
    return completed / prescribed


def assess_exercise(records, crew_id, exercise, cfg=HEALTH_RULES):
    """Assess one crew member on one exercise from their session history."""
    mine = [r for r in records if r.crew_id == crew_id and r.exercise == exercise]
    mine.sort(key=lambda r: r.day)
    all_metrics = [summarize_session(r, cfg) for r in mine]
    usable = [m for m in all_metrics if m.usable]
    latest_day = all_metrics[-1].day if all_metrics else 0
    alerts = []
    notes = []

    # Adherence needs no baseline: it compares against the prescription itself.
    ratio = adherence_ratio(all_metrics, latest_day, cfg.adherence.window_days)
    if ratio is not None:
        level = _adherence_level(ratio, cfg.adherence)
        if level:
            pct = ratio * 100
            series = []
            for m in all_metrics:
                value = 100 * m.completed_reps / m.prescribed_reps if m.prescribed_reps else 0
                series.append(SeriesPoint(day=m.day, value=value))
            alerts.append(_make_alert(
                crew_id, exercise, latest_day, "adherence", level, 100, pct, pct - 100,
                f"{f1(pct)}% of prescribed reps completed over the last {cfg.adherence.window_days} days "
                f"(prescription = 100%).",
                series,
            ))

    baseline = compute_baseline(usable, cfg)
    if baseline is None:
        ready = min(len(usable), cfg.baseline_sessions)
        notes.append(f"Building baseline ({ready}/{cfg.baseline_sessions} valid sessions). "
                     f"No trend alerts until it is ready.")
        skipped = len(all_metrics) - len(usable)
        if skipped > 0:
            notes.append(f"{skipped} session(s) ignored: fewer than {cfg.min_valid_reps} valid reps or low confidence.")
        return _finish(crew_id, exercise, None, len(usable), alerts, notes, cfg, None, [])

    asym_series = _series(usable, lambda m: m.asymmetry_deg)
    after = usable[cfg.baseline_sessions:]
    comparable = [m for m in after if abs(m.gravity_g - baseline.gravity_g) <= cfg.gravity_tolerance]
    if len(comparable) < len(after):
        notes.append(f"{len(after) - len(comparable)} session(s) at a different gravity than the baseline "
                     f"({f1(baseline.gravity_g)} g) were not compared.")
    if len(comparable) < cfg.min_recent_sessions:
        notes.append(f"Waiting for {cfg.min_recent_sessions} comparable sessions after the baseline "
                     f"({len(comparable)} so far).")
        return _finish(crew_id, exercise, baseline, len(usable), alerts, notes, cfg, None, asym_series)

    recent = comparable[-cfg.recent_sessions:]
    now_depth = median([m.depth_deg for m in recent])
    now_concentric = median([m.concentric_s for m in recent])
    now_asymmetry = median([m.asymmetry_deg for m in recent])
    now_variability = median([m.variability_deg for m in recent])
    latest_day = max(latest_day, recent[-1].day)

    depth_delta = now_depth - baseline.depth_deg  # positive = shallower
    level = level_for(depth_delta, cfg.depth)
    if level:
        alerts.append(_make_alert(
            crew_id, exercise, latest_day, "depth", level, baseline.depth_deg, now_depth, depth_delta,
            f"Bottom knee angle {f1(baseline.depth_deg)}° at baseline → {f1(now_depth)}° now "
            f"({f1(depth_delta)}° shallower).",
            _series(usable, lambda m: m.depth_deg),
        ))

    if baseline.concentric_s > 0:
        con_pct = (now_concentric - baseline.concentric_s) / baseline.concentric_s * 100
    else:
        con_pct = math.nan
    level = level_for(con_pct, cfg.concentric)
    if level:
        alerts.append(_make_alert(
            crew_id, exercise, latest_day, "concentric", level, baseline.concentric_s, now_concentric,
            now_concentric - baseline.concentric_s,
            f"Lifting phase {f1(baseline.concentric_s)} s at baseline → {f1(now_concentric)} s now "
            f"({f1(con_pct)}% slower).",
            _series(usable, lambda m: m.concentric_s),
        ))

    asym_delta = now_asymmetry - baseline.asymmetry_deg
    level = level_for(asym_delta, cfg.asymmetry)
    if level:
        alerts.append(_make_alert(
            crew_id, exercise, latest_day, "asymmetry", level, baseline.asymmetry_deg, now_asymmetry, asym_delta,
            f"Left/right difference {f1(baseline.asymmetry_deg)}° at baseline → {f1(now_asymmetry)}° now "
            f"(+{f1(asym_delta)}°).",
            _series(usable, lambda m: m.asymmetry_deg),
        ))

    var_delta = now_variability - baseline.variability_deg
    level = level_for(var_delta, cfg.variability)
    if level:
        alerts.append(_make_alert(
            crew_id, exercise, latest_day, "variability", level, baseline.variability_deg, now_variability, var_delta,
            f"Rep-to-rep depth variability {f1(baseline.variability_deg)}° at baseline → {f1(now_variability)}° now "
            f"(+{f1(var_delta)}°).",
            _series(usable, lambda m: m.variability_deg),
        ))

    deltas = Deltas(depth_deg=depth_delta, concentric_pct=con_pct, asymmetry_deg=asym_delta, variability_deg=var_delta)
    return _finish(crew_id, exercise, baseline, len(usable), alerts, notes, cfg, deltas, asym_series)


def _finish(crew_id, exercise, baseline, usable_sessions, alerts, notes, cfg, deltas, asymmetry_series):
    """Work out the status and apply escalation (several WATCH rules together = ACT)."""
    status = worst_status(NOMINAL, *[a.level for a in alerts])
    watch_count = len([a for a in alerts if a.level == WATCH])
    if status == WATCH and watch_count >= cfg.escalate_watch_count:
        status = ACT
        notes.append(f"{watch_count} rules are at WATCH together, which escalates to ACT.")
    return ExerciseAssessment(
        crew_id=crew_id, exercise=exercise, status=status, baseline=baseline, usable_sessions=usable_sessions,
        alerts=alerts, asymmetry_series=asymmetry_series, deltas=deltas, notes=notes,
    )


def assess_crew(records, crew_id, cfg=HEALTH_RULES, checkins=None, vitals=None):
    """Assess every exercise a crew member has sessions for, then fold in check-ins and vitals.

    Status = worst alert level across everything.
    """
    from engine.vitals_rules import assess_vitals  # local import keeps the modules independent

    checkins = checkins or []
    vitals = vitals or []
    exercises = []
    for r in records:
        if r.crew_id == crew_id and r.exercise not in exercises:
            exercises.append(r.exercise)
    per_exercise = [assess_exercise(records, crew_id, e, cfg) for e in exercises]

    checkin_alerts = assess_checkins(checkins, crew_id, per_exercise, cfg)
    for e in per_exercise:
        for a in e.alerts:
            context = context_for(a.rule, checkins, crew_id, cfg)
            if context:
                a.context = context
    vital_alerts = assess_vitals(vitals, crew_id, cfg)

    alerts = []
    for e in per_exercise:
        alerts.extend(e.alerts)
    alerts.extend(checkin_alerts)
    alerts.extend(vital_alerts)

    levels = [e.status for e in per_exercise] + [a.level for a in checkin_alerts] + [a.level for a in vital_alerts]
    return CrewAssessment(crew_id=crew_id, status=worst_status(NOMINAL, *levels), exercises=per_exercise, alerts=alerts)
