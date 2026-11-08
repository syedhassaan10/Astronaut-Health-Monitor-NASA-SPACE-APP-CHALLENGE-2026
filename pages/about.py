"""About: problem, solution, hazards, how it works, benchmark, limitations, claims we avoid, team."""

import streamlit as st

from ui import state, theme

from config.health_rules import HEALTH_RULES
from engine.adaptive_sampler import DEFAULT_SAMPLER

state.page_start()

theme.page_header("About OrbitFit", "What it does, how it works, what it does not claim, and who built it.")

st.subheader("The problem")
st.write(
    "NASA Space Apps Challenge 2026, \"Create Health Monitoring Software for Astronauts on Space Missions\". "
    "Long missions expose astronauts to radiation, isolation and confinement, altered gravity and a closed, hostile "
    "environment. Halfway to Mars, the ground is minutes away and sometimes out of contact. Astronauts are not "
    "doctors, yet they carry much of the responsibility for noticing changes in themselves, and for acting when a "
    "crewmate suddenly becomes ill."
)

st.subheader("What OrbitFit does")
st.markdown(
    "- **Measures**: the laptop or tablet camera measures every squat (depth, tempo, left-right balance); a 30-second "
    "daily check-in records sleep, fatigue, pain and stress; vital signs (heart rate, blood pressure, temperature, "
    "blood sugar, oxygen saturation) are entered with step-by-step how-to guides.\n"
    "- **Explains**: each value is compared with a normal range or with the person's own baseline, and shown as "
    "● NOMINAL, ▲ WATCH or ■ ACT, always with what changed, why it matters in space, and what to do.\n"
    "- **Guides emergencies**: a few yes/no questions give a priority and step-by-step guides (CPR, chest pain, "
    "breathing, bleeding, stroke, seizure, allergy, head injury), adapted to microgravity, Moon/Mars or Earth.\n"
    "- **Reminds**: the header shows what is still to do today; a streak counts days with the full routine done.\n"
    "- **Adapts to the place**: the exercise plan and the emergency steps change with gravity (Earth, ISS, transit, "
    "Moon, Mars, custom).\n"
    "- **Works offline**: everything runs on the computer; the logbook is a local SQLite file."
)

st.subheader("Hazards addressed")
st.markdown(
    "- **Altered gravity**: gravity-scaled exercise plan; joint angles from 3D landmarks, so 'up' does not matter.\n"
    "- **Isolation and confinement**: daily check-in, stress and recovery alerts.\n"
    "- **Distance from Earth**: all analysis on the device; emergency guidance that does not need the ground; a "
    "simulated downlink with delay, blackouts and acknowledgements.\n"
    "- **Closed environment**: oxygen saturation and cabin-air checks in the emergency guides.\n"
    "- **Radiation**: daily dose from each person's dosimeter, a shelter alert for a solar storm, and the "
    "mission total against NASA's 600 mSv career limit."
)

st.subheader("How it works")
st.markdown(
    f"- **Measurement**: MediaPipe pose (lite model, bundled) gives 3D body points. A rep is top → bottom → top with "
    f"a gap between thresholds so jitter cannot create reps; 'top' is learned from each person's standing angle.\n"
    f"- **Battery saving**: the pose model runs on 1 frame in {DEFAULT_SAMPLER.base_stride}, plus every frame for "
    f"{DEFAULT_SAMPLER.burst_ms:g} ms at the top and bottom of each rep.\n"
    f"- **Baselines**: the median of a person's first {HEALTH_RULES.baseline_sessions} valid sessions; sessions with "
    f"fewer than {HEALTH_RULES.min_valid_reps} valid reps or low camera confidence never count.\n"
    "- **Rules**: depth decline, slower lifting, rising left-right difference, rising variability, adherence, "
    "pain, recovery, stress, knee pain with rising asymmetry, vital-sign ranges and a rising resting heart rate. "
    "Several WATCH rules at once escalate to ACT. All thresholds are in one file: config/health_rules.py."
)

st.subheader("Battery-saving benchmark (measured)")
st.write("Measured on 6 November 2026 on the development laptop, bundled demo clip (24 fps), same rep count in both modes:")
st.table({
    "Run": ["Demo clip, 1 play (10 s)", "Demo clip, 3 loops (30 s)", "Demo clip, 6 loops (60 s)",
            "Simulated 30 fps camera (test)"],
    "Model calls saved": ["75.8%", "74.2%", "72.5%", "80.0%"],
    "Reps (both modes)": ["3", "11", "23", "8"],
})
st.caption("At 24 fps a 300 ms burst costs more frames than with a 30 fps webcam, so the saving on the clip is "
           "around the 75% target rather than clearly above it. Run it yourself: python -m pose.benchmark")

state.demo_evidence_section()

st.subheader("Limitations")
st.markdown(
    "- Prototype, not a medical device. Thresholds are demonstration values, not clinically validated or tested "
    "with astronauts.\n"
    "- Camera estimates depend on placement, light and clothing; pose estimation can be wrong when limbs are hidden.\n"
    "- The camera measures squat and deadlift; heel raise has a plan but is not measured yet.\n"
    "- The exercise device load is simulated. The Earth link is simulated.\n"
    "- Vital signs are typed in by the crew; OrbitFit does not connect to medical devices.\n"
    "- The demo crew data is synthetic (its trends follow NASA figures, see above).\n"
    "- The emergency guides follow common first-aid steps; they do not replace the onboard medical procedures."
)

st.subheader("Claims we avoid")
st.markdown(
    "- **No diagnosis.** OrbitFit never says a person has a condition; it says a value or trend moved and what to do.\n"
    "- **No bone density or muscle mass numbers.** A camera cannot measure them.\n"
    "- **No medicine doses.** Medicines are given only as the onboard procedures or the flight surgeon say."
)

st.subheader("Team")
st.write("Built for the NASA Space Apps Challenge 2026 by Syed Hassaan Areeb Kazmi (Team Owner), Azam Tariq "
         "(Developer), Mohammad Bin Javed (Developer), Hudebia Shaikh (Developer) and Eman Fatima (UI/UX Designer).")

state.footer()
