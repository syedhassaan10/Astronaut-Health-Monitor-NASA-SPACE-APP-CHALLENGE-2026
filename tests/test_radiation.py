"""Radiation dose: the daily dosimeter reading, the mission total, the logbook and the CSV."""

import sqlite3

from config.health_rules import HEALTH_RULES
from data.logbook_csv import COLUMNS, parse_logbook_csv, to_logbook_csv
from db import repo
from db.database import open_db
from engine.vitals_rules import VitalReading, assess_vitals, mission_dose


def dose(day, msv, crew_id="c1"):
    return VitalReading(id=f"v{day}", crew_id=crew_id, day=day, radiation_msv=msv)


def rules_of(readings):
    return {a.rule: a for a in assess_vitals(readings, "c1")}


def test_deep_space_background_raises_nothing():
    readings = [dose(d, 1.8) for d in range(1, 31)]
    assert rules_of(readings) == {}


def test_a_high_day_is_watch_and_a_solar_storm_day_is_act_with_shelter_steps():
    r = HEALTH_RULES.vitals.radiation_msv
    assert rules_of([dose(1, r.watch_high + 0.5)])["radiation_msv"].level == "WATCH"
    storm = rules_of([dose(1, r.act_high + 5)])["radiation_msv"]
    assert storm.level == "ACT"
    assert "shelter" in storm.actions[0].lower()


def test_mission_total_counts_against_the_career_limit():
    v = HEALTH_RULES.vitals
    assert v.radiation_career_limit_msv == 600
    per_day = 2.5
    days_to_watch = int(v.mission_dose_msv.watch / per_day) + 1
    readings = [dose(d, per_day) for d in range(1, days_to_watch + 1)]
    alert = rules_of(readings)["mission_dose"]
    assert alert.level == "WATCH"
    assert "600 mSv" in alert.what.summary
    assert alert.what.series[-1].value == mission_dose(readings, "c1")
    readings = [dose(d, per_day) for d in range(1, int(v.mission_dose_msv.act / per_day) + 2)]
    assert rules_of(readings)["mission_dose"].level == "ACT"


def test_mission_dose_skips_missing_readings_and_other_crew():
    readings = [dose(1, 1.5), VitalReading(id="x", crew_id="c1", day=2), dose(3, 2.0, crew_id="c2")]
    assert mission_dose(readings, "c1") == 1.5


def test_saved_dose_is_read_back(tmp_path):
    conn = open_db(tmp_path / "log.db")
    repo.save_vitals(conn, "c1", 4, heart_rate=60, radiation_msv=1.9)
    v = repo.load_vitals(conn)[0]
    assert v.radiation_msv == 1.9 and v.heart_rate == 60


def test_an_older_logbook_gets_the_new_column(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(str(path))
    old.execute("CREATE TABLE vitals (id TEXT PRIMARY KEY, crew_id TEXT NOT NULL, day INTEGER NOT NULL, "
                "heart_rate REAL, systolic REAL, diastolic REAL, temperature_c REAL, glucose_mg_dl REAL, spo2_pct REAL)")
    old.execute("INSERT INTO vitals (id, crew_id, day, heart_rate) VALUES ('a', 'c1', 1, 61)")
    old.commit()
    old.close()
    conn = open_db(path)
    v = repo.load_vitals(conn)[0]
    assert v.heart_rate == 61 and v.radiation_msv is None


def test_csv_carries_the_dose_and_reads_files_without_it():
    assert COLUMNS[-1] == "radiationMsv"
    from tests.test_csv_round_trip import sample
    d = sample()
    d.vitals[0].radiation_msv = 1.7
    p = parse_logbook_csv(to_logbook_csv(d))
    assert p.errors == []
    assert p.vitals[0].radiation_msv == 1.7
    # A file exported before radiation existed has no radiationMsv column: still imports.
    text = to_logbook_csv(d).splitlines()
    header = text[0].split(",")
    cut = header.index("radiationMsv")
    old = "\r\n".join(",".join(line.split(",")[:cut]) for line in text)
    p = parse_logbook_csv(old)
    assert p.vitals and p.vitals[0].radiation_msv is None
