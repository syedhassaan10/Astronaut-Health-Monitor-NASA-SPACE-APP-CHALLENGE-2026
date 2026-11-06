"""Joint angles from MediaPipe 3D WORLD landmarks.

World landmarks are in metres with the origin at the hip centre. The angle between
two bone vectors does not change when the body rotates, so nothing here uses the
screen's "up" direction. That keeps it safe in microgravity, where "up" means little.
"""

import math
from dataclasses import dataclass


@dataclass
class Vec3:
    x: float
    y: float
    z: float
    visibility: float | None = None


# MediaPipe Pose landmark numbers used by OrbitFit.
L_SHOULDER = 11
R_SHOULDER = 12
L_HIP = 23
R_HIP = 24
L_KNEE = 25
R_KNEE = 26
L_ANKLE = 27
R_ANKLE = 28
L_FOOT = 31
R_FOOT = 32

# Landmarks that must be visible before a lower-body measurement is trusted.
KEY_LANDMARKS = [11, 12, 23, 24, 25, 26, 27, 28]


def angle_deg(a, b, c):
    """Angle in degrees at joint b, between b->a and b->c.

    180 = fully straight, smaller = more bent. Returns None if two points coincide.
    Works with any objects that have x, y and z attributes.
    """
    ux = a.x - b.x
    uy = a.y - b.y
    uz = a.z - b.z
    vx = c.x - b.x
    vy = c.y - b.y
    vz = c.z - b.z
    length_u = math.sqrt(ux * ux + uy * uy + uz * uz)
    length_v = math.sqrt(vx * vx + vy * vy + vz * vz)
    if length_u < 1e-6 or length_v < 1e-6:
        return None
    cos = (ux * vx + uy * vy + uz * vz) / (length_u * length_v)
    cos = max(-1.0, min(1.0, cos))
    return math.degrees(math.acos(cos))


@dataclass
class JointAngles:
    knee_l: float
    knee_r: float
    knee: float  # mean of left and right
    hip_l: float
    hip_r: float
    ankle_l: float
    ankle_r: float


def _angle_at(landmarks, a, b, c):
    """Angle for three landmark numbers, or None if any landmark is missing."""
    if max(a, b, c) >= len(landmarks):
        return None
    return angle_deg(landmarks[a], landmarks[b], landmarks[c])


def joint_angles(landmarks):
    """Knee (hip-knee-ankle), hip (shoulder-hip-knee) and ankle (knee-ankle-foot) angles."""
    knee_l = _angle_at(landmarks, L_HIP, L_KNEE, L_ANKLE)
    knee_r = _angle_at(landmarks, R_HIP, R_KNEE, R_ANKLE)
    hip_l = _angle_at(landmarks, L_SHOULDER, L_HIP, L_KNEE)
    hip_r = _angle_at(landmarks, R_SHOULDER, R_HIP, R_KNEE)
    ankle_l = _angle_at(landmarks, L_KNEE, L_ANKLE, L_FOOT)
    ankle_r = _angle_at(landmarks, R_KNEE, R_ANKLE, R_FOOT)
    values = [knee_l, knee_r, hip_l, hip_r, ankle_l, ankle_r]
    if any(v is None for v in values):
        return None
    return JointAngles(
        knee_l=knee_l, knee_r=knee_r, knee=(knee_l + knee_r) / 2,
        hip_l=hip_l, hip_r=hip_r, ankle_l=ankle_l, ankle_r=ankle_r,
    )


def mean_visibility(landmarks, indices=KEY_LANDMARKS):
    """Mean visibility (0..1) over the given landmarks; 0 if none are present."""
    if not indices:
        return 0.0
    total = 0.0
    for i in indices:
        if i < len(landmarks):
            visibility = getattr(landmarks[i], "visibility", None)
            if visibility is not None:
                total += visibility
    return total / len(indices)
