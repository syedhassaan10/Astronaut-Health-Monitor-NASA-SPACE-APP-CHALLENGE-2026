"""Reading and writing the logbook: sessions, reps, check-ins, vital signs, notes, alert log, demo data."""

import time
import uuid
from datetime import datetime, timezone

from data.crew import CREW, crew_by_id
from data.demo_seed import DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS, DEMO_VITALS
from db.database import transaction
from db.schema import AlertRow, NoteRow, RepRow, SessionRow
from engine.alert_log import replay_alert_log
from engine.form_feedback import assess_rep, targets_for
from engine.gravity_engine import build_plan, tempo_for_g
from engine.health_types import CheckIn, RepSample, SessionRecord
from engine.rep_detector import REP_CONFIGS, RepMetrics
from engine.vitals_rules import VitalReading

# The mission day that live sessions, check-ins and vitals are stamped with (the latest demo day).
TODAY = DEMO_DAYS

# Demo mission start: 1 September 2026, 00:00 UTC, in epoch milliseconds.
MISSION_START = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
DAY_MS = 86_400_000

LIVE_SOURCES = ("webcam", "video")


def now_ms():
    return int(time.time() * 1000)


def rep_id(session_id, rep_no):
    return f"{session_id}#{rep_no}"


def checkin_id(crew_id, day):
    return f"{crew_id}:d{day}"


def vitals_id(crew_id, day):
    return f"{crew_id}:v{day}"


# ---- rows <-> objects -----------------------------------------------------------------------

def _session_from_row(row):
    return SessionRow(
        id=row["id"], crew_id=row["crew_id"], exercise=row["exercise"], day=row["day"], gravity_g=row["gravity_g"],
        target_load_kg=row["target_load_kg"], prescribed_reps=row["prescribed_reps"], status=row["status"],
        started_at=row["started_at"], ended_at=row["ended_at"], source=row["source"],
    )


def _rep_from_row(row):
    flags = [f for f in row["flags"].split(";") if f]
    return RepRow(
        id=row["id"], session_id=row["session_id"], crew_id=row["crew_id"], exercise=row["exercise"],
        timestamp=row["timestamp"], gravity_g=row["gravity_g"], target_load_kg=row["target_load_kg"],
        rep_no=row["rep_no"], min_knee_angle=row["min_knee_angle"], eccentric_s=row["eccentric_s"],
        concentric_s=row["concentric_s"], asymmetry=row["asymmetry"], confidence=row["confidence"],
        form_score=row["form_score"], flags=flags, level=row["level"],
    )


def _checkin_from_row(row):
    return CheckIn(id=row["id"], crew_id=row["crew_id"], day=row["day"], sleep=row["sleep"], fatigue=row["fatigue"],
                   pain=row["pain"], pain_location=row["pain_location"], stress=row["stress"])


def _vitals_from_row(row):
    return VitalReading(
        id=row["id"], crew_id=row["crew_id"], day=row["day"], heart_rate=row["heart_rate"], systolic=row["systolic"],
        diastolic=row["diastolic"], temperature_c=row["temperature_c"], glucose_mg_dl=row["glucose_mg_dl"],
        spo2_pct=row["spo2_pct"],
    )


def _alert_from_row(row):
    return AlertRow(
        key=row["key"], crew_id=row["crew_id"], exercise=row["exercise"], rule=row["rule"], level=row["level"],
        title=row["title"], summary=row["summary"], day=row["day"], raised_at=row["raised_at"],
        acknowledged=bool(row["acknowledged"]),
    )


def _insert_session(conn, s, replace=True):
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    conn.execute(
        f"{verb} INTO sessions (id, crew_id, exercise, day, gravity_g, target_load_kg, prescribed_reps, status, "
        "started_at, ended_at, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (s.id, s.crew_id, s.exercise, s.day, s.gravity_g, s.target_load_kg, s.prescribed_reps, s.status,
         s.started_at, s.ended_at, s.source),
    )


