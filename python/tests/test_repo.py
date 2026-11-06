"""SQLite logbook: crash-proof reps, sessions, check-ins, vitals, notes, alert log, demo data, import/export."""

from dataclasses import replace

import pytest

from config.health_rules import HEALTH_RULES
from data.crew import CREW
from data.demo_seed import DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS, DEMO_VITALS
from data.logbook_csv import LogbookData, to_logbook_csv
from db import repo
from db.database import open_db
from db.logbook_io import export_logbook_csv, import_logbook_csv
from db.schema import RepRow, SessionRow
from engine.alert_log import AlertLogEntry
from engine.change_detection import assess_crew
from engine.health_types import CheckIn


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "orbitfit.db"


@pytest.fixture
def conn(db_path):
    c = open_db(db_path)
    yield c
    c.close()


def make_rep(session_id, rep_no, **changes):
    r = RepRow(id=repo.rep_id(session_id, rep_no), session_id=session_id, crew_id="c1", exercise="squat",
               timestamp=1_000_000 + rep_no * 1000, gravity_g=0, target_load_kg=110, rep_no=rep_no, min_knee_angle=95,
               eccentric_s=3, concentric_s=1, asymmetry=2, confidence=0.9, form_score=90, flags=[], level="green")
    return replace(r, **changes)


def start_live(conn, crew_id="c1"):
    return repo.start_session(conn, crew_id, "squat", 0, 110, 24, "webcam")


def put_crew(conn):
    repo.save_crew(conn, CREW)


def assessment_key(a):
    return sorted(f"{x.rule}:{x.level}" for x in a.alerts)


# ---- crash-proof recording -------------------------------------------------------------------

def test_a_rep_survives_closing_without_finishing(db_path):
    conn = open_db(db_path)
    put_crew(conn)
    s = start_live(conn)
    repo.add_rep(conn, make_rep(s.id, 1))
    repo.add_rep(conn, make_rep(s.id, 2))
    conn.close()  # "the app crashed" without finish_session

    reopened = open_db(db_path)
    assert len(repo.session_reps(reopened, s.id)) == 2
    active = repo.list_active_sessions(reopened)
    assert [x.id for x in active] == [s.id]  # -> the "Resume session" prompt
    assert active[0].status == "active"
    reopened.close()


def test_reps_keep_order_and_numbering_across_a_resume(conn):
    s = start_live(conn)
    for k in [3, 1, 2]:
        repo.add_rep(conn, make_rep(s.id, k))
    assert [r.rep_no for r in repo.session_reps(conn, s.id)] == [1, 2, 3]
    repo.add_rep(conn, make_rep(s.id, 4))
    assert repo.count(conn, "reps") == 4


def test_writing_the_same_rep_twice_replaces_it(conn):
    s = start_live(conn)
    repo.add_rep(conn, make_rep(s.id, 1))
    repo.add_rep(conn, make_rep(s.id, 1, min_knee_angle=99))
    rows = repo.session_reps(conn, s.id)
    assert len(rows) == 1
    assert rows[0].min_knee_angle == 99


def test_stores_every_field_of_a_rep(conn):
    s = start_live(conn)
    original = make_rep(s.id, 1, flags=["shallow", "asymmetry"], form_score=70, level="amber")
    repo.add_rep(conn, original)
    assert repo.session_reps(conn, s.id)[0] == original


def test_finish_session_closes_it(conn):
    s = start_live(conn)
    repo.add_rep(conn, make_rep(s.id, 1))
    repo.finish_session(conn, s.id)
    assert repo.list_active_sessions(conn) == []
    row = repo.get_session(conn, s.id)
    assert row.status == "completed"
    assert row.ended_at is not None


def test_a_live_session_with_no_reps_is_deleted_on_finish(conn):
    s = start_live(conn)
    repo.finish_session(conn, s.id)
    assert repo.get_session(conn, s.id) is None


def test_finishing_an_unknown_session_is_harmless(conn):
    repo.finish_session(conn, "nope")


# ---- load_session_records --------------------------------------------------------------------

def test_joins_sessions_and_reps_for_the_health_rules(conn):
    s = start_live(conn)
    repo.add_rep(conn, make_rep(s.id, 1, min_knee_angle=90, asymmetry=4))
    repo.finish_session(conn, s.id)
    [r] = repo.load_session_records(conn)
    assert (r.id, r.crew_id, r.exercise, r.day, r.prescribed_reps) == (s.id, "c1", "squat", repo.TODAY, 24)
    assert len(r.reps) == 1
    assert (r.reps[0].min_knee_angle, r.reps[0].asymmetry_deg, r.reps[0].confidence) == (90, 4, 0.9)


def test_ignores_empty_live_sessions_but_keeps_empty_seeded_ones(conn):
    start_live(conn)
    repo._insert_session(conn, SessionRow(id="seed-skip", crew_id="c1", exercise="squat", day=5, gravity_g=0,
                                          target_load_kg=100, prescribed_reps=24, status="completed", started_at=1,
                                          ended_at=2, source="demo-seed"))
    recs = repo.load_session_records(conn)
    assert [r.id for r in recs] == ["seed-skip"]
    assert recs[0].reps == []


