"""Today: the astronaut's page. 1 Check-in, 2 Vitals, 3 Workout (camera), 4 My status."""

import time
from pathlib import Path

import pandas as pd
import streamlit as st

from config.health_rules import HEALTH_RULES
from db import repo
from db.live_file import LiveFile
from engine.checkin_rules import LOCATION_LABEL
from engine.gravity_engine import EXERCISE_IDS, EXERCISES
from engine.health_types import BODY_LOCATIONS
from engine.rep_detector import REP_CONFIGS
from engine.vitals_rules import range_level
from guidance.measurements import guide_by_id
from guidance.routine import routine_for_day, streak
from ui import state, widgets

state.page_start()

PROJECT_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_DIR / "var" / "uploads"

conn = state.get_conn()
ctx = state.context()
crew = ctx.crew
data = state.load_data(conn)
assessment = state.assess(data, crew.id)

# ---- header ----------------------------------------------------------------------------------

st.title(f"Today · {crew.name}")
st.caption(f"{crew.role} · {ctx.location.label} · mission day {ctx.day}")
widgets.show_status(assessment.status, "1.6rem")

flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)

routine = routine_for_day(crew.id, ctx.day, data.checkins, data.vitals, data.records)
days_in_a_row = streak(crew.id, ctx.day, data.checkins, data.vitals, data.records)
c1, c2, c3, c4 = st.columns(4)
c1.metric("1 · Check-in", "Done ✓" if routine.checkin else "To do")
c2.metric("2 · Vitals", "Done ✓" if routine.vitals else "To do")
c3.metric("3 · Workout", "Done ✓" if routine.workout else "To do")
c4.metric("Routine streak", f"{days_in_a_row} days", help="Days in a row with check-in, vitals and workout all done.")

tab_checkin, tab_vitals, tab_workout, tab_status = st.tabs(
    ["1 · Check-in", "2 · Vitals", "3 · Workout", "4 · My status"])

# ---- 1. check-in -----------------------------------------------------------------------------

with tab_checkin:
    existing = None
    for c in data.checkins:
        if c.crew_id == crew.id and c.day == ctx.day:
            existing = c
    st.write("How are you today? About 30 seconds. Your answers sit next to your exercise trends so the "
             "Crew Medical Officer sees the whole picture. This is self-reported decision support, not a diagnosis.")
    with st.form(f"checkin-{crew.id}"):
        col_a, col_b = st.columns(2)
        sleep = col_a.slider("Sleep quality (0 very poor · 10 excellent)", 0, 10, existing.sleep if existing else 7)
        fatigue = col_b.slider("Fatigue (0 fresh · 10 exhausted)", 0, 10, existing.fatigue if existing else 3)
        pain = col_a.slider("Muscle or joint pain (0 none · 10 worst imaginable)", 0, 10, existing.pain if existing else 0)
        stress = col_b.slider("Mood / stress (0 calm · 10 very stressed)", 0, 10, existing.stress if existing else 3)
        options = [""] + BODY_LOCATIONS
        current = existing.pain_location if existing and existing.pain_location else ""
        location = col_a.selectbox("If you have pain: where?", options, index=options.index(current),
                                   format_func=lambda x: "Choose…" if x == "" else LOCATION_LABEL[x])
        submitted = st.form_submit_button("Update today's check-in" if existing else "Save check-in", type="primary")
    if submitted:
        if pain > 0 and location == "":
            st.error("Please choose where it hurts.")
        else:
            repo.save_checkin(conn, crew.id, ctx.day, sleep, fatigue, pain, location or None, stress)
            st.session_state.flash = f"Check-in saved for mission day {ctx.day}. Your status has been updated."
            st.rerun()
    with st.expander("How to answer the check-in"):
        for i, step in enumerate(guide_by_id("checkin").how_to, start=1):
            st.markdown(f"{i}. {step}")

# ---- 2. vitals -------------------------------------------------------------------------------

