"""Downlink (spacecraft side): build a short summary for the flight surgeon and send it when a
comms window opens. Everything about the link is SIMULATED (1 simulated minute = 1 second)."""

import time
import uuid

import streamlit as st

from data.crew import CREW
from db import repo
from downlink import stores
from downlink.packet import build_packet, format_kb, packet_size_bytes
from downlink.sender import DownlinkSender
from engine.downlink_queue import phase_of
from ui import state

state.page_start()

PHASE_WORDS = {
    "waiting-for-window": ("Waiting for a link", "No link (blackout). It leaves as soon as a window opens."),
    "starting": ("Starting to send", "The link is open."),
    "in-transit": ("On its way to Earth", "Travelling through space."),
    "awaiting-ack": ("Arrived at Earth", "Waiting for Earth's confirmation to travel back."),
    "acked": ("Delivered ✓", "Earth confirmed it arrived."),
    "gave-up": ("Not delivered", "Gave up after 20 tries. Cancel it and queue a new one."),
}
STEPS = ["Ready", "Waiting for link", "On its way", "Delivered ✓"]
STEP_OF_PHASE = {"waiting-for-window": 1, "starting": 2, "in-transit": 2, "awaiting-ack": 2, "acked": 4, "gave-up": 1}

conn = state.get_conn()
ctx = state.context()
if "link" not in st.session_state:
    st.session_state.link = stores.open_link()
link = st.session_state.link
if "sender" not in st.session_state:
    st.session_state.sender = DownlinkSender(conn, link)
sender = st.session_state.sender

st.title("📡 Downlink to Earth")
st.write("Send a short summary to the flight surgeon on Earth. On a deep-space mission messages take minutes to "
         "arrive and the link is often down, so the packet waits in a queue, survives a restart, and is sent again "
         "until Earth confirms it.")
st.caption("SIMULATED link: one simulated minute of delay = one real second. Open the Earth receiver page in a "
           "second browser tab to play the ground side.")

# ---- comms window ----------------------------------------------------------------------------

window_open = stores.get_setting(conn, "window_open", False)
latency_min = stores.get_setting(conn, "latency_min", 10)
c1, c2 = st.columns([1, 2])
with c1:
    if window_open:
        st.markdown('<div style="font-size:1.4rem;font-weight:800;color:#34d399">● LINK OPEN</div>',
                    unsafe_allow_html=True)
        if st.button("Close the link (start a blackout)"):
            stores.set_setting(conn, "window_open", False)
            st.rerun()
    else:
        st.markdown('<div style="font-size:1.4rem;font-weight:800;color:#f87171">■ BLACKOUT · no link</div>',
                    unsafe_allow_html=True)
        if st.button("Open a comms window", type="primary"):
            stores.set_setting(conn, "window_open", True)
            st.rerun()
with c2:
    new_latency = st.slider("One-way delay (minutes; Earth to Mars is 5 to 20, up to 40 at worst)", 1, 40, latency_min)
    if new_latency != latency_min:
        stores.set_setting(conn, "latency_min", new_latency)
        latency_min = new_latency

# ---- build a packet --------------------------------------------------------------------------

with st.container(border=True):
    st.markdown("**New flight surgeon packet**")
    window_days = st.select_slider("Days of detail in the packet", [3, 7, 14, 30], value=7)
    data = state.load_data(conn)
    notes = {}
    for member in CREW:
        note = repo.get_note(conn, member.id)
        if note and note.text.strip():
            notes[member.id] = note.text
    preview = build_packet(data.records, data.checkins, data.vitals, CREW, ctx.day, window_days, "preview",
                           int(time.time() * 1000), notes=notes)
    st.caption(f"Contains: each crew member's status, alerts, latest check-in and vitals, CMO notes, and a "
               f"{window_days}-day table of sessions and check-ins. Size: {format_kb(packet_size_bytes(preview))}.")
    if st.button("Queue packet for Earth", type="primary"):
        packet_id = f"pkt-d{ctx.day}-{uuid.uuid4().hex[:8]}"
        packet = build_packet(data.records, data.checkins, data.vitals, CREW, ctx.day, window_days, packet_id,
                              int(time.time() * 1000), notes=notes)
        stores.enqueue_packet(conn, packet, time.time() * 1000)
        st.success(f"Queued {packet_id}. It leaves when a comms window is open.")


# ---- queue (refreshes every second) ----------------------------------------------------------

def step_bar(current):
    parts = []
    for i, name in enumerate(STEPS):
        if i < current:
            colour, mark = "#34d399", "✓"
        elif i == current:
            colour, mark = "#38bdf8", "●"
        else:
            colour, mark = "#7a8aa8", "○"
        parts.append(f'<span style="color:{colour};font-weight:600">{mark} {name}</span>')
    return " &nbsp;→&nbsp; ".join(parts)


@st.fragment(run_every=1.0)
def queue_panel():
    window = stores.get_setting(conn, "window_open", False)
    latency = stores.get_setting(conn, "latency_min", 10)
    sender.tick(window, latency * 1000)
    now = time.time() * 1000
    if sender.earth_online():
        st.caption("🌍 Earth receiver: listening")
    else:
        st.caption("🌍 Earth receiver: not open. Packets sent now will be lost and re-sent later.")
    items = stores.list_queue(conn)
    if not items:
        st.info("No packets yet. Queue one above.")
        return
    for item, size, day in items:
        phase = phase_of(item, window)
        title, detail = PHASE_WORDS[phase]
        with st.container(border=True):
            st.markdown(f"**{item.id}** · mission day {day} · {format_kb(size)} · tries: {item.attempts}")
            st.markdown(step_bar(STEP_OF_PHASE[phase]), unsafe_allow_html=True)
            if phase == "in-transit" and item.sent_at is not None and item.deliver_at:
                share = (now - item.sent_at) / max(1.0, item.deliver_at - item.sent_at)
                share = min(1.0, max(0.0, share))
                minutes_left = max(0.0, (item.deliver_at - now) / 1000)
                st.progress(share, text=f"{title}: about {minutes_left:.0f} simulated minutes to go")
            else:
                st.caption(f"{title}. {detail}")
            if item.status != "acked":
                if st.button("Cancel", key=f"cancel-{item.id}"):
                    stores.cancel_packet(conn, item.id)
                    st.rerun()


st.subheader("Packets")
queue_panel()

state.footer()
