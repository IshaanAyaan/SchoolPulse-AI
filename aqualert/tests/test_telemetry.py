"""Telemetry tests: store-and-forward survives an outage with no loss or dupes."""

from aqualert.models import TelemetryMsg
from aqualert.telemetry import Publisher, SpoolStore, TelemetryClient


class RecordingPublisher(Publisher):
    """Pretends to be a broker. Fails while offline; records what it receives."""

    def __init__(self):
        self.online = True
        self.received: list[str] = []

    def publish(self, msg: TelemetryMsg) -> bool:
        if not self.online:
            return False
        self.received.append(msg.msg_id)
        return True


def _msg(i: int) -> TelemetryMsg:
    return TelemetryMsg(
        msg_id=f"m{i:04d}",
        device_id="dev-1",
        timestamp_utc=f"2026-01-01T00:{i:02d}:00+00:00",
        level_cm=18.0,
        level_ci=(17.9, 18.1),
        state="NORMAL",
        confidence=0.99,
        slope_cm_per_hr=0.0,
        slope_ci=(-0.01, 0.01),
        refill_events=0,
        est_waste_gpd=(0.0, 0.1),
        config_version="1.0.0",
        firmware_version="1.0.0",
    )


def _client(tmp_path):
    pub = RecordingPublisher()
    spool = SpoolStore(str(tmp_path / "spool.sqlite"), max_rows=1000)
    return pub, TelemetryClient(pub, spool)


def test_persists_during_outage(tmp_path):
    pub, client = _client(tmp_path)
    pub.online = False
    for i in range(3):
        assert client.send(_msg(i)) is False  # not delivered
    assert client.pending_count() == 3        # all safely queued
    assert pub.received == []                  # nothing reached the broker
    client.close()


def test_flushes_on_reconnect_in_order(tmp_path):
    pub, client = _client(tmp_path)
    pub.online = False
    for i in range(3):
        client.send(_msg(i))
    pub.online = True
    assert client.flush() is True
    assert client.pending_count() == 0
    # Delivered exactly once each, oldest-first.
    assert pub.received == ["m0000", "m0001", "m0002"]
    client.close()


def test_no_duplicates_while_queued(tmp_path):
    # The device spool dedupes by msg_id while messages are still queued
    # (e.g. the same reading re-enqueued during a retry). End-to-end
    # idempotency after delivery is the server's job (see test_server.py).
    pub, client = _client(tmp_path)
    pub.online = False
    client.send(_msg(5))
    client.send(_msg(5))                 # same id re-enqueued during outage
    assert client.pending_count() == 1   # collapsed to one queued row
    pub.online = True
    client.flush()
    assert pub.received.count("m0005") == 1
    client.close()


def test_send_succeeds_when_online(tmp_path):
    pub, client = _client(tmp_path)
    assert client.send(_msg(1)) is True
    assert client.pending_count() == 0
    assert pub.received == ["m0001"]
    client.close()


def test_partial_outage_then_recovery(tmp_path):
    pub, client = _client(tmp_path)
    client.send(_msg(0))            # delivered
    pub.online = False
    client.send(_msg(1))            # queued
    client.send(_msg(2))            # queued
    assert client.pending_count() == 2
    pub.online = True
    client.send(_msg(3))            # flush drains 1,2 then sends 3
    assert client.pending_count() == 0
    assert pub.received == ["m0000", "m0001", "m0002", "m0003"]
    client.close()
