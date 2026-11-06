"""The spacecraft side of the downlink.

Each tick asks the queue state machine (engine/downlink_queue.py) what to do, applies the
changes in one transaction (so two open pages cannot both send a packet), puts due packets
on the link, and records Earth's acknowledgements. An ACK that arrives during a blackout is
lost, like the radio signal itself; the packet is then sent again and Earth ignores the copy.
"""

import json
import time

from db.database import transaction
from downlink import stores
from engine.downlink_queue import StepConfig, step_queue


def now_ms():
    return time.time() * 1000


class DownlinkSender:
    def __init__(self, conn, link, clock=now_ms, retry_margin_ms=3000, max_attempts=20):
        self.conn = conn
        self.link = link
        self.clock = clock
        self.retry_margin_ms = retry_margin_ms
        self.max_attempts = max_attempts
        stores.ensure_queue_tables(conn)

    def earth_online(self):
        return stores.is_online(self.link, "earth", self.clock())

    def tick(self, window_open, latency_ms):
        """One step: move packets along the queue, send what is due, read ACKs."""
        now = self.clock()
        cfg = StepConfig(now=now, window_open=window_open, latency_ms=latency_ms,
                         retry_margin_ms=self.retry_margin_ms, max_attempts=self.max_attempts)
        to_send = []
        with transaction(self.conn):
            result = step_queue(stores.queue_items(self.conn), cfg)
            for packet_id, patch in result.updates:
                stores.update_item(self.conn, packet_id, patch)
            for packet_id in result.transmit:
                payload = stores.queue_payload(self.conn, packet_id)
                if payload is not None:
                    to_send.append(payload)
        # Put packets "on the air" only after the queue change is saved, so the two never disagree.
        # The one-way delay was already spent in the queue (sent -> deliver_at), so they arrive now.
        for payload in to_send:
            stores.post(self.link, "to_earth", {"type": "packet", "packet": json.loads(payload), "latencyMs": latency_ms},
                        deliver_at=now)

        for raw in stores.take(self.link, "to_space", now):
            message = stores.parse_message(raw)
            if message is None or message["type"] != "ack":
                continue
            if not window_open:
                continue  # blackout: the ACK is lost; the packet will be re-sent later
            with transaction(self.conn):
                self.conn.execute("UPDATE downlink_queue SET status = 'acked', acked_at = ? "
                                  "WHERE id = ? AND status != 'acked'", (now, message["id"]))
