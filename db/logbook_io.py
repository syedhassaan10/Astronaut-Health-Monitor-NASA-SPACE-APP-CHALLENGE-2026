"""Export the whole logbook as CSV, and import a CSV as a merge (never overwrite)."""

from dataclasses import dataclass, field

from data.logbook_csv import LogbookData, RowError, parse_logbook_csv, to_logbook_csv
from db import repo
from db.database import transaction


def export_logbook_csv(conn):
    sessions = repo.all_sessions(conn)
    reps = repo.all_reps(conn)
    checkins = repo.load_checkins(conn)
    vitals = repo.load_vitals(conn)
    return to_logbook_csv(LogbookData(sessions=sessions, reps=reps, checkins=checkins, vitals=vitals))


@dataclass
class ImportReport:
    total_rows: int = 0
    # Rows written that were not in the logbook before.
    added: dict = field(default_factory=lambda: {"sessions": 0, "reps": 0, "checkins": 0, "vitals": 0})
    # Rows whose id was already in the logbook; left untouched (an import never overwrites).
    already_present: int = 0
    errors: list = field(default_factory=list)


def _existing_ids(conn, table):
    return {row[0] for row in conn.execute(f"SELECT id FROM {table}")}


def import_logbook_csv(conn, text):
    """Import a logbook CSV as a merge.

    Every row has a stable id. Rows already in the logbook are left alone, so importing the
    same file twice adds nothing and an old file can never overwrite newer data. Invalid rows,
    rows for unknown crew, and reps whose session is unknown are reported and skipped; the
    valid rows are still imported.
    """
    parsed = parse_logbook_csv(text)
    report = ImportReport(total_rows=parsed.total_rows, errors=list(parsed.errors))
    known_crew = set(repo.crew_ids(conn))

    def for_known_crew(rows, what):
        kept = []
        for r in rows:
            if r.crew_id in known_crew:
                kept.append(r)
            else:
                report.errors.append(RowError(0, f'{what} {r.id}: unknown crew "{r.crew_id}"'))
        return kept

    sessions = for_known_crew(parsed.sessions, "session")
    checkins = for_known_crew(parsed.checkins, "check-in")
    vitals = for_known_crew(parsed.vitals, "vitals")

    db_sessions = _existing_ids(conn, "sessions")
    db_reps = _existing_ids(conn, "reps")
    db_checkins = _existing_ids(conn, "checkins")
    db_vitals = _existing_ids(conn, "vitals")

    file_session_ids = {s.id for s in sessions}
    reps = []
    for r in for_known_crew(parsed.reps, "rep"):
        if r.session_id in file_session_ids or r.session_id in db_sessions:
            reps.append(r)
        else:
            report.errors.append(RowError(0, f'rep {r.id}: unknown session "{r.session_id}"'))

    new_sessions = [s for s in sessions if s.id not in db_sessions]
    new_reps = [r for r in reps if r.id not in db_reps]
    new_checkins = [c for c in checkins if c.id not in db_checkins]
    new_vitals = [v for v in vitals if v.id not in db_vitals]

    with transaction(conn):
        for s in new_sessions:
            repo._insert_session(conn, s, replace=False)
        for r in new_reps:
            repo._insert_rep(conn, r, replace=False)
        for c in new_checkins:
            repo._insert_checkin(conn, c, replace=False)
        for v in new_vitals:
            repo._insert_vitals(conn, v, replace=False)

    report.added = {
        "sessions": len(new_sessions), "reps": len(new_reps),
        "checkins": len(new_checkins), "vitals": len(new_vitals),
    }
    report.already_present = (len(sessions) - len(new_sessions) + len(reps) - len(new_reps)
                              + len(checkins) - len(new_checkins) + len(vitals) - len(new_vitals))
    return report
