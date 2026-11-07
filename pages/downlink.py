"""Downlink (spacecraft side): build a short summary for the flight surgeon and send it when a
comms window opens. Everything about the link is SIMULATED (1 simulated minute = 1 second)."""

import time
import uuid

import streamlit as st

from db import repo
from downlink import stores
from downlink.packet import build_packet, format_kb, packet_size_bytes
from downlink.sender import DownlinkSender
from engine.downlink_queue import phase_of
from ui import state, theme

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

theme.page_header("Downlink to Earth", "Send a short summary to the flight surgeon. It waits until a link is open.")
st.caption("Simulated link: 1 minute of delay = 1 second. Open the Earth page in a second browser tab.")

# ---- comms window ----------------------------------------------------------------------------

window_open = stores.get_setting(conn, "window_open", False)
latency_min = stores.get_setting(conn, "latency_min", 10)
c1, c2 = st.columns([1, 2])
with c1:
    if window_open:
        st.markdown(theme.pill("LINK OPEN", theme.GOOD), unsafe_allow_html=True)
        if st.button("Close the link (start a blackout)"):
            stores.set_setting(conn, "window_open", False)
            st.rerun()
    else:
        st.markdown(theme.pill("BLACKOUT · no link", theme.BAD), unsafe_allow_html=True)
        if st.button("Open a comms window", type="primary"):
            stores.set_setting(conn, "window_open", True)
            st.rerun()
with c2:
    new_latency = st.slider("One-way delay (minutes; Earth to Mars is 5 to 20, up to 40 at worst)", 1, 40, latency_min)
    if new_latency != latency_min:
        stores.set_setting(conn, "latency_min", new_latency)
        latency_min = new_latency

# ---- build a packet --------------------------------------------------------------------------

with theme.card():
    theme.html_block('<div class="of-title">New flight surgeon packet</div>')
    window_days = st.select_slider("Days of detail in the packet", [3, 7, 14, 30], value=7)
    data = state.load_data(conn)
    notes = {}
    for member in ctx.team:
        note = repo.get_note(conn, member.id)
        if note and note.text.strip():
            notes[member.id] = note.text
    preview = build_packet(data.records, data.checkins, data.vitals, ctx.team, ctx.day, window_days, "preview",
                           int(time.time() * 1000), notes=notes)
    st.caption(f"Contains: each crew member's status, alerts, latest check-in and vitals, CMO notes, and a "
               f"{window_days}-day table of sessions and check-ins. Size: {format_kb(packet_size_bytes(preview))}.")
    if st.button("Queue packet for Earth", type="primary"):
        packet_id = f"pkt-d{ctx.day}-{uuid.uuid4().hex[:8]}"
        packet = build_packet(data.records, data.checkins, data.vitals, ctx.team, ctx.day, window_days, packet_id,
                              int(time.time() * 1000), notes=notes)
        stores.enqueue_packet(conn, packet, time.time() * 1000)
        st.success(f"Queued {packet_id}. It leaves when a comms window is open.")


# ---- queue (refreshes every second) ----------------------------------------------------------

def step_bar(current):
    parts = []
    for i, name in enumerate(STEPS):
        if i < current:
            colour, mark = theme.GOOD, "✓"
        elif i == current:
            colour, mark = theme.CYAN, "●"
        else:
            colour, mark = theme.FAINT, "○"
        parts.append(f'<span style="color:{colour};font-weight:600">{mark} {name}</span>')
    return " &nbsp;→&nbsp; ".join(parts)


@st.fragment(run_every=1.0)
def queue_panel():
    theme.reset_cards("queue")
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
        with theme.card():
            theme.html_block(f'<div class="of-row"><span class="of-title">{theme.esc(item.id)}</span>'
                             f'{theme.chip(f"Mission day {day}")}{theme.chip(format_kb(size))}'
                             f'{theme.chip(f"Tries: {item.attempts}")}</div>')
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
