"""Small building blocks shared by the pages: status badges, alert cards, charts, the plan card."""

import html

import plotly.graph_objects as go
import streamlit as st

from engine.gravity_engine import EXERCISES, build_plan
from engine.health_types import ACT, NOMINAL, WATCH
from guidance.sources import source_by_id

# Status is always shown as shape + word + colour, never colour alone.
STATUS = {
    NOMINAL: ("●", "#34d399", "All good"),
    WATCH: ("▲", "#fbbf24", "Keep an eye on it"),
    ACT: ("■", "#f87171", "Needs action"),
}
FORM_COLOUR = {"green": "#34d399", "amber": "#fbbf24", "red": "#f87171", "neutral": "#38bdf8"}
ACCENT = "#38bdf8"


def status_html(status, size="1rem"):
    shape, colour, words = STATUS[status]
    return (f'<span style="color:{colour};font-weight:700;font-size:{size};white-space:nowrap">'
            f'{shape} {status}</span> <span style="color:#aab8d0;font-size:{size}">· {words}</span>')


def show_status(status, size="1.4rem"):
    st.markdown(status_html(status, size), unsafe_allow_html=True)


def coloured(text, colour, size="1rem", weight=600):
    return f'<span style="color:{colour};font-size:{size};font-weight:{weight}">{html.escape(text)}</span>'


def series_chart(points, baseline=None, unit="", title="", height=220):
    """A small line chart of a trend, with the person's baseline as a dashed line."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[p.day for p in points], y=[p.value for p in points], mode="lines+markers",
                             line=dict(color=ACCENT, width=2), marker=dict(size=5), name=title or "value",
                             hovertemplate="Day %{x}: %{y:.1f} " + unit + "<extra></extra>"))
    if baseline is not None:
        fig.add_hline(y=baseline, line_dash="dash", line_color="#7a8aa8",
                      annotation_text="your baseline", annotation_font_color="#aab8d0")
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30 if title else 10, b=10), title=title,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#e6edf7"),
                      xaxis=dict(title="Mission day", gridcolor="#1a2740"),
                      yaxis=dict(title=unit, gridcolor="#1a2740"), showlegend=False)
    return fig


def alert_card(alert, key):
    """Short first (what changed + what to do now); the details open on demand."""
    with st.container(border=True):
        st.markdown(f"{status_html(alert.level)} &nbsp; **{html.escape(alert.title)}**", unsafe_allow_html=True)
        st.write(alert.what.summary)
        if alert.actions:
            st.markdown(f"**Do now:** {alert.actions[0]}")
        with st.expander("Why it matters and what else to do"):
            if len(alert.what.series) > 1:
                st.plotly_chart(series_chart(alert.what.series, alert.what.baseline, alert.what.unit,
                                             alert.what.metric), key=f"chart-{key}")
            st.markdown("**Why it matters in space**")
            st.write(alert.why_text)
            src = source_by_id(alert.why_source_id)
            if src:
                st.caption(f"Source: [{src.title}]({src.url}) ({src.organization})")
            st.markdown("**Suggested actions**")
            for action in alert.actions:
                st.markdown(f"- {action}")
            for note in alert.context:
                st.info(note)


def plan_card(member, g, exercise_id):
    """The gravity-adjusted exercise plan. The device load is simulated."""
    plan = build_plan(member.mass_kg, g, exercise_id)
    ex = EXERCISES[exercise_id]
    v = plan.volume
    with st.container(border=True):
        st.markdown(f"**Your plan for today: {ex.label}** · at {g:.3g} g")
        # Two by two, so the numbers fit on a tablet in portrait.
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        c1.metric("Suggested weight (simulated)", f"{plan.target_load_kg:.1f} kg",
                  help=f"Replaces the load gravity no longer gives you, plus the normal training load "
                       f"({ex.base_training_load_kg} kg). Formula: mass × (1 − g) × {ex.exercise_factor} + base. "
                       f"Capped at about 272 kg (ARED maximum).{' Cap reached.' if plan.capped else ''}")
        c2.metric("Body weight you carry", f"{plan.effective_bodyweight_n:.0f} N",
                  help="mass × g × 9.81. It falls to zero in microgravity, which is why muscles and bones weaken.")
        c3.metric("Tempo down / up / pause", f"{plan.tempo.eccentric_s:.1f} / {plan.tempo.concentric_s:.1f} / "
                  f"{plan.tempo.hold_s:.1f} s",
                  help="Lower gravity means slower reps to keep the muscle working. 1 g: 2/1/0 s, 0 g: 4/2/1 s.")
        c4.metric("This week", f"{v.sessions_per_week} × {v.sets}×{v.reps}",
                  help=f"Sessions per week × sets × reps, about {v.minutes_per_day} min of exercise a day. "
                       "Less gravity means more exercise.")
        st.caption("The exercise device load is simulated by a simplified model; OrbitFit does not control hardware.")
