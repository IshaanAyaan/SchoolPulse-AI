from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import SUPABASE_SECRET_KEY, SUPABASE_SYNC_SOURCE, SUPABASE_SYNC_URL, WATER_LIVE_FRESHNESS_SECONDS
from .database import get_connection
from .schemas import WaterSensorReading


log = logging.getLogger("pulse-agent.water_live")


LIVE_WATER_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS water_sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    location TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    arduino_sequence INTEGER,
    uptime_ms INTEGER,
    distance_cm REAL NOT NULL,
    fill_depth_cm REAL NOT NULL,
    tank_depth_cm REAL NOT NULL,
    fill_percent REAL NOT NULL,
    status TEXT NOT NULL,
    confidence REAL NOT NULL,
    sample_count INTEGER NOT NULL,
    spread_cm REAL,
    reading_source TEXT NOT NULL
);
"""


class WaterLiveService:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def ensure_table(self) -> None:
        with get_connection(self.db_path) as connection:
            connection.execute(LIVE_WATER_TABLE_SQL)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_water_sensor_recorded_at "
                "ON water_sensor_readings (recorded_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_water_sensor_device_time "
                "ON water_sensor_readings (device_id, recorded_at DESC)"
            )
            connection.commit()

    def ingest(self, reading: WaterSensorReading) -> dict:
        self.ensure_table()
        stored = self._store(reading)
        synced = self._forward_to_supabase(stored)
        return {
            "stored": True,
            "synced_to_supabase": synced,
            "reading": stored,
        }

    def latest_reading(self) -> dict | None:
        self.ensure_table()
        with get_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM water_sensor_readings ORDER BY recorded_at DESC, id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return self._decorate(dict(row))

    def recent_readings(self, limit: int = 12) -> list[dict]:
        self.ensure_table()
        safe_limit = max(1, min(limit, 50))
        with get_connection(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM water_sensor_readings ORDER BY recorded_at DESC, id DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [self._decorate(dict(row)) for row in rows]

    def build_action_card(self, reading: dict | None) -> dict | None:
        if reading is None:
            return None

        status = str(reading["status"]).lower()
        if status == "normal":
            return None

        if status == "sensor_fault":
            title = f"Ultrasonic sensor needs checking at {reading['location']}"
            recommendation = "Check wiring, sensor angle, and USB serial feed before trusting the tank reading."
            estimated_impact = "Sensor data is not trustworthy until the echo signal stabilizes."
            confidence = 0.4
        elif status == "critical":
            title = f"Tank level is critically low at {reading['location']}"
            recommendation = "Inspect the toilet tank now for a refill issue, flapper leak, or stuck valve."
            estimated_impact = f"Tank is only {reading['fill_percent']:.1f}% full right now."
            confidence = max(0.75, float(reading["confidence"]))
        elif status == "low":
            title = f"Tank level is trending low at {reading['location']}"
            recommendation = "Check the tank in person and watch for a slow refill or small continuous leak."
            estimated_impact = f"Tank is at {reading['fill_percent']:.1f}% full."
            confidence = max(0.65, float(reading["confidence"]))
        else:
            title = f"Tank readings are unstable at {reading['location']}"
            recommendation = "Keep the lid still and verify the sensor is aimed straight at the water surface."
            estimated_impact = f"Reading spread is {reading.get('spread_cm', 0.0):.2f} cm, so stability needs a human check."
            confidence = max(0.45, float(reading["confidence"]) * 0.8)

        return {
            "module": "Water",
            "priority": "high" if status in {"critical", "sensor_fault"} else "medium",
            "title": title,
            "location": str(reading["location"]),
            "recommendation": recommendation,
            "evidence": (
                f"Live ultrasonic reading {reading['distance_cm']:.1f} cm from sensor, "
                f"{reading['fill_percent']:.1f}% full, status {reading['status']}."
            ),
            "estimated_impact": estimated_impact,
            "confidence": min(0.99, confidence),
            "human_check": "Look inside the tank and confirm the water line before escalating or repairing anything.",
        }

    def _store(self, reading: WaterSensorReading) -> dict:
        payload = reading.model_dump()
        recorded_at = payload["recorded_at"] or datetime.now(timezone.utc)
        payload["recorded_at"] = recorded_at.astimezone(timezone.utc).isoformat()
        payload["status"] = payload["status"].lower()

        with get_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO water_sensor_readings (
                    device_id, location, recorded_at, arduino_sequence, uptime_ms,
                    distance_cm, fill_depth_cm, tank_depth_cm, fill_percent, status,
                    confidence, sample_count, spread_cm, reading_source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["device_id"],
                    payload["location"],
                    payload["recorded_at"],
                    payload.get("arduino_sequence"),
                    payload.get("uptime_ms"),
                    payload["distance_cm"],
                    payload["fill_depth_cm"],
                    payload["tank_depth_cm"],
                    payload["fill_percent"],
                    payload["status"],
                    payload["confidence"],
                    payload["sample_count"],
                    payload.get("spread_cm"),
                    payload["reading_source"],
                ),
            )
            connection.commit()

        latest = self.latest_reading()
        if latest is None:
            raise RuntimeError("water live reading insert did not return a row")
        return latest

    def _decorate(self, row: dict) -> dict:
        recorded_at = datetime.fromisoformat(str(row["recorded_at"]).replace("Z", "+00:00"))
        freshness_seconds = max(0.0, (datetime.now(timezone.utc) - recorded_at).total_seconds())
        row["freshness_seconds"] = round(freshness_seconds, 1)
        row["is_live"] = freshness_seconds <= WATER_LIVE_FRESHNESS_SECONDS
        return row

    def _forward_to_supabase(self, reading: dict) -> bool | None:
        if not SUPABASE_SYNC_URL or not SUPABASE_SECRET_KEY:
            return None

        payload = {
            "kind": "operations_logs",
            "records": [
                {
                    "event_time": reading["recorded_at"],
                    "module": "water",
                    "source": SUPABASE_SYNC_SOURCE,
                    "payload": {
                        "reading_type": "ultrasonic_tank_level",
                        **reading,
                    },
                    "metadata": {
                        "device_id": reading["device_id"],
                        "location": reading["location"],
                        "status": reading["status"],
                    },
                }
            ],
        }

        try:
            response = requests.post(
                SUPABASE_SYNC_URL,
                headers={
                    "Content-Type": "application/json",
                    "apikey": SUPABASE_SECRET_KEY,
                },
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as exc:
            log.warning("failed to sync live water reading to Supabase: %s", exc)
            return False
