"""Emergency triage: from a few yes/no questions (and any vitals at hand) to a priority
and a step-by-step guide, adapted to the environment (microgravity, Moon/Mars, Earth).

This is decision support for crew who are not doctors. It follows widely taught first-aid
steps and always sends the crew to the Crew Medical Officer, the onboard medical procedures
and the flight surgeon. It never gives a diagnosis and never doses a medicine.
"""

from dataclasses import dataclass, field

EMERGENCY = "EMERGENCY"  # act now, alert the whole crew
URGENT = "URGENT"        # needs the Crew Medical Officer soon
MONITOR = "MONITOR"      # no red flags found; measure and watch

DISCLAIMER = ("Decision-support guide for crew who are not doctors. It does not replace the onboard medical "
              "procedures, the Crew Medical Officer or the flight surgeon. If in doubt, treat it as an emergency.")

# Vital signs that are dangerous on their own (demonstration values).
DANGER_SPO2_BELOW = 90
DANGER_HR_BELOW = 40
DANGER_HR_ABOVE = 150
DANGER_SYSTOLIC_BELOW = 90
DANGER_GLUCOSE_BELOW = 54


@dataclass
class EmergencyAnswers:
    responsive: bool = True           # answers when you speak loudly and tap the shoulders
    breathing_normally: bool = True   # regular breaths, not gasping
    chest_pain: bool = False
    breathing_difficulty: bool = False
    severe_bleeding: bool = False
    stroke_signs: bool = False        # face drooping, arm weakness, slurred speech
    seizure: bool = False
    allergic_reaction: bool = False   # swelling of face or throat, widespread rash, after a trigger
    head_injury: bool = False
    # Optional measurements (None = not measured).
    heart_rate: float | None = None
    systolic: float | None = None
    spo2_pct: float | None = None
    glucose_mg_dl: float | None = None


@dataclass
class TriageResult:
    priority: str
    protocols: list = field(default_factory=list)  # protocol ids, most urgent first
    reasons: list = field(default_factory=list)    # plain-language reasons


def danger_vitals(a):
    """Plain-language reasons for any dangerous vital sign."""
    reasons = []
    if a.spo2_pct is not None and a.spo2_pct < DANGER_SPO2_BELOW:
        reasons.append(f"Oxygen saturation {a.spo2_pct:g}% is below {DANGER_SPO2_BELOW}%.")
    if a.heart_rate is not None and a.heart_rate < DANGER_HR_BELOW:
        reasons.append(f"Heart rate {a.heart_rate:g} bpm is below {DANGER_HR_BELOW}.")
    if a.heart_rate is not None and a.heart_rate > DANGER_HR_ABOVE:
        reasons.append(f"Heart rate {a.heart_rate:g} bpm is above {DANGER_HR_ABOVE}.")
    if a.systolic is not None and a.systolic < DANGER_SYSTOLIC_BELOW:
        reasons.append(f"Systolic blood pressure {a.systolic:g} mmHg is below {DANGER_SYSTOLIC_BELOW}.")
    if a.glucose_mg_dl is not None and a.glucose_mg_dl < DANGER_GLUCOSE_BELOW:
        reasons.append(f"Blood sugar {a.glucose_mg_dl:g} mg/dL is below {DANGER_GLUCOSE_BELOW}.")
    return reasons


def triage(a):
    """Decide the priority and which guides to show, most urgent first."""
    protocols = []
    reasons = []

    if not a.responsive and not a.breathing_normally:
        protocols.append("cpr")
        reasons.append("Not responding and not breathing normally: start CPR now.")
    elif not a.responsive:
        protocols.append("unresponsive")
        reasons.append("Not responding, but breathing: protect the airway and watch breathing.")

    if a.severe_bleeding:
        protocols.append("bleeding")
        reasons.append("Severe bleeding.")
    if a.allergic_reaction:
        protocols.append("allergy")
        reasons.append("Possible severe allergic reaction.")
    if a.breathing_difficulty:
        protocols.append("breathing")
        reasons.append("Difficulty breathing.")
    if a.chest_pain:
        protocols.append("chest-pain")
        reasons.append("Chest pain.")
    if a.stroke_signs:
        protocols.append("stroke")
        reasons.append("Signs of a stroke (face, arm, speech).")
    if a.seizure:
        protocols.append("seizure")
        reasons.append("Seizure.")

    vital_reasons = danger_vitals(a)
    reasons.extend(vital_reasons)

    if protocols:
        return TriageResult(priority=EMERGENCY, protocols=protocols + _extra_for_head(a), reasons=reasons)
    if vital_reasons:
        return TriageResult(priority=EMERGENCY, protocols=["abnormal-vitals"] + _extra_for_head(a), reasons=reasons)
    if a.head_injury:
        return TriageResult(priority=URGENT, protocols=["head-injury"], reasons=["Head injury."])
    return TriageResult(priority=MONITOR, protocols=["monitor"],
                        reasons=["No red flags in the answers. Measure, watch and tell the Crew Medical Officer."])


