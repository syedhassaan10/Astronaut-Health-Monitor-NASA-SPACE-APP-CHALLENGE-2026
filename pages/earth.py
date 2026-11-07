"""Earth receiver (SIMULATED ground side): the flight surgeon's inbox. Open it in a second browser tab."""

import streamlit as st

from downlink import stores
from downlink.packet import adherence_pct, merge_trends
from downlink.receiver import EarthReceiver
from engine.checkin_rules import LOCATION_LABEL
from engine.health_types import SeriesPoint
from ui import state, theme, widgets

state.page_start()

if "link" not in st.session_state:
    st.session_state.link = stores.open_link()
if "earth" not in st.session_state:
    st.session_state.earth = stores.open_earth()
link = st.session_state.link
earth = st.session_state.earth
if "receiver" not in st.session_state:
    st.session_state.receiver = EarthReceiver(earth, link)
receiver = st.session_state.receiver

theme.page_header("Earth receiver", "The flight surgeon on the ground. Simulated.")
st.caption("Keep this page open while packets are sent. It has its own inbox and never reads the spacecraft logbook.")

TREND_METRICS = {
    "Squat depth (bottom knee angle, °)": ("depth_deg", "°"),
    "Lifting time (s)": ("concentric_s", "s"),
    "Left-right difference (°)": ("asymmetry_deg", "°"),
    "Reps completed (% of prescribed)": ("adherence", "%"),
}


def vitals_text(v):
    if not v:
        return ""
    parts = []
    if v.get("heartRate") is not None:
        parts.append(f"HR {v['heartRate']:g}")
    if v.get("systolic") is not None and v.get("diastolic") is not None:
        parts.append(f"BP {v['systolic']:g}/{v['diastolic']:g}")
    if v.get("temperatureC") is not None:
        parts.append(f"{v['temperatureC']:g} °C")
    if v.get("spo2Pct") is not None:
        parts.append(f"SpO2 {v['spo2Pct']:g}%")
    if v.get("glucoseMgDl") is not None:
        parts.append(f"glucose {v['glucoseMgDl']:g}")
    return f"Vitals day {v['day']}: " + " · ".join(parts)


@st.fragment(run_every=1.0)
def inbox():
    theme.reset_cards("earth")
    receiver.tick()
    packets = stores.earth_packets(earth)
    if receiver.received:
        packet_id, duplicate = receiver.received[-1]
        if duplicate:
            st.caption(f"Last delivery: {packet_id} arrived again (already stored); confirmation sent anyway.")
        else:
            st.caption(f"Last delivery: {packet_id}; confirmation sent back to the spacecraft.")
    if not packets:
        st.info("Listening… No packets yet. On the Downlink page: queue a packet, then open a comms window.")
        return

    latest = packets[-1]
    summary = latest["summary"]
    day_chip = theme.chip("Mission day " + str(latest["missionDay"]))
    theme.html_block('<div class="of-row" style="margin-top:0.4rem"><span class="of-title">Latest packet</span>'
                     + theme.chip(latest["id"]) + day_chip + "</div>")
    st.caption(summary["disclaimer"])
    cols = st.columns(min(4, max(1, len(summary["crew"]))))
    for index, c in enumerate(summary["crew"]):
        with theme.card(cols[index % len(cols)]):
            theme.html_block(
                f'<div class="of-row"><div><div class="of-title">{theme.esc(c["name"])}</div>'
                f'<div class="of-muted">{theme.esc(c.get("role", ""))}</div></div>'
                f'<span class="of-right">{theme.badge(c["status"], True)}</span></div>')
            for a in c["alerts"]:
                theme.html_block(f'<div style="margin-top:0.6rem">{theme.badge(a["level"])} '
                                 f'<b>{theme.esc(a["title"])}</b></div>'
                                 f'<div class="of-muted" style="margin-top:0.15rem">{theme.esc(a["summary"])}</div>')
            ci = c.get("latestCheckin")
            if ci:
                where = f" ({LOCATION_LABEL.get(ci['painLocation'], ci['painLocation'])})" if ci.get("painLocation") else ""
                st.caption(f"Check-in day {ci['day']}: sleep {ci['sleep']} · fatigue {ci['fatigue']} · "
                           f"pain {ci['pain']}{where} · stress {ci['stress']}")
            text = vitals_text(c.get("latestVitals"))
            if text:
                st.caption(text)
            if c.get("note"):
                with st.expander("Crew Medical Officer notes"):
                    st.text(c["note"])

    st.subheader("Trends from all received packets")
    rows = merge_trends([p["csv"] for p in packets])
    t1, t2 = st.columns(2)
    names = {c["crewId"]: c["name"] for c in summary["crew"]}
    crew_id = t1.selectbox("Crew member", list(names), format_func=lambda i: names[i], key="earth_crew")
    metric = t2.selectbox("Measurement", list(TREND_METRICS), key="earth_metric")
    attr, unit = TREND_METRICS[metric]
    points = []
    for r in rows:
        if r.crew_id != crew_id:
            continue
        value = adherence_pct(r) if attr == "adherence" else getattr(r, attr)
        if value is not None:
            points.append(SeriesPoint(r.day, value))
    if points:
        st.plotly_chart(widgets.series_chart(points, None, unit, metric, height=320), key="earth_chart")
        st.caption(f"Days {points[0].day} to {points[-1].day}, joined from {len(packets)} packet(s).")
    else:
        st.info("No data for this measurement in the received packets.")

    with st.expander(f"All received packets ({len(packets)})"):
        for p in reversed(packets):
            st.caption(f"{p['id']} · mission day {p['missionDay']}")


inbox()

if st.button("Clear the Earth inbox"):
    stores.clear_earth(earth)
    receiver.received.clear()
    st.rerun()

state.footer()
