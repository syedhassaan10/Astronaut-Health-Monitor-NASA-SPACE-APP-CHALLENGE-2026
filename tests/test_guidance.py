"""Guidance content: routine/streak, body map statuses, and guides that agree with the config."""

from config.health_rules import HEALTH_RULES
from data.demo_seed import DEMO_CHECKINS, DEMO_SESSIONS, DEMO_VITALS
from engine.change_detection import assess_crew
from engine.health_types import CheckIn, RepSample, SessionRecord
from engine.vitals_rules import VitalReading
from guidance.body_map import REGIONS, latest_pain_location, region_by_id, region_status
from guidance.measurements import guide_by_id, measurement_guides
from guidance.routine import routine_for_day, streak
from guidance.sources import source_by_id


def checkin(day, crew_id="c1", pain=0, loc=None):
    return CheckIn(f"{crew_id}:d{day}", crew_id, day, 7, 3, pain, loc, 3)


def vitals(day, crew_id="c1"):
    return VitalReading(f"{crew_id}:v{day}", crew_id, day, heart_rate=60)


def session(day, crew_id="c1", reps=1):
    return SessionRecord(f"s{day}", crew_id, "squat", day, 0, 24, [RepSample(95, 2, 1, 2, 0.9)] * reps)


# ---- routine ---------------------------------------------------------------------------------

def test_routine_lists_what_is_missing():
    r = routine_for_day("c1", 5, [checkin(5)], [], [session(5)])
    assert (r.checkin, r.vitals, r.workout) == (True, False, True)
    assert r.missing() == ["Vitals"]
    assert r.done_count == 2


def test_an_empty_session_is_not_a_workout():
    assert routine_for_day("c1", 5, [], [], [session(5, reps=0)]).workout is False


def test_streak_counts_full_days_in_a_row():
    days = [1, 2, 3, 4]
    c = [checkin(d) for d in days]
    v = [vitals(d) for d in days if d != 2]
    s = [session(d) for d in days]
    assert streak("c1", 4, c, v, s) == 2          # days 3 and 4
    assert streak("c1", 5, c, v, s) == 2          # today (5) not done yet: counts up to yesterday
    assert streak("c2", 4, c, v, s) == 0


def test_demo_crew_has_a_30_day_streak():
    assert streak("c2", 30, DEMO_CHECKINS, DEMO_VITALS, DEMO_SESSIONS) == 30


# ---- body map --------------------------------------------------------------------------------

def statuses_for(crew_id):
    a = assess_crew(DEMO_SESSIONS, crew_id, HEALTH_RULES, DEMO_CHECKINS, DEMO_VITALS)
    pain_loc = latest_pain_location(DEMO_CHECKINS, crew_id)
    return {r.id: region_status(r, a.alerts, pain_loc) for r in REGIONS}


def test_body_map_for_the_demo_crew():
    tanaka = statuses_for("c3")    # knee pain + asymmetry
    assert tanaka["knees"] == "WATCH"
    assert tanaka["heart"] == "NOMINAL"
    rivera = statuses_for("c1")    # deconditioning, poor sleep, rising heart rate
    assert rivera["knees"] == "ACT"
    assert rivera["heart"] == "WATCH"
    assert rivera["brain"] == "WATCH"
    okafor = statuses_for("c2")
    assert set(okafor.values()) == {"NOMINAL"}


def test_every_region_points_to_existing_guides():
    for r in REGIONS:
        for guide_id in r.measures:
            assert guide_by_id(guide_id) is not None, (r.id, guide_id)
    assert region_by_id("nope") is None


# ---- measurement guides ----------------------------------------------------------------------

def test_every_guide_has_steps_why_normal_and_a_real_source():
    for g in measurement_guides():
        assert len(g.how_to) >= 3, g.id
        assert len(g.why_space) > 40, g.id
        assert g.normal, g.id
        assert g.call_cmo_when, g.id
        assert source_by_id(g.source_id) is not None, g.id


def test_guide_ranges_come_from_the_config():
    v = HEALTH_RULES.vitals
    assert f"{v.heart_rate.watch_low:g}-{v.heart_rate.watch_high:g} bpm" in guide_by_id("heart_rate").normal
    assert f"Below {v.spo2_pct.act_low:g}%" in guide_by_id("spo2_pct").call_cmo_when


def test_every_alert_source_exists():
    for crew_id in ("c1", "c3"):
        a = assess_crew(DEMO_SESSIONS, crew_id, HEALTH_RULES, DEMO_CHECKINS, DEMO_VITALS)
        for alert in a.alerts:
            assert source_by_id(alert.why_source_id) is not None, alert.why_source_id
    for source in ("hrp-cardio", "hrp-immune", "hrp-nutrition", "hrp-hypoxia"):
        assert source_by_id(source).url.startswith("https://www.nasa.gov/")
