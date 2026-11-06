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
    """The three-part alert from the original app: what changed / why it matters / suggested action."""
    colour = theme.ACT if alert.level == ACT else theme.WATCH
    with st.container(border=True):
        theme.html_block(
            f'<div class="of-row">{theme.badge(alert.level)}'
            f'<span class="of-title">{theme.esc(alert.title)}</span>'
            f'<span class="of-right of-label">{theme.esc(_subject(alert))} · day {alert.day}</span></div>')
        if compact:
            left, right = st.container(), st.container()
        else:
            left, right = st.columns([1.1, 1], gap="large")
        with left:
            theme.html_block(f'{theme.label("1 · What changed")}<div style="margin-top:0.2rem">'
                             f'{theme.esc(alert.what.summary)}</div>')
            if len(alert.what.series) > 1:
                st.plotly_chart(series_chart(alert.what.series, alert.what.baseline, alert.what.unit, height=200,
                                             colour=colour), key=f"chart-{key}", config={"displayModeBar": False})
        with right:
            if alert.context:
                items = "".join(f"<li>{theme.esc(c)}</li>" for c in alert.context)
                theme.html_block(f'<div class="of-box">{theme.label("Context from your check-ins")}'
                                 f'<ul style="margin:0.3rem 0 0 0;color:{theme.INK_300}">{items}</ul></div>')
            src = source_by_id(alert.why_source_id)
            link = f' <a href="{src.url}" target="_blank">Source</a>' if src else ""
            theme.html_block(f'<div style="margin-top:0.6rem">{theme.label("2 · Why it matters in spaceflight")}'
                             f'<div style="color:{theme.INK_300};margin-top:0.2rem">{theme.esc(alert.why_text)}'
                             f'</div><div style="font-size:0.8rem">{link}</div></div>')
            actions = "".join(f"<li>{theme.esc(a)}</li>" for a in alert.actions)
            theme.html_block(f'<div style="margin-top:0.6rem">{theme.label("3 · Suggested action")}'
                             f'<ul style="margin:0.2rem 0 0 0">{actions}</ul></div>')


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
    """The gravity-adjusted exercise plan. The device load is simulated."""
    plan = build_plan(member.mass_kg, g, exercise_id)
    ex = EXERCISES[exercise_id]
    v = plan.volume
    with st.container(border=True):
        theme.html_block(f'<div class="of-row"><span class="of-title">Simulated ARED target load</span>'
                         f'<span class="of-right of-label">simplified prototype model · simulated device</span></div>'
                         f'<div class="of-muted" style="margin:0.2rem 0 0.4rem 0">{ex.label} at {g:.3g} g for a '
                         f'{member.mass_kg:g} kg crew member. We simulate the device; we do not control hardware.</div>')
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Suggested weight", f"{plan.target_load_kg:.1f} kg",
                  help=f"Replaces the load gravity no longer gives you, plus the normal training load "
                       f"({ex.base_training_load_kg} kg). Formula: mass × (1 − g) × {ex.exercise_factor} + base. "
                       f"Capped at about 272 kg (ARED maximum).{' Cap reached.' if plan.capped else ''}")
        c2.metric("Body weight", f"{plan.effective_bodyweight_n:.0f} N",
                  help="Weight your skeleton actually carries: mass × g × 9.81. It falls to zero in microgravity, "
                       "which is why muscles and bones weaken.")
        c3.metric("Tempo down / up / hold", f"{plan.tempo.eccentric_s:.1f}/{plan.tempo.concentric_s:.1f}/"
                  f"{plan.tempo.hold_s:.1f} s",
                  help="Slower reps at lower gravity keep the muscle working. 1 g: 2/1/0 s, 0 g: 4/2/1 s.")
        c4.metric("Weekly volume", f"{v.sessions_per_week}× {v.sets}×{v.reps}",
                  help=f"Sessions per week × sets × reps, about {v.minutes_per_day} min of exercise a day. "
                       "Less gravity means more exercise.")
