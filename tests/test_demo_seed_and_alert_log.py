"""Demo data stories and the alert log built from them."""

from config.health_rules import HEALTH_RULES
from data.demo_seed import (
    DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS, DEMO_VITALS, generate_demo_checkins, generate_demo_sessions,
    generate_demo_vitals,
)
from engine.alert_log import alert_key, new_log_entries, replay_alert_log, to_log_entry
from engine.change_detection import assess_crew

CREW_IDS = ["c1", "c2", "c3"]


def up_to(items, day):
    return [x for x in items if x.day <= day]


def status(crew_id, day):
    return assess_crew(up_to(DEMO_SESSIONS, day), crew_id).status


def run_with_everything(crew_id):
    """Status per day, and the first day each rule fired, using sessions, check-ins and vitals."""
    first = {}
    statuses = []
    for d in range(1, DEMO_DAYS + 1):
        a = assess_crew(up_to(DEMO_SESSIONS, d), crew_id, HEALTH_RULES, up_to(DEMO_CHECKINS, d), up_to(DEMO_VITALS, d))
        for al in a.alerts:
            first.setdefault(al.rule, d)
        statuses.append(a.status)
    return first, statuses


# ---- demo data -------------------------------------------------------------------------------

def test_demo_data_is_deterministic():
    assert generate_demo_sessions() == generate_demo_sessions()
    assert generate_demo_checkins() == generate_demo_checkins()
    assert generate_demo_vitals() == generate_demo_vitals()


def test_3_crew_by_30_days():
    assert len(DEMO_SESSIONS) == 3 * DEMO_DAYS
    assert len(DEMO_CHECKINS) == 3 * DEMO_DAYS
    assert len(DEMO_VITALS) == 3 * DEMO_DAYS


def test_c1_goes_nominal_then_watch_then_act():
    assert status("c1", 8) == "NOMINAL"
    seen = [status("c1", d) for d in range(1, DEMO_DAYS + 1)]
    first_watch = seen.index("WATCH")
    first_act = seen.index("ACT")
    assert first_watch > 8
    assert first_act > first_watch
    assert seen[-1] == "ACT"


def test_c2_never_leaves_nominal():
    for d in range(1, DEMO_DAYS + 1):
        assert status("c2", d) == "NOMINAL"


def test_c3_reaches_watch_from_asymmetry_alone():
    a = assess_crew(DEMO_SESSIONS, "c3")
    assert a.status != "NOMINAL"
    assert "asymmetry" in [x.rule for x in a.alerts]


def test_every_final_alert_has_what_why_and_action():
    for crew_id in ["c1", "c3"]:
        for al in assess_crew(DEMO_SESSIONS, crew_id, HEALTH_RULES, DEMO_CHECKINS, DEMO_VITALS).alerts:
            assert len(al.what.summary) > 10
            assert len(al.what.series) > 3
            assert len(al.why_text) > 20
            assert len(al.actions) > 0


def test_check_ins_are_in_range_and_pain_location_matches_pain():
    for c in DEMO_CHECKINS:
        for value in (c.sleep, c.fatigue, c.pain, c.stress):
            assert 0 <= value <= 10
        assert (c.pain_location is None) == (c.pain == 0)


def test_c2_has_no_alerts_of_any_kind_including_vitals():
    first, statuses = run_with_everything("c2")
    assert first == {}
    assert all(s == "NOMINAL" for s in statuses)


def test_c3_knee_pain_plus_asymmetry_comes_before_asymmetry_alone():
    first, statuses = run_with_everything("c3")
    assert first["pain-asymmetry"] < first["asymmetry"]
    assert statuses[-1] == "WATCH"


def test_c1_poor_recovery_and_rising_heart_rate_are_flagged():
    first, statuses = run_with_everything("c1")
    assert statuses[8] == "NOMINAL"
    assert statuses[-1] == "ACT"
    assert "recovery" in first
    assert "heart_rate_trend" in first
    assert first["heart_rate_trend"] > 18


