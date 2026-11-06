"""Emergency: a few questions, then a priority and step-by-step guides for the crew's environment."""

import time

import streamlit as st

from data.crew import CREW, crew_by_id
from db import repo
from engine.emergency import (
    DISCLAIMER, EMERGENCY, MONITOR, PROTOCOLS, URGENT, EmergencyAnswers, steps_for, triage,
)
from ui import state, theme

state.page_start()

PRIORITY_STYLE = {
    EMERGENCY: ("■", theme.BAD, "EMERGENCY: act now and alert the whole crew"),
    URGENT: ("▲", theme.WARN, "URGENT: get the Crew Medical Officer soon"),
    MONITOR: ("●", theme.GOOD, "No red flags found: measure and keep watching"),
}
ENVIRONMENT_WORDS = {
    "microgravity": "microgravity (nothing stays put)",
    "partial": "partial gravity (Moon or Mars)",
    "earth": "Earth gravity",
}

conn = state.get_conn()
ctx = state.context()

theme.page_header("Emergency", "Someone is unwell. Stay calm: this guide walks you through it.")
st.markdown("**First: call out to your crew and the Crew Medical Officer.** Then answer below. "
            "The guide updates as you answer.")
st.caption(DISCLAIMER)
st.caption(f"Steps are adapted to {ENVIRONMENT_WORDS[ctx.environment]} ({ctx.location.label}). "
           "Change the location at the top of the page if that is wrong.")

patient_id = st.selectbox("Who needs help?", [c.id for c in CREW],
                          index=[c.id for c in CREW].index(ctx.crew.id),
                          format_func=lambda i: crew_by_id(i).name)


def yes_no(question, default_yes, key, help_text=None):
    answer = st.radio(question, ["Yes", "No"], index=0 if default_yes else 1, horizontal=True, key=key,
                      help=help_text)
    return answer == "Yes"


with st.container(border=True):
    theme.html_block(theme.label("1 · Check the person"))
    left, right = st.columns(2)
    with left:
        responsive = yes_no("Do they answer when you speak loudly and tap their shoulders?", True, "q_responsive")
        breathing = yes_no("Are they breathing normally (not gasping)?", True, "q_breathing",
                           "Look at the chest and listen for up to 10 seconds.")
        chest_pain = yes_no("Chest pain, pressure or tightness?", False, "q_chest")
        breathing_difficulty = yes_no("Difficulty breathing?", False, "q_breath_diff")
        severe_bleeding = yes_no("Severe bleeding?", False, "q_bleeding")
    with right:
        stroke_signs = yes_no("Face drooping, arm weakness or slurred speech?", False, "q_stroke")
        seizure = yes_no("Seizure (uncontrolled shaking)?", False, "q_seizure")
        allergic = yes_no("Swelling of face or throat, or a widespread rash after a trigger?", False, "q_allergy")
        head_injury = yes_no("Hit their head?", False, "q_head")

with st.expander("2 · Measurements, if you have them (leave empty if not)"):
    m1, m2, m3, m4 = st.columns(4)
    heart_rate = m1.number_input("Heart rate (bpm)", 0.0, 300.0, value=None, step=1.0)
    systolic = m2.number_input("Blood pressure, top number", 0.0, 300.0, value=None, step=1.0)
    spo2 = m3.number_input("Oxygen saturation (%)", 0.0, 100.0, value=None, step=1.0)
    glucose = m4.number_input("Blood sugar (mg/dL)", 0.0, 800.0, value=None, step=1.0)

answers = EmergencyAnswers(
    responsive=responsive, breathing_normally=breathing, chest_pain=chest_pain,
    breathing_difficulty=breathing_difficulty, severe_bleeding=severe_bleeding, stroke_signs=stroke_signs,
    seizure=seizure, allergic_reaction=allergic, head_injury=head_injury,
    heart_rate=heart_rate, systolic=systolic, spo2_pct=spo2, glucose_mg_dl=glucose,
)
result = triage(answers)

shape, colour, words = PRIORITY_STYLE[result.priority]
st.markdown(f'<div style="border:2px solid {theme.tint(colour, 0.6)};background:{theme.tint(colour, 0.12)};'
            f'border-radius:22px;padding:16px 22px;margin:12px 0;box-shadow:0 0 30px {theme.tint(colour, 0.25)}">'
            f'<div style="color:{colour};font-size:1.8rem;font-weight:800">{shape} {words}</div>'
            f'<div style="color:{theme.TEXT};margin-top:6px">{"<br>".join(result.reasons)}</div></div>',
            unsafe_allow_html=True)

st.subheader("3 · What to do")
for protocol_id in result.protocols:
    guide = PROTOCOLS[protocol_id]
    with st.container(border=True):
        st.markdown(f"### {guide['title']}")
        st.caption(guide["goal"])
        for i, step in enumerate(steps_for(protocol_id, ctx.environment), start=1):
            st.checkbox(f"{i}. {step}", key=f"step-{protocol_id}-{i}")

# ---- event notes -----------------------------------------------------------------------------

st.subheader("4 · Keep notes for the Crew Medical Officer and flight surgeon")
if "emergency_started" not in st.session_state:
    if st.button("Start the clock (note the time the event began)"):
        st.session_state.emergency_started = time.time()
        st.rerun()
else:
    started = st.session_state.emergency_started
    minutes = (time.time() - started) / 60
    st.info(f"Event started at {time.strftime('%H:%M', time.localtime(started))} "
            f"({minutes:.0f} min ago). Refresh the page to update the time.")
notes = st.text_area("What happened, what you saw, readings with times, what you did",
                     key="emergency_notes", height=140)
n1, n2 = st.columns(2)
if n1.button("Save notes to this crew member's CMO notes", disabled=not notes.strip()):
    stamp = time.strftime("%Y-%m-%d %H:%M")
    priority = result.priority
    previous = repo.get_note(conn, patient_id)
    text = f"[{stamp}] EMERGENCY LOG ({priority}): {notes.strip()}"
    if previous and previous.text.strip():
        text = previous.text.rstrip() + "\n\n" + text
    repo.set_note(conn, patient_id, text)
    st.success("Saved to the Crew Medical Officer page notes. Send them to Earth on the Downlink page when a link is open.")
if n2.button("Clear this emergency (start over)"):
    for key in list(st.session_state.keys()):
        if key.startswith(("q_", "step-", "emergency_")):
            del st.session_state[key]
    st.rerun()

state.footer()
