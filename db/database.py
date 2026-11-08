"""Opening the SQLite logbook.

The connection runs in autocommit mode: every single write is on disk as soon as the call
returns, so a crash or a closed window loses nothing that was already saved. Groups of writes
that must happen together use `transaction()`.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from db.schema import SCHEMA

PROJECT_DIR = Path(__file__).resolve().parent.parent


def default_db_path():
    """The logbook file. Set ORBITFIT_DB to use another file."""
    custom = os.environ.get("ORBITFIT_DB")
    if custom:
        return Path(custom)
    return PROJECT_DIR / "var" / "orbitfit.db"


def open_db(path=None):
    """Open (and create if needed) the logbook database."""
    if path is None:
        path = default_db_path()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    # WAL lets one page read while another writes (e.g. the Crew and Earth pages at once).
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.executescript(SCHEMA)
    _add_missing_columns(conn)
    return conn


# Columns added after the first release: a logbook made by an older version gets them on open.
NEW_COLUMNS = [("vitals", "radiation_msv", "REAL")]


def _add_missing_columns(conn):
    for table, column, kind in NEW_COLUMNS:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")


@contextmanager
def transaction(conn):
    """All writes inside happen together, or not at all."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