VITAL_FIELDS = [
    # (field, label, guide id, config range, min, max, step)
    ("heart_rate", "Resting heart rate (bpm)", "heart_rate", HEALTH_RULES.vitals.heart_rate, 20.0, 250.0, 1.0),
    ("systolic", "Blood pressure, top number (mmHg)", "blood_pressure", HEALTH_RULES.vitals.systolic, 40.0, 260.0, 1.0),
    ("diastolic", "Blood pressure, bottom number (mmHg)", "blood_pressure", HEALTH_RULES.vitals.diastolic, 20.0, 160.0, 1.0),
    ("temperature_c", "Body temperature (°C)", "temperature_c", HEALTH_RULES.vitals.temperature_c, 30.0, 45.0, 0.1),
    ("glucose_mg_dl", "Blood sugar (mg/dL)", "glucose_mg_dl", HEALTH_RULES.vitals.glucose_mg_dl, 10.0, 700.0, 1.0),
    ("spo2_pct", "Oxygen saturation (%)", "spo2_pct", HEALTH_RULES.vitals.spo2_pct, 50.0, 100.0, 1.0),
]

LEVEL_COLOUR = {None: "#34d399", "WATCH": "#fbbf24", "ACT": "#f87171"}
LEVEL_WORD = {None: "● normal", "WATCH": "▲ outside the normal range", "ACT": "■ well outside the normal range"}

with tab_vitals:
    today_vitals = None
    for v in data.vitals:
        if v.crew_id == crew.id and v.day == ctx.day:
            today_vitals = v
    st.write("Measure what you can; leave the rest empty. Each measurement has a short how-to guide below. "
             "Normal ranges are demonstration values for a resting adult.")
    with st.form(f"vitals-{crew.id}"):
        cols = st.columns(3)
        values = {}
        for i, (field, label, _, _, low, high, step) in enumerate(VITAL_FIELDS):
            current = getattr(today_vitals, field) if today_vitals else None
            values[field] = cols[i % 3].number_input(label, min_value=low, max_value=high, step=step,
                                                    value=float(current) if current is not None else None)
        saved = st.form_submit_button("Save vitals", type="primary")
    if saved:
        if all(v is None for v in values.values()):
            st.error("Enter at least one measurement.")
        else:
            repo.save_vitals(conn, crew.id, ctx.day, **values)
            st.session_state.flash = "Vitals saved. Check what each number means below."
            st.rerun()

    if today_vitals is not None:
        st.subheader("What today's numbers mean")
        for field, label, guide_id, rng, *_ in VITAL_FIELDS:
            value = getattr(today_vitals, field)
            if value is None:
                continue
            level, side = range_level(value, rng)
            guide = guide_by_id(guide_id)
            line = f"**{label}: {value:g}** — " + widgets.coloured(LEVEL_WORD[level], LEVEL_COLOUR[level])
            st.markdown(line, unsafe_allow_html=True)
            if level is not None:
                advice = guide.if_high if side == "high" else guide.if_low
                st.markdown(f"&nbsp;&nbsp;&nbsp;What to do: {advice}", unsafe_allow_html=True)
                st.markdown(f"&nbsp;&nbsp;&nbsp;Tell the Crew Medical Officer when: {guide.call_cmo_when}",
                            unsafe_allow_html=True)
        st.caption("Feeling unwell right now? Open the Emergency page.")

    st.subheader("How to measure")
    for guide_id in ("heart_rate", "blood_pressure", "temperature_c", "glucose_mg_dl", "spo2_pct"):
        guide = guide_by_id(guide_id)
        with st.expander(f"{guide.title} · {guide.equipment}"):
            for i, step in enumerate(guide.how_to, start=1):
                st.markdown(f"{i}. {step}")
            note = guide.environment_notes.get(ctx.environment)
            if note:
                st.info(note)
            st.markdown(f"**Normal:** {guide.normal}")

# ---- 4. my status (drawn before the workout so the camera loop can run last) -----------------

with tab_status:
    widgets.show_status(assessment.status)
    for e in assessment.exercises:
        for note in e.notes:
            st.caption(f"{EXERCISES[e.exercise].label}: {note}")
    if not assessment.alerts:
        st.success("No trend alerts. Keep up the routine.")
    for i, alert in enumerate(assessment.alerts):
        widgets.alert_card(alert, key=f"today-{i}")
    st.caption("These are trend estimates for decision support, not a diagnosis. The Health guides page explains "
               "each measurement and body area.")

# ---- 3. workout ------------------------------------------------------------------------------

if "live_file" not in st.session_state:
    st.session_state.live_file = LiveFile()
live_file = st.session_state.live_file


def stop_camera():
    st.session_state.camera = None


def start_camera(kind, path=None):
    st.session_state.camera = {"kind": kind, "path": path}


