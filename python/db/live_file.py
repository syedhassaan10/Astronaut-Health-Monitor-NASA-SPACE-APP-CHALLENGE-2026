"""Live logbook file: a CSV file on disk that gets every rep added the moment the rep ends.

Same columns as "Export CSV", so it can be imported back. It is a second copy next to the
SQLite logbook, never a replacement. Each rep is opened, written, flushed to disk and closed,
so it survives a crash or power loss.
"""

import os
import threading
from dataclasses import dataclass
from pathlib import Path

from data.logbook_csv import logbook_csv_header, rep_csv_line


@dataclass
class LiveFileStatus:
    file_name: str | None = None
    reps_written: int = 0
    error: str | None = None


def append_to_file(path, text):
    """Add text to the end of the file and make sure it is on disk before returning."""
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


class LiveFile:
    def __init__(self):
        self.path = None
        self.status = LiveFileStatus()
        self._lock = threading.Lock()  # keeps writes in order, one after the other

    def use(self, path):
        """Start using this file. A new or empty file gets the header line first."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.stat().st_size == 0:
            append_to_file(path, logbook_csv_header())
        self.path = path
        self.status = LiveFileStatus(file_name=path.name, reps_written=0, error=None)

    def stop(self):
        self.path = None
        self.status = LiveFileStatus()

    def append_rep(self, rep):
        """Add one rep, if a file is chosen. Never raises: a failed write shows up in status.error."""
        path = self.path
        if path is None:
            return
        with self._lock:
            try:
                append_to_file(path, rep_csv_line(rep))
            except OSError as e:
                self.status.error = str(e)
                return
            self.status.reps_written += 1
            self.status.error = None