def _insert_rep(conn, r, replace=True):
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    conn.execute(
        f"{verb} INTO reps (id, session_id, crew_id, exercise, timestamp, gravity_g, target_load_kg, rep_no, "
        "min_knee_angle, eccentric_s, concentric_s, asymmetry, confidence, form_score, flags, level) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (r.id, r.session_id, r.crew_id, r.exercise, r.timestamp, r.gravity_g, r.target_load_kg, r.rep_no,
         r.min_knee_angle, r.eccentric_s, r.concentric_s, r.asymmetry, r.confidence, r.form_score,
         ";".join(r.flags), r.level),
    )


def _insert_checkin(conn, c, replace=True):
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    conn.execute(
        f"{verb} INTO checkins (id, crew_id, day, sleep, fatigue, pain, pain_location, stress) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (c.id, c.crew_id, c.day, c.sleep, c.fatigue, c.pain, c.pain_location, c.stress),
    )


def _insert_vitals(conn, v, replace=True):
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
    conn.execute(
        f"{verb} INTO vitals (id, crew_id, day, heart_rate, systolic, diastolic, temperature_c, glucose_mg_dl, "
        "spo2_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (v.id, v.crew_id, v.day, v.heart_rate, v.systolic, v.diastolic, v.temperature_c, v.glucose_mg_dl, v.spo2_pct),
    )


# ---- crew -----------------------------------------------------------------------------------

def save_crew(conn, members):
    for m in members:
        conn.execute("INSERT OR REPLACE INTO crew (id, name, role, mass_kg) VALUES (?, ?, ?, ?)",
                     (m.id, m.name, m.role, m.mass_kg))


def crew_ids(conn):
    return [row["id"] for row in conn.execute("SELECT id FROM crew ORDER BY id")]


def count(conn, table):
    """Number of rows in one of the logbook tables."""
    if table not in ("crew", "sessions", "reps", "checkins", "vitals", "alerts", "cmo_notes"):
        raise ValueError(f"unknown table {table}")
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# ---- sessions and reps (crash-proof recording) ----------------------------------------------

def start_session(conn, crew_id, exercise, gravity_g, target_load_kg, prescribed_reps, source, day=TODAY):
    row = SessionRow(
        id=f"s-{uuid.uuid4()}", crew_id=crew_id, exercise=exercise, day=day, gravity_g=gravity_g,
        target_load_kg=target_load_kg, prescribed_reps=prescribed_reps, status="active",
        started_at=now_ms(), ended_at=None, source=source,
    )
    _insert_session(conn, row)
    return row


def add_rep(conn, rep):
    """Write one rep straight away. Writing the same session + rep number again replaces it."""
    _insert_rep(conn, rep)


def get_session(conn, session_id):
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    return _session_from_row(row)


def finish_session(conn, session_id):
    """Close a session. A live session with no reps is deleted, so it never counts as a skipped workout."""
    s = get_session(conn, session_id)
    if s is None:
        return
    n = conn.execute("SELECT COUNT(*) FROM reps WHERE session_id = ?", (session_id,)).fetchone()[0]
    if n == 0 and s.source in LIVE_SOURCES:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return
    conn.execute("UPDATE sessions SET status = 'completed', ended_at = ? WHERE id = ?", (now_ms(), session_id))


def list_active_sessions(conn):
    """Sessions that were never closed: offered as "Resume session"."""
    rows = conn.execute("SELECT * FROM sessions WHERE status = 'active' ORDER BY started_at").fetchall()
    return [_session_from_row(r) for r in rows]


def session_reps(conn, session_id):
    rows = conn.execute("SELECT * FROM reps WHERE session_id = ? ORDER BY rep_no", (session_id,)).fetchall()
    return [_rep_from_row(r) for r in rows]


def all_sessions(conn):
    rows = conn.execute("SELECT * FROM sessions ORDER BY day, started_at").fetchall()
    return [_session_from_row(r) for r in rows]


def all_reps(conn):
    rows = conn.execute("SELECT * FROM reps ORDER BY timestamp, rep_no").fetchall()
    return [_rep_from_row(r) for r in rows]


