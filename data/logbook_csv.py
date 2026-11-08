"""The logbook as one flat CSV table: one row per record, with a `record` column
(session | rep | checkin | vitals). It opens directly in Excel and can be filtered by `record`.
Unused cells are empty.

The first 28 columns are exactly the original app's columns, in the same order, so files move
between the two apps. The 6 vital-sign columns are added at the end for `vitals` rows.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from data.csv_codec import BOM, encode_csv, guard_text, parse_csv, unguard_text
from db.schema import SOURCES, RepRow, SessionRow
from engine.gravity_engine import EXERCISE_IDS
from engine.health_types import BODY_LOCATIONS, CheckIn
from engine.vitals_rules import VitalReading

ORIGINAL_COLUMNS = [
    "record", "id", "timestamp", "day", "sessionId", "crewId", "exercise", "gravityG", "targetLoadKg",
    "prescribedReps", "repNo", "minKneeAngle", "eccentricS", "concentricS", "asymmetry", "confidence",
    "formScore", "flags", "level", "sessionStatus", "startedAt", "endedAt", "source",
    "sleep", "fatigue", "pain", "painLocation", "stress",
]
VITAL_COLUMNS = ["heartRate", "systolic", "diastolic", "temperatureC", "glucoseMgDl", "spo2Pct", "radiationMsv"]
COLUMNS = ORIGINAL_COLUMNS + VITAL_COLUMNS

# Hard limits so a broken or hostile file cannot use up all memory.
MAX_ROWS = 200_000
MAX_CHARS = 60_000_000

LEVELS = ["green", "amber", "red"]

# CSV column -> (VitalReading field, lowest allowed, highest allowed)
VITAL_FIELDS = {
    "heartRate": ("heart_rate", 20, 250),
    "systolic": ("systolic", 40, 260),
    "diastolic": ("diastolic", 20, 160),
    "temperatureC": ("temperature_c", 30, 45),
    "glucoseMgDl": ("glucose_mg_dl", 10, 700),
    "spo2Pct": ("spo2_pct", 50, 100),
    "radiationMsv": ("radiation_msv", 0, 1000),
}


@dataclass
class LogbookData:
    sessions: list = field(default_factory=list)
    reps: list = field(default_factory=list)
    checkins: list = field(default_factory=list)
    vitals: list = field(default_factory=list)


@dataclass
class RowError:
    line: int  # 1-based line in the file (header = line 1; 0 = whole file)
    message: str


@dataclass
class ParsedLogbook:
    sessions: list = field(default_factory=list)
    reps: list = field(default_factory=list)
    checkins: list = field(default_factory=list)
    vitals: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    total_rows: int = 0


# ---- writing --------------------------------------------------------------------------------

def num(n):
    """A number rounded to 4 decimals, written without trailing zeros (110.5, 40, 94.1235)."""
    rounded = math.floor(n * 10_000 + 0.5) / 10_000
    text = f"{rounded:.4f}".rstrip("0").rstrip(".")
    if text == "-0":
        return "0"
    return text


def iso(ms):
    """Epoch milliseconds -> 2026-10-07T10:01:00.000Z"""
    moment = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _line(cells):
    return [cells.get(c, "") for c in COLUMNS]


def _rep_row(r):
    return _line({
        "record": "rep", "id": guard_text(r.id), "timestamp": iso(r.timestamp), "sessionId": guard_text(r.session_id),
        "crewId": guard_text(r.crew_id), "exercise": r.exercise, "gravityG": num(r.gravity_g),
        "targetLoadKg": num(r.target_load_kg), "repNo": str(r.rep_no), "minKneeAngle": num(r.min_knee_angle),
        "eccentricS": num(r.eccentric_s), "concentricS": num(r.concentric_s), "asymmetry": num(r.asymmetry),
        "confidence": num(r.confidence), "formScore": str(math.floor(r.form_score + 0.5)),
        "flags": ";".join(r.flags), "level": r.level,
    })


def rep_csv_line(rep):
    """One rep as a single CSV line (CRLF ending), used by the live logbook file."""
    return encode_csv([_rep_row(rep)])


def logbook_csv_header():
    """The header line of a logbook file, with the BOM so Excel reads it as UTF-8."""
    return to_logbook_csv(LogbookData())


def _optional_num(value):
    if value is None:
        return ""
    return num(value)


def to_logbook_csv(d):
    rows = [list(COLUMNS)]
    for s in d.sessions:
        rows.append(_line({
            "record": "session", "id": guard_text(s.id), "day": str(s.day), "crewId": guard_text(s.crew_id),
            "exercise": s.exercise, "gravityG": num(s.gravity_g), "targetLoadKg": num(s.target_load_kg),
            "prescribedReps": str(s.prescribed_reps), "sessionStatus": s.status, "startedAt": iso(s.started_at),
            "endedAt": "" if s.ended_at is None else iso(s.ended_at), "source": s.source,
        }))
    for r in d.reps:
        rows.append(_rep_row(r))
    for c in d.checkins:
        rows.append(_line({
            "record": "checkin", "id": guard_text(c.id), "day": str(c.day), "crewId": guard_text(c.crew_id),
            "sleep": str(c.sleep), "fatigue": str(c.fatigue), "pain": str(c.pain),
            "painLocation": c.pain_location or "", "stress": str(c.stress),
        }))
    for v in d.vitals:
        cells = {"record": "vitals", "id": guard_text(v.id), "day": str(v.day), "crewId": guard_text(v.crew_id)}
        for column, (attr, _, _) in VITAL_FIELDS.items():
            cells[column] = _optional_num(getattr(v, attr))
        rows.append(_line(cells))
    return BOM + encode_csv(rows)


# ---- reading and checking -------------------------------------------------------------------

class BadRow(Exception):
    """A row that fails a check; the message says which cell and why."""


def _text(cells, key, required=True):
    value = unguard_text(cells.get(key, "").strip())
    if required and value == "":
        raise BadRow(f'"{key}" is required')
    return value


def _to_number(raw):
    """Like JavaScript's Number(): None when it is not a finite number."""
    try:
        value = float(raw)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def _number(cells, key, low, high):
    raw = cells.get(key, "").strip()
    if raw == "":
        raise BadRow(f'"{key}" is required')
    value = _to_number(raw)
    if value is None:
        raise BadRow(f'"{key}" is not a number ({raw})')
    if value < low or value > high:
        raise BadRow(f'"{key}" must be between {low:g} and {high:g} (got {value:g})')
    return value


