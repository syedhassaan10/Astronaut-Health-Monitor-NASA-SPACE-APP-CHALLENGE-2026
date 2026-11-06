"""Form scoring for one rep: depth, tempo and left/right difference -> green / amber / red."""

from dataclasses import dataclass, field

GREEN = "green"
AMBER = "amber"
RED = "red"

_RANK = {GREEN: 0, AMBER: 1, RED: 2}

# Plain-language cue for each flag, shown big on the workout screen.
FLAG_CUES = {
    "shallow": "Go deeper",
    "fast-eccentric": "Lower more slowly",
    "slow-eccentric": "Lower a little faster",
    "fast-concentric": "Stand up more slowly",
    "slow-concentric": "Stand up a little faster",
    "asymmetry": "Even out left and right",
}


@dataclass
class FormTargets:
    depth_deg: float
    eccentric_s: float
    concentric_s: float


@dataclass
class FormAssessment:
    depth: str
    tempo: str
    asymmetry: str
    overall: str
    score: int  # 0..100
    flags: list = field(default_factory=list)


def worst(*levels):
    """The worst of several green/amber/red levels."""
    result = GREEN
    for level in levels:
        if _RANK[level] > _RANK[result]:
            result = level
    return result


def depth_level(min_knee, target_deg):
    """Green at or below the target (+5 degrees tolerance), amber within +20, else red."""
    if min_knee <= target_deg + 5:
        return GREEN
    if min_knee <= target_deg + 20:
        return AMBER
    return RED


def tempo_level(actual_s, target_s):
    """Relative miss |actual - target| / target: up to 25% green, up to 50% amber, else red."""
    if target_s <= 0:
        return GREEN
    miss = abs(actual_s - target_s) / target_s
    if miss <= 0.25:
        return GREEN
    if miss <= 0.5:
        return AMBER
    return RED


def asymmetry_level(deg):
    """Left/right knee-angle difference: under 5 green, under 10 amber, else red."""
    if deg < 5:
        return GREEN
    if deg < 10:
        return AMBER
    return RED


def targets_for(cfg, tempo):
    """Form targets from a RepConfig and a Tempo (from the gravity engine)."""
    return FormTargets(depth_deg=cfg.depth_target_deg, eccentric_s=tempo.eccentric_s, concentric_s=tempo.concentric_s)


def _penalty(level):
    """Points taken off the score: 10 for amber, 30 for red."""
    if level == RED:
        return 30
    if level == AMBER:
        return 10
    return 0


def assess_rep(m, t):
    depth = depth_level(m.min_knee_angle, t.depth_deg)
    ecc = tempo_level(m.eccentric_s, t.eccentric_s)
    con = tempo_level(m.concentric_s, t.concentric_s)
    tempo = worst(ecc, con)
    asym = asymmetry_level(m.asymmetry_deg)

    flags = []
    if depth != GREEN:
        flags.append("shallow")
    if ecc != GREEN:
        if m.eccentric_s < t.eccentric_s:
            flags.append("fast-eccentric")
        else:
            flags.append("slow-eccentric")
    if con != GREEN:
        if m.concentric_s < t.concentric_s:
            flags.append("fast-concentric")
        else:
            flags.append("slow-concentric")
    if asym != GREEN:
        flags.append("asymmetry")

    score = max(0, 100 - _penalty(depth) - _penalty(tempo) - _penalty(asym))
    return FormAssessment(depth=depth, tempo=tempo, asymmetry=asym, overall=worst(depth, tempo, asym), score=score, flags=flags)


def feedback_text(assessment):
    """One short cue for the astronaut: the first problem, or praise."""
    if not assessment.flags:
        return "Good depth"
    return FLAG_CUES[assessment.flags[0]]
