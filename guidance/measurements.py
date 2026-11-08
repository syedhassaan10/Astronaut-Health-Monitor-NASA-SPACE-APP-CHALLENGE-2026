"""How to take each measurement, why it matters in space, what is normal, and what to do
when a value does not look normal. Written for crew who are not doctors.

Normal ranges are read from config/health_rules.py, so the guide and the alerts always agree.
They are demonstration values for a resting adult, not clinically validated.
"""

from dataclasses import dataclass, field

from config.health_rules import HEALTH_RULES
from engine.vitals_rules import normal_band_text


@dataclass(frozen=True)
class MeasurementGuide:
    id: str
    title: str
    unit: str
    equipment: str
    how_to: list                 # numbered steps
    why_space: str               # why it matters in spaceflight
    normal: str                  # plain normal range
    if_high: str = ""
    if_low: str = ""
    call_cmo_when: str = ""
    environment_notes: dict = field(default_factory=dict)  # microgravity / partial / earth
    source_id: str = ""


def _v():
    return HEALTH_RULES.vitals


def _bp_normal():
    v = _v()
    return (f"Top number {v.systolic.watch_low:g}-{v.systolic.watch_high:g} mmHg and bottom number "
            f"{v.diastolic.watch_high:g} mmHg or less.")


def measurement_guides():
    v = _v()
    return [
        MeasurementGuide(
            id="heart_rate", title="Resting heart rate", unit="beats per minute (bpm)",
            equipment="Your fingers and a clock, or the pulse oximeter.",
            how_to=[
                "Best time: just after waking, before getting up or drinking coffee. Otherwise rest quietly for 5 minutes first.",
                "Turn one hand palm up. Put the tips of your index and middle fingers on the thumb side of the wrist, "
                "just below the base of the thumb. Press lightly until you feel the beat.",
                "Count the beats for 30 seconds and multiply by 2. If the beat feels irregular, count for a full 60 seconds.",
                "Or clip the pulse oximeter on a finger, keep still, and read the pulse number once it is steady.",
                "Write it down in Vitals. Measure at the same time each day so the trend means something.",
            ],
            why_space="In weightlessness body fluids move towards the head and the heart and blood vessels adapt. "
                      "A resting rate that climbs over days can mean lost fitness, poor sleep, stress, dehydration or "
                      "the start of an illness.",
            normal=f"{normal_band_text(v.heart_rate, 'bpm')} at rest. Fit people can be lower.",
            if_high="Rest 5 more minutes and measure again. Think: just exercised, coffee, stress, fever, too little fluid? "
                    "Drink water, check your temperature.",
            if_low="If you feel fine and are very fit, a low rate can be normal for you. If you feel dizzy, faint or "
                   "short of breath, tell the Crew Medical Officer now.",
            call_cmo_when=f"Above {v.heart_rate.act_high:g} or below {v.heart_rate.act_low:g} at rest, an irregular beat, "
                          "or with chest pain, fainting or breathlessness (use the Emergency page).",
            source_id="hrp-cardio",
        ),
        MeasurementGuide(
            id="blood_pressure", title="Blood pressure", unit="mmHg (top / bottom number)",
            equipment="Automatic arm cuff from the medical kit.",
            how_to=[
                "Rest for 5 minutes. No exercise in the last 30 minutes, no coffee in the last 30 minutes.",
                "Sit with your back supported and feet flat (in microgravity: secure yourself with foot or thigh "
                "restraints so you are still).",
                "Put the cuff on your bare upper arm, its lower edge 2-3 cm above the elbow crease, the tube or arrow "
                "over the inside of the arm. It should fit snugly, with room for one finger.",
                "Rest the arm so the cuff is level with your heart. Do not talk or move while it measures.",
                "Take 2 readings 1 minute apart and record the average of both.",
            ],
            why_space="Spaceflight changes how the heart and vessels control pressure. Low pressure can cause dizziness "
                      "or fainting, especially when gravity returns (landing, Moon, Mars). High pressure strains the heart "
                      "and vessels over a long mission.",
            normal=_bp_normal(),
            if_high="Rest 5 more minutes and repeat. Pain, stress, a full bladder and a cuff that is too small all raise "
                    "the reading.",
            if_low="If you feel light-headed: lie down (or secure yourself) and raise your legs if there is gravity. Drink "
                   "fluids. Do not stand up quickly.",
            call_cmo_when=f"Top number above {v.systolic.act_high:g} or below {v.systolic.act_low:g}, bottom number above "
                          f"{v.diastolic.act_high:g}, or any reading with headache, chest pain, confusion or fainting.",
            environment_notes={
                "microgravity": "There is no 'down', but keep the cuff level with the heart anyway; the device is set up for that.",
                "partial": "On the Moon or Mars, stand up slowly after a reading: blood pressure control has to re-adapt to gravity.",
            },
            source_id="hrp-cardio",
        ),
        MeasurementGuide(
            id="temperature_c", title="Body temperature", unit="°C",
            equipment="Digital thermometer (mouth or ear).",
            how_to=[
                "Wait 30 minutes after exercise, and 15 minutes after eating or drinking (for a mouth reading).",
                "Mouth: put the tip under the tongue, to one side, close your lips and breathe through the nose until it beeps.",
                "Ear: gently pull the ear up and back to straighten the canal, insert the tip snugly, press the button.",
                "Use the same method each time and write down the reading.",
            ],
            why_space="The immune system changes in spaceflight and dormant viruses can reactivate. In a small closed "
                      "cabin an infection can spread to the whole crew, so a fever is worth catching early.",
            normal=normal_band_text(v.temperature_c, "°C"),
            if_high="Rest, drink fluids, and measure again in 30 minutes. Note other symptoms (cough, sore throat, rash). "
                    "Limit close contact with crewmates until the Crew Medical Officer advises.",
            if_low="Warm up (clothing, sleeping bag, warm drink) and measure again. Check the cabin temperature.",
            call_cmo_when=f"Above {v.temperature_c.act_high:g} °C or below {v.temperature_c.act_low:g} °C, or a fever "
                          "with confusion, stiff neck, trouble breathing or a rash.",
            source_id="hrp-immune",
        ),
        MeasurementGuide(
            id="glucose_mg_dl", title="Blood sugar", unit="mg/dL",
            equipment="Glucose meter, test strip and a fresh lancet.",
            how_to=[
                "Note the time since you last ate (fasting = 8 hours or more).",
                "Wash and dry your hands. Put a strip in the meter.",
                "Prick the side of a fingertip with a fresh lancet.",
                "Touch the strip to the drop and wait for the number.",
                "Put the used lancet straight into the sharps container.",
            ],
            why_space="Diet, exercise load, stress and sleep all change blood sugar. Low sugar can cause shakiness, "
                      "confusion or fainting during a critical task; high sugar over time harms health.",
            normal=normal_band_text(v.glucose_mg_dl, "mg/dL") + " (fasting values are usually at the lower end).",
            if_high="Measure again in 1-2 hours. Drink water. Note what and when you last ate.",
            if_low="If you can swallow safely, take fast sugar now (juice, glucose gel), wait 15 minutes, measure again. "
                   "Then eat a proper snack.",
            call_cmo_when=f"Below {v.glucose_mg_dl.act_low:g} or above {v.glucose_mg_dl.act_high:g}, or low sugar with "
                          "confusion or drowsiness (the person must not be left alone).",
            environment_notes={
                "microgravity": "Blood does not drip: the drop stays on the finger as a dome. Touch the strip to it. "
                                "Keep a wipe ready so no droplet floats away.",
            },
            source_id="hrp-nutrition",
        ),
        MeasurementGuide(
            id="spo2_pct", title="Oxygen saturation", unit="%",
            equipment="Finger pulse oximeter.",
            how_to=[
                "Warm your hands if they are cold. Remove nail polish from that finger.",
                "Clip the oximeter on the index or middle finger, nail up.",
                "Keep the hand still and relaxed (rest it on your chest or a surface) for 30 seconds.",
                "Read the number once it has stopped changing. Check that the pulse it shows matches your own count.",
            ],
            why_space="This shows how well the lungs load oxygen into the blood. A drop can come from the lungs or heart, "
                      "or from a problem with the cabin air (low oxygen, high carbon dioxide).",
            normal=normal_band_text(v.spo2_pct, "%"),
            if_low="First re-check: warm the hand, keep still, try another finger. If it is still low, check the cabin air "
                   "readings and alarms, sit upright and breathe slowly. Ask a crewmate to measure themselves too: if "
                   "everyone is low, it is the air.",
            call_cmo_when=f"Below {v.spo2_pct.act_low:g}% (use the Emergency page), or any drop with breathlessness, "
                          "chest pain or confusion.",
            source_id="hrp-hypoxia",
        ),
        MeasurementGuide(
            id="radiation_msv", title="Radiation dose", unit="mSv",
            equipment="Your personal dosimeter (the badge or active dosimeter you wear).",
            how_to=[
                "Wear the dosimeter all day, including while you sleep.",
                "Each morning, read the dose for the last 24 hours (or subtract yesterday's total from today's total).",
                "Enter that daily dose in mSv. Leave it empty if you could not read it.",
                "During a solar storm warning, read it every hour and follow the shelter procedure.",
            ],
            why_space="Outside Earth's magnetic field the crew is exposed to cosmic rays all the time and to solar "
                      "particle events now and then. Radiation adds to the long-term risk of cancer, and NASA limits "
                      f"each astronaut's career dose to {v.radiation_career_limit_msv:g} mSv.",
            normal=f"Up to {v.radiation_msv.watch_high:g} mSv a day (deep-space background is about 1.8 mSv a day; "
                   "on the ISS it is much lower).",
            if_high="Read the dosimeter again and compare with your crewmates. If everyone is high, it is the "
                    "environment: follow the solar storm (shelter) procedure.",
            call_cmo_when=f"Above {v.radiation_msv.act_high:g} mSv in a day, a solar storm warning, or a mission total "
                          f"above {v.mission_dose_msv.watch:g} mSv.",
            environment_notes={
                "microgravity": "In the spacecraft, the storm shelter is the most shielded area (often surrounded by "
                                "water and supplies).",
                "partial": "On the Moon or Mars, the habitat and the ground block half the sky; outside, return to "
                           "the habitat when a solar storm is warned.",
            },
            source_id="nasa-std-3001",
        ),
        MeasurementGuide(
            id="checkin", title="Daily check-in (sleep, fatigue, pain, stress)", unit="0-10 scales",
            equipment="Nothing. About 30 seconds.",
            how_to=[
                "Answer at the same time each day, ideally after waking up.",
                "Sleep: 0 = very poor, 10 = excellent. Fatigue: 0 = fresh, 10 = exhausted.",
                "Pain: 0 = none, 10 = worst imaginable. If above 0, choose where it hurts.",
                "Stress / mood: 0 = calm, 10 = very stressed or low.",
                "Be honest: the trend only helps if the numbers are real. Nobody sees a single day's answer as a test.",
            ],
            why_space="Sleep loss, isolation and confinement affect health and performance. They can also make exercise "
                      "measurements look worse, so the app shows them as context next to exercise trends.",
            normal="Sleep 5 or more, fatigue below 7, pain 0-3, stress below 8 most days.",
            call_cmo_when="Pain of 7 or more, poor sleep with high fatigue for 2 of 3 days, or high stress for 2 of 3 days.",
            source_id="hrp-sleep",
        ),
        MeasurementGuide(
            id="workout", title="Camera workout (squat measurement)", unit="knee angle in degrees, seconds",
            equipment="Laptop or tablet camera. No wearables.",
            how_to=[
                "Place the camera 1.5-2 m away, at hip height, so your whole body from hips to ankles is in view. "
                "Side or front view both work.",
                "Use good light from the front, not a bright window behind you. Wear clothes that show the knees.",
                "Stand still for 2 seconds so the app learns your standing knee angle, then start.",
                "Follow the tempo on the plan card: lower slowly, pause at the bottom (at low gravity), stand up under control.",
                "Watch the big cue: 'Good depth', 'Go deeper', 'Lower more slowly'. If you see 'Measurement unreliable', "
                "move the camera so your legs are fully visible.",
            ],
            why_space="Without gravity, muscles and bones are barely loaded and weaken unless you exercise hard. Small "
                      "changes in depth, speed and left/right balance can show weakening or pain before you notice it.",
            normal="Depth at or below 100° knee angle for a squat; left/right difference under 5°; tempo close to the plan.",
            call_cmo_when="The app shows ACT for an exercise trend, or you have knee pain while squatting.",
            environment_notes={
                "microgravity": "Squats are done on the resistive device (ARED) with a harness. Fix the tablet with "
                                "velcro so it does not drift; the camera angle must stay the same each session.",
                "partial": "On the Moon or Mars, the simulated load adds back part of the missing body weight.",
            },
            source_id="hrp-muscle-bone",
        ),
    ]


def guide_by_id(guide_id):
    for g in measurement_guides():
        if g.id == guide_id:
            return g
    return None
