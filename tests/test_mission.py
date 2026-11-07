"""Mission set-up: demo or new mission, mission day from the calendar, crew, backups."""

from datetime import date, timedelta

import pytest

from data.demo_seed import DEMO_DAYS, DEMO_SESSIONS
from data.logbook_csv import parse_logbook_csv
from db import backup, mission, repo
from db.database import open_db


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "orbitfit.db")
    mission.ensure_table(c)
    yield c
    c.close()


def crew_rows(*people):
    return [{"name": n, "role": r, "mass_kg": m} for n, r, m in people]


def new_mission(conn, start=None, **changes):
    team, errors = mission.validate_crew(crew_rows(("Ana Silva", "Commander", 68), ("Ravi Rao", "Flight Engineer", 81)))
    assert errors == []
    values = dict(name="Mars transit", start_date=start or date.today() - timedelta(days=4), location_id="transit",
                  custom_g=0.5, earth_delay_min=12, crew=team, cmo_id="m2", backup=True, acknowledged=True)
    values.update(changes)
    mission.start_new_mission(conn, **values)


def test_no_mission_before_setup(conn):
    assert mission.get_mission(conn) is None


def test_an_old_logbook_with_crew_becomes_the_demo_mission(conn):
    repo.seed_demo_data(conn)
    m = mission.get_mission(conn)
    assert m.mode == mission.DEMO
    assert mission.mission_day(m) == DEMO_DAYS


def test_demo_mission_loads_the_sample_crew_and_history(conn):
    mission.start_demo_mission(conn)
    assert [c.id for c in mission.list_crew(conn)] == ["c1", "c2", "c3"]
    assert repo.count(conn, "sessions") == len(DEMO_SESSIONS)
    assert mission.get_mission(conn).cmo_id == "c2"


def test_new_mission_has_its_own_crew_and_an_empty_logbook(conn):
    mission.start_demo_mission(conn)
    new_mission(conn)
    m = mission.get_mission(conn)
    assert m.mode == mission.REAL and m.name == "Mars transit" and m.cmo_id == "m2"
    assert [(c.id, c.name, c.mass_kg) for c in mission.list_crew(conn)] == [("m1", "Ana Silva", 68), ("m2", "Ravi Rao", 81)]
    for table in ("sessions", "reps", "checkins", "vitals", "alerts"):
        assert repo.count(conn, table) == 0


def test_mission_day_counts_from_the_start_date(conn):
    new_mission(conn, start=date(2026, 11, 1))
    m = mission.get_mission(conn)
    assert mission.mission_day(m, today=date(2026, 11, 1)) == 1
    assert mission.mission_day(m, today=date(2026, 11, 7)) == 7
    assert mission.mission_day(m, today=date(2026, 10, 30)) == 1  # never below day 1


def test_crew_checks():
    good, errors = mission.validate_crew(crew_rows(("Ana", "", 60), ("", "", None)))
    assert errors == [] and good[0].role == "Crew member" and len(good) == 1   # empty rows are skipped
    assert mission.validate_crew([])[1] == ["Add at least one crew member."]
    assert "enter a name" in mission.validate_crew(crew_rows(("", "Pilot", 70)))[1][0]
    assert "listed twice" in mission.validate_crew(crew_rows(("Ana", "", 60), ("ana", "", 61)))[1][0]
    assert "between 30 and 200" in mission.validate_crew(crew_rows(("Ana", "", 12)))[1][0]
    assert "body weight" in mission.validate_crew(crew_rows(("Ana", "", None)))[1][0]


def test_add_and_edit_crew_keep_history(conn):
    new_mission(conn)
    member, error = mission.add_crew_member(conn, "Li Wei", "Scientist", 59)
    assert error is None and member.id == "m3"
    assert mission.add_crew_member(conn, "li wei", "", 60)[1] is not None  # duplicate name
    repo.save_checkin(conn, "m1", 5, 7, 3, 0, None, 2)
    assert mission.update_crew_member(conn, "m1", "Ana Silva-Costa", "Commander", 69) is None
    renamed = [c for c in mission.list_crew(conn) if c.id == "m1"][0]
    assert renamed.name == "Ana Silva-Costa" and renamed.mass_kg == 69
    assert len(repo.load_checkins(conn)) == 1  # history kept


def test_clear_mission_brings_back_the_setup(conn):
    new_mission(conn)
    mission.clear_mission(conn)
    assert mission.get_mission(conn) is None
    assert mission.list_crew(conn) == []


# ---- daily backup ----------------------------------------------------------------------------

def test_backup_is_written_once_a_day_and_can_be_imported(conn, tmp_path):
    mission.start_demo_mission(conn)
    folder = tmp_path / "backups"
    first = backup.backup_if_due(conn, folder, today=date(2026, 11, 7))
    assert first is not None and first.name == "orbitfit-backup-2026-11-07.csv"
    assert backup.backup_if_due(conn, folder, today=date(2026, 11, 7)) is None   # already done today
    parsed = parse_logbook_csv(first.read_text(encoding="utf-8"))
    assert parsed.errors == [] and len(parsed.sessions) == len(DEMO_SESSIONS)


def test_only_the_last_14_backups_are_kept(conn, tmp_path):
    mission.start_demo_mission(conn)
    folder = tmp_path / "backups"
    for i in range(20):
        backup.write_backup(conn, folder, today=date(2026, 10, 1) + timedelta(days=i))
    files = backup.list_backups(folder)
    assert len(files) == 14
    assert files[0].name == "orbitfit-backup-2026-10-20.csv"
