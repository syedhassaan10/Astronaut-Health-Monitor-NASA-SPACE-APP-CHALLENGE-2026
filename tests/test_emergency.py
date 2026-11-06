"""Emergency triage: priorities, guide order and environment-specific steps."""

from engine.emergency import (
    EMERGENCY, MONITOR, PROTOCOLS, URGENT, EmergencyAnswers, steps_for, triage,
)


def test_not_responding_and_not_breathing_starts_with_cpr():
    r = triage(EmergencyAnswers(responsive=False, breathing_normally=False, chest_pain=True))
    assert r.priority == EMERGENCY
    assert r.protocols[0] == "cpr"
    assert "chest-pain" in r.protocols


def test_not_responding_but_breathing_protects_the_airway():
    r = triage(EmergencyAnswers(responsive=False, breathing_normally=True))
    assert r.priority == EMERGENCY
    assert r.protocols == ["unresponsive"]


def test_chest_pain_is_an_emergency():
    # The challenge scenario: a crewmate has sharp chest pain halfway to Mars.
    r = triage(EmergencyAnswers(chest_pain=True))
    assert r.priority == EMERGENCY
    assert r.protocols == ["chest-pain"]


def test_several_problems_keep_the_most_urgent_first():
    r = triage(EmergencyAnswers(severe_bleeding=True, breathing_difficulty=True, chest_pain=True))
    assert r.protocols == ["bleeding", "breathing", "chest-pain"]


def test_dangerous_vitals_alone_are_an_emergency():
    r = triage(EmergencyAnswers(spo2_pct=86))
    assert r.priority == EMERGENCY
    assert r.protocols == ["abnormal-vitals"]
    assert "86%" in " ".join(r.reasons)


def test_dangerous_vitals_add_reasons_to_a_symptom():
    r = triage(EmergencyAnswers(chest_pain=True, heart_rate=160, systolic=85))
    assert len(r.reasons) == 3


def test_head_injury_alone_is_urgent():
    r = triage(EmergencyAnswers(head_injury=True))
    assert r.priority == URGENT
    assert r.protocols == ["head-injury"]


def test_no_red_flags_means_monitor():
    r = triage(EmergencyAnswers(heart_rate=72, spo2_pct=98))
    assert r.priority == MONITOR
    assert r.protocols == ["monitor"]


def test_cpr_steps_adapt_to_the_environment():
    zero_g = " ".join(steps_for("cpr", "microgravity"))
    moon = " ".join(steps_for("cpr", "partial"))
    earth = " ".join(steps_for("cpr", "earth"))
    assert "restraint" in zero_g
    assert "floor" in moon
    assert "firm, flat surface" in earth
    assert zero_g != moon != earth


def test_every_guide_alerts_someone_and_has_steps_in_every_environment():
    for protocol_id, guide in PROTOCOLS.items():
        assert guide["title"]
        assert guide["goal"]
        for environment in ("microgravity", "partial", "earth"):
            steps = steps_for(protocol_id, environment)
            assert len(steps) >= 3
            assert all(isinstance(s, str) and s for s in steps)
        text = " ".join(steps_for(protocol_id, "earth"))
        assert "Crew Medical Officer" in text


def test_guides_never_dose_medicines_themselves():
    for protocol_id in PROTOCOLS:
        text = " ".join(steps_for(protocol_id, "earth")).lower()
        assert " mg" not in text
        assert "dose" not in text
