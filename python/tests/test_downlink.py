"""Downlink: packet format, and the real sender and Earth receiver over the simulated link.
A fake clock steps through minutes of simulated delay instantly."""

import json

import pytest

from data.crew import CREW
from data.demo_seed import DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS, DEMO_VITALS
from db.database import open_db
from downlink import stores
from downlink.packet import (
    CSV_COLUMNS, MAX_PACKET_CSV_CHARS, adherence_pct, build_packet, format_kb, hash_text, merge_trends, packet_csv,
    packet_json, packet_size_bytes, parse_packet, parse_packet_csv, parse_packet_json,
)
from downlink.receiver import EarthReceiver
from downlink.sender import DownlinkSender
from engine.change_detection import assess_crew
from data.csv_codec import parse_csv

LATENCY = 10_000  # 10 simulated minutes = 10 real seconds


def make_packet(packet_id="pkt-1", day=DEMO_DAYS, window=7, notes=None):
    return build_packet(DEMO_SESSIONS, DEMO_CHECKINS, DEMO_VITALS, CREW, day, window, packet_id, 1_800_000_000_000,
                        notes=notes)


# ---- packet ----------------------------------------------------------------------------------

def test_packet_is_deterministic_and_survives_json():
    a = make_packet()
    assert a == make_packet()
    assert json.loads(packet_json(a)) == a


def test_packet_gives_every_crew_member_the_same_status_as_the_rules():
    p = make_packet()
    for entry in p["summary"]["crew"]:
        expected = assess_crew(DEMO_SESSIONS, entry["crewId"], checkins=DEMO_CHECKINS, vitals=DEMO_VITALS).status
        assert entry["status"] == expected
    statuses = {e["crewId"]: e["status"] for e in p["summary"]["crew"]}
    assert statuses == {"c1": "ACT", "c2": "NOMINAL", "c3": "WATCH"}


def test_packet_carries_alert_summaries_vitals_notes_and_the_disclaimer():
    p = make_packet(notes={"c1": "Reduce load."})
    rivera = p["summary"]["crew"][0]
    assert all(len(a["summary"]) > 10 for a in rivera["alerts"])
    assert rivera["latestVitals"]["day"] == DEMO_DAYS
    assert rivera["latestCheckin"]["day"] == DEMO_DAYS
    assert rivera["note"] == "Reduce load."
    assert "Not a diagnosis" in p["summary"]["disclaimer"]
    squat = rivera["exercises"][0]
    assert squat["baseline"] is not None and squat["deltas"] is not None


def test_packet_is_compact():
    p = make_packet()
    assert packet_size_bytes(p) < 20_000
    assert format_kb(2048) == "2.0 KB"


def test_an_earlier_mission_day_gives_earlier_statuses():
    early = make_packet(day=8)
    assert all(e["status"] == "NOMINAL" for e in early["summary"]["crew"])


def test_packet_csv_covers_exactly_the_window():
    text = packet_csv(DEMO_SESSIONS, DEMO_CHECKINS, DEMO_DAYS, 7)
    rows = parse_csv(text)
    assert rows[0] == CSV_COLUMNS
    assert all(len(r) == len(CSV_COLUMNS) for r in rows)
    sessions = [r for r in rows[1:] if r[0] == "session"]
    checkins = [r for r in rows[1:] if r[0] == "checkin"]
    assert len(sessions) == 3 * 7
    assert len(checkins) == 3 * 7
    assert {int(r[1]) for r in sessions} == set(range(24, 31))
    assert "\r\n" in text
    assert len(packet_csv(DEMO_SESSIONS, DEMO_CHECKINS, DEMO_DAYS, 14)) > len(text)


def test_parse_packet_accepts_a_real_packet_and_rejects_bad_ones():
    good = make_packet()
    assert parse_packet(good)[1] is None
    assert parse_packet(json.loads(packet_json(good)))[1] is None
    bad = [
        "not a dict",
        {**good, "version": 2},
        {**good, "id": "has spaces!"},
        {**good, "createdAt": -1},
        {**good, "missionDay": 1.5},
        {**good, "csv": 5},
        {**good, "csv": "x" * (MAX_PACKET_CSV_CHARS + 1)},
        {**good, "summary": {"crew": [{"crewId": "c1", "name": "x", "status": "FINE", "alerts": [], "exercises": []}]}},
        {**good, "summary": {"crew": [{"crewId": "c1", "name": "x", "status": "ACT",
                                       "alerts": [{"title": "t", "summary": "s", "level": "BAD", "day": 1}],
                                       "exercises": []}]}},
    ]
    for value in bad:
        packet, error = parse_packet(value)
        assert packet is None and error
    assert parse_packet_json("{oops")[1] == "The file is not valid JSON."


