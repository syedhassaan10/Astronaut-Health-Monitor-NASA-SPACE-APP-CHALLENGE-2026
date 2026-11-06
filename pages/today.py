"""Crew (astronaut view): 1 Check-in, 2 Vitals, 3 Workout (camera), 4 My status."""

import time
from pathlib import Path

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
from ui import state, theme, widgets

state.page_start()

PROJECT_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_DIR / "var" / "uploads"

conn = state.get_conn()
ctx = state.context()
crew = ctx.crew
data = state.load_data(conn)
assessment = state.assess(data, crew.id)


def latest_for(items):
    mine = [x for x in items if x.crew_id == crew.id]
    mine.sort(key=lambda x: x.day)
    return mine[-1] if mine else None


# ---- header ----------------------------------------------------------------------------------

theme.page_header("Astronaut view", "Workout + daily self-check.")

flash = st.session_state.pop("flash", None)
if flash:
    st.success(flash)

if "exercise" not in st.session_state:
    st.session_state.exercise = "squat"
with st.container(border=True):
    theme.html_block(f'{theme.label("Active crew member")}'
                     f'<div style="font-size:1.15rem;margin:0.2rem 0 0.4rem 0">{theme.esc(crew.name)} '
                     f'<span style="color:{theme.INK_300}">· {theme.esc(crew.role)}</span>'
                     f'&nbsp;&nbsp;{widgets.status_html(assessment.status, "1rem")}</div>')
    st.segmented_control("Exercise", EXERCISE_IDS, key="exercise", format_func=lambda e: EXERCISES[e].label,
                         label_visibility="collapsed")
exercise = st.session_state.exercise or "squat"

routine = routine_for_day(crew.id, ctx.day, data.checkins, data.vitals, data.records)
days_in_a_row = streak(crew.id, ctx.day, data.checkins, data.vitals, data.records)
c1, c2, c3, c4 = st.columns(4)
c1.metric("1 · Check-in", "Done ✓" if routine.checkin else "To do")
c2.metric("2 · Vitals", "Done ✓" if routine.vitals else "To do")
c3.metric("3 · Workout", "Done ✓" if routine.workout else "To do")
c4.metric("Routine streak", f"{days_in_a_row} days", help="Days in a row with check-in, vitals and workout all done.")

tab_checkin, tab_vitals, tab_workout, tab_status = st.tabs(
    ["1 · Daily check-in", "2 · Vitals", "3 · Workout", "4 · My trend status"])

# ---- 1. check-in -----------------------------------------------------------------------------


def slider_with_ends(column, label, low_word, high_word, value):
    """A 0-10 slider with the original app's end labels under it."""
    chosen = column.slider(label, 0, 10, value)
    column.markdown(f'<div class="of-row" style="margin-top:-0.9rem;font-size:0.72rem;color:{theme.INK_500}">'
                    f'<span>0 · {low_word}</span><span class="of-right">{high_word} · 10</span></div>',
                    unsafe_allow_html=True)
    return chosen


with tab_checkin:
    existing = None
    for c in data.checkins:
        if c.crew_id == crew.id and c.day == ctx.day:
            existing = c
    with st.container(border=True):
        theme.html_block(
            f'<div class="of-row"><span class="of-title">Daily check-in</span>'
            f'<span class="of-muted">· about 30 seconds</span>'
            f'<span class="of-right of-label">{theme.esc(crew.name)} · mission day {ctx.day}</span></div>'
            f'<div style="margin:0.3rem 0 0.6rem 0">How are you today? Your answers sit next to your exercise trends '
            f'so the Crew Medical Officer sees the whole picture. '
            f'This is self-reported decision support, not a diagnosis.</div>')
        with st.form(f"checkin-{crew.id}", border=False):
            col_a, col_b = st.columns(2, gap="large")
            sleep = slider_with_ends(col_a, "Sleep quality", "very poor", "excellent", existing.sleep if existing else 7)
            fatigue = slider_with_ends(col_b, "Fatigue", "fresh", "exhausted", existing.fatigue if existing else 3)
            pain = slider_with_ends(col_a, "Muscle / joint pain", "none", "worst imaginable",
                                    existing.pain if existing else 0)
            stress = slider_with_ends(col_b, "Mood / stress", "calm", "very stressed", existing.stress if existing else 3)
            options = [""] + BODY_LOCATIONS
            current = existing.pain_location if existing and existing.pain_location else ""
            location = col_a.selectbox("If you have pain: where does it hurt?", options, index=options.index(current),
                                       format_func=lambda x: "Choose…" if x == "" else LOCATION_LABEL[x])
            submitted = st.form_submit_button("Update today’s check-in" if existing else "Save check-in",
                                              type="primary", key="save_checkin")
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
LEVEL_STATUS = {None: "NOMINAL", "WATCH": "WATCH", "ACT": "ACT"}
LEVEL_WORD = {None: "normal", "WATCH": "outside the normal range", "ACT": "well outside the normal range"}

