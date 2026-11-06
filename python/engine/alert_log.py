"""Alert log: an entry is written the first time an alert appears at a given level,
so an escalation from WATCH to ACT is logged too."""

from dataclasses import dataclass

from config.health_rules import HEALTH_RULES
from engine.change_detection import assess_crew


@dataclass
class AlertLogEntry:
    key: str
    crew_id: str
    exercise: str | None
    rule: str
    level: str
    title: str
    summary: str
    day: int


def alert_key(alert):
    return f"{alert.id}|{alert.level}"


def to_log_entry(alert, day):
    return AlertLogEntry(
        key=alert_key(alert), crew_id=alert.crew_id, exercise=alert.exercise, rule=alert.rule,
        level=alert.level, title=alert.title, summary=alert.what.summary, day=day,
    )


def new_log_entries(alerts, known_keys, day):
    """Entries for alerts whose key is not known yet."""
    return [to_log_entry(a, day) for a in alerts if alert_key(a) not in known_keys]


def replay_alert_log(sessions, checkins, crew_ids, to_day, cfg=HEALTH_RULES, vitals=None):
    """Replay mission days 1..to_day and record the first day each alert (per level) appeared."""
    vitals = vitals or []
    seen = {}
    for day in range(1, to_day + 1):
        s = [x for x in sessions if x.day <= day]
        c = [x for x in checkins if x.day <= day]
        v = [x for x in vitals if x.day <= day]
        for crew_id in crew_ids:
            for a in assess_crew(s, crew_id, cfg, c, v).alerts:
                key = alert_key(a)
                if key not in seen:
                    seen[key] = to_log_entry(a, day)
    entries = list(seen.values())
    entries.sort(key=lambda e: (e.day, e.key))
    return entries