def test_packet_csv_reads_back_and_merges_packets():
    week1 = make_packet("p1", day=23)["csv"]
    week2 = make_packet("p2", day=30)["csv"]
    rows, error = parse_packet_csv(week2)
    assert error is None and len(rows) == 21
    merged = merge_trends([week1, week2, "garbage"])
    days = {(r.crew_id, r.day) for r in merged}
    assert len(merged) == len(days) == 3 * 14  # days 17-30, no duplicates
    assert adherence_pct(rows[0]) == pytest.approx(100 * rows[0].reps / rows[0].prescribed_reps)
    assert merge_trends([]) == []


def test_packet_csv_rejects_bad_rows():
    head = ",".join(CSV_COLUMNS)
    assert parse_packet_csv(head + "\r\nbanana,1\r\n")[1].startswith("Line 2")
    assert "not a number" in parse_packet_csv(head + "\r\nsession,1.5,c1,squat,8,8,,,,,,,,,,\r\n")[1]
    assert "header" in parse_packet_csv("a,b\r\n")[1]


def test_hash_text_matches_the_original_app():
    # FNV-1a 32-bit of "a" is e40c292c in every implementation.
    assert hash_text("a") == "e40c292c"
    assert hash_text("abc") != hash_text("abd")


# ---- sender and Earth over the link ----------------------------------------------------------

class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def world(tmp_path):
    clock = Clock()
    space = open_db(tmp_path / "orbitfit.db")
    link = stores.open_link(tmp_path / "link.db")
    earth = stores.open_earth(tmp_path / "earth.db")
    sender = DownlinkSender(space, link, clock=clock)
    receiver = EarthReceiver(earth, link, clock=clock)
    yield {"clock": clock, "space": space, "link": link, "earth": earth, "sender": sender, "receiver": receiver,
           "tmp": tmp_path}
    for c in (space, link, earth):
        c.close()


def run(world, seconds, window_open=True, earth_listening=True, latency=LATENCY, step_ms=500):
    """Advance the fake clock, ticking both sides like the pages do."""
    for _ in range(int(seconds * 1000 / step_ms)):
        world["clock"].t += step_ms
        if earth_listening:
            world["receiver"].tick()
        world["sender"].tick(window_open, latency)


def status(world, packet_id="pkt-1"):
    for item, _, _ in stores.list_queue(world["space"]):
        if item.id == packet_id:
            return item
    return None


def stored_ids(world):
    return [p["id"] for p in stores.earth_packets(world["earth"])]