def test_c1_slow_rep_alert_carries_a_fatigue_note():
    a = assess_crew(DEMO_SESSIONS, "c1", HEALTH_RULES, DEMO_CHECKINS)
    slow = [x for x in a.alerts if x.rule == "concentric"][0]
    assert "fatigue" in " ".join(slow.context)


# ---- alert log -------------------------------------------------------------------------------

LOG = replay_alert_log(DEMO_SESSIONS, DEMO_CHECKINS, CREW_IDS, DEMO_DAYS, vitals=DEMO_VITALS)


def find(crew_id, rule, level):
    for e in LOG:
        if e.crew_id == crew_id and e.rule == rule and e.level == level:
            return e
    return None


def test_log_is_chronological_with_no_duplicate_keys():
    days = [e.day for e in LOG]
    assert days == sorted(days)
    assert len({e.key for e in LOG}) == len(LOG)


def test_escalation_is_logged_as_its_own_entry():
    w = find("c1", "concentric", "WATCH")
    a = find("c1", "concentric", "ACT")
    assert w is not None and a is not None
    assert a.day > w.day


def test_nothing_is_logged_for_the_nominal_crew_member():
    assert [e for e in LOG if e.crew_id == "c2"] == []


def test_knee_pain_plus_asymmetry_is_logged_before_asymmetry_alone():
    assert find("c3", "pain-asymmetry", "WATCH").day < find("c3", "asymmetry", "WATCH").day


def test_every_alert_active_on_the_last_day_is_in_the_log():
    keys = {e.key for e in LOG}
    for crew_id in CREW_IDS:
        for a in assess_crew(DEMO_SESSIONS, crew_id, HEALTH_RULES, DEMO_CHECKINS, DEMO_VITALS).alerts:
            assert alert_key(a) in keys


def test_new_log_entries_returns_only_unknown_keys():
    alerts = assess_crew(DEMO_SESSIONS, "c1", HEALTH_RULES, DEMO_CHECKINS).alerts
    fresh = new_log_entries(alerts, {alert_key(alerts[0])}, 31)
    assert len(fresh) == len(alerts) - 1
    assert all(e.day == 31 for e in fresh)
    assert new_log_entries(alerts, {alert_key(a) for a in alerts}, 31) == []


def test_to_log_entry_copies_the_summary():
    alerts = assess_crew(DEMO_SESSIONS, "c1", HEALTH_RULES, DEMO_CHECKINS).alerts
    e = to_log_entry(alerts[0], 12)
    assert e.summary == alerts[0].what.summary
    assert e.day == 12


# ---- demo data shaped by NASA figures --------------------------------------------------------

def test_every_nasa_figure_has_a_real_source_and_page():
    from data import nasa_evidence
    from guidance.sources import source_by_id
    for figure in nasa_evidence.ALL:
        src = source_by_id(figure.source_id)
        assert src is not None and src.url.startswith("https://")
        assert "nasa.gov" in src.url
        assert figure.page > 0 and len(figure.statement) > 30


def test_demo_strength_loss_reaches_the_published_nasa_figures():
    from data.demo_seed import c1_strength_loss, c2_strength_loss
    from data.nasa_evidence import ARED_STRENGTH_LOSS, STRENGTH_STANDARD, UNTREATED_STRENGTH_LOSS
    assert c1_strength_loss(10) == 0
    assert c1_strength_loss(DEMO_DAYS) == UNTREATED_STRENGTH_LOSS.value       # up to 30% without exercise
    assert abs(c2_strength_loss(DEMO_DAYS) - ARED_STRENGTH_LOSS.value) < 1e-9  # 9% with ARED
    # Rivera ends below NASA's 80% strength standard (needs action), Okafor stays above it.
    assert 1 - c1_strength_loss(DEMO_DAYS) < STRENGTH_STANDARD.value
    assert 1 - c2_strength_loss(DEMO_DAYS) > STRENGTH_STANDARD.value