def _integer(cells, key, low, high):
    value = _number(cells, key, low, high)
    if not value.is_integer():
        raise BadRow(f'"{key}" must be a whole number (got {value:g})')
    return int(value)


def _date(cells, key, required=True):
    """ISO date text -> epoch milliseconds."""
    raw = cells.get(key, "").strip()
    if raw == "":
        if required:
            raise BadRow(f'"{key}" is required')
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise BadRow(f'"{key}" is not a valid date ({raw})')
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return int(round(moment.timestamp() * 1000))


def _exercise(cells):
    value = _text(cells, "exercise")
    if value not in EXERCISE_IDS:
        raise BadRow(f'unknown exercise "{value}"')
    return value


def _clean_number(value):
    """Whole numbers come back as int, so 40.0 reads as 40."""
    if value.is_integer():
        return int(value)
    return value


def _to_session(cells):
    source = _text(cells, "source", required=False)
    if source not in SOURCES:
        source = "import"
    return SessionRow(
        id=_text(cells, "id"), crew_id=_text(cells, "crewId"), exercise=_exercise(cells),
        day=_integer(cells, "day", 0, 36_500), gravity_g=_clean_number(_number(cells, "gravityG", 0, 1)),
        target_load_kg=_clean_number(_number(cells, "targetLoadKg", 0, 1000)),
        prescribed_reps=_integer(cells, "prescribedReps", 0, 10_000),
        # An imported session is finished by definition: it must not trigger "Resume session".
        status="completed",
        started_at=_date(cells, "startedAt"), ended_at=_date(cells, "endedAt", required=False), source=source,
    )


