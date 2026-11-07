"""Daily automatic backup: once a day the whole logbook is written to a CSV file
(the same format as "Export CSV", so it can be imported back). The last 14 are kept."""

from datetime import date
from pathlib import Path

from db.database import PROJECT_DIR
from db.logbook_io import export_logbook_csv

DEFAULT_FOLDER = PROJECT_DIR / "var" / "backups"
KEEP = 14
PREFIX = "orbitfit-backup-"


def backup_path(folder, day):
    return Path(folder) / f"{PREFIX}{day.isoformat()}.csv"


def write_backup(conn, folder=DEFAULT_FOLDER, today=None):
    """Write today's backup now (replacing today's earlier one) and remove old ones."""
    today = today or date.today()
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = backup_path(folder, today)
    path.write_text(export_logbook_csv(conn), encoding="utf-8", newline="")
    prune(folder)
    return path


def backup_if_due(conn, folder=DEFAULT_FOLDER, today=None):
    """Write a backup if there is none for today yet. Returns the new file, or None."""
    today = today or date.today()
    if backup_path(folder, today).exists():
        return None
    return write_backup(conn, folder, today)


def list_backups(folder=DEFAULT_FOLDER):
    """Backup files, newest first."""
    folder = Path(folder)
    if not folder.exists():
        return []
    files = sorted(folder.glob(f"{PREFIX}*.csv"), reverse=True)
    return files


def prune(folder, keep=KEEP):
    for old in list_backups(folder)[keep:]:
        old.unlink()
