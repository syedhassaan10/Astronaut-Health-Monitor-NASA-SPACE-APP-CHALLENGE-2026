"""CSV codec and the logbook CSV format (round trip, Excel safety, validation)."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from data.csv_codec import BOM, encode_csv, guard_text, parse_csv, unguard_text
from data.logbook_csv import (
    COLUMNS, MAX_ROWS, ORIGINAL_COLUMNS, LogbookData, parse_logbook_csv, to_logbook_csv,
)
from db.schema import RepRow, SessionRow
from engine.health_types import CheckIn
from engine.vitals_rules import VitalReading


def utc_ms(*args):
    return int(datetime(*args, tzinfo=timezone.utc).timestamp() * 1000)


# ---- codec -----------------------------------------------------------------------------------

TRICKY = [
    ["plain", "with,comma", 'with "quotes"', "multi\nline", " leading", "trailing ", "", "ünïcödé ✓", "a\r\nb"],
    ["x", "", "", "y", '"', ",", '""', "it's", "=SUM(A1)"],
]


def test_round_trips_awkward_cells_exactly():
    assert parse_csv(encode_csv(TRICKY)) == TRICKY


def test_uses_crlf_and_ends_with_one():
    assert encode_csv([["a", "b"], ["c", "d"]]) == "a,b\r\nc,d\r\n"


def test_strips_a_utf8_bom():
    assert parse_csv(f"{BOM}a,b\r\n1,2\r\n") == [["a", "b"], ["1", "2"]]


def test_accepts_all_line_endings_and_skips_blank_lines():
    assert parse_csv("a,b\r\n1,2\n3,4\r5,6\n\n\r\n") == [["a", "b"], ["1", "2"], ["3", "4"], ["5", "6"]]


def test_keeps_an_empty_trailing_cell_and_a_last_line_without_newline():
    assert parse_csv("a,b,\n1,2,3") == [["a", "b", ""], ["1", "2", "3"]]


def test_unterminated_quote_raises():
    with pytest.raises(ValueError, match="never closed"):
        parse_csv('a,"b\n1,2')


def test_formula_guard_is_reversible_and_only_touches_dangerous_starts():
    for v in ["=1+1", "+cmd", "-2", "@x", "\tx"]:
        assert guard_text(v).startswith("'")
        assert unguard_text(guard_text(v)) == v
    assert guard_text("s-123") == "s-123"
    assert unguard_text("it's") == "it's"


# ---- logbook format --------------------------------------------------------------------------

def sample():
    return LogbookData(
        sessions=[SessionRow(id="s-1", crew_id="c1", exercise="squat", day=30, gravity_g=0, target_load_kg=110.5,
                             prescribed_reps=24, status="completed", started_at=utc_ms(2026, 10, 7, 10, 0, 0),
                             ended_at=utc_ms(2026, 10, 7, 10, 20, 0), source="webcam")],
        reps=[
            RepRow(id="s-1#1", session_id="s-1", crew_id="c1", exercise="squat", timestamp=utc_ms(2026, 10, 7, 10, 1, 0),
                   gravity_g=0, target_load_kg=110.5, rep_no=1, min_knee_angle=94.1234, eccentric_s=3.2,
                   concentric_s=1.1, asymmetry=2.5, confidence=0.93, form_score=90,
                   flags=["fast-concentric", "asymmetry"], level="amber"),
            RepRow(id="s-1#2", session_id="s-1", crew_id="c1", exercise="squat", timestamp=utc_ms(2026, 10, 7, 10, 1, 6),
                   gravity_g=0, target_load_kg=110.5, rep_no=2, min_knee_angle=96, eccentric_s=3, concentric_s=1,
                   asymmetry=3, confidence=0.9, form_score=100, flags=[], level="green"),
        ],
        checkins=[
            CheckIn(id="c1:d30", crew_id="c1", day=30, sleep=6, fatigue=4, pain=5, pain_location="knee", stress=3),
            CheckIn(id="c1:d29", crew_id="c1", day=29, sleep=7, fatigue=3, pain=0, pain_location=None, stress=2),
        ],
        vitals=[
            VitalReading(id="c1:v30", crew_id="c1", day=30, heart_rate=64, systolic=118, diastolic=76,
                         temperature_c=36.6, glucose_mg_dl=95, spo2_pct=98),
            VitalReading(id="c1:v29", crew_id="c1", day=29, heart_rate=61),
        ],
    )


def test_bom_header_and_crlf_only():
    t = to_logbook_csv(sample())
    assert t.startswith(BOM)
    assert t[1:].startswith(",".join(COLUMNS))
    assert "\r\n" in t
    assert "\n" not in t.replace("\r\n", "")


def test_first_28_columns_are_the_original_apps_columns():
    assert len(ORIGINAL_COLUMNS) == 28
    assert COLUMNS[:28] == ORIGINAL_COLUMNS
    assert COLUMNS[0] == "record" and COLUMNS[27] == "stress"


def test_every_row_has_as_many_cells_as_the_header():
    rows = parse_csv(to_logbook_csv(sample()))
    assert len(rows) == 1 + 1 + 2 + 2 + 2
    for r in rows:
        assert len(r) == len(COLUMNS)


def test_round_trips_sessions_reps_checkins_and_vitals():
    d = sample()
    p = parse_logbook_csv(to_logbook_csv(d))
    assert p.errors == []
    assert p.sessions == d.sessions
    assert p.reps == d.reps
    assert p.checkins == d.checkins
    assert p.vitals == d.vitals


def test_rounds_long_decimals_to_4_places():
    d = sample()
    d.reps = [replace(d.reps[0], min_knee_angle=94.123456789)]
    assert parse_logbook_csv(to_logbook_csv(d)).reps[0].min_knee_angle == 94.1235


def test_an_exported_active_session_imports_as_completed():
    d = LogbookData(sessions=[replace(sample().sessions[0], status="active", ended_at=None)])
    p = parse_logbook_csv(to_logbook_csv(d))
    assert p.sessions[0].status == "completed"
    assert p.sessions[0].ended_at is None


def test_spreadsheet_formulas_are_neutralised_and_restored():
    d = LogbookData(sessions=[replace(sample().sessions[0], id='=HYPERLINK("x")', crew_id="@c1")])
    t = to_logbook_csv(d)
    assert "'=HYPERLINK" in t
    for line in t.split("\r\n"):
        assert not line.startswith("=HYPERLINK")
        assert ",=HYPERLINK" not in line
    p = parse_logbook_csv(t)
    assert p.sessions[0].id == '=HYPERLINK("x")'
    assert p.sessions[0].crew_id == "@c1"


def test_reads_a_file_saved_by_excel():
    # reordered and extra columns, LF endings, no BOM
    csv = ("extra,record,id,crewId,day,sleep,fatigue,pain,painLocation,stress\n"
           "ignored,checkin,whatever,c2,12,7,3,0,,2\n")
    p = parse_logbook_csv(csv)
    assert p.errors == []
    assert p.checkins == [CheckIn(id="c2:d12", crew_id="c2", day=12, sleep=7, fatigue=3, pain=0,
                                  pain_location=None, stress=2)]


def test_a_file_from_the_original_app_imports():
    # Only the 28 original columns: no vitals columns at all.
    head = ",".join(ORIGINAL_COLUMNS)
    good = "checkin,c1:d1,,1,,c1,,,,,,,,,,,,,,,,,,7,3,0,,2"
    p = parse_logbook_csv("\r\n".join([head, good]))
    assert p.errors == []
    assert len(p.checkins) == 1


def test_invalid_rows_are_reported_with_line_numbers_and_valid_ones_kept():
    head = ",".join(ORIGINAL_COLUMNS)
    good = "checkin,c1:d1,,1,,c1,,,,,,,,,,,,,,,,,,7,3,0,,2"
    bad_range = "checkin,c1:d2,,2,,c1,,,,,,,,,,,,,,,,,,11,3,0,,2"
    bad_num = "checkin,c1:d3,,3,,c1,,,,,,,,,,,,,,,,,,abc,3,0,,2"
    bad_record = "banana,x"
    p = parse_logbook_csv("\r\n".join([head, good, bad_range, bad_num, bad_record]))
    assert len(p.checkins) == 1
    assert [e.line for e in p.errors] == [3, 4, 5]
    assert "sleep" in p.errors[0].message and "between 0 and 10" in p.errors[0].message
    assert "not a number" in p.errors[1].message
    assert "unknown record type" in p.errors[2].message


def test_rejects_bad_reps():
    base = sample().reps[0]
    variants = [
        to_logbook_csv(LogbookData(reps=[replace(base, confidence=1.5)])),
        to_logbook_csv(LogbookData(reps=[replace(base, min_knee_angle=400)])),
        to_logbook_csv(LogbookData(reps=[replace(base, rep_no=0)])),
        to_logbook_csv(LogbookData(reps=[replace(base, exercise="burpee")])),
        to_logbook_csv(LogbookData(reps=[replace(base, level="purple")])),
        to_logbook_csv(LogbookData(reps=[base])).replace("2026-10-07T10:01:00.000Z", "not-a-date"),
    ]
    for v in variants:
        p = parse_logbook_csv(v)
        assert p.reps == []
        assert len(p.errors) > 0


def test_rejects_out_of_range_or_empty_vitals():
    head = ",".join(COLUMNS)
    empty = ",".join(["vitals", "x", "", "3", "", "c1"] + [""] * (len(COLUMNS) - 6))
    too_hot = ",".join(["vitals", "x", "", "3", "", "c1"] + [""] * 22 + ["", "", "", "50", "", ""])
    p = parse_logbook_csv("\r\n".join([head, empty, too_hot]))
    assert p.vitals == []
    assert "at least one measurement" in p.errors[0].message
    assert "temperatureC" in p.errors[1].message


def test_rejects_a_file_that_is_not_a_logbook():
    p = parse_logbook_csv("name,age\r\nann,5\r\n")
    assert "Not an OrbitFit logbook" in p.errors[0].message
    assert p.sessions == [] and p.reps == [] and p.checkins == []


def test_reports_malformed_csv_instead_of_raising():
    p = parse_logbook_csv('record,id\r\nrep,"oops')
    assert len(p.errors) == 1
    assert "never closed" in p.errors[0].message


def test_refuses_files_over_the_row_limit():
    rows = "\n".join(["record,id"] + ["x,y"] * (MAX_ROWS + 1))
    assert "Too many rows" in parse_logbook_csv(rows).errors[0].message