def test_an_unfinished_session_only_counts_what_is_done_so_far(conn):
    s = start_live(conn)
    repo.add_rep(conn, make_rep(s.id, 1))
    repo.add_rep(conn, make_rep(s.id, 2))
    assert repo.load_session_records(conn)[0].prescribed_reps == 2
    repo.finish_session(conn, s.id)
    assert repo.load_session_records(conn)[0].prescribed_reps == 24


def test_orders_by_day_then_start_time(conn):
    for sid, day, started in [("b", 2, 50), ("a", 1, 90), ("c", 2, 10)]:
        repo._insert_session(conn, SessionRow(id=sid, crew_id="c1", exercise="squat", day=day, gravity_g=0,
                                              target_load_kg=1, prescribed_reps=1, status="completed",
                                              started_at=started, ended_at=None, source="demo-seed"))
    assert [r.id for r in repo.load_session_records(conn)] == ["a", "c", "b"]


# ---- check-ins, vitals, notes, alert log -----------------------------------------------------

def test_one_check_in_per_person_per_day(conn):
    repo.save_checkin(conn, "c1", 30, 7, 3, 0, None, 2)
    repo.save_checkin(conn, "c1", 30, 7, 3, 6, "knee", 2)
    rows = repo.load_checkins(conn)
    assert len(rows) == 1
    assert (rows[0].id, rows[0].pain, rows[0].pain_location) == ("c1:d30", 6, "knee")


def test_no_pain_means_no_pain_location(conn):
    c = repo.save_checkin(conn, "c1", 30, 7, 3, 0, "knee", 2)
    assert c.pain_location is None


def test_one_vitals_set_per_person_per_day_and_missing_values_stay_empty(conn):
    repo.save_vitals(conn, "c1", 30, heart_rate=60)
    repo.save_vitals(conn, "c1", 30, heart_rate=64, spo2_pct=97)
    rows = repo.load_vitals(conn)
    assert len(rows) == 1
    assert (rows[0].heart_rate, rows[0].spo2_pct, rows[0].systolic) == (64, 97, None)


def test_notes_persist_per_crew_member_and_update_in_place(conn):
    assert repo.get_note(conn, "c1") is None
    repo.set_note(conn, "c1", "Review knee on day 31")
    repo.set_note(conn, "c1", "Reviewed. Reduce load.")
    repo.set_note(conn, "c2", "All good")
    assert repo.get_note(conn, "c1").text == "Reviewed. Reduce load."
    assert repo.get_note(conn, "c2").text == "All good"
    assert repo.count(conn, "cmo_notes") == 2


def test_alert_log_adds_only_new_keys_and_keeps_the_acknowledged_tick(conn):
    e = AlertLogEntry(key="c1:squat:depth|WATCH", crew_id="c1", exercise="squat", rule="depth", level="WATCH",
                      title="Depth", summary="s", day=20)
    assert repo.add_alert_entries(conn, [e]) == 1
    repo.set_acknowledged(conn, e.key, True)
    escalation = replace(e, key="c1:squat:depth|ACT", level="ACT")
    assert repo.add_alert_entries(conn, [e, escalation]) == 1
    assert repo.get_alert(conn, e.key).acknowledged is True
    assert repo.count(conn, "alerts") == 2


# ---- demo data -------------------------------------------------------------------------------

def test_seeds_everything_exactly_once(conn):
    repo.ensure_seeded(conn)
    repo.ensure_seeded(conn)
    assert repo.count(conn, "crew") == len(CREW)
    assert repo.count(conn, "sessions") == len(DEMO_SESSIONS)
    assert repo.count(conn, "reps") == sum(len(s.reps) for s in DEMO_SESSIONS)
    assert repo.count(conn, "checkins") == len(DEMO_CHECKINS)
    assert repo.count(conn, "vitals") == len(DEMO_VITALS)
    assert repo.count(conn, "alerts") > 0


def test_stored_data_gives_the_same_statuses_as_the_demo_data(conn):
    repo.seed_demo_data(conn)
    records = repo.load_session_records(conn)
    checkins = repo.load_checkins(conn)
    vitals = repo.load_vitals(conn)
    for c in CREW:
        from_db = assess_crew(records, c.id, HEALTH_RULES, checkins, vitals)
        from_memory = assess_crew(DEMO_SESSIONS, c.id, HEALTH_RULES, DEMO_CHECKINS, DEMO_VITALS)
        assert from_db.status == from_memory.status
        assert assessment_key(from_db) == assessment_key(from_memory)


def test_stored_alert_log_records_when_each_alert_was_first_raised(conn):
    repo.seed_demo_data(conn)
    alerts = repo.list_alerts(conn)
    c1 = [a for a in alerts if a.crew_id == "c1"]
    assert len(c1) > 0
    assert min(a.day for a in c1) > 5
    assert max(a.day for a in alerts) <= DEMO_DAYS
    assert [a for a in alerts if a.crew_id == "c2"] == []


