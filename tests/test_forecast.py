"""Forecast page pieces: Hudebia Shaikh's digital twin, the bone-loss projection and energy needs."""

import pytest

from digital_twin.bone_projection import project_bone_loss
from digital_twin.monte_carlo import run_monte_carlo
from engine.energy import daily_energy, resting_energy


def test_twin_is_repeatable_and_in_range():
    a = run_monte_carlo(n_runs=5, mission_duration_hours=3 * 24)
    b = run_monte_carlo(n_runs=5, mission_duration_hours=3 * 24)
    assert a["risk_summary"] == b["risk_summary"]  # seeded: same inputs, same forecast
    rs = a["risk_summary"]
    assert 0 <= rs["mean_prob_fatigue_risk"] <= 1
    assert 0 <= rs["p95_peak_fatigue"] <= 10
    env = a["envelopes"]
    assert len(env["time_hours"]) == len(env["fatigue_mean"]) == len(env["p_ms_coupled_mean"])
    assert all(lo <= m <= hi for lo, m, hi in zip(env["fatigue_min"], env["fatigue_mean"], env["fatigue_max"]))


def test_forecast_length_follows_the_days_asked():
    short = run_monte_carlo(n_runs=3, mission_duration_hours=2 * 24)
    long = run_monte_carlo(n_runs=3, mission_duration_hours=6 * 24)
    assert short["envelopes"]["time_hours"][-1] < 2 * 24 <= long["envelopes"]["time_hours"][-1] + 1
    assert long["envelopes"]["time_hours"][-1] > 5 * 24


def test_bone_projection_compounds_monthly_and_exercise_helps():
    p = project_bone_loss(1.0, 30, 0.0)
    assert p["bmd_percent"][0] == 100
    assert round(p["total_loss_pct"], 6) == 1.0          # 1 % a month for one month
    half = project_bone_loss(2.0, 180, 0.5)
    assert half["effective_rate_pct_per_month"] == 1.0
    assert half["loss_avoided_pct"] > 0
    assert half["ref_high"][-1] < half["ref_low"][-1] < 100
    with pytest.raises(ValueError):
        project_bone_loss(1.0, 0)


def test_energy_needs_follow_mifflin_st_jeor():
    assert resting_energy(70, 175, 30, "M") == 10 * 70 + 6.25 * 175 - 5 * 30 + 5
    assert resting_energy(60, 165, 30, "F") == 10 * 60 + 6.25 * 165 - 5 * 30 - 161
    assert daily_energy(70, 175, 30, "M", "low") < daily_energy(70, 175, 30, "M", "high")
    assert daily_energy(70, 175, 30, "M") % 10 == 0
    with pytest.raises(ValueError):
        daily_energy(0, 175, 30, "M")


def test_forecast_page_runs_the_twin(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from tests.test_pages import APP
    monkeypatch.setenv("ORBITFIT_DB", str(tmp_path / "orbitfit.db"))
    monkeypatch.setenv("ORBITFIT_LINK_DB", str(tmp_path / "link.db"))
    monkeypatch.setenv("ORBITFIT_EARTH_DB", str(tmp_path / "earth.db"))
    monkeypatch.setenv("ORBITFIT_START_WITH_DEMO", "1")
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    at.switch_page("pages/forecast.py")
    at.run()
    assert not at.exception
    at.slider[0].set_value(5)   # few runs keep the test quick
    at.slider[1].set_value(7)
    at.button(key="run_twin").click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [m.label for m in at.metric]
    assert "Time above fatigue risk" in labels and any("Bone lost" in label for label in labels)
    assert any("kcal a day" in m.value for m in at.markdown)
