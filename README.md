# OrbitFit

**Health self-monitoring for astronauts. Works fully offline.**

NASA Space Apps Challenge 2026 · *Create Health Monitoring Software for Astronauts on Space Missions*

Halfway to Mars, the doctors on Earth are minutes away and sometimes out of contact. Astronauts are not doctors.
OrbitFit helps a crew measure their own health, understand what the numbers mean, act early, and handle an
emergency step by step, with nothing but a laptop or tablet and its camera.

> Prototype decision-support tool. Not a medical device. Thresholds are demonstration values, not clinically validated.

## What it does

| Page | For | What it gives |
|---|---|---|
| **Today** | Astronaut | Status (● NOMINAL / ▲ WATCH / ■ ACT), today's routine and streak, then 1 · Check-in, 2 · Vitals, 3 · Workout (camera), 4 · My status |
| **Emergency** | Any crew member | A few yes/no questions → priority and step-by-step guides (CPR, chest pain, breathing, bleeding, stroke, seizure, allergy, head injury), adapted to microgravity, Moon/Mars or Earth |
| **Health guides** | Astronaut | A clickable body figure with each area's status, and how to measure every indicator, why it matters in space, what is normal, and what to do if it is not |
| **Crew Medical Officer** | CMO | Crew overview with a mission-day replay, trend charts against each person's baseline, alerts, alert log, notes, CSV export/import |
| **Downlink to Earth** | Astronaut | A 6 KB summary packet, queued until a comms window opens, with delay, blackouts, acknowledgement and retry (simulated) |
| **Earth receiver** | Flight surgeon | The ground side: received packets, crew summaries, trends joined from several packets |
| **About / Sources** | Judges | How it works, the measured benchmark, limitations, NASA references |

**Measurements**

- **Camera workout:** knee angle from 3D pose points, rep counting (down, bottom, up), depth, tempo, left/right
  difference, confidence, a form score (green / amber / red) and one plain cue ("Good depth", "Go deeper",
  "Lower more slowly").
- **Battery saving:** the pose model runs on about 1 frame in 7, and on every frame for 300 ms at the top and
  bottom of each rep.
- **Daily check-in:** sleep, fatigue, pain (with location) and stress.
- **Vital signs:** resting heart rate, blood pressure, temperature, blood sugar and oxygen saturation. Each comes
  with a how-to guide.

**Health rules**

- **Personal baseline:** the median of a person's first 3 valid sessions.
- **Exercise trends:** depth decline, slower lifting, rising asymmetry, rising variability, adherence.
- **Check-in rules:** pain, poor recovery, stress, and knee pain combined with rising asymmetry.
- **Vital signs:** normal ranges, plus a resting heart rate rising above the person's own baseline.
- **Every alert says** what changed, why it matters in space (with a NASA source) and what to do. All thresholds
  are in one file: [config/health_rules.py](config/health_rules.py).

**Gravity:** the exercise plan (simulated device load, tempo, weekly volume) and the emergency steps change with
the location: Earth, ISS, deep-space transit, Moon, Mars or a custom gravity.

**Logbook**

- **Crash-proof:** every rep is written to SQLite the moment it ends. An unfinished set is offered for resume.
- **CSV:** export, and import as a merge that never overwrites. The first 28 columns are the original OrbitFit
  web app's.
- **Live CSV file:** a CSV file on disk can also receive every rep as it happens.

**Demo data:** 3 made-up crew members × 30 days, so the app is useful on the first start.

- **Rivera** is slowly getting weaker: WATCH, then ACT.
- **Okafor** stays normal.
- **Tanaka** has rising left/right asymmetry with knee pain.

## Install and run (Windows)

