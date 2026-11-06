"""Daily check-in rules: pain, recovery, stress, knee pain + asymmetry, context notes."""

from dataclasses import replace

import pytest

from config.health_rules import HEALTH_RULES, Levels
from engine.change_detection import assess_crew
from engine.checkin_rules import assess_checkins, context_for, recent_checkins
from engine.health_types import CheckIn, RepSample, SessionRecord

_counter = [0]


def ci(day, crew_id="c1", sleep=7, fatigue=3, pain=0, pain_location=None, stress=3):
    _counter[0] += 1
    return CheckIn(id=f"ci{_counter[0]}", crew_id=crew_id, day=day, sleep=sleep, fatigue=fatigue,
                   pain=pain, pain_location=pain_location, stress=stress)


def pain(day, p, loc="knee"):
    return ci(day, pain=p, pain_location=loc)


def session(day, depth=95, asym=2, concentric=1):
    reps = [RepSample(depth + (i / 7 - 0.5) * 4, 2, concentric, asym, 0.9) for i in range(8)]
    return SessionRecord(id=f"s{day}", crew_id="c1", exercise="squat", day=day, gravity_g=0, prescribed_reps=8, reps=reps)


def sessions(**later):
    """Healthy baseline on days 1-3, then two later sessions with the given values."""
    return [session(1), session(2), session(3), session(4, **later), session(5, **later)]


def alerts_of(checkins, recs=None):
    return assess_crew(recs or [], "c1", HEALTH_RULES, checkins).alerts


def rule(checkins, name, recs=None):
    for a in alerts_of(checkins, recs):
        if a.rule == name:
            return a
    return None


def test_recent_checkins_latest_n_for_one_person_oldest_first():
    all_checkins = [ci(5), ci(1), ci(3), ci(4, crew_id="c2"), ci(2)]
    assert [c.day for c in recent_checkins(all_checkins, "c1", 3)] == [2, 3, 5]


# ---- pain ------------------------------------------------------------------------------------

def test_no_alert_for_no_or_mild_pain():
    assert rule([ci(1), ci(2), ci(3)], "pain") is None
    assert rule([pain(1, 2), pain(2, 3), pain(3, 3)], "pain") is None


def test_pain_watch_when_4_or_more_in_2_of_3():
    assert rule([pain(1, 0), pain(2, 4), pain(3, 5)], "pain").level == "WATCH"


def test_one_moderate_report_is_not_enough():
    assert rule([ci(1), ci(2), pain(3, 5)], "pain") is None


def test_single_acute_report_raises_watch():
    assert rule([ci(1), ci(2), pain(3, 7)], "pain").level == "WATCH"


def test_pain_act_when_7_or_more_in_2_of_3():
    assert rule([pain(1, 7), pain(2, 8), pain(3, 2)], "pain").level == "ACT"


def test_pain_alert_names_the_location():
    a = rule([pain(1, 5, "lower-back"), pain(2, 5, "lower-back"), pain(3, 6, "lower-back")], "pain")
    assert "lower back" in a.title
    assert a.exercise is None
    assert "6/10" in a.what.summary
    assert a.why_source_id == "hrp-muscle-bone"
    assert len(a.actions) > 0
    assert len(a.what.series) == 3


def test_old_pain_falls_out_of_the_window():
    assert rule([pain(1, 8), pain(2, 8), ci(3), ci(4), ci(5)], "pain") is None


# ---- recovery and stress ---------------------------------------------------------------------

def bad_night(day):
    return ci(day, sleep=3, fatigue=8)


def test_recovery_watch_when_poor_sleep_and_high_fatigue_are_sustained():
    assert rule([ci(1), bad_night(2), bad_night(3)], "recovery").level == "WATCH"


def test_recovery_needs_both_poor_sleep_and_high_fatigue():
    assert rule([ci(1, sleep=3), ci(2, sleep=3), ci(3, sleep=3)], "recovery") is None
    assert rule([ci(1, fatigue=9), ci(2, fatigue=9), ci(3, fatigue=9)], "recovery") is None


def test_a_single_bad_night_is_not_an_alert():
    assert rule([ci(1), ci(2), bad_night(3)], "recovery") is None


def test_stress_watch_when_8_or_more_in_2_of_3():
    assert rule([ci(1), ci(2, stress=8), ci(3, stress=9)], "stress").level == "WATCH"
    assert rule([ci(1), ci(2), ci(3, stress=9)], "stress") is None


def test_stress_points_to_the_behavioural_health_source():
    assert rule([ci(1, stress=9), ci(2, stress=9)], "stress").why_source_id == "hrp-behavioral"


# ---- knee pain + asymmetry -------------------------------------------------------------------