def test_reset_wipes_live_sessions_and_notes_then_reseeds(conn):
    repo.seed_demo_data(conn)
    s = start_live(conn)
    repo.add_rep(conn, make_rep(s.id, 1))
    repo.set_note(conn, "c1", "x")
    repo.reset_demo_data(conn)
    assert repo.get_session(conn, s.id) is None
    assert repo.get_note(conn, "c1") is None
    assert repo.count(conn, "sessions") == len(DEMO_SESSIONS)


# ---- CSV export / import ---------------------------------------------------------------------

def counts(conn):
    return {t: repo.count(conn, t) for t in ("sessions", "reps", "checkins", "vitals")}


def test_importing_our_own_export_adds_nothing(conn):
    repo.seed_demo_data(conn)
    csv = export_logbook_csv(conn)
    before = counts(conn)
    report = import_logbook_csv(conn, csv)
    assert report.errors == []
    assert report.added == {"sessions": 0, "reps": 0, "checkins": 0, "vitals": 0}
    assert report.already_present == sum(before.values())
    assert counts(conn) == before


def test_a_full_export_restores_a_wiped_logbook_with_identical_assessments(conn, tmp_path):
    repo.seed_demo_data(conn)
    csv = export_logbook_csv(conn)
    other = open_db(tmp_path / "restore.db")
    put_crew(other)
    report = import_logbook_csv(other, csv)
    assert report.errors == []
    assert report.added["reps"] == repo.count(conn, "reps")

    a = repo.load_session_records(conn)
    b = repo.load_session_records(other)
    assert [(r.id, r.crew_id, r.day, r.prescribed_reps, len(r.reps)) for r in a] == \
           [(r.id, r.crew_id, r.day, r.prescribed_reps, len(r.reps)) for r in b]
    # The export rounds to 4 decimals, so values match to within that rounding...
    for ra, rb in zip(a, b):
        for x, y in zip(ra.reps, rb.reps):
            for attr in ("min_knee_angle", "eccentric_s", "concentric_s", "asymmetry_deg", "confidence"):
                assert abs(getattr(x, attr) - getattr(y, attr)) < 1e-4
    # ...and the health rules give the same answers on the restored data.
    for c in CREW:
        ra = assess_crew(a, c.id, HEALTH_RULES, repo.load_checkins(conn), repo.load_vitals(conn))
        rb = assess_crew(b, c.id, HEALTH_RULES, repo.load_checkins(other), repo.load_vitals(other))
        assert rb.status == ra.status
        assert assessment_key(rb) == assessment_key(ra)
    other.close()


def imported_session(sid, status="completed"):
    return SessionRow(id=sid, crew_id="c1", exercise="squat", day=12, gravity_g=0, target_load_kg=100,
                      prescribed_reps=24, status=status, started_at=1_700_000_000_000, ended_at=None, source="webcam")


def test_imported_rows_survive_reopening(db_path):
    conn = open_db(db_path)
    put_crew(conn)
    import_logbook_csv(conn, to_logbook_csv(LogbookData(sessions=[imported_session("s-imp")],
                                                        reps=[make_rep("s-imp", 1)])))
    conn.close()
    reopened = open_db(db_path)
    assert len(repo.session_reps(reopened, "s-imp")) == 1
    reopened.close()


def test_an_imported_active_session_does_not_offer_resume(conn):
    put_crew(conn)
    import_logbook_csv(conn, to_logbook_csv(LogbookData(sessions=[imported_session("s-act", status="active")])))
    assert repo.list_active_sessions(conn) == []


def test_skips_unknown_sessions_and_crew_but_imports_valid_rows(conn):
    put_crew(conn)
    csv = to_logbook_csv(LogbookData(
        sessions=[replace(imported_session("s-ok"), day=3)],
        reps=[make_rep("s-ok", 1), make_rep("s-ghost", 1), make_rep("s-ok", 2, crew_id="zz")],
        checkins=[CheckIn(id="x", crew_id="nobody", day=1, sleep=5, fatigue=5, pain=0, pain_location=None, stress=5)],
    ))
    report = import_logbook_csv(conn, csv)
    assert report.added == {"sessions": 1, "reps": 1, "checkins": 0, "vitals": 0}
    messages = " | ".join(e.message for e in report.errors)
    assert 'unknown session "s-ghost"' in messages
    assert 'unknown crew "zz"' in messages
    assert 'unknown crew "nobody"' in messages


def test_import_never_overwrites_existing_rows(conn):
    put_crew(conn)
    s = start_live(conn)
    repo.add_rep(conn, make_rep(s.id, 1, min_knee_angle=95))
    csv = to_logbook_csv(LogbookData(reps=[make_rep(s.id, 1, min_knee_angle=130), make_rep(s.id, 2)]))
    report = import_logbook_csv(conn, csv)
    assert report.added["reps"] == 1
    assert repo.count(conn, "reps") == 2
    assert repo.session_reps(conn, s.id)[0].min_knee_angle == 95  # the newer data was kept


def test_export_keeps_unusual_text_safe_for_excel(conn):
    put_crew(conn)
    repo._insert_session(conn, replace(imported_session("=cmd"), source="import"))
    csv = export_logbook_csv(conn)
    assert "'=cmd" in csv
    assert csv.startswith("﻿")
