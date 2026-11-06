"""Shared page state: the logbook connection, the chosen crew member and location, the
sidebar, loading data and keeping the alert log up to date."""

from dataclasses import dataclass

import streamlit as st

from config.health_rules import HEALTH_RULES
from data.crew import CREW, crew_by_id
from data.locations import LOCATIONS, environment_for_g, location_by_id
from db import repo
from db.database import open_db
from engine.alert_log import new_log_entries
from engine.change_detection import assess_crew
from guidance.routine import routine_for_day

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
    """The crew member and location chosen in the sidebar."""
    crew = crew_by_id(st.session_state.get("crew_id", CREW[0].id)) or CREW[0]
    location = location_by_id(st.session_state.get("location_id", "leo"))
    if location.id == "custom":
        g = st.session_state.get("custom_g", 0.5)
        environment = environment_for_g(g)
    else:
        g = location.g
        environment = location.environment
    return Context(crew=crew, location=location, g=g, environment=environment, day=repo.TODAY)


def sidebar(conn):
    """Crew and location pickers, plus today's reminders. Shown on every page."""
    with st.sidebar:
        st.markdown("### 🛰️ OrbitFit")
        st.caption("Health self-monitoring for astronauts · works offline")
        ids = [c.id for c in CREW]
        st.selectbox("Crew member", ids, key="crew_id",
                     format_func=lambda i: f"{crew_by_id(i).name} · {crew_by_id(i).role}")
        st.selectbox("Where are you?", [loc.id for loc in LOCATIONS], key="location_id",
                     index=1, format_func=lambda i: location_by_id(i).label,
                     help="Sets gravity. Gravity changes the exercise plan and the emergency steps.")
        if st.session_state.get("location_id") == "custom":
            st.slider("Gravity (g)", 0.0, 1.0, step=0.01, key="custom_g")
        ctx = context()
        st.caption(f"Mission day {ctx.day} · {ctx.g:.3g} g · {ctx.environment}")

        data = load_data(conn)
        today = routine_for_day(ctx.crew.id, ctx.day, data.checkins, data.vitals, data.records)
        if today.complete:
            st.success("Today's routine is done. ✓")
        else:
            st.warning("⏰ Still to do today: " + ", ".join(today.missing()))
        st.caption("🔒 All data stays on this computer. No internet needed.")
    return ctx


def page_start():
    """Call at the top of every page: sidebar, and the alert log kept up to date."""
    conn = get_conn()
    ctx = sidebar(conn)
    sync_alert_log(conn, load_data(conn))
    return ctx


def footer():
    st.divider()
    st.caption(FOOTER)
