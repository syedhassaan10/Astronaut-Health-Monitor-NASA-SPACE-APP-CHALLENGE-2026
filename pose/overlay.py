"""Draw the skeleton, the knee angle and the form colour on a video frame.

Lines and text are large on purpose: the astronaut is 1 to 2 metres from the screen.
"""

import cv2

# Body connections to draw (MediaPipe landmark numbers).
BONES = [
    (11, 12), (11, 23), (12, 24), (23, 24),   # trunk
    (11, 13), (13, 15), (12, 14), (14, 16),   # arms
    (23, 25), (25, 27), (27, 31),             # left leg
    (24, 26), (26, 28), (28, 32),             # right leg
]
LEG_POINTS = [23, 24, 25, 26, 27, 28]

# BGR colours (OpenCV order), matching the app: green / amber / red, sky blue when neutral.
COLOURS = {
    "green": (153, 211, 52),
    "amber": (36, 191, 251),
    "red": (113, 113, 248),
    "neutral": (248, 189, 56),
}


def draw_overlay(frame, pose, knee=None, level="neutral"):
    """Draw on the frame in place and return it."""
    if pose is None:
        return frame
    height, width = frame.shape[:2]
    colour = COLOURS.get(level, COLOURS["neutral"])
    thickness = max(3, width // 160)
    points = {}
    for i, lm in enumerate(pose.landmarks):
        visibility = getattr(lm, "visibility", 1.0) or 0.0
        if visibility >= 0.3:
            points[i] = (int(lm.x * width), int(lm.y * height))

    for a, b in BONES:
        if a in points and b in points:
            cv2.line(frame, points[a], points[b], colour, thickness, cv2.LINE_AA)
    for i in LEG_POINTS:
        if i in points:
            cv2.circle(frame, points[i], thickness + 3, (255, 255, 255), -1, cv2.LINE_AA)

    if knee is not None:
        text = f"{knee:.0f} deg"
        scale = max(1.0, width / 400)
        cv2.putText(frame, text, (16, int(48 * scale)), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0),
                    thickness + 4, cv2.LINE_AA)
        cv2.putText(frame, text, (16, int(48 * scale)), cv2.FONT_HERSHEY_SIMPLEX, scale, colour, thickness,
                    cv2.LINE_AA)
    return frame