You need **Python 3.11 or 3.12** ([python.org](https://www.python.org/downloads/)). The first install needs
internet once; after that everything runs offline.

**Easiest:** double-click `start.bat`. It sets everything up on the first run and opens the app.

**By hand**, in PowerShell inside this folder:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. It only listens on this computer; no data is served to the network and
no usage statistics are sent.

> If PowerShell refuses to run `Activate.ps1`, skip it and call the venv's Python directly:
> `.venv\Scripts\python.exe -m streamlit run app.py`.

### Try it in two minutes

1. **Today → 3 · Workout → ▶ Demo Mode.** A sample squat video plays; reps are counted and saved as they happen.
2. **Location (top of the page) → Moon.** The plan card on the Workout tab changes (weight, tempo, volume).
3. **Emergency:** answer "Chest pain? → Yes". Then try "not responding / not breathing" with the location on
   ISS, then on the Moon: the CPR steps change.
4. **Health guides:** with Cmdr. Rivera selected, click the knees and the heart.
5. **Crew Medical Officer:** drag the mission-day slider back to day 8 and forward to day 30.
6. **Downlink to Earth:** open **Earth receiver** in a second browser tab. Queue a packet, then press
   *Open a comms window* and watch it travel and get confirmed.

## Tests

```powershell
python -m pytest -q
```

287 tests cover:

- **Engine:** pose math, rep detector, form scoring, frame sampler, gravity engine, all health and vitals rules,
  emergency triage, alert log.
- **Data:** demo data, CSV round trip, logbook, live file.
- **Downlink:** retry, blackout and duplicates.
- **Everything else:** the real pose model on the demo clip, every page rendering, and the wording and offline rules.

## Other commands

| Command | What it does |
|---|---|
| `python -m pose.preview` | Camera tracker in a plain window on the demo clip (`webcam` or a file path as argument) |
| `python -m pose.benchmark` | Every-frame vs battery-saving mode on the demo clip: model calls and rep counts |

## Settings

| Setting | How |
|---|---|
| Health thresholds | Edit [config/health_rules.py](config/health_rules.py) |
| Logbook file | `ORBITFIT_DB` (default `var/orbitfit.db`) |
| Pose model file | `ORBITFIT_POSE_MODEL` (default `assets/models/pose_landmarker_lite.task`, included) |
| Simulated link and Earth inbox | `ORBITFIT_LINK_DB`, `ORBITFIT_EARTH_DB` (default in `var/`) |
| Start again with fresh demo data | Crew Medical Officer → Logbook data → Reset demo data |

## Folders

| Folder | Contents |
|---|---|
| `engine/` | Rep detector, form scoring, frame sampler, gravity engine, health, check-in and vitals rules, emergency triage, alert log, downlink queue |
| `config/` | All thresholds |
| `db/` | SQLite logbook, CSV import/export, live CSV file |
| `pose/` | MediaPipe loader, camera tracker, overlay, session recorder, video source, benchmark, preview |
| `downlink/` | Packet builder and checks, queue/link/Earth stores, sender, Earth receiver |
| `guidance/` | Measurement guides, body map, daily routine, sources |
| `pages/`, `ui/` | Streamlit pages and shared widgets |
| `data/` | Crew, locations, demo data, CSV format |
| `assets/` | Pose model and demo clip (bundled, so nothing is downloaded at run time) |
| `tests/` | pytest tests |

## How NASA resources are used

The health indicators, the "why it matters in space" text on every alert and guide, and the exercise model are
based on NASA Human Research Program risk pages. These include muscle, bone, cardiovascular, immune, food and
nutrition, hypoxia, CO2, sleep, behavioural health and in-flight medical conditions. They also draw on NASA
technical reports on ISS exercise countermeasures. Each alert and guide links to its source. NASA's Open Science
Data Repository (OSDR) is named in the challenge as a source of real spaceflight biology data. OrbitFit does not
load an OSDR dataset at run time; its demo crew data is synthetic and generated on the device. Full list:
[guidance/sources.py](guidance/sources.py) and the Sources page.

## Limitations

- Prototype, not a medical device. Thresholds are demonstration values.
- Camera estimates depend on placement, light and clothing. The camera measures squat and deadlift; heel raise
  has a plan but is not measured.
- On the 24 fps demo clip, battery saving cuts model calls by 72-76% with the same rep count (80% at 30 fps).
- Vital signs are typed in; OrbitFit does not connect to medical devices.
- The exercise device load, the Earth link and the demo crew are simulated.
- The emergency guides follow common first-aid steps and never replace the onboard medical procedures, the Crew
  Medical Officer or the flight surgeon.

## Credits

- **Pose model:** MediaPipe Pose Landmarker (lite) by Google, CC BY 4.0.
- **Demo clip:** "A Woman Doing Squats" by Julia Larson, via Pexels (Pexels License).
- **CPR steps:** follow the 2025 American Heart Association guidelines.

## Team and licence

Syed Hassaan Areeb Kazmi (Team Owner), Azam Tariq (Developer), Eman Fatima (UI/UX Designer),
Mohammad Bin Javed, Hudebia. MIT License, see [LICENSE](LICENSE).
