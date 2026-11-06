"""Shared page state: the logbook connection, the chosen crew member and location, the
header, loading data and keeping the alert log up to date."""

from dataclasses import dataclass

import streamlit as st

from config.health_rules import HEALTH_RULES
from data.crew import CREW, crew_by_id
from data.locations import LOCATIONS, environment_for_g, location_by_id
from db import repo
from db.database import open_db
from engine.alert_log import new_log_entries
from engine.change_detection import assess_crew
from downlink import stores
from guidance.routine import routine_for_day
from ui import theme

FOOTER = ("Prototype decision-support tool. Not a medical device. "
          "Thresholds are demonstration values, not clinically validated.")


@dataclass
class Context:
    crew: object        # CrewMember
    location: object    # Location
    g: float
    environment: str    # microgravity / partial / earth
    day: int


@dataclass
class Data:
    records: list
    checkins: list
    vitals: list


def get_conn():
    """One logbook connection per browser session; the demo data is seeded on the very first run."""
    if "conn" not in st.session_state:
        conn = open_db()
        repo.ensure_seeded(conn)
        st.session_state.conn = conn
    return st.session_state.conn


def load_data(conn, up_to_day=None):
    records = repo.load_session_records(conn)
    checkins = repo.load_checkins(conn)
    vitals = repo.load_vitals(conn)
    if up_to_day is not None:
        records = [r for r in records if r.day <= up_to_day]
        checkins = [c for c in checkins if c.day <= up_to_day]
        vitals = [v for v in vitals if v.day <= up_to_day]
    return Data(records=records, checkins=checkins, vitals=vitals)


def assess(data, crew_id):
    return assess_crew(data.records, crew_id, HEALTH_RULES, data.checkins, data.vitals)


def sync_alert_log(conn, data, day=repo.TODAY):
    """Write any alert that is new (or newly escalated) into the alert log."""
    known = {a.key for a in repo.list_alerts(conn)}
    entries = []
    for member in CREW:
        entries.extend(new_log_entries(assess(data, member.id).alerts, known, day))
    if entries:
        repo.add_alert_entries(conn, entries)


def context():
    """The crew member and location chosen in the header."""
    crew = crew_by_id(st.session_state.get("crew_id", CREW[0].id)) or CREW[0]
    location = location_by_id(st.session_state.get("location_id", "leo"))
    if location.id == "custom":
        g = st.session_state.get("custom_g", 0.5)
        environment = environment_for_g(g)
    else:
        g = location.g
        environment = location.environment
    return Context(crew=crew, location=location, g=g, environment=environment, day=repo.TODAY)


def toggle_comms(conn):
    window_open = stores.get_setting(conn, "window_open", False)
    stores.set_setting(conn, "window_open", not window_open)


# The chosen crew member, location and custom gravity are kept in these settings. Streamlit forgets a
# widget's value when you switch pages, so each page copies the setting into its picker ("_" key)
# and the picker copies any change back.
SETTINGS = {"crew_id": CREW[0].id, "location_id": "leo", "custom_g": 0.5}


def _remember(name):
    st.session_state[name] = st.session_state["_" + name]


def _picker_value(name):
    """Make sure the setting exists and load it into the picker for this page."""
    if name not in st.session_state:
        st.session_state[name] = SETTINGS[name]
    st.session_state["_" + name] = st.session_state[name]


def header(conn):
    """The original app's header controls: crew, location, comms status, offline badge, today's to-do."""
    for name in SETTINGS:
        _picker_value(name)
    crew_col, location_col, comms_col, offline_col = st.columns([2.2, 2.2, 1.5, 1.3], vertical_alignment="bottom")
    crew_col.selectbox("Crew", [c.id for c in CREW], key="_crew_id", on_change=_remember, args=("crew_id",),
                       format_func=lambda i: crew_by_id(i).name)
    location_col.selectbox("Location", [loc.id for loc in LOCATIONS], key="_location_id", on_change=_remember,
                           args=("location_id",), format_func=lambda i: location_by_id(i).label,
                           help="Sets gravity. Gravity changes the exercise plan and the emergency steps.")
    window_open = stores.get_setting(conn, "window_open", False)
    words = "● Link open" if window_open else "● Blackout"
    colour = theme.NOMINAL if window_open else theme.ACT
    st.html(f"<style>.st-key-comms_toggle button {{ color: {colour} !important; "
            f"border-color: {theme.tint(colour, 0.5)} !important; background: {theme.tint(colour, 0.12)} !important; "
            f"border-radius: 999px !important; font-size: 0.8rem; }}</style>")
    comms_col.button(words, key="comms_toggle", on_click=toggle_comms, args=(conn,), width="stretch",
                     help="Simulated comms link to Earth. Click to switch between blackout and an open window.")
    offline_col.markdown(f'<div style="padding-bottom:0.45rem">{theme.pill("Works offline", theme.NOMINAL)}</div>',
                         unsafe_allow_html=True)
    if st.session_state.location_id == "custom":
        location_col.slider("Gravity (g)", 0.0, 1.0, step=0.01, key="_custom_g", on_change=_remember,
                            args=("custom_g",))

    ctx = context()
    data = load_data(conn)
    today = routine_for_day(ctx.crew.id, ctx.day, data.checkins, data.vitals, data.records)
    if today.complete:
        todo = theme.pill("Today's routine done ✓", theme.NOMINAL)
    else:
        todo = theme.pill("To do today: " + ", ".join(today.missing()), theme.WATCH)
    st.markdown(f'<div class="of-row" style="margin:0.2rem 0 0.4rem 0">{todo}'
                f'{theme.label(f"Mission day {ctx.day} · {ctx.g:.3g} g · {ctx.environment}")}</div>',
                unsafe_allow_html=True)
    return ctx


def page_start():
    """Call at the top of every page: theme, header, and the alert log kept up to date."""
    theme.inject()
    conn = get_conn()
    ctx = header(conn)
    sync_alert_log(conn, load_data(conn))
    return ctx


def footer():
    st.markdown(f'<div class="of-footer">{theme.esc(FOOTER)}</div>', unsafe_allow_html=True)
