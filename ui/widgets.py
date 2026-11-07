"""Building blocks shared by the pages, in the original OrbitFit style:
outlined status badges, three-part alert cards, stat tiles and dark trend charts."""

import plotly.graph_objects as go
import streamlit as st

from engine.gravity_engine import EXERCISES, build_plan
from engine.health_types import ACT, NOMINAL, WATCH
from guidance.sources import source_by_id
from ui import theme

# Plain words next to each status, for people who are not doctors.
STATUS = {
    NOMINAL: ("●", theme.NOMINAL, "All good"),
    WATCH: ("▲", theme.WATCH, "Keep an eye on it"),
    ACT: ("■", theme.ACT, "Needs action"),
}
FORM_COLOUR = theme.LEVEL_COLOUR
ACCENT = theme.ACCENT


def status_html(status, size=None):
    """Outlined badge plus the plain-language words."""
    large = size is not None and size not in ("0.85rem", "0.8rem")
    words = STATUS[status][2]
    return f'{theme.badge(status, large=large)} <span class="of-muted">{words}</span>'


def show_status(status, size="1.4rem"):
    st.markdown(status_html(status, size), unsafe_allow_html=True)


def coloured(text, colour, size="1rem", weight=600):
    return f'<span style="color:{colour};font-size:{size};font-weight:{weight}">{theme.esc(text)}</span>'


def series_chart(points, baseline=None, unit="", title="", height=220, colour=None):
    """A trend chart like the original: dark grid, coloured line, dashed baseline."""
    colour = colour or theme.ACCENT
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[p.day for p in points], y=[p.value for p in points], mode="lines",
                             line=dict(color=colour, width=2.5, shape="spline", smoothing=0.6), name=title or "value",
                             hovertemplate="Day %{x}: %{y:.1f} " + unit + "<extra></extra>"))
    if baseline is not None:
        fig.add_hline(y=baseline, line_dash="dash", line_color=theme.ACCENT, line_width=1.5,
                      annotation_text="baseline", annotation_position="bottom left",
                      annotation_font=dict(color=theme.ACCENT, size=11))
    grid = dict(gridcolor=theme.SPACE_600, griddash="dash", zeroline=False, linecolor=theme.INK_500,
                tickfont=dict(color=theme.INK_300, size=11))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30 if title else 8, b=8),
                      title=dict(text=title, font=dict(size=13, color=theme.INK_100)) if title else None,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=theme.INK_100, family=theme.SANS), showlegend=False,
                      xaxis=dict(title=dict(text="mission day", font=dict(size=11, color=theme.INK_500)), **grid),
                      yaxis=dict(title=dict(text=unit, font=dict(size=11, color=theme.INK_500)), **grid))
    return fig


def _subject(alert):
    if alert.exercise:
        return EXERCISES[alert.exercise].label
    if alert.rule in ("pain", "recovery", "stress"):
        return "Daily check-in"
    return "Vital signs"


def alert_card(alert, key, compact=False):
    """Short first: what changed and the one thing to do now. Chart, reasons and more on demand."""
    colour = theme.ACT if alert.level == ACT else theme.WATCH
    with st.container(border=True):
        theme.html_block(
            f'<div class="of-row">{theme.badge(alert.level)}'
            f'<span class="of-title">{theme.esc(alert.title)}</span>'
            f'<span class="of-right of-label">{theme.esc(_subject(alert))} · day {alert.day}</span></div>'
            f'<div class="of-big" style="margin-top:0.4rem">{theme.esc(alert.what.summary)}</div>')
        if alert.actions:
            theme.html_block(f'<div class="of-do"><span style="color:{colour}">Do now:</span> '
                             f'{theme.esc(alert.actions[0])}</div>')
        with st.expander("Why, chart and more"):
            if len(alert.what.series) > 1:
                st.plotly_chart(series_chart(alert.what.series, alert.what.baseline, alert.what.unit, height=220,
                                             colour=colour), key=f"chart-{key}", config={"displayModeBar": False})
            for note in alert.context:
                st.info(note)
            src = source_by_id(alert.why_source_id)
            link = f' <a href="{src.url}" target="_blank">Source</a>' if src else ""
            theme.html_block(f'{theme.label("Why it matters in space")}<div>{theme.esc(alert.why_text)}{link}</div>')
            if len(alert.actions) > 1:
                items = "".join(f"<li>{theme.esc(a)}</li>" for a in alert.actions[1:])
                theme.html_block(f'<div style="margin-top:0.6rem">{theme.label("Also")}<ul>{items}</ul></div>')


def checkin_chips(checkin):
    """CHECK-IN D30  Sleep 3  Fatigue 10  Pain 0  Stress 6"""
    if checkin is None:
        return theme.label("No check-in yet")
    from engine.checkin_rules import LOCATION_LABEL
    pain = f"Pain {checkin.pain}"
    if checkin.pain_location:
        pain += f" ({LOCATION_LABEL[checkin.pain_location]})"
    chips = "".join(theme.chip(t) for t in (f"Sleep {checkin.sleep}", f"Fatigue {checkin.fatigue}", pain,
                                             f"Stress {checkin.stress}"))
    return f'{theme.label(f"Check-in D{checkin.day}")} &nbsp;{chips}'


def vitals_chips(v):
    if v is None:
        return ""
    chips = []
    if v.heart_rate is not None:
        chips.append(f"HR {v.heart_rate:g}")
    if v.systolic is not None and v.diastolic is not None:
        chips.append(f"BP {v.systolic:g}/{v.diastolic:g}")
    if v.temperature_c is not None:
        chips.append(f"{v.temperature_c:g} °C")
    if v.spo2_pct is not None:
        chips.append(f"SpO2 {v.spo2_pct:g}%")
    if v.glucose_mg_dl is not None:
        chips.append(f"Glucose {v.glucose_mg_dl:g}")
    return f'{theme.label(f"Vitals D{v.day}")} &nbsp;' + "".join(theme.chip(c) for c in chips)


def plan_card(member, g, exercise_id):
    """Today's exercise plan for this gravity. The device load is simulated."""
    plan = build_plan(member.mass_kg, g, exercise_id)
    ex = EXERCISES[exercise_id]
    v = plan.volume
    with st.container(border=True):
        theme.html_block(f'<div class="of-row"><span class="of-title">Today’s plan: {ex.label}</span>'
                         f'<span class="of-right of-label">Simulated ARED target load · at {g:.3g} g</span></div>')
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Weight", f"{plan.target_load_kg:.0f} kg",
                  help=f"Simulated device load: it replaces the weight gravity no longer gives you, plus the normal "
                       f"training load ({ex.base_training_load_kg} kg). Formula: mass × (1 − g) × {ex.exercise_factor} "
                       f"+ base, capped at about 272 kg.{' Cap reached.' if plan.capped else ''}")
        c2.metric("Down / up", f"{plan.tempo.eccentric_s:.0f} s / {plan.tempo.concentric_s:.0f} s",
                  help=f"Lower for {plan.tempo.eccentric_s:.1f} s, stand up in {plan.tempo.concentric_s:.1f} s, pause "
                       f"{plan.tempo.hold_s:.1f} s at the bottom. Less gravity means slower reps.")
        c3.metric("Sets × reps", f"{v.sets} × {v.reps}",
                  help=f"{v.sessions_per_week} sessions a week, about {v.minutes_per_day} min of exercise a day.")
        c4.metric("Body load", f"{plan.effective_bodyweight_n:.0f} N",
                  help="Weight your skeleton carries: mass × g × 9.81. Zero in microgravity, which is why muscles "
                       "and bones weaken.")
