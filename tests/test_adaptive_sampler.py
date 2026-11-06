"""Battery saving: more than 75% fewer model calls, same rep count."""

import math
from dataclasses import replace

from engine.adaptive_sampler import DEFAULT_SAMPLER, AdaptiveSampler
from engine.gravity_engine import tempo_for_g
from engine.rep_detector import REP_CONFIGS, RepDetector, Sample

FPS = 30


def make_jitter(seed=7):
    """Repeatable jitter of +-0.8 degrees (a simple linear congruential generator)."""
    state = [seed]

    def next_value():
        state[0] = (state[0] * 1664525 + 1013904223) % (2 ** 32)
        return (state[0] / 2 ** 32 - 0.5) * 1.6

    return next_value


def knee_at(t, reps, ecc, hold, con, rest, bottom=95):
    """Knee angle at time t (s) for N reps with the given tempo and rest between reps."""
    top = 172
    period = ecc + hold + con + rest
    u = t - 1  # one second standing before the first rep
    if u < 0 or u >= reps * period:
        return top
    x = u % period
    if x < ecc:
        return top - (top - bottom) * (1 - math.cos(math.pi * x / ecc)) / 2
    if x < ecc + hold:
        return bottom
    if x < ecc + hold + con:
        return bottom + (top - bottom) * (1 - math.cos(math.pi * (x - ecc - hold) / con)) / 2
    return top


def simulate(mode, reps, ecc, hold, con, rest, stride=DEFAULT_SAMPLER.base_stride):
    sampler = AdaptiveSampler(mode, replace(DEFAULT_SAMPLER, base_stride=stride))
    detector = RepDetector(REP_CONFIGS["squat"])
    jitter = make_jitter()
    found = []
    total = 1 + reps * (ecc + hold + con + rest) + 1
    frames = 0
    inferences = 0
    f = 0
    while f / FPS < total:
        frames += 1
        t_ms = f / FPS * 1000
        if sampler.should_run(t_ms):
            inferences += 1
            knee = knee_at(f / FPS, reps, ecc, hold, con, rest) + jitter()
            sampler.on_result(knee, t_ms)
            r = detector.push(Sample(t_ms, knee, 2, 0.9))
            if r is not None and r.kind == "rep":
                found.append(r.rep)
        f += 1
    return frames, inferences, found


def test_full_mode_runs_on_every_frame():
    s = AdaptiveSampler("full")
    for i in range(20):
        assert s.should_run(i * 33) is True


def test_adaptive_mode_runs_every_7th_frame_when_nothing_moves():
    s = AdaptiveSampler("adaptive")
    runs = 0
    for i in range(100):
        if s.should_run(i * 33):
            runs += 1
    assert runs == 14


def test_bursts_to_every_frame_for_300ms_at_a_turning_point():
    s = AdaptiveSampler("adaptive")
    s.on_result(150, 0)
    s.on_result(120, 166)    # fast: about 180 degrees/s
    s.on_result(119.5, 333)  # nearly stopped -> burst until 633 ms
    assert s.should_run(366)
    assert s.should_run(400)
    assert s.should_run(600)
    after = [s.should_run(t) for t in [700, 733, 766, 800, 833, 866, 900]]
    assert after.count(True) == 1


def test_at_least_75_percent_fewer_calls_at_0g_with_the_same_reps():
    t = tempo_for_g(0)
    _, full_calls, full_reps = simulate("full", 8, t.eccentric_s, t.hold_s, t.concentric_s, 1)
    _, adap_calls, adap_reps = simulate("adaptive", 8, t.eccentric_s, t.hold_s, t.concentric_s, 1)
    reduction = 1 - adap_calls / full_calls
    print(f"adaptive reduction (0 g tempo): {reduction * 100:.1f}%")
    assert len(full_reps) == 8
    assert len(adap_reps) == 8
    assert reduction >= 0.75
    # Depth and tempo stay close to the every-frame measurement.
    for a, b in zip(adap_reps, full_reps):
        assert abs(a.min_knee_angle - b.min_knee_angle) < 3
        assert abs(a.eccentric_s - b.eccentric_s) < 0.35


def test_also_clears_75_percent_at_earth_and_mars_tempos():
    for g in [1, 0.38]:
        t = tempo_for_g(g)
        _, full_calls, full_reps = simulate("full", 8, t.eccentric_s, t.hold_s, t.concentric_s, 1)
        _, adap_calls, adap_reps = simulate("adaptive", 8, t.eccentric_s, t.hold_s, t.concentric_s, 1)
        assert 1 - adap_calls / full_calls >= 0.75
        assert len(adap_reps) == len(full_reps)
