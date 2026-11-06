from engine.form_feedback import (
    FormTargets, asymmetry_level, assess_rep, depth_level, feedback_text, tempo_level,
)
from engine.rep_detector import RepMetrics


def test_grades_depth_tempo_and_asymmetry():
    assert depth_level(98, 100) == "green"
    assert depth_level(115, 100) == "amber"
    assert depth_level(130, 100) == "red"
    assert tempo_level(2, 2) == "green"
    assert tempo_level(2.8, 2) == "amber"
    assert tempo_level(1, 2) == "amber"
    assert tempo_level(0.5, 2) == "red"
    assert asymmetry_level(3) == "green"
    assert asymmetry_level(7) == "amber"
    assert asymmetry_level(12) == "red"


def rep(**changes):
    values = dict(rep_no=1, start_ms=0, end_ms=3000, min_knee_angle=95, eccentric_s=2, concentric_s=1,
                  hold_s=0, asymmetry_deg=2, confidence=0.9)
    values.update(changes)
    return RepMetrics(**values)


TARGETS = FormTargets(depth_deg=100, eccentric_s=2, concentric_s=1)


def test_assess_rep_combines_levels_into_overall_and_score():
    a = assess_rep(rep(min_knee_angle=130, asymmetry_deg=12), TARGETS)
    assert a.depth == "red"
    assert a.asymmetry == "red"
    assert a.overall == "red"
    assert a.score == 40
    assert "shallow" in a.flags
    assert "asymmetry" in a.flags


def test_good_rep_scores_100_and_says_good_depth():
    a = assess_rep(rep(), TARGETS)
    assert a.score == 100
    assert a.overall == "green"
    assert feedback_text(a) == "Good depth"


def test_shallow_rep_says_go_deeper():
    a = assess_rep(rep(min_knee_angle=115), TARGETS)
    assert a.score == 90
    assert feedback_text(a) == "Go deeper"