def load_session_records(conn):
    """Sessions joined with their reps, in the shape the health rules use."""
    reps_by_session = {}
    for r in all_reps(conn):
        reps_by_session.setdefault(r.session_id, []).append(r)

    records = []
    for s in all_sessions(conn):
        reps = sorted(reps_by_session.get(s.id, []), key=lambda r: r.rep_no)
        if s.source in LIVE_SOURCES and not reps:
            continue
        # A session still in progress is not a shortfall yet: only count what is done so far.
        if s.status == "active":
            prescribed = min(s.prescribed_reps, len(reps))
        else:
            prescribed = s.prescribed_reps
        samples = [RepSample(r.min_knee_angle, r.eccentric_s, r.concentric_s, r.asymmetry, r.confidence) for r in reps]
        records.append(SessionRecord(id=s.id, crew_id=s.crew_id, exercise=s.exercise, day=s.day,
                                     gravity_g=s.gravity_g, prescribed_reps=prescribed, reps=samples))
    return records


# ---- check-ins and vital signs --------------------------------------------------------------

def save_checkin(conn, crew_id, day, sleep, fatigue, pain, pain_location, stress):
    """One check-in per crew member per mission day: saving again replaces it."""
    if pain == 0:
        pain_location = None
    c = CheckIn(id=checkin_id(crew_id, day), crew_id=crew_id, day=day, sleep=sleep, fatigue=fatigue,
                pain=pain, pain_location=pain_location, stress=stress)
    _insert_checkin(conn, c)
    return c


def load_checkins(conn):
    rows = conn.execute("SELECT * FROM checkins ORDER BY day, crew_id").fetchall()
    return [_checkin_from_row(r) for r in rows]


def save_vitals(conn, crew_id, day, heart_rate=None, systolic=None, diastolic=None, temperature_c=None,
                glucose_mg_dl=None, spo2_pct=None):
    """One set of vitals per crew member per mission day: saving again replaces it."""
    v = VitalReading(id=vitals_id(crew_id, day), crew_id=crew_id, day=day, heart_rate=heart_rate, systolic=systolic,
                     diastolic=diastolic, temperature_c=temperature_c, glucose_mg_dl=glucose_mg_dl, spo2_pct=spo2_pct)
    _insert_vitals(conn, v)
    return v


def load_vitals(conn):
    rows = conn.execute("SELECT * FROM vitals ORDER BY day, crew_id").fetchall()
    return [_vitals_from_row(r) for r in rows]


# ---- Crew Medical Officer notes -------------------------------------------------------------

def get_note(conn, crew_id):
    row = conn.execute("SELECT * FROM cmo_notes WHERE crew_id = ?", (crew_id,)).fetchone()
    if row is None:
        return None
    return NoteRow(crew_id=row["crew_id"], text=row["text"], updated_at=row["updated_at"])


def set_note(conn, crew_id, text):
    conn.execute("INSERT OR REPLACE INTO cmo_notes (crew_id, text, updated_at) VALUES (?, ?, ?)",
                 (crew_id, text, now_ms()))


# ---- alert log ------------------------------------------------------------------------------

def _insert_alert(conn, entry, raised_at):
    conn.execute(
        "INSERT OR IGNORE INTO alerts (key, crew_id, exercise, rule, level, title, summary, day, raised_at, acknowledged) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
        (entry.key, entry.crew_id, entry.exercise, entry.rule, entry.level, entry.title, entry.summary,
         entry.day, raised_at),
    )


def add_alert_entries(conn, entries):
    """Add entries whose key is new. Existing entries (and their acknowledged tick) are untouched.
    Returns how many were added."""
    added = 0
    with transaction(conn):
        for e in entries:
            before = conn.total_changes
            _insert_alert(conn, e, now_ms())
            if conn.total_changes > before:
                added += 1
    return added


def set_acknowledged(conn, key, acknowledged):
    conn.execute("UPDATE alerts SET acknowledged = ? WHERE key = ?", (1 if acknowledged else 0, key))