def _to_rep(cells):
    session_id = _text(cells, "sessionId")
    rep_no = _integer(cells, "repNo", 1, 100_000)
    level = _text(cells, "level", required=False)
    if level != "" and level not in LEVELS:
        raise BadRow(f'unknown level "{level}"')
    flags = []
    for f in _text(cells, "flags", required=False).split(";"):
        if f.strip():
            flags.append(f.strip())
    return RepRow(
        id=_text(cells, "id", required=False) or f"{session_id}#{rep_no}",
        session_id=session_id, crew_id=_text(cells, "crewId"), exercise=_exercise(cells),
        timestamp=_date(cells, "timestamp"), gravity_g=_clean_number(_number(cells, "gravityG", 0, 1)),
        target_load_kg=_clean_number(_number(cells, "targetLoadKg", 0, 1000)), rep_no=rep_no,
        min_knee_angle=_clean_number(_number(cells, "minKneeAngle", 0, 200)),
        eccentric_s=_clean_number(_number(cells, "eccentricS", 0, 120)),
        concentric_s=_clean_number(_number(cells, "concentricS", 0, 120)),
        asymmetry=_clean_number(_number(cells, "asymmetry", 0, 180)),
        confidence=_clean_number(_number(cells, "confidence", 0, 1)),
        form_score=_clean_number(_number(cells, "formScore", 0, 100)),
        flags=flags, level=level or "green",
    )


def _to_checkin(cells):
    location = _text(cells, "painLocation", required=False)
    if location != "" and location not in BODY_LOCATIONS:
        raise BadRow(f'unknown pain location "{location}"')
    crew_id = _text(cells, "crewId")
    day = _integer(cells, "day", 0, 36_500)
    pain = _integer(cells, "pain", 0, 10)
    if pain > 0:
        pain_location = location or "other"
    else:
        pain_location = None
    return CheckIn(
        id=f"{crew_id}:d{day}", crew_id=crew_id, day=day, sleep=_integer(cells, "sleep", 0, 10),
        fatigue=_integer(cells, "fatigue", 0, 10), pain=pain, pain_location=pain_location,
        stress=_integer(cells, "stress", 0, 10),
    )


def _to_vitals(cells):
    crew_id = _text(cells, "crewId")
    day = _integer(cells, "day", 0, 36_500)
    values = {}
    for column, (attr, low, high) in VITAL_FIELDS.items():
        if cells.get(column, "").strip() == "":
            values[attr] = None
        else:
            values[attr] = _clean_number(_number(cells, column, low, high))
    if all(v is None for v in values.values()):
        raise BadRow("a vitals row needs at least one measurement")
    return VitalReading(id=f"{crew_id}:v{day}", crew_id=crew_id, day=day, **values)


def parse_logbook_csv(text):
    """Parse and check a logbook CSV. Bad rows are reported, never silently imported."""
    out = ParsedLogbook()
    if len(text) > MAX_CHARS:
        out.errors.append(RowError(0, "File is too large to import."))
        return out
    try:
        rows = parse_csv(text)
    except ValueError as e:
        out.errors.append(RowError(0, str(e)))
        return out

    header = [h.strip() for h in rows[0]] if rows else []
    if "record" not in header or "id" not in header:
        out.errors.append(RowError(1, 'Not an OrbitFit logbook CSV: the header must include "record" and "id".'))
        return out
    if len(rows) - 1 > MAX_ROWS:
        out.errors.append(RowError(0, f"Too many rows (limit {MAX_ROWS})."))
        return out

    # Read columns by name, so reordered or extra columns (e.g. after editing in Excel) still work.
    index = {}
    for i, name in enumerate(header):
        index[name] = i

    for r in range(1, len(rows)):
        row = rows[r]
        cells = {}
        for column in COLUMNS:
            if column in index:
                i = index[column]
                cells[column] = row[i] if i < len(row) else ""
        out.total_rows += 1
        kind = cells.get("record", "").strip()
        try:
            if kind == "session":
                out.sessions.append(_to_session(cells))
            elif kind == "rep":
                out.reps.append(_to_rep(cells))
            elif kind == "checkin":
                out.checkins.append(_to_checkin(cells))
            elif kind == "vitals":
                out.vitals.append(_to_vitals(cells))
            else:
                raise BadRow(f'unknown record type "{kind}"')
        except BadRow as e:
            out.errors.append(RowError(r + 1, str(e)))
    return out
