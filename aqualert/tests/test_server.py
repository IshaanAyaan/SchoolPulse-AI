"""Server tests: idempotent ingestion and the JSON read API."""

import json
import os
import sys

_HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_HERE, "..", "server"))

import receiver  # noqa: E402


def _payload(msg_id="abc123", device="dev-1", state="LEAK_SUSPECTED"):
    return json.dumps({
        "msg_id": msg_id,
        "device_id": device,
        "timestamp_utc": "2026-01-01T02:00:00+00:00",
        "level_cm": 17.4,
        "level_ci": [17.3, 17.5],
        "state": state,
        "confidence": 0.92,
        "slope_cm_per_hr": -1.2,
        "slope_ci": [-1.3, -1.1],
        "refill_events": 3,
        "est_waste_gpd": [6.5, 7.1],
        "config_version": "1.0.0",
        "firmware_version": "1.0.0",
    })


def test_store_is_idempotent(tmp_path):
    db = str(tmp_path / "t.sqlite")
    receiver.init_db(db)
    assert receiver.store_message(db, _payload()) is True   # newly inserted
    assert receiver.store_message(db, _payload()) is False  # duplicate ignored


def test_read_api_latest_and_history(tmp_path):
    db = str(tmp_path / "t.sqlite")
    receiver.init_db(db)
    receiver.store_message(db, _payload(msg_id="m1", state="NORMAL"))
    receiver.store_message(db, _payload(msg_id="m2", state="LEAK_SUSPECTED"))

    app = receiver.create_app(db)
    client = app.test_client()

    assert client.get("/health").get_json()["status"] == "ok"

    latest = client.get("/devices/dev-1/latest").get_json()
    assert latest["state"] in ("NORMAL", "LEAK_SUSPECTED")
    assert latest["est_waste_gpd"] == [6.5, 7.1]
    assert latest["slope_ci"] == [-1.3, -1.1]

    history = client.get("/devices/dev-1/history?limit=10").get_json()
    assert len(history) == 2

    missing = client.get("/devices/ghost/latest")
    assert missing.status_code == 404


def test_store_roundtrips_payload_fields(tmp_path):
    db = str(tmp_path / "t.sqlite")
    receiver.init_db(db)
    receiver.store_message(db, _payload(msg_id="rt"))
    app = receiver.create_app(db)
    row = app.test_client().get("/devices/dev-1/latest").get_json()
    assert row["msg_id"] == "rt"
    assert row["level_cm"] == 17.4
    assert row["refill_events"] == 3
    assert row["confidence"] == 0.92