def get_alert(conn, key):
    row = conn.execute("SELECT * FROM alerts WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return _alert_from_row(row)


def list_alerts(conn):
    rows = conn.execute("SELECT * FROM alerts ORDER BY day, key").fetchall()
    return [_alert_from_row(r) for r in rows]


# ---- demo data ------------------------------------------------------------------------------

def _seeded_rep_rows(rec, session_start):
    """Stored rep rows for one demo session, with the form score from the real scoring code."""
    cfg = REP_CONFIGS.get(rec.exercise)
    member = crew_by_id(rec.crew_id)
    mass = member.mass_kg if member else 70
    target = build_plan(mass, rec.gravity_g, rec.exercise).target_load_kg
    tempo = tempo_for_g(rec.gravity_g)
    rows = []
    for i, r in enumerate(rec.reps):
        m = RepMetrics(rep_no=i + 1, start_ms=0, end_ms=0, min_knee_angle=r.min_knee_angle, eccentric_s=r.eccentric_s,
                       concentric_s=r.concentric_s, hold_s=0, asymmetry_deg=r.asymmetry_deg, confidence=r.confidence)
        if cfg is not None:
            a = assess_rep(m, targets_for(cfg, tempo))
            score, flags, level = a.score, a.flags, a.overall
        else:
            score, flags, level = 0, [], "green"
        rows.append(RepRow(
            id=rep_id(rec.id, i + 1), session_id=rec.id, crew_id=rec.crew_id, exercise=rec.exercise,
            timestamp=session_start + i * 6000, gravity_g=rec.gravity_g, target_load_kg=target, rep_no=i + 1,
            min_knee_angle=r.min_knee_angle, eccentric_s=r.eccentric_s, concentric_s=r.concentric_s,
            asymmetry=r.asymmetry_deg, confidence=r.confidence, form_score=score, flags=flags, level=level,
        ))
    return rows


def seed_demo_data(conn):
    """Write the 3-crew x 30-day demo data (sessions, reps, check-ins, vitals, alert log)."""
    log = replay_alert_log(DEMO_SESSIONS, DEMO_CHECKINS, [c.id for c in CREW], DEMO_DAYS, vitals=DEMO_VITALS)
    with transaction(conn):
        save_crew(conn, CREW)
        for rec in DEMO_SESSIONS:
            started_at = MISSION_START + rec.day * DAY_MS
            member = crew_by_id(rec.crew_id)
            _insert_session(conn, SessionRow(
                id=rec.id, crew_id=rec.crew_id, exercise=rec.exercise, day=rec.day, gravity_g=rec.gravity_g,
                target_load_kg=build_plan(member.mass_kg, rec.gravity_g, rec.exercise).target_load_kg,
                prescribed_reps=rec.prescribed_reps, status="completed", started_at=started_at,
                ended_at=started_at + 20 * 60_000, source="demo-seed",
            ))
            for r in _seeded_rep_rows(rec, started_at):
                _insert_rep(conn, r)
        for c in DEMO_CHECKINS:
            _insert_checkin(conn, CheckIn(id=checkin_id(c.crew_id, c.day), crew_id=c.crew_id, day=c.day,
                                          sleep=c.sleep, fatigue=c.fatigue, pain=c.pain,
                                          pain_location=c.pain_location, stress=c.stress))
        for v in DEMO_VITALS:
            _insert_vitals(conn, VitalReading(
                id=vitals_id(v.crew_id, v.day), crew_id=v.crew_id, day=v.day, heart_rate=v.heart_rate,
                systolic=v.systolic, diastolic=v.diastolic, temperature_c=v.temperature_c,
                glucose_mg_dl=v.glucose_mg_dl, spo2_pct=v.spo2_pct))
        for e in log:
            _insert_alert(conn, e, MISSION_START + e.day * DAY_MS)


def ensure_seeded(conn):
    """Seed the demo data on the very first run (empty crew table). Safe to call every time."""
    if count(conn, "crew") == 0:
        seed_demo_data(conn)


# Tables cleared by "Reset demo data". The downlink queue is added by the downlink module.
RESET_TABLES = ["crew", "sessions", "reps", "checkins", "vitals", "alerts", "cmo_notes"]


def reset_demo_data(conn, extra_tables=()):
    """Wipe every logbook table, then seed the demo data again."""
    with transaction(conn):
        for table in RESET_TABLES + list(extra_tables):
            conn.execute(f"DELETE FROM {table}")
    seed_demo_data(conn)
