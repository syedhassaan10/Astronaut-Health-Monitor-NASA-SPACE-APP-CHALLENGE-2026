"""The flight surgeon packet: what the crew downlinks to Earth in a short comms window.

Compact on purpose (a few KB): a summary for a quick read plus a session-level CSV for
analysis. It carries decision-support estimates, never a diagnosis. The JSON layout matches
the original app's packet (version 1); `latestVitals` and `note` are extra fields.
"""

import json
import math
import re
from dataclasses import dataclass

from config.health_rules import HEALTH_RULES
from data.csv_codec import encode_csv, parse_csv
from data.logbook_csv import num
from engine.change_detection import assess_crew
from engine.session_metrics import summarize_session
from engine.vitals_rules import mission_dose

PACKET_VERSION = 1
DISCLAIMER = ("Decision-support estimates from a prototype tool. Not a diagnosis or a medical device. "
              "Thresholds are demonstration values.")

CSV_COLUMNS = [
    "record", "day", "crewId", "exercise", "reps", "prescribedReps", "depthDeg", "concentricS", "asymmetryDeg",
    "variabilityDeg", "confidence", "sleep", "fatigue", "pain", "painLocation", "stress",
]

MAX_PACKET_CSV_CHARS = 1_000_000
MAX_CREW = 50
MAX_ALERTS_PER_CREW = 100
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def _r4(n):
    """A number rounded to 4 decimals, or an empty cell when it is not a number."""
    if n is None or not math.isfinite(n):
        return ""
    return num(n)


def packet_csv(sessions, checkins, day, window_days, cfg=HEALTH_RULES):
    """One row per session and per check-in in the last `window_days` mission days."""
    rows = [list(CSV_COLUMNS)]

    def in_window(d):
        return day - window_days < d <= day

    chosen = [s for s in sessions if in_window(s.day)]
    chosen.sort(key=lambda s: (s.day, s.crew_id))
    for rec in chosen:
        m = summarize_session(rec, cfg)
        rows.append([
            "session", str(m.day), rec.crew_id, rec.exercise, str(m.completed_reps), str(m.prescribed_reps),
            _r4(m.depth_deg), _r4(m.concentric_s), _r4(m.asymmetry_deg), _r4(m.variability_deg),
            _r4(m.mean_confidence), "", "", "", "", "",
        ])
    chosen_checkins = [c for c in checkins if in_window(c.day)]
    chosen_checkins.sort(key=lambda c: (c.day, c.crew_id))
    for c in chosen_checkins:
        rows.append(["checkin", str(c.day), c.crew_id, "", "", "", "", "", "", "", "",
                     str(c.sleep), str(c.fatigue), str(c.pain), c.pain_location or "", str(c.stress)])
    return encode_csv(rows)


def _latest(items, crew_id):
    mine = [x for x in items if x.crew_id == crew_id]
    mine.sort(key=lambda x: x.day)
    return mine[-1] if mine else None


def _deltas_dict(d):
    if d is None:
        return None
    return {"depthDeg": d.depth_deg, "concentricPct": d.concentric_pct, "asymmetryDeg": d.asymmetry_deg,
            "variabilityDeg": d.variability_deg}


