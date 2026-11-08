"""Row shapes and the SQLite tables of the offline logbook."""

from dataclasses import dataclass, field

SOURCES = ["webcam", "video", "demo-seed", "import"]


@dataclass
class SessionRow:
    """One workout. status "active" means it was never closed (the app stopped mid-set)."""
    id: str
    crew_id: str
    exercise: str
    day: int
    gravity_g: float
    target_load_kg: float
    prescribed_reps: int
    status: str        # "active" or "completed"
    started_at: int    # epoch milliseconds
    ended_at: int | None
    source: str        # one of SOURCES


@dataclass
class RepRow:
    """One rep, written the moment it completes. id = "<sessionId>#<repNo>"."""
    id: str
    session_id: str
    crew_id: str
    exercise: str
    timestamp: int     # epoch milliseconds when the rep completed
    gravity_g: float
    target_load_kg: float
    rep_no: int
    min_knee_angle: float
    eccentric_s: float
    concentric_s: float
    asymmetry: float   # mean |left - right| knee angle, degrees
    confidence: float
    form_score: float
    flags: list = field(default_factory=list)
    level: str = "green"


@dataclass
class AlertRow:
    """Alert log entry, written when an alert first appears (or escalates). key = "<alertId>|<level>"."""
    key: str
    crew_id: str
    exercise: str | None
    rule: str
    level: str
    title: str
    summary: str
    day: int
    raised_at: int
    acknowledged: bool


@dataclass
class NoteRow:
    crew_id: str
    text: str
    updated_at: int


SCHEMA = """
CREATE TABLE IF NOT EXISTS crew (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    mass_kg REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    crew_id TEXT NOT NULL,
    exercise TEXT NOT NULL,
    day INTEGER NOT NULL,
    gravity_g REAL NOT NULL,
    target_load_kg REAL NOT NULL,
    prescribed_reps INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    ended_at INTEGER,
    source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_status ON sessions(status);
CREATE TABLE IF NOT EXISTS reps (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    crew_id TEXT NOT NULL,
    exercise TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    gravity_g REAL NOT NULL,
    target_load_kg REAL NOT NULL,
    rep_no INTEGER NOT NULL,
    min_knee_angle REAL NOT NULL,
    eccentric_s REAL NOT NULL,
    concentric_s REAL NOT NULL,
    asymmetry REAL NOT NULL,
    confidence REAL NOT NULL,
    form_score REAL NOT NULL,
    flags TEXT NOT NULL,
    level TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reps_session ON reps(session_id);
CREATE TABLE IF NOT EXISTS checkins (
    id TEXT PRIMARY KEY,
    crew_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    sleep INTEGER NOT NULL,
    fatigue INTEGER NOT NULL,
    pain INTEGER NOT NULL,
    pain_location TEXT,
    stress INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS vitals (
    id TEXT PRIMARY KEY,
    crew_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    heart_rate REAL,
    systolic REAL,
    diastolic REAL,
    temperature_c REAL,
    glucose_mg_dl REAL,
    spo2_pct REAL,
    radiation_msv REAL
);
CREATE TABLE IF NOT EXISTS alerts (
    key TEXT PRIMARY KEY,
    crew_id TEXT NOT NULL,
    exercise TEXT,
    rule TEXT NOT NULL,
    level TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    day INTEGER NOT NULL,
    raised_at INTEGER NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS cmo_notes (
    crew_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
"""