with tab_vitals:
    today_vitals = None
    for v in data.vitals:
        if v.crew_id == crew.id and v.day == ctx.day:
            today_vitals = v
    with st.container(border=True):
        theme.html_block(
            '<div class="of-row"><span class="of-title">Vital signs</span>'
            '<span class="of-right of-label">demonstration ranges · resting adult</span></div>'
            f'<div style="margin:0.3rem 0 0.6rem 0">Measure what you can and leave the rest empty. Each measurement '
            f'has a short how-to guide below.</div>')
        with st.form(f"vitals-{crew.id}", border=False):
            cols = st.columns(3)
            values = {}
            for i, (field, label, _, _, low, high, step) in enumerate(VITAL_FIELDS):
                current = getattr(today_vitals, field) if today_vitals else None
                values[field] = cols[i % 3].number_input(label, min_value=low, max_value=high, step=step,
                                                        value=float(current) if current is not None else None)
            saved = st.form_submit_button("Save vitals", type="primary", key="save_vitals")
    if saved:
        if all(v is None for v in values.values()):
            st.error("Enter at least one measurement.")
        else:
            repo.save_vitals(conn, crew.id, ctx.day, **values)
            st.session_state.flash = "Vitals saved. Check what each number means below."
            st.rerun()

    if today_vitals is not None:
        with st.container(border=True):
            theme.html_block(theme.label("What today's numbers mean"))
            for field, label, guide_id, rng, *_ in VITAL_FIELDS:
                value = getattr(today_vitals, field)
                if value is None:
                    continue
                level, side = range_level(value, rng)
                guide = guide_by_id(guide_id)
                line = (f'<div class="of-row" style="margin-top:0.5rem">{theme.badge(LEVEL_STATUS[level])}'
                        f'<b>{theme.esc(label)}: {value:g}</b><span class="of-muted">{LEVEL_WORD[level]}</span></div>')
                if level is not None:
                    advice = guide.if_high if side == "high" else guide.if_low
                    line += (f'<div style="margin:0.2rem 0 0 0.2rem">What to do: {theme.esc(advice)}</div>'
                             f'<div class="of-muted" style="margin-left:0.2rem">Tell the Crew Medical Officer when: '
                             f'{theme.esc(guide.call_cmo_when)}</div>')
                theme.html_block(line)
            st.caption("Feeling unwell right now? Open the Emergency page.")

    theme.html_block(f'<div style="margin-top:0.8rem">{theme.label("How to measure")}</div>')
    for guide_id in ("heart_rate", "blood_pressure", "temperature_c", "glucose_mg_dl", "spo2_pct"):
        guide = guide_by_id(guide_id)
        with st.expander(f"{guide.title} · {guide.equipment}"):
            for i, step in enumerate(guide.how_to, start=1):
                st.markdown(f"{i}. {step}")
            note = guide.environment_notes.get(ctx.environment)
            if note:
                st.info(note)
            st.markdown(f"**Normal:** {guide.normal}")

# ---- 4. my trend status (drawn before the workout so the camera loop can run last) -----------

