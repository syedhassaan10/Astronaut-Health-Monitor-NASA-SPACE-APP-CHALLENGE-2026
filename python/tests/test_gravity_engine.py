import math

import pytest

from engine.gravity_engine import (
    ARED_MAX_KG, EXERCISES, Tempo, VolumeGuidance, build_plan, clamp_g, effective_bodyweight_n,
    target_ared_load_kg, tempo_for_g, volume_for_g,
)


def test_clamps_gravity_and_handles_nan():
    assert clamp_g(-1) == 0
    assert clamp_g(2) == 1
    assert clamp_g(math.nan) == 1


def test_effective_bodyweight_is_m_g_981():
    assert effective_bodyweight_n(70, 1) == pytest.approx(686.7, abs=1e-5)
    assert effective_bodyweight_n(70, 0) == 0
    assert effective_bodyweight_n(70, 0.38) == pytest.approx(70 * 0.38 * 9.81, abs=1e-5)


def test_target_load_at_1g_is_the_base_training_load():
    assert target_ared_load_kg(80, 1, EXERCISES["squat"])[0] == 40


def test_target_load_at_0g_adds_the_missing_bodyweight_times_factor():
    assert target_ared_load_kg(70, 0, EXERCISES["squat"])[0] == 110
    assert target_ared_load_kg(70, 0, EXERCISES["deadlift"])[0] == pytest.approx(70 * 0.6 + 50, abs=1e-9)


def test_target_load_falls_as_gravity_rises():
    a = target_ared_load_kg(75, 0.1, EXERCISES["heelRaise"])[0]
    b = target_ared_load_kg(75, 0.6, EXERCISES["heelRaise"])[0]
    assert a > b


def test_caps_at_the_ared_maximum():
    kg, capped = target_ared_load_kg(500, 0, EXERCISES["squat"])
    assert kg == ARED_MAX_KG
    assert capped is True
    assert target_ared_load_kg(70, 0, EXERCISES["squat"])[1] is False


def test_tempo_anchors_and_linear_interpolation():
    assert tempo_for_g(1) == Tempo(2, 1, 0)
    assert tempo_for_g(0) == Tempo(4, 2, 1)
    mid = tempo_for_g(0.5)
    assert mid.eccentric_s == pytest.approx(3)
    assert mid.concentric_s == pytest.approx(1.5)
    assert mid.hold_s == pytest.approx(0.5)


def test_weekly_volume_rises_as_gravity_falls():
    assert volume_for_g(1) == VolumeGuidance(3, 3, 8, 30)
    assert volume_for_g(0) == VolumeGuidance(6, 4, 10, 120)
    assert volume_for_g(0.166).minutes_per_day > volume_for_g(0.38).minutes_per_day


def test_halves_round_up_like_the_original():
    # 0.5 g: 4.5 sessions -> 5 (Python's round() would give 4)
    assert volume_for_g(0.5).sessions_per_week == 5


def test_build_plan_combines_all_pieces():
    p = build_plan(70, 0, "squat")
    assert p.target_load_kg == 110
    assert p.effective_bodyweight_n == 0
    assert p.tempo.hold_s == 1
