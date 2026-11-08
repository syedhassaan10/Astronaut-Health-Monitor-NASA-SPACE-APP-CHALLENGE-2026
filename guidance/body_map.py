"""The clickable body figure: body regions, what they do, which measurements and alerts belong
to each, and the region's current status (worst alert level)."""

from dataclasses import dataclass

from engine.health_types import NOMINAL, worst_status


@dataclass(frozen=True)
class Region:
    id: str
    label: str
    x: float              # position on the figure (0..10 wide, 0..20 tall, 20 = top)
    y: float
    function: str         # what this part of the body does
    in_space: str         # what spaceflight does to it
    measures: tuple       # measurement guide ids
    rules: tuple          # alert rules that belong here
    pain_locations: tuple  # check-in pain locations that belong here


REGIONS = [
    Region("brain", "Brain, sleep and mood", 5.0, 18.6,
           "Controls attention, mood and decision-making, and needs good sleep to work well.",
           "Isolation, confinement, workload and a 90-minute day-night cycle in orbit disturb sleep and raise stress.",
           ("checkin",), ("recovery", "stress"), ("upper-back-neck",)),
    Region("heart", "Heart and blood vessels", 5.6, 14.6,
           "Pumps blood and keeps blood pressure steady when you change position.",
           "Fluids shift towards the head and the heart works less; when gravity returns, blood pressure control can fail "
           "for a while (dizziness, fainting).",
           ("heart_rate", "blood_pressure"), ("heart_rate", "heart_rate_trend", "blood_pressure"), ()),
    Region("lungs", "Lungs and breathing", 4.2, 15.0,
           "Take oxygen into the blood and remove carbon dioxide.",
           "The cabin air is made by machines; a fault, high carbon dioxide or a leak shows up first as breathlessness "
           "and low oxygen saturation.",
           ("spo2_pct",), ("spo2_pct",), ()),
    Region("immune", "Immune system and temperature", 5.0, 12.4,
           "Fights infection; fever is one of its signals.",
           "Immune function changes in flight and dormant viruses can reactivate. A closed cabin spreads illness quickly. "
           "Space radiation also affects blood-forming and immune cells, so the daily dose is tracked here.",
           ("temperature_c", "radiation_msv"), ("temperature_c", "radiation_msv", "mission_dose"), ()),
    Region("energy", "Energy and nutrition", 5.0, 10.6,
           "Turns food into the fuel muscles and the brain use; blood sugar shows how well that is balanced.",
           "Food choices are limited, appetite changes and exercise load is high, so energy balance can drift.",
           ("glucose_mg_dl",), ("glucose_mg_dl",), ()),
    Region("shoulders", "Shoulders and arms", 2.3, 15.8,
           "Push, pull and hold you in place; in microgravity you move by your arms.",
           "Constant translation by hand and resistive exercise load the shoulders.",
           (), (), ("shoulder",)),
    Region("back", "Back and spine", 7.6, 12.0,
           "Holds you upright and protects the spinal cord.",
           "Without gravity the spine lengthens and back muscles weaken; back pain is common early in flight.",
           (), (), ("lower-back",)),
    Region("hips", "Hips and bones", 5.0, 8.6,
           "Carry the body's weight; the hip and spine are the bones that lose the most in space.",
           "NASA reports an average loss of 1-1.5% of bone density per month at the hip and spine (Bone Fracture "
           "Evidence Report, 2024). OrbitFit cannot measure bone; it tracks the exercise that protects it.",
           ("workout",), ("adherence",), ("hip",)),
    Region("knees", "Thigh muscles and knees", 5.0, 5.4,
           "Leg muscles lift and lower you; the knees guide the movement.",
           "Leg muscles shrink and weaken quickly when unloaded. Squat depth, speed and left/right balance show it early.",
           ("workout",), ("depth", "concentric", "variability", "asymmetry", "pain-asymmetry"), ("knee",)),
    Region("feet", "Ankles and feet", 5.0, 1.4,
           "Balance and push-off.",
           "Feet barely touch anything in orbit; skin and balance change, and ankles must re-adapt when gravity returns.",
           (), (), ("ankle-foot",)),
]


def region_by_id(region_id):
    for r in REGIONS:
        if r.id == region_id:
            return r
    return None


def latest_pain_location(checkins, crew_id):
    """Where the person last reported pain, or None."""
    mine = [c for c in checkins if c.crew_id == crew_id]
    mine.sort(key=lambda c: c.day)
    for c in reversed(mine):
        if c.pain > 0:
            return c.pain_location
    return None


def alerts_for_region(region, alerts, pain_location):
    """Alerts that belong to this region. A pain alert belongs where the pain was reported."""
    out = []
    for a in alerts:
        if a.rule in region.rules:
            out.append(a)
        elif a.rule == "pain" and pain_location in region.pain_locations:
            out.append(a)
    return out


def region_status(region, alerts, pain_location):
    return worst_status(NOMINAL, *[a.level for a in alerts_for_region(region, alerts, pain_location)])