with tab_status:
    with st.container(border=True):
        theme.html_block(
            f'<div class="of-row"><span class="of-title">My trend status</span>{theme.badge(assessment.status, True)}'
            f'<span class="of-muted">{widgets.STATUS[assessment.status][2]}</span>'
            f'<span class="of-right of-label">estimate · decision support · mission day {ctx.day}</span></div>'
            f'<div style="margin-top:0.5rem">{widgets.checkin_chips(latest_for(data.checkins))}</div>'
            f'<div>{widgets.vitals_chips(latest_for(data.vitals))}</div>')
        for e in assessment.exercises:
            for note in e.notes:
                st.caption(f"{EXERCISES[e.exercise].label}: {note}")
        if not assessment.alerts:
            st.markdown("No active alerts. Your depth, speed, symmetry, consistency, exercise volume and vital signs "
                        "are within your normal.")
        for i, alert in enumerate(assessment.alerts):
            widgets.alert_card(alert, key=f"today-{i}")

# ---- 3. workout ------------------------------------------------------------------------------

if "live_file" not in st.session_state:
    st.session_state.live_file = LiveFile()
live_file = st.session_state.live_file


def stop_camera():
    st.session_state.camera = None


def start_camera(kind, path=None):
    st.session_state.camera = {"kind": kind, "path": path}


