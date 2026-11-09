# Space Apps 2026 project form: draft answers

Draft text for the required fields. Edit freely before submitting. Items in **[brackets]** must be filled in by
the team.

---

## Project name

OrbitFit

## High-level summary

Halfway to Mars, a crew cannot wait minutes for a doctor on Earth, and astronauts are not doctors. OrbitFit is an
offline health self-monitoring app that turns a laptop or tablet into a crew health station.

- **Measures:** the camera measures every squat (depth, tempo, left/right balance), with no wearables. A
  30-second check-in records sleep, fatigue, pain and stress, and step-by-step guides show how to take heart
  rate, blood pressure, temperature, blood sugar and oxygen saturation, and the crew logs the day's radiation
  dose from their dosimeters.
- **Explains:** OrbitFit compares each value with the person's own baseline and shows "All good",
  "Keep an eye on it" or "Needs action". Each result explains why it matters in space, using NASA Human Research
  Program sources, and what to do.
- **Guides emergencies:** a few yes/no questions bring up step-by-step guides for CPR, chest pain, breathing
  problems, bleeding, stroke and more, adapted to microgravity, Moon/Mars or Earth.
- **Forecasts:** a digital twin forecasts fatigue and motion-sickness risk, projects bone loss over the mission
  and estimates daily energy needs.
- **Reminds and connects:** it reminds the crew of their daily routine and sends a compact summary to the flight
  surgeon whenever a comms window opens.

## Project details

**What it does**

- **Today (astronaut):**
  - a status at a glance (shape, word and colour);
  - a daily routine with a streak: check-in, vital signs, camera workout;
  - live workout feedback with a big rep counter and one plain cue ("Go deeper", "Lower more slowly").
- **Emergency:** a triage of yes/no questions plus optional readings gives a priority (Emergency / Urgent /
  Monitor) and tickable step-by-step guides, with notes saved for the Crew Medical Officer.
  - In microgravity the CPR guide starts with securing the patient and bracing yourself.
  - On the Moon or Mars it uses the floor.
- **Health guides:** a clickable body figure. Each body area shows its status, what it does, what spaceflight
  does to it, and how to measure it. Every measurement has how-to steps, why it matters in space, the normal
  range, and what to do if high or low.
- **Crew Medical Officer:**
  - crew overview, with a mission-day replay;
  - trends against each person's baseline;
  - an alert log with acknowledgement, and notes;
  - CSV export/import of the offline logbook.
- **Radiation:** the daily dosimeter dose, a storm-shelter alert for a solar particle event, and the mission total
  against NASA's 600 mSv career limit.
- **Forecast:** Hudebia Shaikh's digital twin (a Monte Carlo of the Borbély sleep model coupled with a vestibular
  model) forecasts fatigue and motion-sickness risk; a bone-loss projection shows the effect of exercise; daily
  energy needs are estimated from body weight.
- **Downlink:** a 6 KB packet waits in a queue for a comms window. A simulated link adds the one-way delay,
  blackouts, acknowledgement and retry. An Earth receiver page plays the flight surgeon.

**How it works**

- **Pose:** MediaPipe pose estimation runs on the device and turns 3D body points into knee angles that do not
  depend on which way is "up".
- **Reps and form:** a rep detector with hysteresis counts reps and measures tempo and left/right asymmetry.
- **Battery saving:** the pose model runs on about 1 frame in 7, plus every frame around each turning point. On
  the demo clip that cuts model calls by about 75% with the same rep count.
- **Health rules:**
  - each person's baseline is the median of their first 3 valid sessions;
  - rules compare recent medians with it (depth, lifting speed, asymmetry, variability, adherence);
  - check-in and vital-sign rules sit alongside, and several WATCH signals together escalate to ACT;
  - all thresholds are in one file.
- **Logbook:** every rep is saved to a local SQLite logbook the moment it ends, so a crash loses nothing.
- **Gravity:** the exercise plan scales with gravity (Earth, ISS, transit, Moon, Mars, custom).

**Benefits:** it works with no internet, no wearables and no ground contact. It is plain language for
non-doctors, never claims a diagnosis, and every simulated part is labelled as simulated.

**Tools:** Python, Streamlit, MediaPipe, OpenCV, SQLite, pandas, Plotly, NumPy, pytest (327 tests).

**Impact beyond space:** the same tool could support people in remote communities or places with little access
to health services.

## Use of NASA data and resources

OrbitFit's choice of health indicators, the "why it matters in space" explanation on every alert and guide, and
its exercise model are based on NASA resources. Each alert and guide links to the page it uses.

- **NASA Human Research Program, 5 Hazards of Human Spaceflight:** frames the problem. OrbitFit addresses
  altered gravity, isolation and confinement, distance from Earth, and the closed environment.
- **NASA HRP human system risk pages:** muscle, bone, cardiovascular, immune, food and nutrition, hypoxia, CO2,
  sleep, behavioural health and in-flight medical conditions. They define what is measured, why it matters, and
  when to act.
- **NASA Technical Reports Server:**
  - Advanced Exercise Concepts overview (Perusek et al., 2015) for the ARED exercise device model (about 272 kg
    maximum);
  - Varanoske et al. (2024) on exercise countermeasures.
- **NASA figures that shape the demo data:** the demo crew is synthetic (no real astronaut data), but its
  trends follow published NASA figures, with a 6-month mission squeezed into 30 demo days:
  - up to 30% leg strength loss on long missions without enough exercise, and a 9% average lower-body loss
    with the ARED device (NASA/SP-20250000273, January 2025, pp. 5 and 23);
  - NASA-STD-3001's rule to keep at least 80% of baseline strength (same report, p. 16);
  - 1-1.5% bone density loss per month at the hip and spine (NASA HRP Bone Fracture Evidence Report, July 2024,
    p. 10), shown on the body map and used as the default of the bone-loss projection on the Forecast page.
- **Radiation limits:** NASA-STD-3001 career limit of 600 mSv and 250 mSv per solar particle event (NASA OCHMO
  technical brief OCHMO-TB-020), and the 1.8 mSv a day measured by Curiosity's RAD on the cruise to Mars (NASA JPL,
  30 May 2013). They set the radiation alerts.

  In one sentence: **Demo crew data is synthetic, shaped by NASA evidence; the app also runs a real mission from an
  empty logbook.**
- **NASA Open Science Data Repository (OSDR):** recommended by the challenge for real spaceflight biology data.
  OrbitFit's demo crew data is synthetic and generated on the device. **[If you used an OSDR dataset for testing
  or inspiration, name it here.]**
- **Challenge resources:** the Resources tab opens on 13 November. **[Add any dataset from that list that you
  used.]**

Full list with links: Sources page in the app, and `guidance/sources.py`.

## Space agency partner resources

The challenge is authored by the Brazilian Space Agency (AEB). **[Add any AEB or other partner agency resource
you used, or remove this section.]**

## Repository link

**[GitHub URL]**

## Demo link

https://drive.google.com/file/d/1djFboQ6O8qQLctbERtOGhY7Jhwdl2wvl/view?usp=sharing

## Use of AI tools

**[Fill in as the Space Apps rules require.]**
