"""References and credits. Every URL was opened and checked on 6 November 2026."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    organization: str
    url: str
    used_for: str


NASA_SOURCES = [
    Source("hrp-hazards", "5 Hazards of Human Spaceflight", "NASA Human Research Program",
           "https://www.nasa.gov/hrp/hazards/",
           "Frames the problem. OrbitFit addresses altered gravity, isolation and confinement, distance from Earth, "
           "and (through oxygen saturation and the cabin-air checks in the emergency guide) the closed environment. "
           "It does not measure radiation."),
    Source("hrp-muscle-bone",
           "Risk of Reduced Physical Performance Capabilities Due to Reduced Muscle Size, Strength, and Endurance (Muscle Risk)",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/muscle-risk/",
           "Why unloading reduces muscle size, strength and endurance, and why countermeasure exercise is needed. "
           "Basis for the gravity-scaled exercise plan and the movement trend rules."),
    Source("hrp-bone", "Risk of Bone Fracture due to Spaceflight-induced Changes to Bone",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/risk-of-bone-fracture-due-to-spaceflight-induced-changes-to-bone/",
           "Bone loss context for the body map. OrbitFit does NOT estimate bone density."),
    Source("hrp-cardio",
           "Risk of Cardiovascular Adaptations Contributing to Adverse Mission Performance and Health Outcomes (CV Risk)",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/cv-risk/",
           "Why heart rate and blood pressure are tracked, and why fluid shifts and deconditioning change them."),
    Source("hrp-immune",
           "Risk of In Mission Impacts, Adverse Health Events or Long-Term Health Impacts due to Altered Immune Response (Immune Risk)",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/immune-risk/",
           "Why body temperature (fever) is a useful early sign in a closed crew cabin."),
    Source("hrp-nutrition",
           "Risk of Inadequate Food and Nutrition Causing Decrements in In-Mission Health and Performance and Long-term Health",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/food-and-nutrition-risk/",
           "Why blood sugar is tracked next to exercise load and sleep."),
    Source("hrp-hypoxia", "Risk of Reduced Crew Health and Performance Due to Hypoxia",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/risk-of-reduced-crew-health-and-performance-due-to-hypoxia/",
           "Why oxygen saturation is measured and why a low reading starts with a cabin-air check."),
    Source("hrp-co2", "Risk of Nominal Acute and Chronic Ambient Carbon Dioxide Exposure in Crewed Vehicles (CO2 Risk)",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/carbon-dioxide-risk/",
           "Why the breathing-difficulty guide asks the crew to check the cabin air first."),
    Source("hrp-medical",
           "Risk of Adverse Health Outcomes and Decrements in Performance due to Inflight Medical Conditions",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/risk-of-adverse-health-outcomes-and-decrements-in-performance-due-to-inflight-medical-conditions/",
           "Why the crew needs step-by-step emergency guidance when the ground is minutes away or out of contact."),
    Source("hrp-sleep",
           "Risk of Performance Decrements and Adverse Health Outcomes Resulting from Sleep Loss, Circadian "
           "Desynchronization, and Work Overload",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/risk-of-performance-decrements-and-adverse-health-outcomes-resulting-from-sleep-loss-circadian-desynchronization-and-work-overload/",
           "Why the daily check-in tracks sleep and fatigue, and uses them as context for exercise trends."),
    Source("hrp-behavioral", "Behavioral Health Risk",
           "NASA Human Research Program (Human Health and Performance)",
           "https://www.nasa.gov/directorates/esdmd/hhp/behavioral-health-risk/",
           "Isolation and confinement: why the check-in tracks stress and mood."),
    Source("iss-exercise", "Human Research Program Advanced Exercise Concepts (AEC) Overview (Perusek et al., 2015)",
           "NASA, via NASA Technical Reports Server", "https://ntrs.nasa.gov/citations/20160012339",
           "The ISS exercise hardware used as the model (ARED, T2, CEVIS). Basis for the ARED maximum (~272 kg)."),
    Source("iss-exercise-2024",
           "Effects of Replacing Treadmill Running with Alternative Exercise Countermeasures During Long-Duration "
           "Spaceflight (Varanoske et al., 2024)",
           "NASA, via NASA Technical Reports Server", "https://ntrs.nasa.gov/citations/20240000929",
           "Recent evidence comparing ISS exercise countermeasure devices."),
    Source("osdr", "NASA Open Science Data Repository (OSDR) – Biological and Physical Sciences data",
           "NASA Science", "https://science.nasa.gov/biological-physical/data/",
           "Named in the challenge as a source of real spaceflight biology data for inspiration and testing. "
           "OrbitFit does not load any OSDR dataset at run time; its demo data is synthetic."),
]

OTHER_SOURCES = [
    Source("aha-cpr", "2025 American Heart Association Guidelines for CPR and ECC", "American Heart Association",
           "https://cpr.heart.org/en/resuscitation-science/cpr-and-ecc-guidelines",
           "Standard adult CPR steps used in the emergency guide (push hard and fast, 100-120 per minute, about 5 cm deep, "
           "30 pushes to 2 breaths if trained, use the defibrillator)."),
]

CREDITS = [
    Source("mediapipe", "MediaPipe Pose Landmarker (pose_landmarker_lite model)", "Google (MediaPipe)",
           "https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker",
           "On-device body pose estimation. The model file ships with the app; no video ever leaves the computer. "
           "Model licence: CC BY 4.0; code: Apache 2.0."),
    Source("demo-video", "Demo Mode clip: “A Woman Doing Squats” (downscaled to 480x854)", "Julia Larson, via Pexels",
           "https://www.pexels.com/video/a-woman-doing-squats-6454275/",
           "Sample exercise video so Demo Mode works without a webcam. Pexels License (free to use). Not a NASA source."),
]

ALL_SOURCES = NASA_SOURCES + OTHER_SOURCES + CREDITS


def source_by_id(source_id):
    for s in ALL_SOURCES:
        if s.id == source_id:
            return s
    return None
