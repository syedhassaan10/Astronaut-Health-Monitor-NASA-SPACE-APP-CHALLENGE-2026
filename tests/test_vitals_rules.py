"""Vital-sign rules: normal ranges and the resting heart-rate trend."""

from dataclasses import replace

from config.health_rules import HEALTH_RULES, Range
from engine.change_detection import assess_crew
from engine.vitals_rules import VitalReading, assess_vitals, normal_band_text, range_level

NORMAL = dict(heart_rate=60, systolic=118, diastolic=76, temperature_c=36.6, glucose_mg_dl=95, spo2_pct=98)


def reading(day, crew_id="c1", **changes):
    values = dict(NORMAL)
    values.update(changes)
    return VitalReading(id=f"v{day}", crew_id=crew_id, day=day, **values)


def rules_of(readings):
    return {a.rule: a for a in assess_vitals(readings, "c1")}


def test_range_level_both_sides():
    r = HEALTH_RULES.vitals.heart_rate  # watch 50-100, act 40-120
    assert range_level(70, r) == (None, None)
    assert range_level(100, r) == (None, None)
    assert range_level(101, r) == ("WATCH", "high")
    assert range_level(121, r) == ("ACT", "high")
    assert range_level(49, r) == ("WATCH", "low")
    assert range_level(39, r) == ("ACT", "low")


def test_normal_readings_give_no_alerts():
    assert assess_vitals([reading(d) for d in range(1, 8)], "c1") == []


def test_no_readings_give_no_alerts():
    assert assess_vitals([], "c1") == []


def test_only_the_latest_reading_counts_for_ranges():
    assert rules_of([reading(1, heart_rate=130), reading(2)]) == {}
    assert rules_of([reading(1), reading(2, heart_rate=130)])["heart_rate"].level == "ACT"


def test_each_vital_raises_its_own_alert():
    a = rules_of([reading(1, temperature_c=38.0)])
    assert a["temperature_c"].level == "WATCH"
    assert a["temperature_c"].title == "Body temperature is high"
    assert rules_of([reading(1, glucose_mg_dl=50)])["glucose_mg_dl"].level == "ACT"
    assert rules_of([reading(1, spo2_pct=93)])["spo2_pct"].level == "WATCH"
    assert rules_of([reading(1, spo2_pct=88)])["spo2_pct"].level == "ACT"


def test_blood_pressure_is_one_alert_with_the_worse_side():
    a = rules_of([reading(1, systolic=140, diastolic=102)])["blood_pressure"]
    assert a.level == "ACT"  # diastolic 102 is above the ACT line
    assert "140/102" in a.what.summary
    low = rules_of([reading(1, systolic=85, diastolic=60)])["blood_pressure"]
    assert low.level == "WATCH"
    assert low.title == "Blood pressure is low"


def test_missing_values_are_skipped_not_alerted():
    r = VitalReading(id="x", crew_id="c1", day=1, heart_rate=None, temperature_c=36.5)
    assert assess_vitals([r], "c1") == []


def test_summary_states_the_normal_range():
    a = rules_of([reading(1, heart_rate=105)])["heart_rate"]
    assert "50-100 bpm" in a.what.summary
    assert normal_band_text(HEALTH_RULES.vitals.spo2_pct, "%") == "95 % or more"


def test_heart_rate_trend_against_own_baseline():
    base = [reading(d, heart_rate=58) for d in (1, 2, 3)]
    assert "heart_rate_trend" not in rules_of(base + [reading(d, heart_rate=66) for d in (4, 5, 6)])
    watch = rules_of(base + [reading(d, heart_rate=69) for d in (4, 5, 6)])["heart_rate_trend"]
    assert watch.level == "WATCH"
    assert watch.what.baseline == 58
    assert "+11.0 bpm" in watch.what.summary
    act = rules_of(base + [reading(d, heart_rate=79) for d in (4, 5, 6)])["heart_rate_trend"]
    assert act.level == "ACT"


def test_heart_rate_trend_needs_enough_readings():
    readings = [reading(d, heart_rate=58) for d in (1, 2, 3)] + [reading(4, heart_rate=90), reading(5, heart_rate=90)]
    assert "heart_rate_trend" not in rules_of(readings)


def test_other_crew_readings_are_ignored():
    assert assess_vitals([reading(1, crew_id="c2", heart_rate=150)], "c1") == []


def test_vitals_feed_the_crew_status():
    c = assess_crew([], "c1", HEALTH_RULES, [], [reading(1, spo2_pct=85)])
    assert c.status == "ACT"


def test_vital_limits_are_configurable():
    strict = replace(HEALTH_RULES, vitals=replace(HEALTH_RULES.vitals, heart_rate=Range(55, 70, 50, 80)))
    a = assess_vitals([reading(1, heart_rate=75)], "c1", strict)
    assert a[0].level == "WATCH"


def test_every_vital_alert_has_why_and_actions():
    for a in assess_vitals([reading(1, heart_rate=130, systolic=170, temperature_c=39, glucose_mg_dl=40, spo2_pct=85)], "c1"):
        assert len(a.why_text) > 20
        assert len(a.actions) >= 2
        assert a.exercise is None