with tab_workout:
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

    with st.container(border=True):
        theme.html_block('<div class="of-row"><span class="of-label">Camera · measure your squats</span>'
                         '<span class="of-right of-label">on-device pose estimate · every rep is saved to the offline '
                         'logbook as it completes</span></div>')
        b1, b2, b3, b4, b5 = st.columns([1.2, 1.2, 1, 1.6, 1.8], vertical_alignment="center")
        b1.button("Start webcam", on_click=start_camera, args=("webcam",), disabled=camera is not None,
                  width="stretch", type="primary")
        b2.button("Demo Mode", on_click=start_camera, args=("demo",), disabled=camera is not None,
                  help="Plays a sample squat video, so no webcam is needed.", width="stretch")
        b3.button("Stop", on_click=stop_camera, disabled=camera is None, width="stretch")
        uploaded = b4.file_uploader("Use video file", type=["mp4", "mov", "avi", "mkv", "webm"],
                                    label_visibility="collapsed", disabled=camera is not None)
        if "sampling_mode" not in st.session_state:
            st.session_state.sampling_mode = "adaptive"
        b5.segmented_control("Frame analysis", ["adaptive", "full"], key="sampling_mode", label_visibility="collapsed",
                             format_func=lambda m: "Adaptive" if m == "adaptive" else "Full (every frame)",
                             disabled=camera is not None)
        if uploaded is not None and camera is None:
            if st.button(f"Analyse {uploaded.name}"):
                UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                target = UPLOAD_DIR / Path(uploaded.name).name
                target.write_bytes(uploaded.getvalue())
                start_camera("file", str(target))
                st.rerun()

        left, right = st.columns([3, 2], gap="large")
        overlay_slot = left.empty()
        video_slot = left.empty()
        counter_slot = right.empty()
        cue_slot = right.empty()
        warning_slot = right.empty()
        perf_col, reps_col = st.columns(2, gap="medium")
        stats_slot = perf_col.empty()
        table_slot = reps_col.empty()
        if camera is None:
            video_slot.info("Press Start webcam or Demo Mode. The camera only turns on when you press a button, "
                            "and no video leaves this computer.")

    with st.expander("Live CSV file: also save every rep to a file on disk"):
        default_path = str(PROJECT_DIR / "var" / "live-logbook.csv")
        path = st.text_input("File (same columns as Export CSV, so it can be imported back)",
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


def rep_table_html(rows):
    """SQUAT REPS · N COUNTED, newest first, in the original monospace table style."""
    name = EXERCISES[exercise].label.upper()
    body = ""
    for r in reversed(rows):
        colour = theme.LEVEL_COLOUR.get(r.level, theme.INK_100)
        body += (f"<tr><td>{r.rep_no}</td><td>{r.min_knee_angle:.0f}°</td><td>{r.eccentric_s:.1f}s</td>"
                 f"<td>{r.concentric_s:.1f}s</td><td>{r.asymmetry:.1f}°</td><td>{r.confidence * 100:.0f}%</td>"
                 f'<td style="color:{colour}">● {r.form_score:.0f}</td></tr>')
    return (f'<div class="of-box" style="background:{theme.SPACE_900}">{theme.label(f"{name} reps · {len(rows)} counted")}'
            f'<table class="of-table" style="margin-top:0.3rem"><tr><th>#</th><th>Depth</th><th>Down</th><th>Up</th>'
            f'<th>L/R Δ</th><th>Conf</th><th>Form</th></tr>{body}</table></div>')


def show_last_set():
    """When the camera is off: the most recent camera set of this crew member today."""
    live = [s for s in repo.all_sessions(conn)
            if s.crew_id == crew.id and s.day == ctx.day and s.source in ("webcam", "video") and s.status == "completed"]
    if not live:
        return
    rows = [r for r in repo.session_reps(conn, live[-1].id) if "low-confidence" not in r.flags]
    if not rows:
        return
    average = sum(r.form_score for r in rows) / len(rows)
    counter_slot.markdown(f'<div class="of-count">{len(rows)}</div><div class="of-muted">reps in your last set · '
                          f'average form score {average:.0f}</div>', unsafe_allow_html=True)
    table_slot.markdown(rep_table_html(rows), unsafe_allow_html=True)


def perf_html(tracker, snap):
    mode = "adaptive sampling" if tracker.mode == "adaptive" else "every frame"
    lines = [("Camera FPS", f"{snap.camera_fps:.1f}"), ("Inference calls / s", f"{snap.inference_per_sec:.1f}"),
             ("Avg inference", f"{snap.avg_inference_ms:.1f} ms"), ("Frames skipped", f"{snap.skipped_pct:.0f} %"),
             ("Est. compute saved vs Full", f"{snap.saved_ms / 1000:.1f} s")]
    rows = "".join(f'<div class="of-stat"><span>{k}</span><b>{v}</b></div>' for k, v in lines)
    return f'<div class="of-box" style="background:{theme.SPACE_900}">{theme.label(f"Performance · {mode}")}{rows}</div>'


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
            source_name = "Webcam"
        elif cam["kind"] == "demo":
            source = VideoSource("video", path=DEMO_VIDEO, loop=True)
            source_name = "Demo video"
        else:
            source = VideoSource("video", path=cam["path"], loop=False)
            source_name = Path(cam["path"]).name
        estimator = PoseEstimator()
    except (RuntimeError, FileNotFoundError) as e:
        st.session_state.camera = None
        video_slot.error(str(e))
        return

    tracker = Tracker(exercise, ctx.g, estimator.detect, mode=st.session_state.get("sampling_mode") or "adaptive")
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
                live = result.live
                knee = f"Knee {live.knee:.0f}°" if live.knee is not None else "Knee –"
                form_colour = theme.LEVEL_COLOUR.get(live.level, theme.INK_300)
                overlay_slot.markdown(
                    f'<div class="of-overlay"><span>{theme.esc(source_name)}</span><span>{knee}</span>'
                    f'<span>Confidence {live.confidence * 100:.0f}%</span>'
                    f'<span style="color:{form_colour}">● Form</span></div>', unsafe_allow_html=True)
                # The cue describes the last finished rep, so it takes that rep's form colour.
                colour = theme.LEVEL_COLOUR.get(tracker.last_level, theme.ACCENT)
                counter_slot.markdown(f'<div class="of-count">{tracker.reps}</div>'
                                      f'<div class="of-muted">reps this set</div>', unsafe_allow_html=True)
                cue = tracker.last_feedback or "Stand still for 2 s, then start"
                cue_slot.markdown(theme.cue(cue, colour), unsafe_allow_html=True)
                message = tracker.message(t_ms)
                if message:
                    warning_slot.error(message)
                else:
                    warning_slot.empty()
                table_slot.markdown(rep_table_html(rows), unsafe_allow_html=True)
                stats_slot.markdown(perf_html(tracker, tracker.perf.snapshot(t_ms)), unsafe_allow_html=True)
    finally:
        recorder.finish()
        source.close()
        estimator.close()
    st.session_state.camera = None
    st.session_state.flash = f"Set finished: {tracker.reps} reps saved to the logbook."
    st.rerun()


camera = st.session_state.get("camera")
if camera is not None and REP_CONFIGS.get(exercise) is not None:
    run_camera(camera)
elif camera is not None:
    st.session_state.camera = None
else:
    show_last_set()

state.footer()
