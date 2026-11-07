"""Crew Medical Officer: crew overview, trends, alerts, alert log, notes and logbook tools."""

import pandas as pd
import streamlit as st

from db import repo
from engine.health_types import SeriesPoint
from engine.session_metrics import summarize_session
from ui import state, theme, widgets

state.page_start()

conn = state.get_conn()
ctx = state.context()

theme.page_header("Crew Medical Officer view", "Who needs attention today, and why. Decision support, not a diagnosis.")

if ctx.day >= 2:
    day = st.slider("Mission day (drag back to replay how each crew member's trend developed)", 1, ctx.day, ctx.day,
                    help="The assessments below use only data up to this day.")
else:
    day = ctx.day
data = state.load_data(conn, up_to_day=day)
TEAM = ctx.team
NAMES = state.crew_names(TEAM)
assessments = {m.id: state.assess(data, m.id) for m in TEAM}

tab_overview, tab_trends, tab_alerts, tab_log, tab_notes, tab_data = st.tabs(
    ["Overview", "Trends", "Alerts", "Alert log", "Notes", "Logbook data"])


def latest(items, crew_id):
    mine = [x for x in items if x.crew_id == crew_id]
    mine.sort(key=lambda x: x.day)
    return mine[-1] if mine else None


# ---- overview --------------------------------------------------------------------------------

with tab_overview:
    cols = st.columns(min(len(TEAM), 4))
    for index, member in enumerate(TEAM):
        col = cols[index % len(cols)]
        a = assessments[member.id]
        with theme.card(col):
            theme.html_block(
                f'<div class="of-row"><div><div class="of-title">{theme.esc(member.name)}</div>'
                f'<div class="of-muted">{theme.esc(member.role)}</div></div>'
                f'<span class="of-right">{theme.badge(a.status, True)}</span></div>')
            if a.alerts:
                lines = "".join(
                    f'<div style="margin-top:0.25rem"><span style="color:{theme.STATUS_STYLE[al.level][1]};'
                    f'font-weight:700">{al.level}</span> · {theme.esc(al.title)}</div>' for al in a.alerts)
                theme.html_block(f'<div style="margin-top:0.5rem">{len(a.alerts)} active alerts:{lines}</div>')
            else:
                theme.html_block('<div style="margin-top:0.5rem">No active alerts.</div>')
            theme.html_block(f'<div style="border-top:1px solid {theme.STROKE};margin-top:0.7rem;padding-top:0.6rem">'
                             f'{widgets.checkin_chips(latest(data.checkins, member.id))}</div>'
                             f'<div>{widgets.vitals_chips(latest(data.vitals, member.id))}</div>')

# ---- trends ----------------------------------------------------------------------------------

EXERCISE_METRICS = {
    "Squat depth (bottom knee angle, °)": ("depth_deg", "°"),
    "Lifting time (s)": ("concentric_s", "s"),
    "Left-right difference (°)": ("asymmetry_deg", "°"),
    "Rep-to-rep variability (°)": ("variability_deg", "°"),
    "Reps completed (% of prescribed)": ("adherence", "%"),
}
VITAL_METRICS = {
    "Resting heart rate (bpm)": "heart_rate",
    "Blood pressure, top number (mmHg)": "systolic",
    "Body temperature (°C)": "temperature_c",
    "Blood sugar (mg/dL)": "glucose_mg_dl",
    "Oxygen saturation (%)": "spo2_pct",
}
CHECKIN_METRICS = {"Sleep (0-10)": "sleep", "Fatigue (0-10)": "fatigue", "Pain (0-10)": "pain", "Stress (0-10)": "stress"}

