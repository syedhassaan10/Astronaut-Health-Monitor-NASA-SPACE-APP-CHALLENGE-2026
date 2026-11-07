"""Mission: the mission's details, its crew, and the data (where it lives, backup, export, import, start over)."""

from dataclasses import replace

import streamlit as st

from data.locations import LOCATIONS, location_by_id
from db import backup, mission, repo
from db.database import default_db_path
from db.logbook_io import export_logbook_csv, import_logbook_csv
from ui import state, theme

ctx = state.page_start()
conn = state.get_conn()
m = ctx.mission
is_demo = m.mode == mission.DEMO

theme.page_header("Mission", "Your mission, your crew and your data.")

# ---- mission ---------------------------------------------------------------------------------

with theme.card():
    kind = "Demo mission with sample data" if is_demo else "Real mission"
    theme.html_block(f'<div class="of-row"><span class="of-title">{theme.esc(m.name)}</span>'
                     f'<span class="of-right of-label">{kind}</span></div>'
                     f'<div style="margin-top:0.5rem">{theme.chip(f"Mission day {ctx.day}")}'
                     f'{theme.chip("Started " + m.start_date.isoformat())}'
                     f'{theme.chip(location_by_id(m.location_id).label)}'
                     f'{theme.chip(f"Earth delay {m.earth_delay_min} min")}</div>')
    if is_demo:
        st.caption("The demo mission always shows day 30, so the trends have history to show.")
    else:
        with st.expander("Change mission details"):
            with st.form("mission_details", border=False):
                name = st.text_input("Mission name", value=m.name)
                start = st.date_input("Start date (day 1)", value=m.start_date)
                ids = [loc.id for loc in LOCATIONS]
                location_id = st.selectbox("Usual location", ids, index=ids.index(m.location_id),
                                           format_func=lambda i: location_by_id(i).label)
                delay = st.slider("Usual delay to Earth (minutes)", 1, 40, value=m.earth_delay_min)
                if st.form_submit_button("Save", type="primary"):
                    mission.update_mission(conn, replace(m, name=name.strip() or m.name, start_date=start,
                                                         location_id=location_id, earth_delay_min=delay))
                    st.rerun()

# ---- crew ------------------------------------------------------------------------------------

with theme.card():
    theme.html_block(f'<div class="of-title">Crew ({len(ctx.team)})</div>')
    rows = ""
    for c in ctx.team:
        cmo = ""
        if c.id == m.cmo_id and "medical officer" not in c.role.lower():
            cmo = " · Crew Medical Officer"
        rows += f"<tr><td>{theme.esc(c.name)}</td><td>{theme.esc(c.role)}{cmo}</td><td>{c.mass_kg:g} kg</td></tr>"
    theme.html_block(f'<table class="of-table"><tr><th>Name</th><th>Role</th><th>Body weight</th></tr>{rows}</table>')
    if is_demo:
        st.caption("The demo crew is fixed. Start a new mission below to use your own crew.")
    else:
        with st.expander("Add a crew member"):
            with st.form("add_crew", border=False, clear_on_submit=True):
                a1, a2, a3 = st.columns(3)
                new_name = a1.text_input("Name")
                new_role = a2.text_input("Role", value="Crew member")
                new_mass = a3.number_input("Body weight (kg)", mission.MIN_MASS_KG, mission.MAX_MASS_KG, value=70.0)
                if st.form_submit_button("Add", type="primary"):
                    _, error = mission.add_crew_member(conn, new_name, new_role, new_mass)
                    if error:
                        st.error(error)
                    else:
                        st.rerun()
        with st.expander("Edit a crew member (their history is kept)"):
            names = state.crew_names(ctx.team)
            who = st.selectbox("Who", list(names), format_func=lambda i: names[i])
            member = [c for c in ctx.team if c.id == who][0]
            with st.form(f"edit_{who}", border=False):
                e1, e2, e3 = st.columns(3)
                edit_name = e1.text_input("Name", value=member.name)
                edit_role = e2.text_input("Role", value=member.role)
                edit_mass = e3.number_input("Body weight (kg)", mission.MIN_MASS_KG, mission.MAX_MASS_KG,
                                            value=float(member.mass_kg))
                is_cmo = st.checkbox("Crew Medical Officer", value=member.id == m.cmo_id)
                if st.form_submit_button("Save", type="primary"):
                    error = mission.update_crew_member(conn, who, edit_name, edit_role, edit_mass)
                    if error:
                        st.error(error)
                    else:
                        cmo_id = who if is_cmo else (None if m.cmo_id == who else m.cmo_id)
                        mission.update_mission(conn, replace(m, cmo_id=cmo_id))
                        st.rerun()

# ---- data and privacy ------------------------------------------------------------------------

with theme.card():
    theme.html_block('<div class="of-title">Your data</div>'
                     '<div class="of-big" style="margin-top:0.3rem">Everything stays on this computer, in one file:</div>'
                     f'<div class="of-chip" style="margin:0.4rem 0">{theme.esc(default_db_path())}</div>')
    counts = {t: repo.count(conn, t) for t in ("sessions", "reps", "checkins", "vitals")}
    st.caption(" · ".join(f"{n} {t}" for t, n in counts.items()))

    b1, b2 = st.columns(2)
    b1.download_button("⬇ Export logbook (CSV, opens in Excel)", data=export_logbook_csv(conn).encode("utf-8"),
                       file_name=f"orbitfit-logbook-day{ctx.day}.csv", mime="text/csv", width="stretch")
    if b2.button("Back up now", width="stretch"):
        path = backup.write_backup(conn)
        st.success(f"Saved {path.name}")

    backup_on = st.toggle("Save a backup copy every day (last 14 days kept)", value=m.backup)
    if backup_on != m.backup:
        mission.update_mission(conn, replace(m, backup=backup_on))
        st.rerun()
    saved = backup.list_backups()
    if saved:
        st.caption("Backups: " + ", ".join(p.name for p in saved[:5]) + (" …" if len(saved) > 5 else "")
                   + f" in {backup.DEFAULT_FOLDER}")

    upload = st.file_uploader("Import a logbook CSV (adds new rows; never overwrites what is here)", type=["csv"])
    if upload is not None and st.button("Import this file"):
        report = import_logbook_csv(conn, upload.getvalue().decode("utf-8-sig", errors="replace"))
        added = report.added
        st.success(f"Added {added['sessions']} sessions, {added['reps']} reps, {added['checkins']} check-ins, "
                   f"{added['vitals']} vitals. {report.already_present} were already here and were left untouched.")
        if report.errors:
            st.warning(f"{len(report.errors)} rows were skipped:")
            for err in report.errors[:50]:
                where = f"line {err.line}: " if err.line else ""
                st.caption(f"{where}{err.message}")

# ---- start over ------------------------------------------------------------------------------

with st.expander("Start over: new mission or demo"):
    st.warning("Both options delete the current logbook (every session, check-in, vital sign, note and alert). "
               "Export it first if you want to keep it.")
    sure = st.checkbox("Yes, delete the current logbook")
    s1, s2 = st.columns(2)
    if s1.button("Set up a new mission", disabled=not sure, width="stretch"):
        mission.clear_mission(conn)
        for key in ("crew_id", "location_id", "custom_g", "setup"):
            st.session_state.pop(key, None)
        st.rerun()
    if s2.button("Load the demo mission", disabled=not sure, width="stretch"):
        mission.start_demo_mission(conn)
        for key in ("crew_id", "location_id", "custom_g"):
            st.session_state.pop(key, None)
        st.rerun()

state.footer()