with tab_workout:
    exercise = st.radio("Exercise", EXERCISE_IDS, horizontal=True, key="exercise",
                        format_func=lambda e: EXERCISES[e].label)
    widgets.plan_card(crew, ctx.g, exercise)
    if REP_CONFIGS.get(exercise) is None:
        st.info("Heel raise has an exercise plan, but the camera cannot count it yet (the knee barely bends).")

    unfinished = [s for s in repo.list_active_sessions(conn) if s.crew_id == crew.id]
    camera = st.session_state.get("camera")
    if unfinished and not camera:
        s = unfinished[-1]
        n = len(repo.session_reps(conn, s.id))
        with st.container(border=True):
            st.warning(f"An unfinished {EXERCISES[s.exercise].label.lower()} session with {n} saved reps was found "
                       "(the app stopped mid-set). Nothing was lost.")
            r1, r2 = st.columns(2)
            if r1.button("Resume it with the next camera start"):
                st.session_state.resume_session = s.id
                st.session_state.flash = "The next camera start continues that session."
                st.rerun()
            if r2.button("Close it"):
                repo.finish_session(conn, s.id)
                st.rerun()

    b1, b2, b3, b4 = st.columns(4)
    b1.button("▶ Start webcam", on_click=start_camera, args=("webcam",), disabled=camera is not None,
              width="stretch", type="primary")
    b2.button("▶ Demo Mode", on_click=start_camera, help="Plays a sample squat video, so no webcam is needed.", args=("demo",), disabled=camera is not None,
              width="stretch")
    b4.button("■ Stop", on_click=stop_camera, disabled=camera is None, width="stretch")
    uploaded = b3.file_uploader("Use a video file", type=["mp4", "mov", "avi", "mkv", "webm"],
                                label_visibility="collapsed", disabled=camera is not None)
    if uploaded is not None and camera is None:
        if st.button(f"▶ Analyse {uploaded.name}"):
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            target = UPLOAD_DIR / Path(uploaded.name).name
            target.write_bytes(uploaded.getvalue())
            start_camera("file", str(target))
            st.rerun()

    with st.expander("Settings: live CSV file and battery saving"):
        default_path = str(PROJECT_DIR / "var" / "live-logbook.csv")
        path = st.text_input("Live logbook file (every rep is added the moment it ends)",
                             value=str(live_file.path) if live_file.path else default_path)
        f1, f2 = st.columns(2)
        if f1.button("Use this file", disabled=live_file.path is not None):
            try:
                live_file.use(path)
                st.rerun()
            except OSError as e:
                st.error(f"Could not use that file: {e}")
        if f2.button("Stop writing to it", disabled=live_file.path is None):
            live_file.stop()
            st.rerun()
        if live_file.path:
            st.caption(f"Writing to {live_file.path} · {live_file.status.reps_written} reps this session")
        if live_file.status.error:
            st.error(f"Live file problem: {live_file.status.error}. Reps are still saved in the logbook.")
        st.radio("Frame analysis", ["adaptive", "full"], key="sampling_mode", horizontal=True,
                 format_func=lambda m: "Battery saving (about 1 frame in 7)" if m == "adaptive" else "Every frame",
                 disabled=camera is not None)

    left, right = st.columns([3, 2])
    video_slot = left.empty()
    counter_slot = right.empty()
    cue_slot = right.empty()
    warning_slot = right.empty()
    table_slot = st.empty()
    stats_slot = st.empty()
    if camera is None:
        video_slot.info("Press Start webcam or Demo Mode. The camera only turns on when you press a button, "
                        "and no video leaves this computer.")


def show_rep_table(rows):
    if not rows:
        return
    df = pd.DataFrame([{
        "Rep": r.rep_no, "Depth (°)": round(r.min_knee_angle, 1), "Down (s)": round(r.eccentric_s, 2),
        "Up (s)": round(r.concentric_s, 2), "Left-right difference (°)": round(r.asymmetry, 1),
        "Confidence": round(r.confidence, 2), "Form score": int(r.form_score), "Form": r.level,
    } for r in rows])
    table_slot.dataframe(df, hide_index=True, width="stretch")


