"""State machine for the space-to-Earth downlink queue. No timers, no I/O.

Given the queue, the comms state and the clock, it says what to change and which
packets to transmit right now.

  queued --(window open)--> sent (in transit) --(delay passed)--> transmitted --ACK--> acked
     ^                          | blackout before arrival            | no ACK in time: retry
     +--------------------------+------------------------------------+
"""

from dataclasses import dataclass, field

QUEUED = "queued"
SENT = "sent"
ACKED = "acked"


@dataclass
class QueueItem:
    id: str
    created_at: float
    status: str = QUEUED
    sent_at: float | None = None        # when this attempt started
    deliver_at: float | None = None     # when the packet reaches Earth (simulated delay)
    transmitted_at: float | None = None  # set once the packet has actually reached Earth
    acked_at: float | None = None
    attempts: int = 0


@dataclass
class StepConfig:
    now: float
    window_open: bool
    latency_ms: float              # simulated one-way delay, in real milliseconds
    retry_margin_ms: float = 3000  # extra wait beyond the round trip before a missing ACK means retry
    max_attempts: int = 20


@dataclass
class StepResult:
    updates: list = field(default_factory=list)   # list of (id, dict of changes)
    transmit: list = field(default_factory=list)  # ids of packets to deliver to Earth now


def _cleared():
    return {"sent_at": None, "deliver_at": None, "transmitted_at": None}


def step_queue(items, cfg):
    """What to do next for every packet that is not acknowledged yet, oldest first."""
    result = StepResult()
    pending = [it for it in items if it.status != ACKED]
    pending.sort(key=lambda it: it.created_at)

    for it in pending:
        if not cfg.window_open:
            # Blackout: a packet that has not reached Earth yet is lost; it goes back to the queue.
            if it.status == SENT and it.transmitted_at is None:
                result.updates.append((it.id, {"status": QUEUED, **_cleared()}))
            continue

        if it.status == QUEUED:
            if it.attempts >= cfg.max_attempts:
                continue  # gave up: left in the queue for the operator to see
            result.updates.append((it.id, {
                "status": SENT,
                "sent_at": cfg.now,
                "deliver_at": cfg.now + cfg.latency_ms,
                "transmitted_at": None,
                "attempts": it.attempts + 1,
            }))
            continue

        # status == SENT
        if it.transmitted_at is None:
            if it.deliver_at is not None and cfg.now >= it.deliver_at:
                result.transmit.append(it.id)
                result.updates.append((it.id, {"transmitted_at": cfg.now}))
        elif cfg.now >= it.transmitted_at + cfg.latency_ms + cfg.retry_margin_ms:
            # Delivered, but no ACK came back in time (Earth closed, ACK lost): send again.
            result.updates.append((it.id, {"status": QUEUED, **_cleared()}))

    return result


def phase_of(it, window_open, max_attempts=20):
    """Status word for the screen."""
    if it.status == ACKED:
        return "acked"
    if it.status == QUEUED:
        if it.attempts >= max_attempts:
            return "gave-up"
        if window_open:
            return "starting"
        return "waiting-for-window"
    if it.transmitted_at is None:
        return "in-transit"
    return "awaiting-ack"