with tab_trends:
    t1, t2 = st.columns(2)
    member_id = t1.selectbox("Crew member", list(NAMES), format_func=lambda i: NAMES[i],
                             key="trend_crew")
    metric = t2.selectbox("Measurement", list(EXERCISE_METRICS) + list(VITAL_METRICS) + list(CHECKIN_METRICS),
                          key="trend_metric")
    a = assessments[member_id]
    baseline = None
    rows = []
    unit = ""
    if metric in EXERCISE_METRICS:
        attr, unit = EXERCISE_METRICS[metric]
        for rec in data.records:
            if rec.crew_id != member_id or rec.exercise != "squat":
                continue
            m = summarize_session(rec)
            if attr == "adherence":
                value = 100 * m.completed_reps / m.prescribed_reps if m.prescribed_reps else 0
                rows.append((m.day, value))
            elif m.usable:
                rows.append((m.day, getattr(m, attr)))
        squat = [e for e in a.exercises if e.exercise == "squat"]
        if squat and squat[0].baseline is not None and attr != "adherence":
            base = squat[0].baseline
            baseline = {"depth_deg": base.depth_deg, "concentric_s": base.concentric_s,
                        "asymmetry_deg": base.asymmetry_deg, "variability_deg": base.variability_deg}[attr]
    elif metric in VITAL_METRICS:
        attr = VITAL_METRICS[metric]
        for v in data.vitals:
            if v.crew_id == member_id and getattr(v, attr) is not None:
                rows.append((v.day, getattr(v, attr)))
    else:
        attr = CHECKIN_METRICS[metric]
        for c in data.checkins:
            if c.crew_id == member_id:
                rows.append((c.day, getattr(c, attr)))
    if rows:
        points = [SeriesPoint(d, v) for d, v in sorted(rows)]
        st.plotly_chart(widgets.series_chart(points, baseline, unit, metric, height=360), key="trend_chart")
        if baseline is not None:
            st.caption("Dashed line: this person's own baseline (median of their first 3 valid sessions).")
    else:
        st.info("No data for this measurement yet.")

# ---- alerts ----------------------------------------------------------------------------------

with tab_alerts:
    any_alerts = False
    for member in TEAM:
        a = assessments[member.id]
        if not a.alerts:
            continue
        any_alerts = True
        st.markdown(f"#### {member.name}")
        for i, alert in enumerate(a.alerts):
            widgets.alert_card(alert, key=f"cmo-{member.id}-{i}")
    if not any_alerts:
        st.success("No alerts for anyone on this day.")

# ---- alert log -------------------------------------------------------------------------------

with tab_log:
    st.write("Every alert, with the mission day it was first raised (an escalation from WATCH to ACT is a new entry). "
             "Tick to acknowledge.")
    log = [e for e in repo.list_alerts(conn) if e.day <= day]
    if log:
        df = pd.DataFrame([{
            "key": e.key, "Day": e.day, "Crew member": NAMES.get(e.crew_id, e.crew_id),
            "Level": e.level, "Alert": e.title, "What changed": e.summary, "Acknowledged": e.acknowledged,
        } for e in log])
        edited = st.data_editor(df, hide_index=True, width="stretch", disabled=[c for c in df.columns if c != "Acknowledged"],
                                column_config={"key": None}, key="alert_log_editor")
        for before, after in zip(df.itertuples(), edited.itertuples()):
            if before.Acknowledged != after.Acknowledged:
                repo.set_acknowledged(conn, before.key, bool(after.Acknowledged))
    else:
        st.info("The alert log is empty for this day.")

# ---- notes -----------------------------------------------------------------------------------

with tab_notes:
    for member in TEAM:
        note = repo.get_note(conn, member.id)
        text = st.text_area(member.name, value=note.text if note else "", key=f"note-{member.id}", height=120)
        if st.button(f"Save note for {member.name}", key=f"save-note-{member.id}"):
            repo.set_note(conn, member.id, text)
            st.success("Saved.")

# ---- logbook data ----------------------------------------------------------------------------

with tab_data:
    st.markdown("Export, import, daily backups and starting a new mission are on the Mission page.")
    st.page_link("pages/mission.py", label="Open the Mission page", icon="🗂️")

state.footer()
