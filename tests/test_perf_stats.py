import pytest

from engine.perf_stats import PerfStats


def test_fps_inference_rate_skipped_share_and_saved_time():
    p = PerfStats()
    # 30 fps for 1 s (31 frames), model on every 6th frame.
    for i in range(31):
        t = i * 1000 / 30
        p.on_frame(t)
        if i % 6 == 0:
            p.on_inference(t, 10)
    s = p.snapshot(1000)
    assert s.camera_fps == pytest.approx(30, abs=0.5)
    assert s.frames == 31
    assert s.inferences == 6
    assert s.skipped_pct == pytest.approx(100 * 25 / 31)
    assert s.avg_inference_ms == pytest.approx(10)
    assert s.saved_ms == pytest.approx(25 * 10)


def test_first_warm_up_call_is_left_out_of_the_average():
    p = PerfStats()
    p.on_frame(0)
    p.on_inference(0, 500)
    p.on_inference(100, 10)
    p.on_inference(200, 20)
    assert p.snapshot(200).avg_inference_ms == pytest.approx(15)
    assert p.snapshot(200).inferences == 3


def test_reset_clears_everything():
    p = PerfStats()
    p.on_frame(0)
    p.on_inference(0, 5)
    p.reset()
    s = p.snapshot(0)
    assert s.frames == 0
    assert s.inferences == 0
    assert s.avg_inference_ms == 0