def show_last_set():
    """When the camera is off: the most recent camera set of this crew member today."""
    live = [s for s in repo.all_sessions(conn)
            if s.crew_id == crew.id and s.day == ctx.day and s.source in ("webcam", "video") and s.status == "completed"]
    if not live:
        return
    last = live[-1]
    rows = [r for r in repo.session_reps(conn, last.id) if "low-confidence" not in r.flags]
    if not rows:
        return
    average = sum(r.form_score for r in rows) / len(rows)
    counter_slot.markdown(f'<div style="font-size:4rem;font-weight:800;line-height:1">{len(rows)}</div>'
                          f'<div style="color:#aab8d0">reps in your last set · average form score {average:.0f}</div>',
                          unsafe_allow_html=True)
    show_rep_table(rows)


def run_camera(cam):
    """The live workout loop. Every rep is saved the moment it ends."""
    from pose.landmarker import DEMO_VIDEO, PoseEstimator
    from pose.overlay import draw_overlay
    from pose.recorder import SessionRecorder
    from pose.tracker import Tracker
    from pose.video_source import VideoSource

    try:
        if cam["kind"] == "webcam":
            source = VideoSource("webcam")
        elif cam["kind"] == "demo":
            source = VideoSource("video", path=DEMO_VIDEO, loop=True)
        else:
            source = VideoSource("video", path=cam["path"], loop=False)
        estimator = PoseEstimator()
    except (RuntimeError, FileNotFoundError) as e:
        st.session_state.camera = None
        video_slot.error(str(e))
        return

    tracker = Tracker(exercise, ctx.g, estimator.detect, mode=st.session_state.get("sampling_mode", "adaptive"))
    recorder = SessionRecorder(conn, crew, exercise, ctx.g, "webcam" if cam["kind"] == "webcam" else "video",
                               live_file=live_file if live_file.path else None)
    resume_id = st.session_state.pop("resume_session", None)
    resume = repo.get_session(conn, resume_id) if resume_id else None
    if resume is not None and resume.crew_id == crew.id and resume.status == "active":
        rows = [r for r in recorder.resume(resume) if "low-confidence" not in r.flags]
    else:
        recorder.start()
        rows = []

    last_ui = -1000.0
    first_t = None
    wall_start = time.monotonic()
    try:
        while True:
            item = source.read()
            if item is None:
                break
            frame, t_ms = item
            result = tracker.process(frame, t_ms)
            if result.event is not None:
                row = recorder.record(result.event)
                if row is not None and result.event.kind == "rep":
                    rows.append(row)
            draw_overlay(frame, result.pose, result.live.knee, result.live.level)

            if source.kind == "video":
                # Play files at their real speed.
                if first_t is None:
                    first_t = t_ms
                    wall_start = time.monotonic()
                wait = (t_ms - first_t) / 1000 - (time.monotonic() - wall_start)
                if wait > 0:
                    time.sleep(wait)
            video_slot.image(frame, channels="BGR", output_format="JPEG", width=520)

            if t_ms - last_ui >= 250:
                last_ui = t_ms
                # The cue describes the last finished rep, so it takes that rep's form colour.
                colour = widgets.FORM_COLOUR.get(tracker.last_level, widgets.ACCENT)
                counter_slot.markdown(
                    f'<div style="font-size:5rem;font-weight:800;line-height:1">{tracker.reps}</div>'
                    f'<div style="color:#aab8d0">reps this set</div>', unsafe_allow_html=True)
                cue = tracker.last_feedback or "Stand still for 2 s, then start"
                cue_slot.markdown(f'<div style="font-size:2.2rem;font-weight:700;color:{colour}">{cue}</div>',
                                  unsafe_allow_html=True)
                message = tracker.message(t_ms)
                if message:
                    warning_slot.error(message)
                else:
                    warning_slot.empty()
                show_rep_table(rows)
                snap = tracker.perf.snapshot(t_ms)
                stats_slot.caption(f"{tracker.mode} mode · camera {snap.camera_fps:.0f} fps · model "
                                   f"{snap.inference_per_sec:.0f}/s · {snap.skipped_pct:.0f}% of frames skipped · "
                                   f"{snap.avg_inference_ms:.0f} ms per model run")
    finally:
        recorder.finish()
        source.close()
        estimator.close()
    st.session_state.camera = None
    st.session_state.flash = f"Set finished: {tracker.reps} reps saved to the logbook."
    st.rerun()


camera = st.session_state.get("camera")
if camera is not None and REP_CONFIGS.get(st.session_state.get("exercise", "squat")) is not None:
    run_camera(camera)
elif camera is not None:
    st.session_state.camera = None
else:
    show_last_set()

state.footer()
