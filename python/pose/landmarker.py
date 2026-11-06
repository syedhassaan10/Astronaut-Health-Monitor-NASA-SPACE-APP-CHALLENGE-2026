"""MediaPipe Pose Landmarker, loaded from a local model file.

The model ships with the app (assets/models/pose_landmarker_lite.task), so nothing is
downloaded at run time and it works offline. Set ORBITFIT_POSE_MODEL to use another file.
"""

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = PROJECT_DIR / "assets" / "models" / "pose_landmarker_lite.task"
DEMO_VIDEO = PROJECT_DIR / "assets" / "demo" / "squat.mp4"


def model_path():
    custom = os.environ.get("ORBITFIT_POSE_MODEL")
    if custom:
        return Path(custom)
    return DEFAULT_MODEL


@dataclass
class PoseResult:
    landmarks: list  # 33 image landmarks (x, y in 0..1 of the frame), for drawing and visibility
    world: list      # 33 world landmarks in metres (hip centre = origin), for joint angles


class PoseEstimator:
    """Finds one person's body points in a video frame."""

    def __init__(self, path=None):
        # Imported here so the rest of the app (and its tests) work without MediaPipe installed.
        import mediapipe as mp
        from mediapipe.tasks import python as mp_tasks
        from mediapipe.tasks.python import vision

        path = Path(path) if path else model_path()
        if not path.exists():
            raise FileNotFoundError(
                f"Pose model not found at {path}. Put pose_landmarker_lite.task there or set ORBITFIT_POSE_MODEL.")
        self._mp = mp
        options = vision.PoseLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self._last_ts = -1

    def detect(self, frame_bgr, t_ms):
        """Body points for one frame (OpenCV BGR image), or None if no person is found."""
        import cv2

        # MediaPipe needs strictly increasing whole-millisecond timestamps.
        ts = max(self._last_ts + 1, int(round(t_ms)))
        self._last_ts = ts
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        out = self._landmarker.detect_for_video(image, ts)
        if not out.pose_landmarks or not out.pose_world_landmarks:
            return None
        return PoseResult(landmarks=out.pose_landmarks[0], world=out.pose_world_landmarks[0])

    def close(self):
        self._landmarker.close()