def test_blackout_keeps_the_packet_queued_and_sends_nothing(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    run(world, 120, window_open=False)
    assert status(world).status == "queued"
    assert status(world).attempts == 0
    assert stored_ids(world) == []


def test_a_queued_packet_survives_a_restart(world, tmp_path):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    world["space"].close()
    reopened = open_db(tmp_path / "orbitfit.db")
    items = stores.list_queue(reopened)
    assert [i.id for i, _, _ in items] == ["pkt-1"]
    world["space"] = reopened


def test_delivers_only_after_the_delay_then_earth_acknowledges(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    run(world, 9)            # 9 s of a 10 s one-way delay
    assert stored_ids(world) == []
    assert status(world).status == "sent"
    run(world, 2)            # arrives at Earth
    assert stored_ids(world) == ["pkt-1"]
    assert status(world).status == "sent"      # the ACK is still on its way back
    run(world, 11)           # ACK travels back over the same delay
    assert status(world).status == "acked"


def test_earth_stores_exactly_what_was_sent(world):
    p = make_packet(notes={"c3": "Knee review on day 31."})
    stores.enqueue_packet(world["space"], p, world["clock"]())
    run(world, 25)
    [received] = stores.earth_packets(world["earth"])
    received.pop("receivedAt")
    assert received == p


def test_a_packet_that_waited_through_a_blackout_goes_when_the_window_opens(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    run(world, 60, window_open=False)
    run(world, 25, window_open=True)
    assert status(world).status == "acked"


def test_several_packets_are_each_delivered_once(world):
    for i in range(3):
        stores.enqueue_packet(world["space"], make_packet(f"pkt-{i}"), world["clock"]() + i)
    run(world, 30)
    assert sorted(stored_ids(world)) == ["pkt-0", "pkt-1", "pkt-2"]
    assert all(item.status == "acked" for item, _, _ in stores.list_queue(world["space"]))


def test_enqueueing_the_same_packet_twice_queues_it_once(world):
    p = make_packet()
    stores.enqueue_packet(world["space"], p, world["clock"]())
    stores.enqueue_packet(world["space"], p, world["clock"]())
    assert len(stores.list_queue(world["space"])) == 1


def test_earth_stores_a_repeated_delivery_once_but_acks_every_time(world):
    p = make_packet()
    stores.post(world["link"], "to_earth", {"type": "packet", "packet": p, "latencyMs": 0}, world["clock"]())
    stores.post(world["link"], "to_earth", {"type": "packet", "packet": p, "latencyMs": 0}, world["clock"]())
    world["receiver"].tick()
    assert stored_ids(world) == ["pkt-1"]
    assert world["receiver"].received == [("pkt-1", False), ("pkt-1", True)]
    acks = stores.take(world["link"], "to_space", world["clock"]())
    assert acks == [{"type": "ack", "id": "pkt-1"}, {"type": "ack", "id": "pkt-1"}]


def test_two_open_pages_sharing_the_queue_send_a_packet_only_once(world):
    second = DownlinkSender(world["space"], world["link"], clock=world["clock"])
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    for _ in range(60):  # 30 s: 10 s out, 10 s for the ACK back, with room to spare
        world["clock"].t += 500
        world["sender"].tick(True, LATENCY)
        second.tick(True, LATENCY)
        world["receiver"].tick()
    assert world["receiver"].received == [("pkt-1", False)]
    assert status(world).status == "acked"


def test_earth_not_listening_means_the_transmission_is_lost_and_retried(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    run(world, 40, earth_listening=False)
    assert stored_ids(world) == []
    assert status(world).attempts >= 2            # it tried again
    assert status(world).status != "acked"
    run(world, 40, earth_listening=True)
    assert stored_ids(world) == ["pkt-1"]
    assert status(world).status == "acked"


def test_a_blackout_during_transit_sends_the_packet_back_to_the_queue(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    run(world, 4)                                     # in transit
    assert status(world).status == "sent"
    run(world, 2, window_open=False)                  # link lost
    item = status(world)
    assert item.status == "queued" and item.deliver_at is None
    run(world, 30)                                    # next window
    assert stored_ids(world) == ["pkt-1"]
    assert status(world).status == "acked"


def test_an_ack_lost_in_a_blackout_leads_to_a_resend_that_earth_does_not_duplicate(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    run(world, 11)                                    # delivered to Earth
    assert stored_ids(world) == ["pkt-1"]
    run(world, 12, window_open=False)                 # the ACK arrives during a blackout and is lost
    assert status(world).status != "acked"
    run(world, 40, window_open=True)                  # resend, Earth acks again
    assert status(world).status == "acked"
    assert stored_ids(world) == ["pkt-1"]
    assert ("pkt-1", True) in world["receiver"].received


def test_a_cancelled_packet_is_never_delivered(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    stores.cancel_packet(world["space"], "pkt-1")
    run(world, 30)
    assert stored_ids(world) == []


def test_an_acknowledged_packet_cannot_be_cancelled(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    run(world, 25)
    stores.cancel_packet(world["space"], "pkt-1")
    assert status(world).status == "acked"


def test_the_sender_notices_earth_and_notices_it_is_gone(world):
    assert world["sender"].earth_online() is False
    world["receiver"].tick()
    assert world["sender"].earth_online() is True
    world["clock"].t += 11_000
    assert world["sender"].earth_online() is False


def test_parse_message_drops_anything_malformed():
    p = make_packet()
    assert stores.parse_message({"type": "ack", "id": "pkt-1"}) == {"type": "ack", "id": "pkt-1"}
    for bad in [None, "x", {"type": "ack"}, {"type": "ack", "id": "bad id!"}, {"type": "hello"},
                {"type": "packet", "packet": p, "latencyMs": -1},
                {"type": "packet", "packet": p, "latencyMs": True},
                {"type": "packet", "packet": {"version": 1}, "latencyMs": 0}]:
        assert stores.parse_message(bad) is None
    assert stores.parse_message({"type": "packet", "packet": p, "latencyMs": 5})["type"] == "packet"


def test_earth_ignores_malformed_messages_on_the_link(world):
    stores.post(world["link"], "to_earth", {"type": "packet", "packet": {"version": 1, "id": "x"}, "latencyMs": 0},
                world["clock"]())
    world["link"].execute("INSERT INTO messages (direction, body, deliver_at) VALUES ('to_earth', 'not json', ?)",
                          (world["clock"](),))
    world["receiver"].tick()
    assert stored_ids(world) == []


def test_a_forged_ack_for_an_unknown_packet_changes_nothing(world):
    stores.enqueue_packet(world["space"], make_packet(), world["clock"]())
    stores.post(world["link"], "to_space", {"type": "ack", "id": "someone-else"}, world["clock"]())
    world["sender"].tick(False, LATENCY)
    world["sender"].tick(True, LATENCY)
    assert status(world).status == "sent"
    assert stores.list_queue(world["space"])[0][0].acked_at is None
