"""First-start setup, shown until a mission exists. About two minutes, five steps:

1 Choose: try the demo mission, or start a new one
2 Mission: name, start date, location, delay to Earth
3 Crew: names, roles, body weights, who is the Crew Medical Officer
4 Your normal: how OrbitFit learns each person's baseline
5 Data and privacy: where data lives, daily backup, acknowledgement
"""

import math
from datetime import date

import pandas as pd
import streamlit as st

from data.locations import LOCATIONS, location_by_id
from db import mission
from db.database import default_db_path
from downlink import stores
from ui import theme

STEPS = ["Choose", "Mission", "Crew", "Your normal", "Data and privacy"]
# Typical one-way radio delay in minutes for each place (Moon and ISS are nearly instant).
DEFAULT_DELAY = {"earth": 1, "leo": 1, "moon": 1, "transit": 10, "mars": 12, "custom": 5}
ACKNOWLEDGEMENT = ("I understand OrbitFit is a prototype decision-support tool, not a medical device. It does not "
                   "replace the onboard medical procedures, the Crew Medical Officer or the flight surgeon.")


def _data():
    if "setup" not in st.session_state:
        st.session_state.setup = {
            "step": 1, "name": "", "start_date": date.today(), "location_id": "leo", "custom_g": 0.5,
            "delay": DEFAULT_DELAY["leo"], "cmo": "", "backup": True,
            "crew": [{"name": "", "role": "Commander", "mass_kg": None},
                     {"name": "", "role": "Crew Medical Officer", "mass_kg": None},
                     {"name": "", "role": "Flight Engineer", "mass_kg": None}],
        }
    return st.session_state.setup


def _go(step):
    _data()["step"] = step


def _progress(step):
    parts = []
    for i, name in enumerate(STEPS, start=1):
        if i < step:
            colour, mark = theme.GOOD, "✓"
        elif i == step:
            colour, mark = theme.CYAN, "●"
        else:
            colour, mark = theme.FAINT, "○"
        parts.append(f'<span style="color:{colour};font-weight:700">{mark} {i} · {name}</span>')
    theme.html_block('<div class="of-row" style="margin-bottom:0.8rem">' + " &nbsp;→&nbsp; ".join(parts) + "</div>")


def _nav(back_step, next_label="Next", next_disabled=False):
    """Back and Next buttons. Returns True when Next was pressed."""
    left, _, right = st.columns([1, 3, 1])
    if back_step:
        left.button("← Back", on_click=_go, args=(back_step,), width="stretch", key=f"setup_back_{back_step}")
    return right.button(next_label, type="primary", width="stretch", disabled=next_disabled, key="setup_next")


# ---- step 1 ----------------------------------------------------------------------------------

def _step_choose(conn):
    theme.page_header("Welcome to OrbitFit", "Health self-monitoring for astronauts. Set up in about two minutes.")
    demo_col, new_col = st.columns(2, gap="large")
    with demo_col.container(border=True):
        theme.html_block('<div class="of-title">Try the demo mission</div>'
                         '<div class="of-big" style="margin:0.4rem 0 0.8rem 0">3 sample crew members with 30 days '
                         'of history. Best for a first look and for judges.</div>')
        if st.button("Open the demo", type="primary", width="stretch", key="setup_demo"):
            mission.start_demo_mission(conn)
            st.session_state.pop("setup", None)
            st.rerun()
    with new_col.container(border=True):
        theme.html_block('<div class="of-title">Start a new mission</div>'
                         '<div class="of-big" style="margin:0.4rem 0 0.8rem 0">Your own crew and an empty logbook. '
                         'Mission days are counted from your start date.</div>')
        st.button("Set up a new mission", width="stretch", on_click=_go, args=(2,), key="setup_new")
    st.caption("You can switch later on the Mission page. Everything stays on this computer.")


# ---- step 2 ----------------------------------------------------------------------------------

def _step_mission():
    d = _data()
    theme.page_header("Your mission", "Where you are sets gravity, the exercise plan and the emergency steps.")
    _progress(2)
    with st.container(border=True):
        name = st.text_input("Mission name", value=d["name"], placeholder="e.g. Artemis training, Mars transit")
        start = st.date_input("Mission start date (day 1)", value=d["start_date"], max_value=date.today(),
                              help="The mission day is counted from this date.")
        ids = [loc.id for loc in LOCATIONS]
        location_id = st.selectbox("Where are you?", ids, index=ids.index(d["location_id"]),
                                   format_func=lambda i: location_by_id(i).label)
        custom_g = d["custom_g"]
        if location_id == "custom":
            custom_g = st.slider("Gravity (g)", 0.0, 1.0, value=float(d["custom_g"]), step=0.01)
        delay_default = d["delay"] if location_id == d["location_id"] else DEFAULT_DELAY[location_id]
        delay = st.slider("Usual one-way delay to Earth (minutes)", 1, 40, value=int(delay_default),
                          help="Used by the simulated downlink. Mars is 5 to 20 minutes away by radio.")
    day = max(1, (date.today() - start).days + 1)
    st.caption(f"Today will be mission day {day}.")
    if _nav(1):
        d.update(name=name, start_date=start, location_id=location_id, custom_g=custom_g, delay=delay)
        _go(3)
        st.rerun()


