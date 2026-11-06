"""Exercise trend rules: baseline, depth, slower lifting, asymmetry, variability, adherence."""

import math
from dataclasses import replace

import pytest

from config.health_rules import HEALTH_RULES, Levels
from engine.change_detection import adherence_ratio, assess_crew, assess_exercise, compute_baseline, level_for
from engine.health_types import RepSample, SeriesPoint, SessionRecord
from engine.session_metrics import median, slope_per_day, std_dev, summarize_session


def session(day, depth=95, concentric=1, asym=2, spread=2, conf=0.9, n_reps=8, prescribed=None, g=0,
            crew_id="c1", exercise="squat"):
    """A session whose summary equals the requested values (even depth spread across reps)."""
    reps = []
    for i in range(n_reps):
        offset = 0 if n_reps == 1 else (i / (n_reps - 1) - 0.5) * 2 * spread
        reps.append(RepSample(depth + offset, 2, concentric, asym, conf))
    if prescribed is None:
        prescribed = n_reps
    return SessionRecord(id=f"s{day}", crew_id=crew_id, exercise=exercise, day=day, gravity_g=g,
                         prescribed_reps=prescribed, reps=reps)


def with_baseline(*later):
    """Three healthy baseline sessions on days 1-3 plus later ones (dicts of session arguments)."""
    return [session(d) for d in (1, 2, 3)] + [session(**o) for o in later]


def rules(recs):
    return assess_exercise(recs, "c1", "squat")


def rule_levels(recs):
    return {a.rule: a.level for a in rules(recs).alerts}


# ---- statistics ------------------------------------------------------------------------------

