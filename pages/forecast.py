"""Forecast: what could happen over the coming weeks. Hudebia Shaikh's digital twin (fatigue, sleep and
motion sickness), a bone-loss projection and daily energy needs. Models and estimates, not measurements."""

import plotly.graph_objects as go
import streamlit as st

from data.nasa_evidence import BONE_LOSS_PER_MONTH
from digital_twin.bone_projection import NASA_RANGE_PCT_PER_MONTH, project_bone_loss
from digital_twin.monte_carlo import run_monte_carlo
from engine.energy import ACTIVITY_FACTORS, daily_energy
from guidance.sources import source_by_id
from ui import state, theme

ctx = state.page_start()
conn = state.get_conn()
crew = ctx.crew
data = state.load_data(conn)

theme.page_header("Forecast", "What could happen over the coming weeks. A model, not a measurement.")


def chart(title, ytitle, height=300):
    fig = go.Figure()
    grid = dict(gridcolor=theme.SPACE_600, griddash="dash", zeroline=False, linecolor=theme.INK_500,
                tickfont=dict(color=theme.INK_300, size=11))
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=8), showlegend=True,
                      title=dict(text=title, font=dict(size=14, color=theme.INK_100)),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=theme.INK_100, family=theme.SANS),
                      legend=dict(orientation="h", y=-0.25),
                      xaxis=dict(title=dict(text="mission day", font=dict(size=11, color=theme.INK_500)), **grid),
                      yaxis=dict(title=dict(text=ytitle, font=dict(size=11, color=theme.INK_500)), **grid))
    return fig


# ---- 1. fatigue, sleep and motion sickness (digital twin) -------------------------------------

recent_hr = [v.heart_rate for v in data.vitals if v.crew_id == crew.id and v.heart_rate is not None][-7:]
recent_sleep = [c.sleep for c in data.checkins if c.crew_id == crew.id][-7:]
baseline_hr = sum(recent_hr) / len(recent_hr) if recent_hr else 75.0
sleep_quality = sum(recent_sleep) / len(recent_sleep) / 10 if recent_sleep else 0.8

with theme.card():
    theme.html_block('<div class="of-row"><span class="of-title">Fatigue and motion sickness</span>'
                     '<span class="of-right of-label">digital twin by Hudebia Shaikh</span></div>'
                     '<div class="of-big" style="margin-top:0.3rem">Simulates many possible missions for '
                     f'{theme.esc(crew.name)} and shows the range of fatigue and motion-sickness risk.</div>')
    seeded = "your last 7 days" if recent_hr or recent_sleep else "default values (no readings yet)"
    st.caption(f"Starts from {seeded}: resting heart rate {baseline_hr:.0f} bpm, sleep quality "
               f"{sleep_quality * 10:.1f} / 10. Model: Borbély two-process sleep model coupled with Oman's "
               "vestibular-mismatch model, run as a Monte Carlo simulation.")
    c1, c2 = st.columns(2)
    runs = c1.slider("Simulated missions", 5, 50, 20, help="More runs give a smoother range but take longer.")
    days = c2.slider("Days ahead", 7, 60, 14)
    key = f"twin_{crew.id}"
    params = (runs, days, round(baseline_hr, 1), round(sleep_quality, 2))
    if st.button("Run forecast", type="primary", key="run_twin"):
        with st.spinner("Simulating..."):
            st.session_state[key] = (params, run_monte_carlo(n_runs=runs, mission_duration_hours=days * 24,
                                                             baseline_hr=baseline_hr,
                                                             baseline_sleep_quality=sleep_quality))
    saved = st.session_state.get(key)
    if saved is None:
        st.info("Press Run forecast. It takes a few seconds and runs on this computer.")
    else:
        used, res = saved
        if used != params:
            st.caption("The settings changed since this forecast. Press Run forecast to update it.")
        rs, env = res["risk_summary"], res["envelopes"]
        m = st.columns(4)
        m[0].metric("Time above fatigue risk", f"{rs['mean_prob_fatigue_risk'] * 100:.0f} %",
                    help="Share of the time the fatigue index is above 5 out of 10, averaged over all runs.")
        m[1].metric("Peak fatigue (worst 5 %)", f"{rs['p95_peak_fatigue']:.1f} / 10")
        m[2].metric("Time with poor sleep", f"{rs['mean_prob_sleep_risk'] * 100:.0f} %")
        m[3].metric("Motion-sickness episodes", f"{rs['mean_ms_events']:.1f}")
        t = [h / 24 for h in env["time_hours"]]
        f1 = chart("Fatigue index: average and range", "fatigue (0-10)")
        f1.add_trace(go.Scatter(x=t + t[::-1], y=env["fatigue_max"] + env["fatigue_min"][::-1], fill="toself",
                                fillcolor=theme.tint(theme.CYAN, 0.15), line=dict(width=0), name="range of runs",
                                hoverinfo="skip"))
        f1.add_trace(go.Scatter(x=t, y=env["fatigue_mean"], line=dict(color=theme.CYAN, width=2.5), name="average"))
        f1.add_hline(y=5, line_dash="dash", line_color=theme.BAD, annotation_text="risk level",
                     annotation_font=dict(color=theme.BAD, size=11))
        f2 = chart("Motion-sickness chance per half hour", "probability")
        f2.add_trace(go.Scatter(x=t, y=env["p_ms_coupled_mean"], line=dict(color=theme.BAD, width=2.5),
                                name="with sleep pressure"))
        f2.add_trace(go.Scatter(x=t, y=env["p_ms_independent_mean"], line=dict(color=theme.CYAN, width=2),
                                name="without"))
        g1, g2 = st.columns(2)
        g1.plotly_chart(f1, key="twin_fatigue", config={"displayModeBar": False})
        g2.plotly_chart(f2, key="twin_ms", config={"displayModeBar": False})
        with st.expander("What the model found"):
            for line in res["conclusions"]:
                st.write(line)
    st.caption("A research model with population parameters, not this person's physiology. Use it to plan rest "
               "and workload, not to judge how someone feels: the daily check-in does that.")

