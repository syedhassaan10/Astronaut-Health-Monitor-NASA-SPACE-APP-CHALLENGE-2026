"""Shared page state: the logbook connection, the mission and its crew, the chosen crew member and
location, the header, loading data, the daily backup, and keeping the alert log up to date."""

import os
from dataclasses import dataclass

import streamlit as st

from config.health_rules import HEALTH_RULES
from data.locations import LOCATIONS, environment_for_g, location_by_id
from db import backup, mission, repo
from db.database import open_db
from downlink import stores
from engine.alert_log import new_log_entries
from engine.change_detection import assess_crew
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
    day: int            # mission day
    mission: object     # Mission
    team: list          # every CrewMember on this mission


@dataclass
class Data:
    records: list
    checkins: list
    vitals: list


def get_conn():
    """One logbook connection per browser session."""
    if "conn" not in st.session_state:
        conn = open_db()
        mission.ensure_table(conn)
        # For automated tests and kiosks: skip the first-start setup and open the demo mission.
        if os.environ.get("ORBITFIT_START_WITH_DEMO") == "1" and mission.get_mission(conn) is None:
            mission.start_demo_mission(conn)
        st.session_state.conn = conn
    return st.session_state.conn


def crew_list(conn):
    return mission.list_crew(conn)


def crew_names(team):
    return {c.id: c.name for c in team}


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


def sync_alert_log(conn, data, team, day):
    """Write any alert that is new (or newly escalated) into the alert log."""
    known = {a.key for a in repo.list_alerts(conn)}
    entries = []
    for member in team:
        entries.extend(new_log_entries(assess(data, member.id).alerts, known, day))
    if entries:
        repo.add_alert_entries(conn, entries)


def context():
    """The mission, and the crew member and location chosen in the header."""
    conn = get_conn()
    m = mission.get_mission(conn)
    team = crew_list(conn)
    by_id = {c.id: c for c in team}
    crew = by_id.get(st.session_state.get("crew_id"), team[0] if team else None)
    location = location_by_id(st.session_state.get("location_id", m.location_id if m else "leo"))
    if location.id == "custom":
        g = st.session_state.get("custom_g", m.custom_g if m else 0.5)
        environment = environment_for_g(g)
    else:
        g = location.g
        environment = location.environment
    return Context(crew=crew, location=location, g=g, environment=environment, day=mission.mission_day(m),
                   mission=m, team=team)


def toggle_comms(conn):
    window_open = stores.get_setting(conn, "window_open", False)
    stores.set_setting(conn, "window_open", not window_open)


# The chosen crew member, location and custom gravity are kept in these settings. Streamlit forgets a
# widget's value when you switch pages, so each page copies the setting into its picker ("_" key)
# and the picker copies any change back.
SETTING_NAMES = ["crew_id", "location_id", "custom_g"]


def _defaults(m, team):
    return {"crew_id": team[0].id, "location_id": m.location_id, "custom_g": m.custom_g}


def _remember(name):
    st.session_state[name] = st.session_state["_" + name]


def _picker_value(name, defaults, team):
    """Make sure the setting exists (and still fits this mission), then load it into the picker."""
    if name not in st.session_state:
        st.session_state[name] = defaults[name]
    if name == "crew_id" and st.session_state[name] not in {c.id for c in team}:
        st.session_state[name] = defaults[name]
    st.session_state["_" + name] = st.session_state[name]


def header(conn, m, team):
    """Header controls: crew, location, comms status, offline badge, today's to-do."""
    defaults = _defaults(m, team)
    for name in SETTING_NAMES:
        _picker_value(name, defaults, team)
    names = crew_names(team)
    crew_col, location_col, comms_col, offline_col = st.columns([2.2, 2.2, 1.5, 1.3], vertical_alignment="bottom")
    crew_col.selectbox("Crew", list(names), key="_crew_id", on_change=_remember, args=("crew_id",),
                       format_func=lambda i: names[i])
    location_col.selectbox("Location", [loc.id for loc in LOCATIONS], key="_location_id", on_change=_remember,
                           args=("location_id",), format_func=lambda i: location_by_id(i).label,
                           help="Sets gravity. Gravity changes the exercise plan and the emergency steps.")
    window_open = stores.get_setting(conn, "window_open", False)
    words = "● Link open" if window_open else "● Blackout"
    colour = theme.NOMINAL if window_open else theme.ACT
    st.html(f"<style>.st-key-comms_toggle button {{ color: {colour} !important; "
            f"border-color: {theme.tint(colour, 0.5)} !important; background: {theme.tint(colour, 0.12)} !important; "
            f"border-radius: 999px !important; }} .st-key-comms_toggle button p {{ color: {colour} !important; }}</style>")
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
    kind = "demo" if m.mode == mission.DEMO else theme.esc(m.name)
    st.markdown(f'<div class="of-row" style="margin:0.2rem 0 0.4rem 0">{todo}'
                f'{theme.label(f"{kind} · mission day {ctx.day} · {ctx.g:.3g} g · {ctx.environment}")}</div>',
                unsafe_allow_html=True)
    return ctx, data


def page_start():
    """Call at the top of every page: theme, first-start setup if needed, header, alert log, backup."""
    theme.inject()
    conn = get_conn()
    m = mission.get_mission(conn)
    team = crew_list(conn)
    if m is None or not team:
        from ui import setup
        setup.render(conn)
        footer()
        st.stop()
    ctx, data = header(conn, m, team)
    if m.mode == mission.DEMO:
        demo_banner()
    sync_alert_log(conn, data, team, ctx.day)
    if m.backup:
        backup.backup_if_due(conn)
    return ctx


def demo_banner():
    """Shown on every page in the demo mission, so nobody takes the sample crew for real astronauts."""
    theme.html_block(
        f'<div class="of-do" style="border:2px solid {theme.tint(theme.WARN, 0.5)};background:{theme.tint(theme.WARN, 0.08)};'
        f'margin:0 0 0.6rem 0">{theme.pill("Demo mission · sample data", theme.WARN)}&nbsp; '
        "Made-up crew, not real astronauts. Their trends follow published NASA figures, with a 6-month mission "
        "squeezed into 30 days. Start a real mission on the Mission page.</div>")


def demo_evidence_section():
    """How the demo data is built: each NASA figure, its source and what it shapes."""
    from data import nasa_evidence
    from guidance.sources import source_by_id
    st.subheader("How the demo data is built")
    st.write("The demo crew is synthetic: no real astronaut data is used. Its trends follow figures published by "
             "NASA, with a long-duration mission (about 6 months) squeezed into 30 demo days so the changes are "
             "visible in the demo.")
    for figure in nasa_evidence.ALL:
        src = source_by_id(figure.source_id)
        with st.container(border=True):
            theme.html_block(f'<div class="of-big"><b>{theme.esc(figure.statement)}</b></div>'
                             f'<div class="of-muted" style="margin-top:0.3rem">Used for: {theme.esc(figure.used_for)}</div>'
                             f'<div style="margin-top:0.3rem;font-size:0.9rem"><a href="{src.url}" target="_blank">'
                             f'{theme.esc(src.title)}</a>, p. {figure.page}</div>')
    st.caption("Modelling assumptions (not NASA figures): lifting time grows as strength falls (time ∝ 1 / strength), "
               "and a weaker squat is shallower (60° per 100% strength lost). Check-in and vital-sign patterns are "
               "illustrative.")


def footer():
    st.markdown(f'<div class="of-footer">{theme.esc(FOOTER)}</div>', unsafe_allow_html=True)