# ---- step 3 ----------------------------------------------------------------------------------

def _clean_rows(df):
    rows = []
    for record in df.to_dict("records"):
        mass = record.get("mass_kg")
        if isinstance(mass, float) and math.isnan(mass):
            mass = None
        name = record.get("name")
        role = record.get("role")
        rows.append({"name": name if isinstance(name, str) else "", "role": role if isinstance(role, str) else "",
                     "mass_kg": mass})
    return rows


def _step_crew():
    d = _data()
    theme.page_header("Your crew", "Body weight sets each person's exercise load. Add or remove rows as needed.")
    _progress(3)
    with st.container(border=True):
        edited = st.data_editor(
            pd.DataFrame(d["crew"], columns=["name", "role", "mass_kg"]), num_rows="dynamic", width="stretch",
            key="setup_crew_editor", hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("Name", required=True),
                "role": st.column_config.TextColumn("Role"),
                "mass_kg": st.column_config.NumberColumn("Body weight (kg)", min_value=mission.MIN_MASS_KG,
                                                         max_value=mission.MAX_MASS_KG, step=0.5),
            })
        rows = _clean_rows(edited)
        named = [r["name"].strip() for r in rows if r["name"].strip()]
        options = [""] + named
        current = d["cmo"] if d["cmo"] in named else ""
        cmo = st.selectbox("Crew Medical Officer", options, index=options.index(current),
                           format_func=lambda n: "Nobody yet" if n == "" else n)
    members, errors = mission.validate_crew(rows)
    if errors == ["Add at least one crew member."]:
        st.info("Type each person's name and body weight in the table.")
    else:
        for e in errors:
            st.error(e)
    if _nav(2, next_disabled=bool(errors)):
        d.update(crew=rows, cmo=cmo)
        _go(4)
        st.rerun()


# ---- step 4 ----------------------------------------------------------------------------------

def _step_normal():
    theme.page_header("How OrbitFit learns your normal", "Alerts compare you with yourself, not with an average.")
    _progress(4)
    cards = [
        ("Exercise", "Your first 3 workouts with at least 5 good reps become your normal for depth, speed and "
                     "left-right balance. Until then you see “Building your normal: 1 of 3”."),
        ("Heart rate", "Your first 3 morning heart-rate readings become your resting normal. Measure before getting "
                       "up, in the same position each day."),
        ("Always on", "Safety ranges for vital signs, pain and the Emergency page work from day 1. They do not "
                      "need a baseline."),
    ]
    cols = st.columns(3)
    for col, (title, text) in zip(cols, cards):
        with col.container(border=True):
            theme.html_block(f'<div class="of-title">{title}</div><div class="of-big" style="margin-top:0.4rem">'
                             f'{theme.esc(text)}</div>')
    with st.container(border=True):
        theme.html_block(f'{theme.label("Camera set-up for workouts")}<ul class="of-big">'
                         "<li>Camera 1.5 to 2 m away, at hip height.</li>"
                         "<li>Hips, knees and ankles in view; good light from the front.</li>"
                         "<li>Stand still for 2 seconds before the first rep.</li></ul>")
    if _nav(3):
        _go(5)
        st.rerun()


# ---- step 5 ----------------------------------------------------------------------------------

def _step_privacy(conn):
    d = _data()
    theme.page_header("Your data", "It stays on this computer. You decide what is sent to Earth.")
    _progress(5)
    with st.container(border=True):
        theme.html_block(
            f'<div class="of-big">The logbook is one file on this computer:</div>'
            f'<div class="of-chip" style="margin:0.4rem 0">{theme.esc(default_db_path())}</div>'
            '<ul class="of-big"><li>No internet, no account, no cloud. Video never leaves the computer.</li>'
            "<li>Only the summary you choose to queue on the Downlink page is sent to Earth.</li>"
            "<li>Export or import the logbook as CSV any time on the Mission page.</li></ul>")
        backup_on = st.toggle("Save a backup copy every day (last 14 days kept)", value=d["backup"])
        agreed = st.checkbox(ACKNOWLEDGEMENT)
    if _nav(4, next_label="Start mission", next_disabled=not agreed):
        team, errors = mission.validate_crew(d["crew"])
        if errors:
            st.error(errors[0])
            return
        cmo_id = None
        for member in team:
            if member.name == d["cmo"]:
                cmo_id = member.id
        mission.start_new_mission(conn, d["name"], d["start_date"], d["location_id"], d["custom_g"], d["delay"],
                                  team, cmo_id, backup_on, agreed)
        stores.set_setting(conn, "latency_min", d["delay"])
        for key in ("setup", "crew_id", "location_id", "custom_g"):
            st.session_state.pop(key, None)
        st.rerun()


def render(conn):
    step = _data()["step"]
    if step == 1:
        _step_choose(conn)
    elif step == 2:
        _step_mission()
    elif step == 3:
        _step_crew()
    elif step == 4:
        _step_normal()
    else:
        _step_privacy(conn)