# ---- 2. bone loss projection -----------------------------------------------------------------

with theme.card():
    src = source_by_id("hrp-bone-2024")
    link = f' <a href="{src.url}" target="_blank">Source</a>' if src else ""
    theme.html_block('<div class="of-title">Bone loss projection</div>'
                     '<div class="of-big" style="margin-top:0.3rem">How much hip and spine bone could be lost by the '
                     f'end of the mission, with and without exercise.{link}</div>')
    b1, b2, b3 = st.columns(3)
    rate = b1.slider("Loss without exercise (% a month)", 0.0, 3.0, round(BONE_LOSS_PER_MONTH.value * 100, 1), 0.1,
                     help="NASA reports about 1 to 1.5 % a month at the hip and spine in weightlessness.")
    exercise = b2.slider("Exercise protects (%)", 0, 100, 50,
                         help="How much of the loss the exercise programme prevents. An assumption: set it with "
                              "the Crew Medical Officer.")
    mission_days = b3.slider("Mission length (days)", 30, 900, 180, 30)
    if ctx.environment == "earth":
        st.caption("On Earth gravity keeps loading the bones, so this projection does not apply here.")
    bone = project_bone_loss(rate, mission_days, exercise / 100)
    k = st.columns(3)
    k[0].metric("Loss rate with exercise", f"{bone['effective_rate_pct_per_month']:.2f} % a month")
    k[1].metric(f"Bone lost by day {mission_days}", f"{bone['total_loss_pct']:.1f} %")
    k[2].metric("Loss avoided by exercise", f"{bone['loss_avoided_pct']:.1f} %")
    fb = chart("Bone density (% of the start)", "% of the start", height=320)
    fb.add_trace(go.Scatter(x=bone["days"], y=bone["bmd_percent"], line=dict(color=theme.CYAN, width=3),
                            name="this projection"))
    low, high = NASA_RANGE_PCT_PER_MONTH
    fb.add_trace(go.Scatter(x=bone["days"], y=bone["ref_low"], line=dict(color=theme.WARN, width=1.5, dash="dash"),
                            name=f"{low:g} % a month, no exercise"))
    fb.add_trace(go.Scatter(x=bone["days"], y=bone["ref_high"], line=dict(color=theme.BAD, width=1.5, dash="dash"),
                            name=f"{high:g} % a month, no exercise"))
    st.plotly_chart(fb, key="bone_projection", config={"displayModeBar": False})
    st.caption("A simple compound-loss projection (from Hudebia Shaikh's app), not a bone scan. "
               "OrbitFit does not measure bone density.")

# ---- 3. daily energy needs -------------------------------------------------------------------

with theme.card():
    theme.html_block('<div class="of-title">Daily energy needs</div>'
                     f'<div class="of-big" style="margin-top:0.3rem">About how many calories {theme.esc(crew.name)} '
                     'needs a day, to plan meals and avoid losing weight.</div>')
    e1, e2, e3, e4 = st.columns(4)
    age = e1.number_input("Age", 18, 80, 40, key=f"age_{crew.id}")
    sex = e2.selectbox("Sex", ["F", "M"], format_func=lambda s: {"F": "Female", "M": "Male"}[s], key=f"sex_{crew.id}")
    height = e3.number_input("Height (cm)", 140, 210, 172, key=f"height_{crew.id}")
    activity = e4.selectbox("Activity", list(ACTIVITY_FACTORS), index=1, key=f"act_{crew.id}",
                            format_func=str.capitalize)
    kcal = daily_energy(crew.mass_kg, height, age, sex, activity)
    theme.html_block(f'<div style="font-size:2.4rem;font-weight:800;margin-top:0.4rem">{kcal:,} kcal a day</div>')
    st.caption(f"Body weight {crew.mass_kg:g} kg from the crew list. Mifflin-St Jeor resting energy × activity "
               f"factor ({ACTIVITY_FACTORS[activity]:g}). An estimate: weigh in weekly and adjust with the Crew "
               "Medical Officer.")

state.footer()
