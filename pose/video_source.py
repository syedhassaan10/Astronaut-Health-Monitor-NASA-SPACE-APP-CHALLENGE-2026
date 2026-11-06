"""Frames from the webcam or a video file, each with a timestamp in milliseconds.

For a video file the timestamp is the video's own clock, so a slow computer cannot make
reps look slower than they were. For the webcam it is the real clock.
"""

import time

import cv2


class VideoSource:
    def __init__(self, kind, path=None, camera_index=0, loop=False):
        self.kind = kind  # "webcam" or "video"
        self.loop = loop
        if kind == "webcam":
            # DirectShow opens Windows webcams quickly; other systems ignore it and use their default.
            self.capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        else:
            self.capture = cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            if kind == "webcam":
                raise RuntimeError("Could not open the camera. Check that no other app is using it, or use Demo Mode.")
            raise RuntimeError(f"Could not open the video file {path}.")
        fps = self.capture.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 1 else 30.0
        self._start = time.monotonic()
        self._loop_offset_ms = 0.0
        self._frame_no = 0

    def read(self):
        """The next (frame, t_ms), or None at the end of a video."""
        ok, frame = self.capture.read()
        if not ok and self.kind == "video" and self.loop:
            # Start the clip again; keep time running forward.
            self._loop_offset_ms += self._frame_no * 1000 / self.fps
            self._frame_no = 0
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.capture.read()
        if not ok:
            return None
        if self.kind == "webcam":
            frame = cv2.flip(frame, 1)  # mirror view, like a selfie
            t_ms = (time.monotonic() - self._start) * 1000
        else:
            t_ms = self._loop_offset_ms + self._frame_no * 1000 / self.fps
            self._frame_no += 1
        return frame, t_ms

    def close(self):
        self.capture.release()
