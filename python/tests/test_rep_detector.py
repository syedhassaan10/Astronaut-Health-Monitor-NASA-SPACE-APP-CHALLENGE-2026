import math

import pytest

from engine.rep_detector import REP_CONFIGS, RepDetector, Sample

CFG = REP_CONFIGS["squat"]


def rep_samples(t0, ecc, hold, con, bottom, fps=30, conf=0.9, asym=2):
    """Samples for one smooth rep: top -> bottom -> top (cosine easing)."""
    out = []
    top = 172
    total = ecc + hold + con
    t = 0.0
    while t <= total + 0.5 / fps:
        if t < ecc:
            k = top - (top - bottom) * (1 - math.cos(math.pi * t / ecc)) / 2
        elif t < ecc + hold:
            k = bottom
        else:
            k = bottom + (top - bottom) * (1 - math.cos(math.pi * (t - ecc - hold) / con)) / 2
        out.append(Sample(t_ms=t0 + t * 1000, knee=k, asymmetry_deg=asym, confidence=conf))
        t += 1 / fps
    return out


def run(samples):
    d = RepDetector(CFG)
    results = []
    for s in samples:
        r = d.push(s)
        if r is not None:
            results.append(r)
    return results


def lead(conf=0.9, asym=2):
    return [Sample(t_ms=0, knee=172, asymmetry_deg=asym, confidence=conf)]


def test_counts_one_rep_with_correct_depth_and_tempo():
    res = run(lead() + rep_samples(500, 2, 0, 1, 95))
    assert len(res) == 1
    assert res[0].kind == "rep"
    m = res[0].rep
    assert m.rep_no == 1
    assert m.min_knee_angle == pytest.approx(95, abs=0.5)
    assert 1.0 < m.eccentric_s < 2.0
    assert 0.4 < m.concentric_s < 1.0
    assert m.asymmetry_deg == pytest.approx(2, abs=1e-5)


def test_counts_several_consecutive_reps():
    s = lead()
    t = 500
    for _ in range(5):
        s += rep_samples(t, 2, 0.5, 1, 98)
        t += 4500
    reps = [r for r in run(s) if r.kind == "rep"]
    assert len(reps) == 5


def test_shallow_dip_is_partial_not_a_rep():
    res = run(lead() + rep_samples(500, 2, 0, 1, 135))
    assert len([r for r in res if r.kind == "rep"]) == 0
    assert any(r.kind == "partial" for r in res)


def test_hysteresis_jitter_around_descend_threshold_makes_no_rep():
    d = RepDetector(CFG)
    t = 0
    out = [d.push(Sample(t, 172, 1, 0.9))]
    for i in range(60):
        t += 33
        knee = 150 + (4 if i % 2 else -2)
        out.append(d.push(Sample(t, knee, 1, 0.9)))
    assert len([r for r in out if r is not None and r.kind == "rep"]) == 0


def test_low_confidence_reps_are_unreliable():
    res = run(lead(conf=0.3) + rep_samples(500, 2, 0, 1, 95, 30, 0.3))
    assert len([r for r in res if r.kind == "rep"]) == 0
    assert len([r for r in res if r.kind == "unreliable"]) == 1


def test_resets_after_a_long_tracking_gap():
    d = RepDetector(CFG)
    d.push(Sample(0, 172, 1, 0.9))
    d.push(Sample(33, 140, 1, 0.9))
    d.push(Sample(66, 100, 1, 0.9))
    # 5 s of lost tracking, then the person is standing again.
    assert d.push(Sample(5066, 172, 1, 0.9)) is None


def test_asymmetry_is_the_mean_left_right_difference():
    res = run(lead(asym=12) + rep_samples(500, 2, 0, 1, 95, 30, 0.9, 12))
    assert res[0].rep.asymmetry_deg == pytest.approx(12, abs=1e-5)


# ---- person-relative top threshold ---------------------------------------------------------

def bent_stance_samples(top, bottom, reps):
    """Reps whose standing knee angle only reaches `top`, like a real, slightly bent stance."""
    out = []
    t = 0
    for _ in range(reps):
        for i in range(61):
            # 2 s down, 2 s up, cosine easing, 30 fps
            x = (i / 60) * 2 * math.pi
            knee = top - (top - bottom) * (1 - math.cos(x)) / 2
            out.append(Sample(t + i * 1000 / 30, knee, 3, 0.95))
        t += 2000 + 500
        for i in range(15):
            out.append(Sample(t + i * 1000 / 30, top, 3, 0.95))
        t += 500
    return out


def count_reps(samples):
    d = RepDetector(CFG)
    n = 0
    for s in samples:
        r = d.push(s)
        if r is not None and r.kind == "rep":
            n += 1
    return n


def test_counts_reps_for_a_person_who_never_extends_past_154():
    # The first rep may be used up learning the person's standing angle.
    assert count_reps(bent_stance_samples(154, 90, 5)) >= 4


def test_still_ignores_squats_that_do_not_reach_depth():
    assert count_reps(bent_stance_samples(154, 135, 4)) == 0


def test_does_not_lower_the_top_below_the_depth_gate_plus_margin():
    # Someone who stays in a deep squat (90..125) must not count as "standing".
    assert count_reps(bent_stance_samples(125, 90, 4)) == 0