def _extra_for_head(a):
    if a.head_injury:
        return ["head-injury"]
    return []


# ---- guides -------------------------------------------------------------------------------
# Each guide: a title, a one-line goal, and steps. A step can be a plain string (all
# environments) or a dict {environment: text} when the step differs by environment.

ALERT_CREW = "Shout for help: alert the whole crew and the Crew Medical Officer. Ask someone to bring the medical kit and the defibrillator (AED)."
CONTACT_SURGEON = "Contact the flight surgeon as soon as the link allows; if the link is down, keep notes (times, readings, what you did) to send later."

PROTOCOLS = {
    "cpr": {
        "title": "Not breathing: CPR",
        "goal": "Keep blood flowing to the brain until the heart restarts or the Crew Medical Officer takes over.",
        "steps": [
            ALERT_CREW,
            {
                "microgravity": "Secure the person on their back to a firm surface (medical restraint, or a wall). "
                                "Anchor yourself with foot restraints or a handrail, or brace against the opposite "
                                "wall, so your pushes do not push both of you away.",
                "partial": "Lay the person on their back on the floor. You weigh less here, so lock your arms and use "
                           "your shoulders; brace your feet if you start to lift off.",
                "earth": "Lay the person on their back on a firm, flat surface.",
            },
            "Push hard and fast in the centre of the chest: about 5 cm deep, 100 to 120 pushes per minute. "
            "Let the chest come fully back up between pushes.",
            "If you are trained, give 2 rescue breaths after every 30 pushes. If not, keep pushing without stopping.",
            "Switch the defibrillator (AED) on as soon as it arrives and follow its voice instructions.",
            "Swap with another crew member every 2 minutes so the pushes stay strong.",
            "Do not stop until the person breathes normally, the AED tells you to stop, or the Crew Medical Officer takes over.",
            CONTACT_SURGEON,
        ],
    },
    "unresponsive": {
        "title": "Not responding, but breathing",
        "goal": "Keep the airway open and catch any change in breathing.",
        "steps": [
            ALERT_CREW,
            {
                "microgravity": "Gently secure the person so they cannot drift into equipment. Keep the head tilted "
                                "back slightly and the chin lifted to keep the airway open.",
                "partial": "Roll the person onto their side (recovery position) so the airway stays clear.",
                "earth": "Roll the person onto their side (recovery position) so the airway stays clear.",
            },
            "Watch and listen to the breathing all the time. If it stops or becomes gasping, start CPR.",
            "Measure oxygen saturation and heart rate, and blood sugar if you can: low blood sugar can cause this.",
            "Check for injuries, and for a problem with the cabin air (alarms, smell, smoke) that could affect you too.",
            CONTACT_SURGEON,
        ],
    },
    "bleeding": {
        "title": "Severe bleeding",
        "goal": "Stop the blood loss.",
        "steps": [
            ALERT_CREW,
            "Put on gloves (and eye protection in microgravity: blood forms floating droplets).",
            "Press firmly and directly on the wound with a clean dressing. Keep pressing.",
            "If blood soaks through, do not remove the dressing: add more on top and press harder.",
            {
                "microgravity": "Catch floating blood with absorbent pads so it does not spread through the cabin.",
                "partial": "Keep the person lying down; raise the bleeding limb if it does not hurt.",
                "earth": "Keep the person lying down; raise the bleeding limb if it does not hurt.",
            },
            "Watch for shock: pale, cold, sweaty skin, fast heart rate, confusion. Measure heart rate and blood pressure.",
            "Use a tourniquet from the medical kit only if the onboard procedures say so for this kind of wound.",
            CONTACT_SURGEON,
        ],
    },
    "allergy": {
        "title": "Severe allergic reaction",
        "goal": "Recognise a dangerous reaction fast and use the emergency medicine.",
        "steps": [
            ALERT_CREW,
            "Look for swelling of the lips, tongue or throat, trouble breathing or swallowing, widespread rash, dizziness.",
            "Use the emergency allergy medicine (adrenaline auto-injector) from the medical kit exactly as the onboard "
            "procedures describe.",
            "Remove or move away from the trigger if known (food, medicine, chemical).",
            "Measure oxygen saturation, heart rate and blood pressure every 5 minutes.",
            "If breathing stops, start CPR.",
            CONTACT_SURGEON,
        ],
    },
    "breathing": {
        "title": "Difficulty breathing",
        "goal": "Find out if it is the person or the cabin air, and support breathing.",
        "steps": [
            ALERT_CREW,
            "Check the cabin first: alarms, smoke, smell, carbon dioxide or pressure readings. If the air is the problem, "
            "follow the cabin emergency procedure and put on masks.",
            "Help the person sit upright and stay calm; loosen tight clothing.",
            "Measure oxygen saturation and heart rate. If saturation is below 90%, give oxygen as the onboard procedures "
            "describe.",
            "Ask about chest pain, allergy triggers and how fast it started, and note the answers.",
            "If breathing stops or the person stops responding, start CPR.",
            CONTACT_SURGEON,
        ],
    },
    "chest-pain": {
        "title": "Chest pain",
        "goal": "Rest, measure, and get the Crew Medical Officer involved quickly; be ready for CPR.",
        "steps": [
            "Stop all activity. Help the person rest in the position they find easiest (sitting up often helps). Keep them calm.",
            ALERT_CREW,
            "Measure heart rate, blood pressure and oxygen saturation. Repeat every 5 minutes and write down the times.",
            "Ask and note: when did it start? Pressure, tightness or sharp? Does it spread to the arm, jaw or back? "
            "Short of breath, sweating, sick? Worse when breathing in or pressing on the chest?",
            "Follow the onboard procedure for chest pain. Give medicines only as that procedure or the flight surgeon says.",
            "If they stop responding or stop breathing normally, start CPR at once.",
            CONTACT_SURGEON,
        ],
    },
    "stroke": {
        "title": "Signs of a stroke",
        "goal": "Recognise it fast and note the time: treatment options depend on it.",
        "steps": [
            ALERT_CREW,
            "Check FAST: Face (ask them to smile: does one side droop?), Arms (raise both: does one drift down?), "
            "Speech (slurred or strange?), Time (note when it started or when they were last normal).",
            "Measure blood sugar: low blood sugar can look like a stroke and is treatable.",
            "Measure blood pressure, heart rate and oxygen saturation.",
            "Give nothing to eat or drink; swallowing may be unsafe.",
            "Keep the person secured and comfortable; if they stop responding, follow the 'not responding' guide.",
            CONTACT_SURGEON,
        ],
    },
    "seizure": {
        "title": "Seizure",
        "goal": "Prevent injury while it happens and protect the airway afterwards.",
        "steps": [
            ALERT_CREW,
            "Note the time it started.",
            {
                "microgravity": "Do not hold the person tightly. Guide them loosely away from hard surfaces and "
                                "equipment, and shield the head.",
                "partial": "Do not hold the person down. Move hard objects away and cushion the head.",
                "earth": "Do not hold the person down. Move hard objects away and cushion the head.",
            },
            "Never put anything in their mouth.",
            "If it lasts more than 5 minutes or another starts, follow the onboard procedure and treat it as an emergency.",
            "Afterwards, keep the airway clear (recovery position if there is gravity), check breathing and blood sugar.",
            CONTACT_SURGEON,
        ],
    },
    "head-injury": {
        "title": "Head injury",
        "goal": "Spot signs that it is getting worse.",
        "steps": [
            "Stop activity and rest. No exercise or critical tasks today.",
            "Tell the Crew Medical Officer.",
            "Check every 15 minutes for the first hour: alertness, confusion, worsening headache, vomiting, unequal "
            "pupils, weakness. Any of these makes it an emergency.",
            "Treat cuts with gentle pressure and a clean dressing.",
            CONTACT_SURGEON,
        ],
    },
    "abnormal-vitals": {
        "title": "Dangerous vital sign",
        "goal": "Check the reading is real, then act on it.",
        "steps": [
            ALERT_CREW,
            "Measure again straight away, carefully (see the how-to guide). A loose finger clip or cuff gives false readings.",
            "If oxygen saturation is still below 90%: sit upright, check the cabin air, give oxygen as the onboard procedures describe.",
            "If blood sugar is very low and the person can swallow safely: give fast sugar (juice, glucose gel) as the procedures describe.",
            "If they feel faint with low blood pressure: lie them down (or secure them) and raise the legs if there is gravity.",
            "Keep measuring every 5 minutes and write the readings down.",
            CONTACT_SURGEON,
        ],
    },
    "monitor": {
        "title": "No red flags right now",
        "goal": "Measure, watch, and do not ignore it.",
        "steps": [
            "Measure a full set of vitals: heart rate, blood pressure, temperature, oxygen saturation, blood sugar.",
            "Log symptoms in the daily check-in and measure again in 15 minutes.",
            "Tell the Crew Medical Officer. If anything gets worse, come back to this guide.",
        ],
    },
}


def steps_for(protocol_id, environment):
    """The steps of a guide as plain strings, for one environment ("microgravity", "partial", "earth")."""
    steps = []
    for step in PROTOCOLS[protocol_id]["steps"]:
        if isinstance(step, dict):
            steps.append(step[environment])
        else:
            steps.append(step)
    return steps
