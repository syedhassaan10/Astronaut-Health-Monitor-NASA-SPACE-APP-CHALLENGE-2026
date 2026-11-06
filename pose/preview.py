"""Try the camera tracker in a plain window (before the Streamlit pages exist).

Run:  python -m pose.preview            (demo clip)
      python -m pose.preview webcam     (your camera)
      python -m pose.preview my.mp4     (a video file)
Keys: q = quit, m = switch between adaptive and every-frame mode.
Nothing is saved to the logbook from this preview.
"""

import sys

import cv2

from pose.landmarker import DEMO_VIDEO, PoseEstimator
from pose.overlay import draw_overlay
from pose.tracker import Tracker
from pose.video_source import VideoSource


def put_text(frame, text, y, scale=0.8, colour=(255, 255, 255)):
    cv2.putText(frame, text, (16, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 5, cv2.LINE_AA)
    cv2.putText(frame, text, (16, y), cv2.FONT_HERSHEY_SIMPLEX, scale, colour, 2, cv2.LINE_AA)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if arg == "webcam":
        source = VideoSource("webcam")
    elif arg == "demo":
        source = VideoSource("video", path=DEMO_VIDEO, loop=True)
    else:
        source = VideoSource("video", path=arg, loop=True)
    estimator = PoseEstimator()
    tracker = Tracker("squat", 1.0, estimator.detect)
    delay = max(1, int(1000 / source.fps)) if source.kind == "video" else 1
    try:
        while True:
            item = source.read()
            if item is None:
                break
            frame, t_ms = item
            result = tracker.process(frame, t_ms)
            draw_overlay(frame, result.pose, result.live.knee, result.live.level)
            height = frame.shape[0]
            snap = tracker.perf.snapshot(t_ms)
            put_text(frame, f"Reps: {tracker.reps}", height - 90, 1.2)
            put_text(frame, tracker.last_feedback or "Start squatting", height - 50, 0.9)
            put_text(frame, f"{tracker.mode}: {snap.skipped_pct:.0f}% frames skipped", height - 16, 0.6)
            warning = tracker.message(t_ms)
            if warning:
                put_text(frame, warning[:48], 100, 0.55, (113, 113, 248))
            cv2.imshow("OrbitFit preview (q = quit, m = mode)", frame)
            key = cv2.waitKey(delay) & 0xFF
            if key == ord("q"):
                break
            if key == ord("m"):
                tracker.set_mode("full" if tracker.mode == "adaptive" else "adaptive")
    finally:
        source.close()
        estimator.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
