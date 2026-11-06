"""The real pose model on the bundled demo clip (skipped if MediaPipe or the files are missing)."""

import pytest

pytest.importorskip("mediapipe")
pytest.importorskip("cv2")

from pose.benchmark import run_benchmark  # noqa: E402
from pose.landmarker import DEFAULT_MODEL, DEMO_VIDEO  # noqa: E402

if not DEFAULT_MODEL.exists() or not DEMO_VIDEO.exists():
    pytest.skip("pose model or demo clip not present", allow_module_level=True)


@pytest.fixture(scope="module")
def result():
    return run_benchmark(DEMO_VIDEO, loops=3)


def test_counts_reps_on_the_demo_clip(result):
    assert result.full.reps >= 3


def test_adaptive_sampling_keeps_the_rep_count_and_saves_most_model_calls(result):
    # Measured on this 24 fps clip: 75.8% for one play, 74.2% for 3 loops, 72.5% for 6 loops.
    # At 24 fps a 300 ms burst costs more frames than with a 30 fps webcam (80% in test_adaptive_sampler.py).
    print(f"full: {result.full}\nadaptive: {result.adaptive}\nsaved: {result.reduction_pct:.1f}%")
    assert result.same_reps
    assert result.reduction_pct > 70
