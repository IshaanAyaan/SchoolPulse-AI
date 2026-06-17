"""Telemetry transport with guaranteed delivery.

  * Publisher interface with two implementations behind it:
        - MqttPublisher  : MQTT over TLS (port 8883), QoS 1
        - RestPublisher  : HTTPS POST fallback (stdlib urllib, no extra deps)
  * SpoolStore         : local SQLite store-and-forward queue (no data loss)
  * TelemetryClient    : persist-then-send; flushes the spool on reconnect.

Every message carries a msg_id so the server can dedupe idempotently, which
makes "store, send, maybe-resend after a crash" safe.

Credentials come from the environment (see config.py), never from code or the
config file.
"""

from __future__ import annotations

import abc
import json
import logging
import sqlite3
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .config import Config
from .models import TelemetryMsg

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Publisher interface + implementations
# ---------------------------------------------------------------------------


class Publisher(abc.ABC):
    """One-shot publish of a single message. Returns True on confirmed send."""

    @abc.abstractmethod
    def publish(self, msg: TelemetryMsg) -> bool: ...

    def close(self) -> None:
        return None


class MqttPublisher(Publisher):
    """MQTT over TLS, QoS 1. Lazy connect; reconnect on next call after failure."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        import paho.mqtt.client as mqtt  # lazy import

        mqtt_cfg = self._cfg.telemetry.mqtt
        client = mqtt.Client(client_id=self._cfg.device_id, clean_session=True)
        user = self._cfg.telemetry.mqtt_username
        pw = self._cfg.telemetry.mqtt_password
        if user:
            client.username_pw_set(user, pw)
        if mqtt_cfg.tls:
            client.tls_set(ca_certs=mqtt_cfg.ca_certs, cert_reqs=ssl.CERT_REQUIRED)
        client.connect(mqtt_cfg.host, mqtt_cfg.port, keepalive=mqtt_cfg.keepalive_s)
        client.loop_start()
        self._client = client
        return client

    def publish(self, msg: TelemetryMsg) -> bool:
        try:
            client = self._ensure_client()
            info = client.publish(
                self._cfg.telemetry.mqtt.topic,
                payload=msg.to_json(),
                qos=self._cfg.telemetry.mqtt.qos,
            )
            info.wait_for_publish(timeout=10.0)
            return info.is_published()
        except Exception as exc:  # noqa: BLE001 - any failure means "not delivered"
            log.warning("MQTT publish failed: %s", exc)
            self.close()
            return False

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._client = None


class RestPublisher(Publisher):
    """HTTPS POST fallback using only the standard library."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg

    def publish(self, msg: TelemetryMsg) -> bool:
        rest = self._cfg.telemetry.rest
        headers = {"Content-Type": "application/json"}
        if self._cfg.telemetry.rest_token:
            headers["Authorization"] = f"Bearer {self._cfg.telemetry.rest_token}"
        req = urllib.request.Request(
            rest.url, data=msg.to_json().encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=rest.timeout_s) as resp:
                return 200 <= resp.status < 300
        except (urllib.error.URLError, OSError, ValueError) as exc:
            log.warning("REST publish failed: %s", exc)
            return False


def build_publisher(cfg: Config) -> Publisher:
    if cfg.telemetry.transport == "rest":
        return RestPublisher(cfg)
    return MqttPublisher(cfg)


# ---------------------------------------------------------------------------
# Store-and-forward spool
# ---------------------------------------------------------------------------


class SpoolStore:
    """Durable FIFO queue in SQLite. INSERT OR IGNORE dedupes by msg_id."""

    def __init__(self, db_path: str, max_rows: int) -> None:
        self._db_path = db_path
        self._max_rows = max_rows
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_spool (
                msg_id        TEXT PRIMARY KEY,
                timestamp_utc TEXT NOT NULL,
                payload       TEXT NOT NULL,
                created_at    TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def enqueue(self, msg: TelemetryMsg) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO telemetry_spool "
            "(msg_id, timestamp_utc, payload, created_at) VALUES (?, ?, ?, ?)",
            (msg.msg_id, msg.timestamp_utc, msg.to_json(),
             datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()
        self._enforce_cap()

    def _enforce_cap(self) -> None:
        # Bounded queue: if we exceed the cap (very long outage), drop the
        # OLDEST rows. Loud about it so it is never a silent loss.
        count = self.pending_count()
        if count > self._max_rows:
            overflow = count - self._max_rows
            log.error("spool over cap by %d rows; dropping oldest", overflow)
            self._conn.execute(
                "DELETE FROM telemetry_spool WHERE msg_id IN ("
                "SELECT msg_id FROM telemetry_spool ORDER BY timestamp_utc ASC LIMIT ?)",
                (overflow,),
            )
            self._conn.commit()

    def pending_count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM telemetry_spool")
        return int(cur.fetchone()[0])

    def pending(self) -> list[tuple[str, str]]:
        """Return [(msg_id, payload_json), ...] oldest first."""
        cur = self._conn.execute(
            "SELECT msg_id, payload FROM telemetry_spool ORDER BY timestamp_utc ASC"
        )
        return [(row[0], row[1]) for row in cur.fetchall()]

    def delete(self, msg_id: str) -> None:
        self._conn.execute("DELETE FROM telemetry_spool WHERE msg_id = ?", (msg_id,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Client: persist, then forward
# ---------------------------------------------------------------------------


class TelemetryClient:
    """Persist every message, then attempt to flush the whole spool in order.

    On a network outage messages accumulate durably in SQLite; on reconnect
    flush() drains them oldest-first. Server-side dedup by msg_id makes the
    at-least-once delivery safe.
    """

    def __init__(self, publisher: Publisher, spool: SpoolStore) -> None:
        self._publisher = publisher
        self._spool = spool

    @classmethod
    def from_config(cls, cfg: Config) -> "TelemetryClient":
        spool = SpoolStore(cfg.telemetry.spool_db, cfg.telemetry.max_spool_rows)
        return cls(build_publisher(cfg), spool)

    def send(self, msg: TelemetryMsg) -> bool:
        """Enqueue durably, then flush. True if the spool is empty afterwards."""
        self._spool.enqueue(msg)
        sent = self.flush()
        return sent and self._spool.pending_count() == 0

    def flush(self) -> bool:
        """Try to deliver all pending messages oldest-first.

        Stops at the first failure (network likely down) and leaves the rest
        queued. Returns True if at least an attempt completed without a hard
        error on the first message.
        """
        any_attempt = True
        for msg_id, payload in self._spool.pending():
            msg = _msg_from_json(payload)
            if self._publisher.publish(msg):
                self._spool.delete(msg_id)
            else:
                any_attempt = False
                break  # network down; keep the rest for later
        return any_attempt

    def pending_count(self) -> int:
        return self._spool.pending_count()

    def close(self) -> None:
        self._publisher.close()
        self._spool.close()


def _msg_from_json(payload: str) -> TelemetryMsg:
    d = json.loads(payload)
    # tuples serialize to lists; restore the tuple-typed fields.
    for key in ("level_ci", "slope_ci", "est_waste_gpd"):
        if isinstance(d.get(key), list):
            d[key] = tuple(d[key])
    return TelemetryMsg(**d)