def _clean(value):
    """JSON cannot hold NaN: turn it into None."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def build_packet(sessions, checkins, vitals, crew, day, window_days, packet_id, now_ms, notes=None,
                 cfg=HEALTH_RULES):
    """Build a packet from the logbook. Same input, same packet."""
    notes = notes or {}
    sessions = [s for s in sessions if s.day <= day]
    checkins = [c for c in checkins if c.day <= day]
    vitals = [v for v in vitals if v.day <= day]
    crew_entries = []
    for member in crew:
        a = assess_crew(sessions, member.id, cfg, checkins, vitals)
        latest_checkin = _latest(checkins, member.id)
        latest_vitals = _latest(vitals, member.id)
        crew_entries.append({
            "crewId": member.id, "name": member.name, "role": member.role, "status": a.status,
            "alerts": [{"rule": al.rule, "level": al.level, "title": al.title, "summary": al.what.summary,
                        "exercise": al.exercise, "day": al.day} for al in a.alerts],
            "exercises": [{
                "exercise": e.exercise, "status": e.status,
                "baseline": None if e.baseline is None else {
                    "depthDeg": e.baseline.depth_deg, "concentricS": e.baseline.concentric_s,
                    "asymmetryDeg": e.baseline.asymmetry_deg, "variabilityDeg": e.baseline.variability_deg},
                "deltas": _deltas_dict(e.deltas),
            } for e in a.exercises],
            "latestCheckin": None if latest_checkin is None else {
                "day": latest_checkin.day, "sleep": latest_checkin.sleep, "fatigue": latest_checkin.fatigue,
                "pain": latest_checkin.pain, "painLocation": latest_checkin.pain_location,
                "stress": latest_checkin.stress},
            "latestVitals": None if latest_vitals is None else {
                "day": latest_vitals.day, "heartRate": latest_vitals.heart_rate, "systolic": latest_vitals.systolic,
                "diastolic": latest_vitals.diastolic, "temperatureC": latest_vitals.temperature_c,
                "glucoseMgDl": latest_vitals.glucose_mg_dl, "spo2Pct": latest_vitals.spo2_pct,
                "radiationMsv": latest_vitals.radiation_msv},
            "missionDoseMsv": round(mission_dose(vitals, member.id), 1),
            "note": notes.get(member.id, ""),
        })
    packet = {
        "version": PACKET_VERSION, "id": packet_id, "createdAt": now_ms, "missionDay": day,
        "summary": {"missionDay": day, "windowDays": window_days, "disclaimer": DISCLAIMER, "crew": crew_entries},
        "csv": packet_csv(sessions, checkins, day, window_days, cfg),
    }
    return _clean(packet)


def packet_json(packet):
    """Compact JSON text, as it would cross the link."""
    return json.dumps(packet, separators=(",", ":"), ensure_ascii=False)


def packet_size_bytes(packet):
    return len(packet_json(packet).encode("utf-8"))


def format_kb(n_bytes):
    return f"{n_bytes / 1024:.1f} KB"


# ---- checking untrusted packets -------------------------------------------------------------

def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _is_status(v):
    return v in ("NOMINAL", "WATCH", "ACT")


def parse_packet(value):
    """Strictly check something that claims to be a packet. Returns (packet, None) or (None, error). Never raises."""
    if not isinstance(value, dict):
        return None, "Not a packet: expected an object."
    if value.get("version") != PACKET_VERSION:
        return None, f"Unsupported packet version ({value.get('version')})."
    pid = value.get("id")
    if not isinstance(pid, str) or not ID_PATTERN.match(pid):
        return None, "Packet id is missing or malformed."
    if not _is_number(value.get("createdAt")) or value["createdAt"] <= 0:
        return None, "Packet createdAt is invalid."
    day = value.get("missionDay")
    if not isinstance(day, int) or isinstance(day, bool) or day < 0 or day > 36_500:
        return None, "Packet missionDay is invalid."
    if not isinstance(value.get("csv"), str):
        return None, "Packet csv is missing."
    if len(value["csv"]) > MAX_PACKET_CSV_CHARS:
        return None, "Packet csv is too large."
    summary = value.get("summary")
    if not isinstance(summary, dict) or not isinstance(summary.get("crew"), list):
        return None, "Packet summary is missing."
    if len(summary["crew"]) > MAX_CREW:
        return None, "Packet lists too many crew members."
    for c in summary["crew"]:
        if not isinstance(c, dict) or not isinstance(c.get("crewId"), str) or not isinstance(c.get("name"), str) \
                or not _is_status(c.get("status")):
            return None, "A crew entry in the summary is malformed."
        alerts = c.get("alerts")
        if not isinstance(alerts, list) or len(alerts) > MAX_ALERTS_PER_CREW:
            return None, "A crew entry has invalid alerts."
        for a in alerts:
            if not isinstance(a, dict) or not isinstance(a.get("title"), str) or not isinstance(a.get("summary"), str) \
                    or a.get("level") not in ("WATCH", "ACT") or not _is_number(a.get("day")):
                return None, "An alert in the summary is malformed."
        if not isinstance(c.get("exercises"), list):
            return None, "A crew entry has no exercises list."
    return value, None


def parse_packet_json(text):
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return None, "The file is not valid JSON."
    return parse_packet(value)


# ---- reading a packet's CSV back (Earth side) ------------------------------------------------

@dataclass
class TrendRow:
    day: int
    crew_id: str
    exercise: str
    reps: float
    prescribed_reps: float
    depth_deg: float | None
    concentric_s: float | None
    asymmetry_deg: float | None
    variability_deg: float | None


class _BadCell(Exception):
    pass


def _optional_number(cell):
    """Empty cell -> None. Text that is not a number -> error."""
    if cell is None or cell.strip() == "":
        return None
    try:
        value = float(cell)
    except ValueError:
        raise _BadCell()
    if not math.isfinite(value):
        raise _BadCell()
    return value


def _session_row(cells):
    try:
        day = float(cells[1])
        reps = float(cells[4])
        prescribed = float(cells[5])
        depth = _optional_number(cells[6])
        concentric = _optional_number(cells[7])
        asymmetry = _optional_number(cells[8])
        variability = _optional_number(cells[9])
    except (ValueError, IndexError, _BadCell):
        return None
    crew_id = cells[2].strip() if len(cells) > 2 else ""
    if not day.is_integer() or day < 0 or day > 36_500 or crew_id == "":
        return None
    if not (math.isfinite(reps) and math.isfinite(prescribed)):
        return None
    return TrendRow(day=int(day), crew_id=crew_id, exercise=cells[3].strip(), reps=reps, prescribed_reps=prescribed,
                    depth_deg=depth, concentric_s=concentric, asymmetry_deg=asymmetry, variability_deg=variability)


def parse_packet_csv(text):
    """Session rows of a packet CSV. Returns (rows, None) or (None, error)."""
    try:
        rows = parse_csv(text)
    except ValueError as e:
        return None, str(e)
    header = [h.strip() for h in rows[0]] if rows else []
    if header != CSV_COLUMNS:
        return None, "Not an OrbitFit downlink CSV: the header does not match the packet format."
    out = []
    for i in range(1, len(rows)):
        cells = rows[i]
        line = i + 1
        if cells[0] == "checkin":
            continue
        if cells[0] != "session":
            return None, f'Line {line}: unknown record type "{cells[0]}".'
        row = _session_row(cells)
        if row is None:
            return None, f"Line {line}: a value is missing or not a number."
        out.append(row)
    return out, None


def adherence_pct(row):
    if row.prescribed_reps <= 0:
        return None
    return 100 * row.reps / row.prescribed_reps


def merge_trends(csvs_oldest_first):
    """Join the session rows of several packets into one series. For the same crew member,
    exercise and day, the later packet wins. Unreadable packets are skipped."""
    by_key = {}
    for text in csvs_oldest_first:
        rows, error = parse_packet_csv(text)
        if error:
            continue
        for row in rows:
            by_key[(row.crew_id, row.exercise, row.day)] = row
    merged = list(by_key.values())
    merged.sort(key=lambda r: (r.day, r.crew_id))
    return merged


def hash_text(text):
    """Small repeatable content hash (FNV-1a, 32 bit), same as the original app."""
    h = 0x811C9DC5
    for ch in text:
        for unit in _utf16_units(ch):
            h ^= unit
            h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def _utf16_units(ch):
    code = ord(ch)
    if code < 0x10000:
        return [code]
    code -= 0x10000
    return [0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)]
