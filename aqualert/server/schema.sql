-- Server-side telemetry store. msg_id is the idempotency key: re-delivered
-- messages (at-least-once from the device store-and-forward) are ignored.

CREATE TABLE IF NOT EXISTS telemetry (
    msg_id           TEXT PRIMARY KEY,
    device_id        TEXT NOT NULL,
    timestamp_utc    TEXT NOT NULL,
    level_cm         REAL,
    level_ci_low     REAL,
    level_ci_high    REAL,
    state            TEXT NOT NULL,
    confidence       REAL NOT NULL,
    slope_cm_per_hr  REAL,
    slope_ci_low     REAL,
    slope_ci_high    REAL,
    refill_events    INTEGER NOT NULL,
    waste_gpd_low    REAL,
    waste_gpd_high   REAL,
    config_version   TEXT,
    firmware_version TEXT,
    received_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
    ON telemetry (device_id, timestamp_utc DESC);
