"""Camera tracker and session recorder, tested with made-up poses (no camera, no model)."""

import math

import pytest

from data.crew import CREW
from data.logbook_csv import parse_logbook_csv
from db import repo
from db.database import open_db
from db.live_file import LiveFile
from engine.pose_math import Vec3
from pose.landmarker import PoseResult
from pose.recorder import SessionRecorder
from pose.tracker import Tracker

FPS = 30


def fake_pose(knee_deg, asym_deg=2.0, visibility=0.95):
    """33 landmarks of a person whose left knee is at knee_deg and right knee at knee_deg + asym_deg."""
    world = [Vec3(0, 0, 0, visibility) for _ in range(33)]
    world[11] = Vec3(-0.15, -0.5, 0, visibility)
    world[12] = Vec3(0.15, -0.5, 0, visibility)
    for side, x, angle in (("L", -0.1, knee_deg), ("R", 0.1, knee_deg + asym_deg)):
        hip = Vec3(x, 0, 0, visibility)
        knee = Vec3(x, 0.45, 0, visibility)
        rad = math.radians(angle)
        ankle = Vec3(x, 0.45 - 0.45 * math.cos(rad), 0.45 * math.sin(rad), visibility)
        foot = Vec3(x, ankle.y, ankle.z + 0.15, visibility)
        if side == "L":
            world[23], world[25], world[27], world[31] = hip, knee, ankle, foot
        else:
            world[24], world[26], world[28], world[32] = hip, knee, ankle, foot
    # Image landmarks: only visibility and a position inside the frame matter here.
    image = [Vec3(0.5, 0.5, 0, visibility) for _ in range(33)]
    return PoseResult(landmarks=image, world=world)


def knee_at(t, reps=5, ecc=2.6, con=1.3, rest=1.0, bottom=95.0, top=172.0):
    period = ecc + con + rest
    u = t - 1
    if u < 0 or u >= reps * period:
        return top
    x = u % period
    if x < ecc:
        return top - (top - bottom) * (1 - math.cos(math.pi * x / ecc)) / 2
    if x < ecc + con:
        return bottom + (top - bottom) * (1 - math.cos(math.pi * (x - ecc) / con)) / 2
    return top


def run(tracker, seconds, pose_for_time):
    """Feed `seconds` of frames. The 'frame' is just its time; the fake detector reads it."""
    events = []
    for f in range(int(seconds * FPS)):
        t_ms = f * 1000 / FPS
        result = tracker.process(t_ms / 1000, t_ms)
        if result.event is not None:
            events.append(result.event)
    return events


def make_tracker(pose_for_time, mode="adaptive", exercise="squat", g=1.0):
    def detect(frame, t_ms):
        return pose_for_time(frame)
    return Tracker(exercise, g, detect, mode=mode)


def squats(t):
    return fake_pose(knee_at(t))


# ---- tracker ---------------------------------------------------------------------------------

def test_fake_pose_has_the_requested_knee_angle():
    from engine.pose_math import joint_angles
    a = joint_angles(fake_pose(100, asym_deg=6).world)
    assert a.knee_l == pytest.approx(100, abs=1e-6)
    assert a.knee_r == pytest.approx(106, abs=1e-6)


def test_counts_reps_and_gives_feedback():
    tracker = make_tracker(squats, mode="full")
    events = run(tracker, 27, squats)
    reps = [e for e in events if e.kind == "rep"]
    assert len(reps) == 5
    assert tracker.reps == 5
    assert reps[0].metrics.min_knee_angle == pytest.approx(95, abs=1)
    assert reps[0].assessment.depth == "green"
    assert reps[0].feedback == "Good depth"


def test_shallow_squats_say_go_deeper():
    def shallow(t):
        return fake_pose(knee_at(t, bottom=117))
    tracker = make_tracker(shallow, mode="full")
    reps = [e for e in run(tracker, 27, shallow) if e.kind == "rep"]
    assert len(reps) == 5
    assert reps[0].feedback == "Go deeper"
    assert reps[0].assessment.depth == "amber"


def test_adaptive_mode_skips_most_frames_with_the_same_rep_count():
    full = make_tracker(squats, mode="full")
    adaptive = make_tracker(squats, mode="adaptive")
    run(full, 27, squats)
    run(adaptive, 27, squats)
    assert adaptive.reps == full.reps == 5
    snap = adaptive.perf.snapshot(27_000)
    assert snap.skipped_pct > 75


