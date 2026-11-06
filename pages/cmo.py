"""Crew Medical Officer: crew overview, trends, alerts, alert log, notes and logbook tools."""

import pandas as pd
import streamlit as st

from data.crew import CREW, crew_by_id
from db import repo
from db.logbook_io import export_logbook_csv, import_logbook_csv
from engine.health_types import SeriesPoint
from engine.session_metrics import summarize_session
from ui import state, theme, widgets

state.page_start()

conn = state.get_conn()
ctx = state.context()

theme.page_header("Crew Medical Officer view", "Status of all crew, trend estimates and alerts. Decision support only, not a diagnosis.")

day = st.slider("Mission day (drag back to replay how each crew member's trend developed)", 1, ctx.day, ctx.day,
                help="Demo feature: the assessments below use only data up to this day.")
data = state.load_data(conn, up_to_day=day)
assessments = {m.id: state.assess(data, m.id) for m in CREW}

tab_overview, tab_trends, tab_alerts, tab_log, tab_notes, tab_data = st.tabs(
    ["Overview", "Trends", "Alerts", "Alert log", "Notes", "Logbook data"])


def latest(items, crew_id):
    mine = [x for x in items if x.crew_id == crew_id]
    mine.sort(key=lambda x: x.day)
    return mine[-1] if mine else None


# ---- overview --------------------------------------------------------------------------------

with tab_overview:
    cols = st.columns(len(CREW))
    for col, member in zip(cols, CREW):
        a = assessments[member.id]
        with col.container(border=True):
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
    member_id = t1.selectbox("Crew member", [m.id for m in CREW], format_func=lambda i: crew_by_id(i).name,
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
    for member in CREW:
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
            "key": e.key, "Day": e.day, "Crew member": crew_by_id(e.crew_id).name if crew_by_id(e.crew_id) else e.crew_id,
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
    for member in CREW:
        note = repo.get_note(conn, member.id)
        text = st.text_area(member.name, value=note.text if note else "", key=f"note-{member.id}", height=120)
        if st.button(f"Save note for {member.name}", key=f"save-note-{member.id}"):
            repo.set_note(conn, member.id, text)
            st.success("Saved.")

# ---- logbook data ----------------------------------------------------------------------------

with tab_data:
    st.write("Everything is stored in a local SQLite file on this computer. Every rep is saved the moment it ends.")
    counts = {t: repo.count(conn, t) for t in ("sessions", "reps", "checkins", "vitals", "alerts")}
    st.caption(" · ".join(f"{n} {t}" for t, n in counts.items()))

    st.download_button("⬇ Export logbook as CSV (opens in Excel)", data=export_logbook_csv(conn).encode("utf-8"),
                       file_name=f"orbitfit-logbook-day{ctx.day}.csv", mime="text/csv")

    upload = st.file_uploader("Import a logbook CSV (adds new rows; never overwrites what is here)", type=["csv"])
    if upload is not None and st.button("Import this file"):
        text = upload.getvalue().decode("utf-8-sig", errors="replace")
        report = import_logbook_csv(conn, text)
        added = report.added
        st.success(f"Read {report.total_rows} rows. Added {added['sessions']} sessions, {added['reps']} reps, "
                   f"{added['checkins']} check-ins, {added['vitals']} vitals. {report.already_present} were already "
                   "in the logbook and were left untouched.")
        if report.errors:
            st.warning(f"{len(report.errors)} rows were skipped:")
            for err in report.errors[:50]:
                where = f"line {err.line}: " if err.line else ""
                st.caption(f"{where}{err.message}")

    st.divider()
    st.markdown("**Reset demo data**: deletes everything (including notes and live sessions) and restores the "
                "3 sample crew members with 30 days of history.")
    confirm = st.checkbox("Yes, delete all logbook data and restore the demo")
    if st.button("Reset demo data", disabled=not confirm):
        extra = ["downlink_queue"] if "downlink_queue" in [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")] else []
        repo.reset_demo_data(conn, extra_tables=extra)
        st.success("Demo data restored.")
        st.rerun()

state.footer()
