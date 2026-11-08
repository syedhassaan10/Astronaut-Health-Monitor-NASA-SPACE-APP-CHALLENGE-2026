"""The mission: demo or real, its name, start date, location and crew.

- Demo mission: the 3 sample crew members with 30 days of history. The mission day stays at 30.
- New mission: the crew's own names and body weights, an empty logbook, and a mission day
  counted from the start date on the calendar.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from data.crew import CrewMember
from data.demo_seed import DEMO_DAYS
from db import repo
from db.database import transaction

DEMO = "demo"
REAL = "real"

SCHEMA = """
CREATE TABLE IF NOT EXISTS mission (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mode TEXT NOT NULL,
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    location_id TEXT NOT NULL,
    custom_g REAL NOT NULL,
    earth_delay_min INTEGER NOT NULL,
    cmo_id TEXT,
    backup INTEGER NOT NULL,
    acknowledged INTEGER NOT NULL
);
"""

MIN_MASS_KG = 30.0
MAX_MASS_KG = 200.0
MAX_CREW = 12


@dataclass
class Mission:
    mode: str
    name: str
    start_date: date
    location_id: str
    custom_g: float
    earth_delay_min: int
    cmo_id: str | None
    backup: bool
    acknowledged: bool


def ensure_table(conn):
    conn.executescript(SCHEMA)


def _save(conn, m):
    conn.execute(
        "INSERT OR REPLACE INTO mission (id, mode, name, start_date, location_id, custom_g, earth_delay_min, cmo_id, "
        "backup, acknowledged) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (m.mode, m.name, m.start_date.isoformat(), m.location_id, m.custom_g, m.earth_delay_min, m.cmo_id,
         1 if m.backup else 0, 1 if m.acknowledged else 0),
    )


def demo_mission():
    return Mission(mode=DEMO, name="Demo mission (sample data)", start_date=date.today() - timedelta(days=DEMO_DAYS - 1),
                   location_id="leo", custom_g=0.5, earth_delay_min=10, cmo_id="c2", backup=False, acknowledged=True)


def get_mission(conn):
    """The current mission, or None before the first-start setup.

    A logbook made before missions existed (it already has crew) is treated as the demo mission.
    """
    ensure_table(conn)
    row = conn.execute("SELECT * FROM mission WHERE id = 1").fetchone()
    if row is None:
        if repo.count(conn, "crew") > 0:
            m = demo_mission()
            _save(conn, m)
            return m
        return None
    return Mission(mode=row["mode"], name=row["name"], start_date=date.fromisoformat(row["start_date"]),
                   location_id=row["location_id"], custom_g=row["custom_g"], earth_delay_min=row["earth_delay_min"],
                   cmo_id=row["cmo_id"], backup=bool(row["backup"]), acknowledged=bool(row["acknowledged"]))


def update_mission(conn, m):
    ensure_table(conn)
    _save(conn, m)


def mission_day(m, today=None):
    """Day 1 is the start date. The demo mission always shows its last day (30)."""
    if m is None or m.mode == DEMO:
        return DEMO_DAYS
    today = today or date.today()
    return max(1, (today - m.start_date).days + 1)


def list_crew(conn):
    rows = conn.execute("SELECT * FROM crew ORDER BY id").fetchall()
    return [CrewMember(r["id"], r["name"], r["role"], r["mass_kg"]) for r in rows]


def validate_crew(rows):
    """Check the crew table from the setup form. Returns (crew members, error messages).

    Each row is a dict with "name", "role" and "mass_kg". Empty rows are skipped.
    """
    members = []
    errors = []
    seen = set()
    for i, row in enumerate(rows, start=1):
        name = (row.get("name") or "").strip()
        role = (row.get("role") or "").strip() or "Crew member"
        mass = row.get("mass_kg")
        if not name and mass in (None, ""):
            continue
        if not name:
            errors.append(f"Row {i}: enter a name.")
            continue
        if name.lower() in seen:
            errors.append(f"Row {i}: {name} is listed twice.")
            continue
        try:
            mass = float(mass)
        except (TypeError, ValueError):
            errors.append(f"Row {i}: enter {name}'s body weight in kg.")
            continue
        if not MIN_MASS_KG <= mass <= MAX_MASS_KG:
            errors.append(f"Row {i}: body weight must be between {MIN_MASS_KG:g} and {MAX_MASS_KG:g} kg.")
            continue
        seen.add(name.lower())
        members.append(CrewMember(id=f"m{len(members) + 1}", name=name, role=role, mass_kg=mass))
    if not members and not errors:
        errors.append("Add at least one crew member.")
    if len(members) > MAX_CREW:
        errors.append(f"At most {MAX_CREW} crew members.")
    return members, errors


def start_demo_mission(conn):
    """Wipe the logbook and load the 3-crew, 30-day demo mission."""
    ensure_table(conn)
    repo.reset_demo_data(conn, extra_tables=_downlink_tables(conn))
    _save(conn, demo_mission())


def start_new_mission(conn, name, start_date, location_id, custom_g, earth_delay_min, crew, cmo_id, backup,
                      acknowledged):
    """Wipe the logbook and start an empty real mission with this crew."""
    ensure_table(conn)
    with transaction(conn):
        for table in repo.RESET_TABLES + _downlink_tables(conn):
            conn.execute(f"DELETE FROM {table}")
        repo.save_crew(conn, crew)
    _save(conn, Mission(mode=REAL, name=name.strip() or "New mission", start_date=start_date,
                        location_id=location_id, custom_g=custom_g, earth_delay_min=earth_delay_min, cmo_id=cmo_id,
                        backup=backup, acknowledged=acknowledged))


def clear_mission(conn):
    """Delete the mission and its whole logbook; the first-start setup appears again."""
    ensure_table(conn)
    with transaction(conn):
        for table in repo.RESET_TABLES + _downlink_tables(conn):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM mission")


def add_crew_member(conn, name, role, mass_kg):
    """Add one person to the current mission. Returns (member, error)."""
    existing = list_crew(conn)
    members, errors = validate_crew([{"name": c.name, "role": c.role, "mass_kg": c.mass_kg} for c in existing]
                                    + [{"name": name, "role": role, "mass_kg": mass_kg}])
    if errors:
        return None, errors[0]
    used = {c.id for c in existing}
    number = len(existing) + 1
    while f"m{number}" in used:
        number += 1
    member = CrewMember(id=f"m{number}", name=members[-1].name, role=members[-1].role, mass_kg=members[-1].mass_kg)
    repo.save_crew(conn, [member])
    return member, None


def update_crew_member(conn, crew_id, name, role, mass_kg):
    """Change a person's name, role or body weight (their history is kept). Returns an error or None."""
    others = [c for c in list_crew(conn) if c.id != crew_id]
    rows = [{"name": c.name, "role": c.role, "mass_kg": c.mass_kg} for c in others]
    members, errors = validate_crew(rows + [{"name": name, "role": role, "mass_kg": mass_kg}])
    if errors:
        return errors[0]
    changed = members[-1]
    repo.save_crew(conn, [CrewMember(id=crew_id, name=changed.name, role=changed.role, mass_kg=changed.mass_kg)])
    return None


def _downlink_tables(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return [t for t in ("downlink_queue",) if t in names]
