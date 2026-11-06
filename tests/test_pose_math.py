import math

import pytest

from engine import pose_math as pm
from engine.pose_math import Vec3, angle_deg, joint_angles, mean_visibility


def v(x, y, z, visibility=1.0):
    return Vec3(x, y, z, visibility)


def rotate(p, axis, rad):
    """Rotate a point about an axis (Rodrigues) to test that angles ignore orientation."""
    n = math.sqrt(axis.x ** 2 + axis.y ** 2 + axis.z ** 2)
    kx, ky, kz = axis.x / n, axis.y / n, axis.z / n
    c = math.cos(rad)
    s = math.sin(rad)
    dot = kx * p.x + ky * p.y + kz * p.z
    cx = ky * p.z - kz * p.y
    cy = kz * p.x - kx * p.z
    cz = kx * p.y - ky * p.x
    return Vec3(
        p.x * c + cx * s + kx * dot * (1 - c),
        p.y * c + cy * s + ky * dot * (1 - c),
        p.z * c + cz * s + kz * dot * (1 - c),
        p.visibility,
    )


def test_straight_right_and_folded_angles():
    assert angle_deg(v(0, 1, 0), v(0, 0, 0), v(0, -1, 0)) == pytest.approx(180, abs=1e-6)
    assert angle_deg(v(1, 0, 0), v(0, 0, 0), v(0, 1, 0)) == pytest.approx(90, abs=1e-6)
    assert angle_deg(v(1, 0, 0), v(0, 0, 0), v(2, 0, 0)) == pytest.approx(0, abs=1e-4)


def test_coincident_points_give_none():
    assert angle_deg(v(0, 0, 0), v(0, 0, 0), v(1, 0, 0)) is None


def pose():
    w = [v(0, 0, 0) for _ in range(33)]
    # Both legs bent 90 degrees at the knee, trunk leaning.
    w[pm.L_SHOULDER] = v(-0.2, -0.5, 0.1)
    w[pm.R_SHOULDER] = v(0.2, -0.5, 0.1)
    w[pm.L_HIP] = v(-0.1, 0, 0)
    w[pm.R_HIP] = v(0.1, 0, 0)
    w[pm.L_KNEE] = v(-0.1, 0, 0.4)
    w[pm.R_KNEE] = v(0.1, 0, 0.4)
    w[pm.L_ANKLE] = v(-0.1, 0.4, 0.4)
    w[pm.R_ANKLE] = v(0.1, 0.4, 0.4)
    w[pm.L_FOOT] = v(-0.1, 0.4, 0.6)
    w[pm.R_FOOT] = v(0.1, 0.4, 0.6)
    return w


def test_computes_a_90_degree_knee():
    a = joint_angles(pose())
    assert a.knee_l == pytest.approx(90, abs=1e-5)
    assert a.knee_r == pytest.approx(90, abs=1e-5)
    assert a.knee == pytest.approx(90, abs=1e-5)


def test_any_3d_rotation_gives_the_same_angles():
    # e.g. floating upside down in microgravity
    base = joint_angles(pose())
    for axis, rad in [(v(1, 0, 0), math.pi), (v(0, 0, 1), 1.3), (v(1, 2, 3), 2.7)]:
        r = joint_angles([rotate(p, axis, rad) for p in pose()])
        assert r.knee == pytest.approx(base.knee, abs=1e-5)
        assert r.hip_l == pytest.approx(base.hip_l, abs=1e-5)
        assert r.ankle_r == pytest.approx(base.ankle_r, abs=1e-5)


def test_missing_landmarks_give_none():
    assert joint_angles([]) is None


def test_mean_visibility_of_key_landmarks():
    w = pose()
    for i in [11, 12, 23, 24]:
        w[i] = v(0, 0, 0, 0.2)
    assert mean_visibility(w) == pytest.approx((4 * 0.2 + 4 * 1) / 8, abs=1e-9)
