"""Downlink retry: blackout, delay, acknowledgement and retries."""

from dataclasses import replace

from engine.downlink_queue import QueueItem, StepConfig, phase_of, step_queue

L = 10_000  # 10 s simulated one-way delay (10 min at 1 min = 1 s)
RETRY_MARGIN = StepConfig(now=0, window_open=True, latency_ms=0).retry_margin_ms
MAX_ATTEMPTS = StepConfig(now=0, window_open=True, latency_ms=0).max_attempts


def item(id, **changes):
    return replace(QueueItem(id=id, created_at=1000), **changes)


def cfg(now=100_000, window_open=True, latency_ms=L):
    return StepConfig(now=now, window_open=window_open, latency_ms=latency_ms)


def apply(it, result):
    for item_id, patch in result.updates:
        if item_id == it.id:
            return replace(it, **patch)
    return it


# ---- blackout -------------------------------------------------------------------------------

def test_blackout_leaves_queued_packets_queued():
    q = item("a")
    for t in range(10):
        r = step_queue([q], cfg(now=100_000 + t * 60_000, window_open=False))
        assert r.updates == []
        assert r.transmit == []
        q = apply(q, r)
    assert q.status == "queued"
    assert q.attempts == 0


def test_packet_in_transit_when_the_window_closes_goes_back_to_the_queue():
    in_flight = item("a", status="sent", sent_at=100_000, deliver_at=110_000, attempts=1)
    r = step_queue([in_flight], cfg(now=105_000, window_open=False))
    assert r.transmit == []
    back = apply(in_flight, r)
    assert back.status == "queued"
    assert back.sent_at is None
    assert back.deliver_at is None
    assert back.transmitted_at is None
    assert back.attempts == 1


def test_delivered_packet_is_not_recalled_by_a_later_blackout():
    delivered = item("a", status="sent", sent_at=100_000, deliver_at=110_000, transmitted_at=110_000, attempts=1)
    assert step_queue([delivered], cfg(now=115_000, window_open=False)).updates == []


# ---- window open ----------------------------------------------------------------------------

def test_starts_sending_but_does_not_deliver_before_the_delay():
    q = item("a")
    r1 = step_queue([q], cfg(now=100_000))
    assert r1.transmit == []
    sent = apply(q, r1)
    assert (sent.status, sent.sent_at, sent.deliver_at, sent.attempts) == ("sent", 100_000, 110_000, 1)
    assert step_queue([sent], cfg(now=109_999)).transmit == []


def test_delivers_exactly_when_the_delay_has_passed_and_only_once():
    sent = item("a", status="sent", sent_at=100_000, deliver_at=110_000, attempts=1)
    r = step_queue([sent], cfg(now=110_000))
    assert r.transmit == ["a"]
    done = apply(sent, r)
    assert done.transmitted_at == 110_000
    assert step_queue([done], cfg(now=111_000)).transmit == []


def test_retries_when_no_ack_arrives_in_time():
    delivered = item("a", status="sent", sent_at=100_000, deliver_at=110_000, transmitted_at=110_000, attempts=1)
    wait_until = 110_000 + L + RETRY_MARGIN
    assert step_queue([delivered], cfg(now=wait_until - 1)).updates == []
    requeued = apply(delivered, step_queue([delivered], cfg(now=wait_until)))
    assert requeued.status == "queued"
    assert requeued.transmitted_at is None
    assert requeued.attempts == 1
    again = apply(requeued, step_queue([requeued], cfg(now=wait_until + 100)))
    assert again.status == "sent"
    assert again.attempts == 2


def test_gives_up_after_max_attempts():
    stuck = item("a", attempts=MAX_ATTEMPTS)
    assert step_queue([stuck], cfg()).updates == []
    assert phase_of(stuck, True) == "gave-up"


def test_never_touches_acknowledged_packets():
    done = item("a", status="acked", acked_at=5, attempts=1)
    assert step_queue([done], cfg(window_open=True)).updates == []
    assert step_queue([done], cfg(window_open=False)).updates == []


def test_handles_several_packets_oldest_first():
    items = [item("late", created_at=3000), item("early", created_at=1000), item("mid", created_at=2000)]
    r = step_queue(items, cfg())
    assert [u[0] for u in r.updates] == ["early", "mid", "late"]


def test_longer_delay_delays_delivery():
    q = item("a")
    s = apply(q, step_queue([q], cfg(now=0, latency_ms=40_000)))
    assert s.deliver_at == 40_000
    assert step_queue([s], cfg(now=39_999, latency_ms=40_000)).transmit == []
    assert step_queue([s], cfg(now=40_000, latency_ms=40_000)).transmit == ["a"]


def test_phase_words_for_the_screen():
    assert phase_of(item("a"), False) == "waiting-for-window"
    assert phase_of(item("a"), True) == "starting"
    assert phase_of(item("a", status="sent", deliver_at=1), True) == "in-transit"
    assert phase_of(item("a", status="sent", transmitted_at=1), True) == "awaiting-ack"
    assert phase_of(item("a", status="acked"), False) == "acked"
