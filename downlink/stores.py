"""Where downlink data lives. Three separate SQLite files, like three separate places:

  orbitfit.db  (spacecraft)  downlink_queue + downlink_settings: packets waiting, in transit, acknowledged
  link.db      (the radio)   messages "in the air" between spacecraft and Earth
  earth.db     (the ground)  packets Earth has received; Earth never reads the spacecraft logbook

Everything about the link is SIMULATED: one simulated minute of delay = one real second.
"""

import json
import os
import re
import sqlite3
from pathlib import Path

from db.database import PROJECT_DIR, transaction
from downlink.packet import packet_json, packet_size_bytes, parse_packet
from engine.downlink_queue import QueueItem

# A message nobody picks up within this time is lost (no listener on the other end).
MESSAGE_TTL_MS = 10_000
# Earth counts as "online" if it was seen this recently.
EARTH_ONLINE_MS = 10_000
MAX_LATENCY_MS = 60 * 60 * 1000
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")

QUEUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS downlink_queue (
    id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    status TEXT NOT NULL,
    payload TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mission_day INTEGER NOT NULL,
    sent_at REAL,
    deliver_at REAL,
    transmitted_at REAL,
    acked_at REAL,
    attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS downlink_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

LINK_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT NOT NULL,      -- to_earth or to_space
    body TEXT NOT NULL,
    deliver_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS presence (
    who TEXT PRIMARY KEY,
    last_seen REAL NOT NULL
);
"""

EARTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS packets (
    id TEXT PRIMARY KEY,
    received_at REAL NOT NULL,
    created_at REAL NOT NULL,
    mission_day INTEGER NOT NULL,
    payload TEXT NOT NULL
);
"""


def _open(path, schema):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(schema)
    return conn


def _env_path(name, default_file):
    custom = os.environ.get(name)
    if custom:
        return Path(custom)
    return PROJECT_DIR / "var" / default_file


def open_link(path=None):
    return _open(path or _env_path("ORBITFIT_LINK_DB", "link.db"), LINK_SCHEMA)


def open_earth(path=None):
    return _open(path or _env_path("ORBITFIT_EARTH_DB", "earth.db"), EARTH_SCHEMA)


def ensure_queue_tables(conn):
    conn.executescript(QUEUE_SCHEMA)


# ---- spacecraft queue -----------------------------------------------------------------------

def _item_from_row(row):
    return QueueItem(id=row["id"], created_at=row["created_at"], status=row["status"], sent_at=row["sent_at"],
                     deliver_at=row["deliver_at"], transmitted_at=row["transmitted_at"], acked_at=row["acked_at"],
                     attempts=row["attempts"])


def enqueue_packet(conn, packet, now_ms):
    """Add a packet to the queue to wait for a comms window. Adding the same packet id twice does nothing."""
    ensure_queue_tables(conn)
    conn.execute(
        "INSERT OR IGNORE INTO downlink_queue (id, created_at, status, payload, size_bytes, mission_day, attempts) "
        "VALUES (?, ?, 'queued', ?, ?, ?, 0)",
        (packet["id"], now_ms, packet_json(packet), packet_size_bytes(packet), packet["missionDay"]),
    )


def cancel_packet(conn, packet_id):
    """Remove a packet that Earth has not acknowledged yet."""
    ensure_queue_tables(conn)
    conn.execute("DELETE FROM downlink_queue WHERE id = ? AND status != 'acked'", (packet_id,))


def list_queue(conn):
    """Newest first: (QueueItem, size_bytes, mission_day)."""
    ensure_queue_tables(conn)
    rows = conn.execute("SELECT * FROM downlink_queue ORDER BY created_at DESC").fetchall()
    return [(_item_from_row(r), r["size_bytes"], r["mission_day"]) for r in rows]


def queue_items(conn):
    return [_item_from_row(r) for r in conn.execute("SELECT * FROM downlink_queue").fetchall()]


def queue_payload(conn, packet_id):
    row = conn.execute("SELECT payload FROM downlink_queue WHERE id = ?", (packet_id,)).fetchone()
    return row["payload"] if row else None


def update_item(conn, packet_id, patch):
    columns = ", ".join(f"{key} = ?" for key in patch)
    conn.execute(f"UPDATE downlink_queue SET {columns} WHERE id = ?", (*patch.values(), packet_id))


def get_setting(conn, key, default):
    ensure_queue_tables(conn)
    row = conn.execute("SELECT value FROM downlink_settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_setting(conn, key, value):
    ensure_queue_tables(conn)
    conn.execute("INSERT OR REPLACE INTO downlink_settings (key, value) VALUES (?, ?)", (key, json.dumps(value)))


# ---- the simulated radio link ---------------------------------------------------------------

def post(link, direction, message, deliver_at):
    link.execute("INSERT INTO messages (direction, body, deliver_at) VALUES (?, ?, ?)",
                 (direction, json.dumps(message, separators=(",", ":")), deliver_at))


def take(link, direction, now_ms):
    """Messages that have arrived by now, each handed out once. Messages nobody took in time are lost."""
    with transaction(link):
        link.execute("DELETE FROM messages WHERE direction = ? AND deliver_at < ?", (direction, now_ms - MESSAGE_TTL_MS))
        rows = link.execute("SELECT id, body FROM messages WHERE direction = ? AND deliver_at <= ? ORDER BY id",
                            (direction, now_ms)).fetchall()
        for r in rows:
            link.execute("DELETE FROM messages WHERE id = ?", (r["id"],))
    out = []
    for r in rows:
        try:
            out.append(json.loads(r["body"]))
        except ValueError:
            out.append(None)
    return out


def heartbeat(link, who, now_ms):
    link.execute("INSERT OR REPLACE INTO presence (who, last_seen) VALUES (?, ?)", (who, now_ms))


def is_online(link, who, now_ms):
    row = link.execute("SELECT last_seen FROM presence WHERE who = ?", (who,)).fetchone()
    return row is not None and now_ms - row["last_seen"] < EARTH_ONLINE_MS


def parse_message(data):
    """Check a message from the link. Anything that does not match exactly is dropped (returns None)."""
    if not isinstance(data, dict):
        return None
    kind = data.get("type")
    if kind == "ack":
        if isinstance(data.get("id"), str) and ID_PATTERN.match(data["id"]):
            return {"type": "ack", "id": data["id"]}
        return None
    if kind == "packet":
        latency = data.get("latencyMs")
        if isinstance(latency, bool) or not isinstance(latency, (int, float)) or not 0 <= latency <= MAX_LATENCY_MS:
            return None
        packet, error = parse_packet(data.get("packet"))
        if error:
            return None
        return {"type": "packet", "packet": packet, "latencyMs": latency}
    return None


# ---- Earth inbox ----------------------------------------------------------------------------

def store_packet(earth, packet, now_ms):
    """Store a received packet once. Returns True if it was already there (a duplicate delivery)."""
    with transaction(earth):
        before = earth.total_changes
        earth.execute("INSERT OR IGNORE INTO packets (id, received_at, created_at, mission_day, payload) "
                      "VALUES (?, ?, ?, ?, ?)",
                      (packet["id"], now_ms, packet["createdAt"], packet["missionDay"], packet_json(packet)))
        duplicate = earth.total_changes == before
    return duplicate


def earth_packets(earth):
    """Received packets, oldest first, as dicts with 'received_at' added."""
    rows = earth.execute("SELECT * FROM packets ORDER BY created_at").fetchall()
    out = []
    for r in rows:
        packet = json.loads(r["payload"])
        packet["receivedAt"] = r["received_at"]
        out.append(packet)
    return out


def clear_earth(earth):
    earth.execute("DELETE FROM packets")