def test_median_std_dev_and_slope():
    assert median([3, 1, 2]) == 2
    assert median([1, 2, 3, 4]) == 2.5
    assert math.isnan(median([]))
    assert std_dev([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(2.138, abs=1e-3)
    assert std_dev([5]) == 0
    points = [SeriesPoint(0, 1), SeriesPoint(1, 3), SeriesPoint(2, 5)]
    assert slope_per_day(points) == pytest.approx(2)


def test_level_for_is_inclusive_and_ignores_improvement():
    t = Levels(watch=5, act=10)
    assert level_for(4.99, t) is None
    assert level_for(5, t) == "WATCH"
    assert level_for(9.99, t) == "WATCH"
    assert level_for(10, t) == "ACT"
    assert level_for(-3, t) is None
    assert level_for(math.nan, t) is None


# ---- session guards --------------------------------------------------------------------------

def test_low_confidence_reps_are_dropped_first():
    rec = session(1, n_reps=8)
    rec.reps[0] = replace(rec.reps[0], confidence=0.2, min_knee_angle=170)
    m = summarize_session(rec)
    assert m.completed_reps == 8
    assert m.valid_reps == 7
    assert m.depth_deg < 100


def test_not_usable_with_fewer_than_k_valid_reps():
    assert summarize_session(session(1, n_reps=HEALTH_RULES.min_valid_reps - 1)).usable is False
    assert summarize_session(session(1, n_reps=HEALTH_RULES.min_valid_reps)).usable is True


def test_not_usable_at_low_confidence():
    assert summarize_session(session(1, conf=0.5)).usable is False


def test_handles_an_empty_skipped_session():
    rec = session(1)
    rec.reps = []
    m = summarize_session(rec)
    assert m.usable is False
    assert m.valid_reps == 0


# ---- baseline --------------------------------------------------------------------------------

def test_baseline_is_the_median_of_the_first_3_usable_sessions():
    recs = [session(1, depth=90), session(2, depth=100), session(3, depth=95), session(4, depth=130)]
    usable = [m for m in (summarize_session(r) for r in recs) if m.usable]
    b = compute_baseline(usable)
    assert b.depth_deg == pytest.approx(95)
    assert b.days == [1, 2, 3]


def test_baseline_skips_unusable_sessions():
    recs = [session(1, depth=90), session(2, n_reps=2), session(3, depth=100), session(4, depth=95)]
    assert assess_exercise(recs, "c1", "squat").baseline.days == [1, 3, 4]


def test_not_ready_until_n_usable_sessions():
    a = rules([session(1), session(2)])
    assert a.baseline is None
    assert a.status == "NOMINAL"
    assert "Building baseline (2/3 valid sessions)" in " ".join(a.notes)


def test_baseline_size_is_configurable():
    cfg = replace(HEALTH_RULES, baseline_sessions=2)
    assert assess_exercise([session(1), session(2)], "c1", "squat", cfg).baseline is not None


# ---- depth -----------------------------------------------------------------------------------

def test_depth_quiet_below_watch():
    assert rule_levels(with_baseline(dict(day=4, depth=102), dict(day=5, depth=102))) == {}


def test_depth_watch_at_8_and_act_at_16():
    assert rule_levels(with_baseline(dict(day=4, depth=103), dict(day=5, depth=103)))["depth"] == "WATCH"
    assert rule_levels(with_baseline(dict(day=4, depth=111), dict(day=5, depth=111)))["depth"] == "ACT"


def test_deeper_than_baseline_is_never_an_alert():
    assert rule_levels(with_baseline(dict(day=4, depth=80), dict(day=5, depth=80))) == {}


def test_alert_has_what_why_action_and_series():
    a = rules(with_baseline(dict(day=4, depth=105), dict(day=5, depth=105))).alerts[0]
    assert a.what.baseline == pytest.approx(95)
    assert a.what.now == pytest.approx(105)
    assert "shallower" in a.what.summary
    assert len(a.what.series) == 5
    assert a.why_source_id == "hrp-muscle-bone"
    assert len(a.why_text) > 20
    assert len(a.actions) > 0


# ---- slower lifting, asymmetry, variability --------------------------------------------------

def test_concentric_watch_from_15_and_act_from_30_percent():
    assert rule_levels(with_baseline(dict(day=4, concentric=1.14), dict(day=5, concentric=1.14))) == {}
    assert rule_levels(with_baseline(dict(day=4, concentric=1.16), dict(day=5, concentric=1.16)))["concentric"] == "WATCH"
    assert rule_levels(with_baseline(dict(day=4, concentric=1.31), dict(day=5, concentric=1.31)))["concentric"] == "ACT"


def test_faster_than_baseline_is_not_an_alert():
    assert rule_levels(with_baseline(dict(day=4, concentric=0.7), dict(day=5, concentric=0.7))) == {}


def test_asymmetry_watch_at_4_and_act_at_8():
    assert rule_levels(with_baseline(dict(day=4, asym=5.9), dict(day=5, asym=5.9))) == {}
    assert rule_levels(with_baseline(dict(day=4, asym=6), dict(day=5, asym=6)))["asymmetry"] == "WATCH"
    assert rule_levels(with_baseline(dict(day=4, asym=10), dict(day=5, asym=10)))["asymmetry"] == "ACT"


def test_variability_fires_when_depth_spread_grows():
    assert rule_levels(with_baseline(dict(day=4), dict(day=5))) == {}
    loose = with_baseline(dict(day=4, spread=14), dict(day=5, spread=14))
    assert rule_levels(loose)["variability"] in ("WATCH", "ACT")


# ---- adherence -------------------------------------------------------------------------------

def week(reps):
    return [session(d, n_reps=reps, prescribed=10) for d in range(1, 8)]


def test_adherence_nominal_at_full_volume():
    assert rule_levels(week(10)) == {}


def test_adherence_watch_below_80_and_act_below_60():
    assert rule_levels(week(7))["adherence"] == "WATCH"
    assert rule_levels(week(5))["adherence"] == "ACT"


def test_skipped_sessions_count_against_adherence():
    recs = week(10)
    for r in recs[4:]:
        r.reps = []
    metrics = [summarize_session(r) for r in recs]
    assert adherence_ratio(metrics, 7, 7) == pytest.approx(40 / 70)
    assert rule_levels(recs)["adherence"] == "ACT"


def test_low_camera_confidence_is_not_skipped_exercise():
    recs = [session(d, conf=0.3, prescribed=8) for d in range(1, 8)]
    assert "adherence" not in rule_levels(recs)


def test_adherence_works_before_a_baseline():
    a = rules([session(1, n_reps=4, prescribed=10)])
    assert a.baseline is None
    assert a.alerts[0].rule == "adherence"


def test_adherence_ignores_sessions_outside_the_window():
    old = session(1, n_reps=0, prescribed=10)
    recent = [session(d, n_reps=10, prescribed=10) for d in (20, 21, 22)]
    metrics = [summarize_session(r) for r in [old] + recent]
    assert adherence_ratio(metrics, 22, 7) == 1


# ---- guards against false alerts -------------------------------------------------------------

def test_a_single_bad_session_does_not_alert():
    recs = with_baseline(dict(day=4, depth=95), dict(day=5, depth=125), dict(day=6, depth=95))
    assert rule_levels(recs) == {}


def test_needs_min_recent_sessions_after_baseline():
    a = rules(with_baseline(dict(day=4, depth=130)))
    assert a.alerts == []
    assert "Waiting for 2 comparable sessions" in " ".join(a.notes)


def test_low_confidence_bad_sessions_never_alert():
    a = rules(with_baseline(dict(day=4, depth=140, conf=0.4), dict(day=5, depth=140, conf=0.4)))
    assert a.alerts == []
    assert a.usable_sessions == 3


def test_sessions_with_too_few_valid_reps_never_alert():
    recs = with_baseline(dict(day=4, depth=140, n_reps=3), dict(day=5, depth=140, n_reps=3))
    assert [a for a in rules(recs).alerts if a.rule != "adherence"] == []


def test_different_gravity_pauses_the_comparison():
    a = rules(with_baseline(dict(day=4, depth=130, g=0.38), dict(day=5, depth=130, g=0.38)))
    assert [x for x in a.alerts if x.rule != "adherence"] == []
    assert "different gravity" in " ".join(a.notes)


def test_does_not_mix_crew_members_or_exercises():
    recs = with_baseline(dict(day=4), dict(day=5))
    recs += [session(d, crew_id="c2", depth=150) for d in range(1, 6)]
    recs += [session(d, exercise="deadlift", depth=150) for d in range(1, 6)]
    assert assess_exercise(recs, "c1", "squat").status == "NOMINAL"


# ---- status and escalation -------------------------------------------------------------------

def test_status_is_the_worst_alert_level():
    assert rules(with_baseline(dict(day=4, depth=103), dict(day=5, depth=103))).status == "WATCH"
    assert rules(with_baseline(dict(day=4, depth=120), dict(day=5, depth=120))).status == "ACT"


def test_three_watch_rules_escalate_to_act():
    a = rules(with_baseline(dict(day=4, depth=103, concentric=1.2, asym=6.5),
                            dict(day=5, depth=103, concentric=1.2, asym=6.5)))
    assert all(x.level == "WATCH" for x in a.alerts)
    assert len(a.alerts) >= 3
    assert a.status == "ACT"
    assert "escalates to ACT" in " ".join(a.notes)


def test_two_watch_rules_stay_watch():
    assert rules(with_baseline(dict(day=4, depth=103, asym=6.5), dict(day=5, depth=103, asym=6.5))).status == "WATCH"


def test_assess_crew_takes_the_worst_status_across_exercises():
    recs = with_baseline(dict(day=4), dict(day=5))
    recs += [session(d, exercise="deadlift") for d in (1, 2, 3)]
    recs += [session(d, exercise="deadlift", depth=125) for d in (4, 5)]
    c = assess_crew(recs, "c1")
    assert len(c.exercises) == 2
    assert c.status == "ACT"
    assert all(a.exercise == "deadlift" for a in c.alerts)


def test_thresholds_are_configurable():
    strict = replace(HEALTH_RULES, depth=Levels(watch=2, act=4))
    recs = with_baseline(dict(day=4, depth=99), dict(day=5, depth=99))
    assert assess_exercise(recs, "c1", "squat", strict).alerts[0].level == "ACT"
