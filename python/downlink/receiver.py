"""The Earth side of the downlink (the flight surgeon on the ground).

Each tick: say "Earth is listening", store every packet that arrived (once, by id), and send
an ACK back, which takes the same simulated delay to reach the spacecraft. A duplicate packet
is stored zero times but still acknowledged, so a spacecraft whose first ACK was lost can finish.
"""

import time

from downlink import stores


def now_ms():
    return time.time() * 1000


class EarthReceiver:
    def __init__(self, earth, link, clock=now_ms):
        self.earth = earth
        self.link = link
        self.clock = clock
        self.received = []  # (packet id, duplicate) for the screen

    def tick(self):
        now = self.clock()
        stores.heartbeat(self.link, "earth", now)
        for raw in stores.take(self.link, "to_earth", now):
            message = stores.parse_message(raw)
            if message is None or message["type"] != "packet":
                continue  # anything malformed on the link is ignored
            packet = message["packet"]
            duplicate = stores.store_packet(self.earth, packet, now)
            self.received.append((packet["id"], duplicate))
            stores.post(self.link, "to_space", {"type": "ack", "id": packet["id"]},
                        deliver_at=now + message["latencyMs"])
