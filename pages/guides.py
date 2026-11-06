"""Health guides: a clickable body figure (status per body area) and how-to guides for every measurement."""

import plotly.graph_objects as go
import streamlit as st

from engine.health_types import ACT, NOMINAL, WATCH
from guidance.body_map import REGIONS, alerts_for_region, latest_pain_location, region_by_id, region_status
from guidance.measurements import guide_by_id, measurement_guides
from guidance.sources import source_by_id
from ui import state, theme, widgets

state.page_start()

SYMBOL = {NOMINAL: "circle", WATCH: "triangle-up", ACT: "square"}
OUTLINE = theme.MUTED
# Where each label sits in the right-hand label column (spread out so none overlap).
LABEL_X = 9.6
LABEL_Y = {"brain": 19.0, "shoulders": 17.2, "lungs": 15.8, "heart": 14.4, "immune": 13.0, "back": 11.6,
           "energy": 10.2, "hips": 8.4, "knees": 5.4, "feet": 1.4}

conn = state.get_conn()
ctx = state.context()
data = state.load_data(conn)
assessment = state.assess(data, ctx.crew.id)
pain_location = latest_pain_location(data.checkins, ctx.crew.id)


def body_figure(statuses):
    """A simple body outline with one clickable marker per body area."""
    fig = go.Figure()
    line = dict(color=OUTLINE, width=3)
    fig.add_shape(type="circle", x0=3.9, y0=17.5, x1=6.1, y1=19.8, line=line)                    # head
    fig.add_shape(type="line", x0=5, y0=17.5, x1=5, y1=16.9, line=line)                        # neck
    fig.add_shape(type="path", path="M 3.2 16.8 L 6.8 16.8 L 6.4 9 L 3.6 9 Z", line=line)        # torso
    for x0, y0, x1, y1 in [(3.2, 16.6, 2.0, 12.6), (2.0, 12.6, 1.6, 9.2),                     # left arm
                           (6.8, 16.6, 8.0, 12.6), (8.0, 12.6, 8.4, 9.2),                     # right arm
                           (4.2, 9, 4.1, 5.2), (4.1, 5.2, 4.1, 1.2),                          # left leg
                           (5.8, 9, 5.9, 5.2), (5.9, 5.2, 5.9, 1.2)]:                         # right leg
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1, line=line)

    # Labels sit in a column on the right, joined to their marker by a thin line, so they never overlap.
    for r in REGIONS:
        fig.add_shape(type="line", x0=r.x, y0=r.y, x1=LABEL_X - 0.2, y1=LABEL_Y[r.id],
                      line=dict(color="#26375a", width=1))

    for status in (NOMINAL, WATCH, ACT):
        regions = [r for r in REGIONS if statuses[r.id] == status]
        if not regions:
            continue
        _, colour, words = widgets.STATUS[status]
        marker = dict(size=26, color=colour, symbol=SYMBOL[status], line=dict(color="#060b16", width=2))
        fig.add_trace(go.Scatter(
            x=[r.x for r in regions], y=[r.y for r in regions], mode="markers", marker=marker,
            customdata=[r.id for r in regions], text=[r.label for r in regions], name=f"{status} · {words}",
            hovertemplate="%{text}<br>" + status + "<extra></extra>",
        ))
        # The label is clickable too (a small marker in front of the text).
        fig.add_trace(go.Scatter(
            x=[LABEL_X for _ in regions], y=[LABEL_Y[r.id] for r in regions], mode="markers+text",
            marker=dict(size=12, color=colour, symbol=SYMBOL[status]),
            text=[r.label for r in regions], textposition="middle right", textfont=dict(color=theme.TEXT, size=13),
            customdata=[r.id for r in regions], showlegend=False, hovertemplate="%{text}<extra></extra>",
        ))
    fig.update_layout(height=640, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", clickmode="event+select",
                      xaxis=dict(visible=False, range=[0, 20], fixedrange=True),
                      yaxis=dict(visible=False, range=[0, 20.5], fixedrange=True, scaleanchor="x"),
                      legend=dict(orientation="h", y=-0.02, font=dict(color=theme.TEXT)))
    return fig


def selected_region(event):
    """The region id from a plotly click, if any."""
    try:
        points = event.selection.points
    except AttributeError:
        return None
    if not points:
        return None
    custom = points[0].get("customdata")
    if isinstance(custom, list):
        custom = custom[0] if custom else None
    return custom


def show_guide(guide, environment):
    st.markdown(f"**You need:** {guide.equipment}")
    st.markdown("**How to measure**")
    for i, step in enumerate(guide.how_to, start=1):
        st.markdown(f"{i}. {step}")
    note = guide.environment_notes.get(environment)
    if note:
        st.info(note)
    st.markdown(f"**Why it matters in space:** {guide.why_space}")
    st.markdown(f"**Normal:** {guide.normal}")
    if guide.if_high:
        st.markdown(f"**If it is high:** {guide.if_high}")
    if guide.if_low:
        st.markdown(f"**If it is low:** {guide.if_low}")
    if guide.call_cmo_when:
        st.warning(f"Tell the Crew Medical Officer when: {guide.call_cmo_when}")
    src = source_by_id(guide.source_id)
    if src:
        st.caption(f"Source: [{src.title}]({src.url})")


theme.page_header("Health guides", "Your body, what spaceflight does to it, and how to measure it.")
st.write(f"Tap a body area to see what it does, what spaceflight does to it, {ctx.crew.name}'s current status "
         "there, and how to measure it. You do not need to be a doctor: every step is written out.")

statuses = {r.id: region_status(r, assessment.alerts, pain_location) for r in REGIONS}
if "region" not in st.session_state:
    st.session_state.region = "heart"

fig_col, info_col = st.columns([1, 1])
with fig_col:
    event = st.plotly_chart(body_figure(statuses), on_select="rerun", selection_mode="points",
                            key="body_map", config={"displayModeBar": False})
    clicked = selected_region(event)
    if clicked and clicked != st.session_state.get("last_click"):
        st.session_state.last_click = clicked
        st.session_state.region = clicked
    st.selectbox("Or choose a body area", [r.id for r in REGIONS], key="region",
                 format_func=lambda i: region_by_id(i).label)

with info_col:
    region = region_by_id(st.session_state.region)
    st.subheader(region.label)
    widgets.show_status(statuses[region.id])
    st.markdown(f"**What it does:** {region.function}")
    st.markdown(f"**In space:** {region.in_space}")
    region_alerts = alerts_for_region(region, assessment.alerts, pain_location)
    for i, alert in enumerate(region_alerts):
        widgets.alert_card(alert, key=f"region-{i}", compact=True)
    if not region_alerts:
        st.success("No alerts for this area right now.")
    for guide_id in region.measures:
        guide = guide_by_id(guide_id)
        with st.expander(f"How to measure: {guide.title}", expanded=len(region.measures) == 1):
            show_guide(guide, ctx.environment)

st.divider()
st.subheader("All measurement guides")
guides = measurement_guides()
tabs = st.tabs([g.title for g in guides])
for tab, guide in zip(tabs, guides):
    with tab:
        show_guide(guide, ctx.environment)

state.footer()