def test_combined_watch_with_knee_pain_and_asymmetry_up_2_degrees():
    recs = sessions(asym=4.5)  # +2.5 degrees: below the asymmetry rule's own WATCH line
    all_alerts = alerts_of([ci(1), ci(2), pain(3, 3)], recs)
    assert not any(a.rule == "asymmetry" for a in all_alerts)
    a = [x for x in all_alerts if x.rule == "pain-asymmetry"][0]
    assert a.level == "WATCH"
    assert a.exercise == "squat"
    assert a.what.delta == pytest.approx(2.5)
    assert "Knee pain" in a.what.summary


def test_knee_pain_alone_does_not_trigger_it():
    assert rule([ci(1), ci(2), pain(3, 3)], "pain-asymmetry", sessions(asym=2)) is None


def test_asymmetry_alone_does_not_trigger_it():
    assert rule([ci(1), ci(2), ci(3)], "pain-asymmetry", sessions(asym=5)) is None


def test_pain_elsewhere_is_not_knee_pain():
    assert rule([ci(1), ci(2), pain(3, 5, "shoulder")], "pain-asymmetry", sessions(asym=5)) is None


def test_needs_knee_pain_of_at_least_3():
    assert rule([ci(1), ci(2), pain(3, 2)], "pain-asymmetry", sessions(asym=5)) is None


def test_act_with_sustained_severe_knee_pain():
    assert rule([pain(1, 7), pain(2, 8), pain(3, 7)], "pain-asymmetry", sessions(asym=5)).level == "ACT"


def test_act_when_the_asymmetry_alert_itself_is_act():
    assert rule([ci(1), ci(2), pain(3, 4)], "pain-asymmetry", sessions(asym=11)).level == "ACT"


def test_no_exercise_history_means_no_combined_alert():
    assert rule([pain(1, 6), pain(2, 6), pain(3, 6)], "pain-asymmetry", []) is None


def test_combined_rule_makes_the_crew_status_watch():
    c = assess_crew(sessions(asym=4.5), "c1", HEALTH_RULES, [ci(1), ci(2), pain(3, 3)])
    assert c.status == "WATCH"


# ---- check-ins feed the status ---------------------------------------------------------------

def test_check_ins_alone_can_raise_a_crew_member():
    assert assess_crew([], "c1", HEALTH_RULES, [pain(1, 8), pain(2, 8), pain(3, 8)]).status == "ACT"


def test_other_crew_check_ins_are_ignored():
    others = [ci(d, crew_id="c2", pain=9, pain_location="knee") for d in (1, 2, 3)]
    assert assess_checkins(others, "c1", []) == []


def test_no_check_ins_means_no_check_in_alerts():
    assert assess_checkins([], "c1", []) == []


def test_check_in_thresholds_are_configurable():
    strict = replace(HEALTH_RULES, checkin=replace(HEALTH_RULES.checkin, pain=Levels(watch=2, act=3), acute_pain=9))
    a = assess_checkins([pain(1, 3), pain(2, 3)], "c1", [], strict)
    assert [x for x in a if x.rule == "pain"][0].level == "ACT"


# ---- context notes ---------------------------------------------------------------------------

def test_fatigue_note_on_slowing_alerts():
    c = assess_crew(sessions(concentric=1.4), "c1", HEALTH_RULES, [ci(1), ci(2, fatigue=8), ci(3, fatigue=8)])
    a = [x for x in c.alerts if x.rule == "concentric"][0]
    assert "high fatigue" in " ".join(a.context)


def test_knee_pain_note_on_depth_alerts():
    c = assess_crew(sessions(depth=115), "c1", HEALTH_RULES, [pain(1, 4), pain(2, 4), pain(3, 4)])
    a = [x for x in c.alerts if x.rule == "depth"][0]
    assert "knee pain" in " ".join(a.context)


def test_no_context_when_the_person_feels_fine():
    c = assess_crew(sessions(depth=115), "c1", HEALTH_RULES, [ci(1), ci(2), ci(3)])
    a = [x for x in c.alerts if x.rule == "depth"][0]
    assert a.context == []


def test_context_ignores_rules_self_report_cannot_explain():
    assert context_for("adherence", [ci(1, fatigue=9)], "c1") == []
    assert context_for("asymmetry", [ci(1, fatigue=9)], "c1") == []


def test_context_never_changes_the_status():
    recs = sessions(concentric=1.4)
    base = assess_crew(recs, "c1", HEALTH_RULES, [])
    tired = assess_crew(recs, "c1", HEALTH_RULES, [ci(1, fatigue=9), ci(2, fatigue=9)])
    assert tired.status == base.status