def test_no_person_gives_a_message_and_no_reps():
    def nobody(t):
        return None
    tracker = make_tracker(nobody, mode="full")
    assert run(tracker, 3, nobody) == []
    assert tracker.live.present is False
    assert "No person detected" in tracker.message(3000)


def test_low_visibility_frames_are_ignored_and_flagged():
    def blurry(t):
        return fake_pose(knee_at(t), visibility=0.2)
    tracker = make_tracker(blurry, mode="full")
    assert run(tracker, 27, blurry) == []
    assert tracker.live.present is True
    assert "unreliable" in tracker.message(27_000)


def test_middling_confidence_reps_are_reported_unreliable():
    def shaky(t):
        return fake_pose(knee_at(t), visibility=0.45)
    tracker = make_tracker(shaky, mode="full")
    events = run(tracker, 27, shaky)
    assert [e.kind for e in events] == ["unreliable"] * 5
    assert tracker.rejected == 5


def test_heel_raise_has_no_rep_counter():
    tracker = make_tracker(squats, mode="full", exercise="heelRaise")
    assert run(tracker, 10, squats) == []


def test_live_colour_turns_green_at_depth_while_moving():
    tracker = make_tracker(squats, mode="full")
    colours = set()
    for f in range(int(4 * FPS)):
        t_ms = f * 1000 / FPS
        colours.add(tracker.process(t_ms / 1000, t_ms).live.level)
    assert "green" in colours


# ---- session recorder ------------------------------------------------------------------------

@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "orbitfit.db")
    repo.save_crew(c, CREW)
    yield c
    c.close()


def test_every_rep_is_saved_the_moment_it_ends(conn, tmp_path):
    live = LiveFile()
    live.use(tmp_path / "live.csv")
    recorder = SessionRecorder(conn, CREW[0], "squat", 0.0, "video", live_file=live)
    session = recorder.start()
    assert session.prescribed_reps == 4 * 10  # 0 g: 4 sets x 10

    tracker = make_tracker(squats, g=0.0)
    saved_counts = []
    for f in range(int(27 * FPS)):
        t_ms = f * 1000 / FPS
        result = tracker.process(t_ms / 1000, t_ms)
        if result.event is not None:
            recorder.record(result.event)
            saved_counts.append(repo.count(conn, "reps"))  # already on disk, before the next frame
    assert saved_counts == [1, 2, 3, 4, 5]
    assert live.status.reps_written == 5
    with open(tmp_path / "live.csv", encoding="utf-8", newline="") as f:
        assert len(parse_logbook_csv(f.read()).reps) == 5
    recorder.finish()
    assert repo.get_session(conn, session.id).status == "completed"


def test_unreliable_reps_are_kept_with_a_flag_and_partials_are_not_saved(conn):
    from pose.tracker import RepEvent
    from engine.rep_detector import RepMetrics
    recorder = SessionRecorder(conn, CREW[0], "squat", 0.0, "webcam")
    recorder.start()
    m = RepMetrics(1, 0, 3000, 95, 2, 1, 0, 2, 0.4)
    assert recorder.record(RepEvent(kind="partial")) is None
    row = recorder.record(RepEvent(kind="unreliable", metrics=m))
    assert row.flags == ["low-confidence"]
    assert row.level == "red"
    assert repo.count(conn, "reps") == 1


def test_resume_carries_on_the_rep_numbers(conn):
    from engine.form_feedback import FormAssessment
    from engine.rep_detector import RepMetrics
    from pose.tracker import RepEvent
    event = RepEvent(kind="rep", metrics=RepMetrics(1, 0, 3000, 95, 4, 2, 1, 2, 0.9),
                     assessment=FormAssessment("green", "green", "green", "green", 100, []))
    first = SessionRecorder(conn, CREW[0], "squat", 0.0, "webcam")
    session = first.start()
    first.record(event)
    first.record(event)
    # The app stops without finishing; next time the session is offered for resume.
    assert [s.id for s in repo.list_active_sessions(conn)] == [session.id]
    second = SessionRecorder(conn, CREW[0], "squat", 0.0, "webcam")
    saved = second.resume(session)
    assert len(saved) == 2
    row = second.record(event)
    assert row.rep_no == 3


def test_a_session_with_no_reps_leaves_nothing_behind(conn):
    recorder = SessionRecorder(conn, CREW[0], "squat", 0.0, "webcam")
    session = recorder.start()
    recorder.finish()
    assert repo.get_session(conn, session.id) is None
