"""Saves each rep the moment it ends: to the SQLite logbook and, if chosen, to the live CSV file."""

from db import repo
from db.schema import RepRow
from engine.gravity_engine import build_plan, volume_for_g


class SessionRecorder:
    def __init__(self, conn, crew, exercise, g, source, live_file=None, day=repo.TODAY):
        self.conn = conn
        self.crew = crew          # CrewMember (needs id and mass_kg)
        self.exercise = exercise
        self.g = g
        self.source = source      # "webcam" or "video"
        self.live_file = live_file
        self.day = day
        self.session = None
        self.next_rep_no = 1

    def start(self):
        """Open a new logbook session. Prescribed reps = sets x reps for this gravity."""
        volume = volume_for_g(self.g)
        target = build_plan(self.crew.mass_kg, self.g, self.exercise).target_load_kg
        self.session = repo.start_session(self.conn, self.crew.id, self.exercise, self.g, target,
                                          volume.sets * volume.reps, self.source, day=self.day)
        self.next_rep_no = 1
        return self.session

    def resume(self, session):
        """Continue an unfinished session; rep numbers carry on after the last saved rep."""
        self.session = session
        saved = repo.session_reps(self.conn, session.id)
        last = 0
        for r in saved:
            last = max(last, r.rep_no)
        self.next_rep_no = last + 1
        return saved

    def record(self, event):
        """Save a rep event. Partial reps are not saved. Returns the saved RepRow or None."""
        if self.session is None or event.kind == "partial":
            return None
        m = event.metrics
        if event.kind == "rep":
            score = event.assessment.score
            flags = list(event.assessment.flags)
            level = event.assessment.overall
        else:
            # Unreliable reps are kept for the record; the health rules ignore low-confidence reps.
            score = 0
            flags = ["low-confidence"]
            level = "red"
        rep_no = self.next_rep_no
        self.next_rep_no += 1
        row = RepRow(
            id=repo.rep_id(self.session.id, rep_no), session_id=self.session.id, crew_id=self.session.crew_id,
            exercise=self.session.exercise, timestamp=repo.now_ms(), gravity_g=self.session.gravity_g,
            target_load_kg=self.session.target_load_kg, rep_no=rep_no, min_knee_angle=m.min_knee_angle,
            eccentric_s=m.eccentric_s, concentric_s=m.concentric_s, asymmetry=m.asymmetry_deg,
            confidence=m.confidence, form_score=score, flags=flags, level=level,
        )
        repo.add_rep(self.conn, row)
        if self.live_file is not None:
            self.live_file.append_rep(row)
        return row

    def finish(self):
        """Close the session (an empty live session is deleted)."""
        if self.session is not None:
            repo.finish_session(self.conn, self.session.id)
        self.session = None
