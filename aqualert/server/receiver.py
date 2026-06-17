"""Minimal server-side ingestion (no dashboard -- another team owns that).

  * store_message()  : parse a telemetry JSON payload and upsert into SQLite
                       (idempotent on msg_id).
  * MQTT subscriber  : subscribes to the telemetry topic and stores messages.
  * Flask read API   : GET /devices/<id>/latest, GET /devices/<id>/history

Run:
    python server/receiver.py --config config.yaml --db telemetry.sqlite
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import ssl
import sys
import threading
from datetime import datetime, timezone

from flask import Flask, jsonify

# Allow running as a script: make the package importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aqualert.config import load_config  # noqa: E402

log = logging.getLogger("aqualert.server")

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def init_db(db_path: str) -> None:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        schema = fh.read()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def _pair(value, idx, default=None):
    """Safely pull element idx from a 2-list/tuple, else default."""
    if isinstance(value, (list, tuple)) and len(value) > idx:
        return value[idx]
    return default


def store_message(db_path: str, payload: str | dict) -> bool:
    """Upsert one telemetry message. Returns True if newly inserted.

    Idempotent: a repeated msg_id is ignored (INSERT OR IGNORE).
    """
    d = json.loads(payload) if isinstance(payload, str) else payload
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO telemetry (
                msg_id, device_id, timestamp_utc, level_cm,
                level_ci_low, level_ci_high, state, confidence,
                slope_cm_per_hr, slope_ci_low, slope_ci_high, refill_events,
                waste_gpd_low, waste_gpd_high, config_version, firmware_version,
                received_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                d["msg_id"], d["device_id"], d["timestamp_utc"], d.get("level_cm"),
                _pair(d.get("level_ci"), 0), _pair(d.get("level_ci"), 1),
                d["state"], d["confidence"],
                d.get("slope_cm_per_hr"),
                _pair(d.get("slope_ci"), 0), _pair(d.get("slope_ci"), 1),
                d["refill_events"],
                _pair(d.get("est_waste_gpd"), 0), _pair(d.get("est_waste_gpd"), 1),
                d.get("config_version"), d.get("firmware_version"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["level_ci"] = [d.pop("level_ci_low"), d.pop("level_ci_high")]
    d["slope_ci"] = [d.pop("slope_ci_low"), d.pop("slope_ci_high")]
    d["est_waste_gpd"] = [d.pop("waste_gpd_low"), d.pop("waste_gpd_high")]
    return d


# ---------------------------------------------------------------------------
# Flask read API
# ---------------------------------------------------------------------------


def create_app(db_path: str) -> Flask:
    app = Flask(__name__)

    def _connect() -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/devices/<device_id>/latest")
    def latest(device_id: str):
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM telemetry WHERE device_id = ? "
                "ORDER BY timestamp_utc DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return jsonify({"error": "no telemetry for device"}), 404
        return jsonify(_row_to_dict(row))

    @app.get("/devices/<device_id>/history")
    def history(device_id: str):
        from flask import request

        try:
            limit = min(int(request.args.get("limit", 100)), 1000)
        except ValueError:
            limit = 100
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM telemetry WHERE device_id = ? "
                "ORDER BY timestamp_utc DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        finally:
            conn.close()
        return jsonify([_row_to_dict(r) for r in rows])

    return app


# ---------------------------------------------------------------------------
# MQTT subscriber
# ---------------------------------------------------------------------------


def start_subscriber(config_path: str, db_path: str) -> threading.Thread:
    """Start a background thread subscribing to the telemetry topic."""
    import paho.mqtt.client as mqtt

    cfg = load_config(config_path)
    mqtt_cfg = cfg.telemetry.mqtt

    def on_connect(client, _userdata, _flags, rc):
        log.info("subscriber connected rc=%s; subscribing to %s", rc, mqtt_cfg.topic)
        client.subscribe(mqtt_cfg.topic, qos=mqtt_cfg.qos)

    def on_message(_client, _userdata, message):
        try:
            inserted = store_message(db_path, message.payload.decode("utf-8"))
            log.info("stored msg (new=%s) on %s", inserted, message.topic)
        except Exception as exc:  # noqa: BLE001 - never kill the subscriber loop
            log.error("failed to store message: %s", exc)

    client = mqtt.Client(client_id=f"{cfg.device_id}-server", clean_session=True)
    if cfg.telemetry.mqtt_username:
        client.username_pw_set(cfg.telemetry.mqtt_username, cfg.telemetry.mqtt_password)
    if mqtt_cfg.tls:
        client.tls_set(ca_certs=mqtt_cfg.ca_certs, cert_reqs=ssl.CERT_REQUIRED)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(mqtt_cfg.host, mqtt_cfg.port, keepalive=mqtt_cfg.keepalive_s)

    thread = threading.Thread(target=client.loop_forever, name="mqtt-sub", daemon=True)
    thread.start()
    return thread


def main() -> None:
    ap = argparse.ArgumentParser(description="Aqualert server receiver")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--db", default="telemetry.sqlite")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-mqtt", action="store_true", help="run only the read API")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    init_db(args.db)
    if not args.no_mqtt:
        start_subscriber(args.config, args.db)
    app = create_app(args.db)
    log.info("read API on http://%s:%d", args.host, args.port)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
