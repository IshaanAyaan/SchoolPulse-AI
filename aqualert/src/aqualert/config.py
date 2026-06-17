"""Configuration loading and validation.

A single config.yaml feeds the whole system. Validation runs on load and
raises ConfigError on any bad value (fail loudly, no silent defaults that
mask mistakes). No magic numbers live in code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import time
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when configuration is missing or invalid."""


# --- typed sub-sections -----------------------------------------------------


@dataclass(slots=True)
class SensorConfig:
    mode: str
    sim_scenario: str
    sim_seed: int | None


@dataclass(slots=True)
class GpioConfig:
    trig_pin: int
    echo_pin: int
    echo_timeout_s: float


@dataclass(slots=True)
class GeometryConfig:
    mount_height_cm: float
    full_line_cm: float
    cross_section_cm2: float


@dataclass(slots=True)
class MeasurementConfig:
    sample_count: int
    min_valid_samples: int
    confidence_level: float
    mad_k: float
    turbulence_cm: float
    sensor_min_cm: float
    sensor_max_cm: float


@dataclass(slots=True)
class IdleWindow:
    start: time
    end: time

    def contains(self, t: time) -> bool:
        """True if t is inside the window, handling wrap past midnight."""
        if self.start <= self.end:
            return self.start <= t < self.end
        return t >= self.start or t < self.end  # wraps midnight


@dataclass(slots=True)
class DetectionConfig:
    sample_interval_s: float
    rolling_window_min: float
    min_points: int
    min_leak_rate_cm_per_hr: float
    watch_rate_cm_per_hr: float
    refill_min_cm: float
    flush_drop_cm: float
    min_refills_for_leak: int
    occupied_confidence_discount: float
    idle_window: IdleWindow


@dataclass(slots=True)
class MqttConfig:
    host: str
    port: int
    topic: str
    qos: int
    tls: bool
    ca_certs: str | None
    keepalive_s: int


@dataclass(slots=True)
class RestConfig:
    url: str
    timeout_s: float


@dataclass(slots=True)
class TelemetryConfig:
    transport: str
    mqtt: MqttConfig
    rest: RestConfig
    spool_db: str
    max_spool_rows: int
    # Credentials are pulled from the environment, never the file.
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    rest_token: str | None = None


@dataclass(slots=True)
class Config:
    config_version: str
    firmware_version: str
    device_id: str
    sensor: SensorConfig
    gpio: GpioConfig
    geometry: GeometryConfig
    measurement: MeasurementConfig
    detection: DetectionConfig
    telemetry: TelemetryConfig
    source_path: str | None = field(default=None)


# --- helpers ----------------------------------------------------------------


_VALID_MODES = {"real", "sim"}
_VALID_SCENARIOS = {"normal", "leak_slow", "leak_fast", "sensor_fault"}
_VALID_TRANSPORTS = {"mqtt", "rest"}


def _require(d: dict, key: str, ctx: str) -> Any:
    if key not in d:
        raise ConfigError(f"missing required key '{key}' in {ctx}")
    return d[key]


def _parse_hhmm(value: str, ctx: str) -> time:
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError) as exc:
        raise ConfigError(f"bad time '{value}' in {ctx}; expected HH:MM") from exc


def load_config(path: str) -> Config:
    """Load YAML config, overlay env-var credentials, and validate."""
    if not os.path.exists(path):
        raise ConfigError(f"config file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ConfigError("config root must be a mapping")

    sensor_raw = _require(raw, "sensor", "config")
    gpio_raw = _require(raw, "gpio", "config")
    geom_raw = _require(raw, "geometry", "config")
    meas_raw = _require(raw, "measurement", "config")
    det_raw = _require(raw, "detection", "config")
    tel_raw = _require(raw, "telemetry", "config")
    idle_raw = _require(det_raw, "idle_window", "detection")
    mqtt_raw = _require(tel_raw, "mqtt", "telemetry")
    rest_raw = _require(tel_raw, "rest", "telemetry")

    cfg = Config(
        config_version=str(_require(raw, "config_version", "config")),
        firmware_version=str(_require(raw, "firmware_version", "config")),
        device_id=str(_require(raw, "device_id", "config")),
        sensor=SensorConfig(
            mode=str(_require(sensor_raw, "mode", "sensor")),
            sim_scenario=str(_require(sensor_raw, "sim_scenario", "sensor")),
            sim_seed=sensor_raw.get("sim_seed"),
        ),
        gpio=GpioConfig(
            trig_pin=int(_require(gpio_raw, "trig_pin", "gpio")),
            echo_pin=int(_require(gpio_raw, "echo_pin", "gpio")),
            echo_timeout_s=float(_require(gpio_raw, "echo_timeout_s", "gpio")),
        ),
        geometry=GeometryConfig(
            mount_height_cm=float(_require(geom_raw, "mount_height_cm", "geometry")),
            full_line_cm=float(_require(geom_raw, "full_line_cm", "geometry")),
            cross_section_cm2=float(_require(geom_raw, "cross_section_cm2", "geometry")),
        ),
        measurement=MeasurementConfig(
            sample_count=int(_require(meas_raw, "sample_count", "measurement")),
            min_valid_samples=int(_require(meas_raw, "min_valid_samples", "measurement")),
            confidence_level=float(_require(meas_raw, "confidence_level", "measurement")),
            mad_k=float(_require(meas_raw, "mad_k", "measurement")),
            turbulence_cm=float(_require(meas_raw, "turbulence_cm", "measurement")),
            sensor_min_cm=float(_require(meas_raw, "sensor_min_cm", "measurement")),
            sensor_max_cm=float(_require(meas_raw, "sensor_max_cm", "measurement")),
        ),
        detection=DetectionConfig(
            sample_interval_s=float(_require(det_raw, "sample_interval_s", "detection")),
            rolling_window_min=float(_require(det_raw, "rolling_window_min", "detection")),
            min_points=int(_require(det_raw, "min_points", "detection")),
            min_leak_rate_cm_per_hr=float(
                _require(det_raw, "min_leak_rate_cm_per_hr", "detection")
            ),
            watch_rate_cm_per_hr=float(_require(det_raw, "watch_rate_cm_per_hr", "detection")),
            refill_min_cm=float(_require(det_raw, "refill_min_cm", "detection")),
            flush_drop_cm=float(_require(det_raw, "flush_drop_cm", "detection")),
            min_refills_for_leak=int(_require(det_raw, "min_refills_for_leak", "detection")),
            occupied_confidence_discount=float(
                _require(det_raw, "occupied_confidence_discount", "detection")
            ),
            idle_window=IdleWindow(
                start=_parse_hhmm(_require(idle_raw, "start", "idle_window"), "idle_window"),
                end=_parse_hhmm(_require(idle_raw, "end", "idle_window"), "idle_window"),
            ),
        ),
        telemetry=TelemetryConfig(
            transport=str(_require(tel_raw, "transport", "telemetry")),
            mqtt=MqttConfig(
                host=str(_require(mqtt_raw, "host", "mqtt")),
                port=int(_require(mqtt_raw, "port", "mqtt")),
                topic=str(_require(mqtt_raw, "topic", "mqtt")),
                qos=int(_require(mqtt_raw, "qos", "mqtt")),
                tls=bool(_require(mqtt_raw, "tls", "mqtt")),
                ca_certs=mqtt_raw.get("ca_certs"),
                keepalive_s=int(_require(mqtt_raw, "keepalive_s", "mqtt")),
            ),
            rest=RestConfig(
                url=str(_require(rest_raw, "url", "rest")),
                timeout_s=float(_require(rest_raw, "timeout_s", "rest")),
            ),
            spool_db=str(_require(tel_raw, "spool_db", "telemetry")),
            max_spool_rows=int(_require(tel_raw, "max_spool_rows", "telemetry")),
            mqtt_username=os.environ.get("AQUALERT_MQTT_USERNAME"),
            mqtt_password=os.environ.get("AQUALERT_MQTT_PASSWORD"),
            rest_token=os.environ.get("AQUALERT_REST_TOKEN"),
        ),
        source_path=path,
    )
    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    """Raise ConfigError on any out-of-range or inconsistent value."""
    errs: list[str] = []

    if cfg.sensor.mode not in _VALID_MODES:
        errs.append(f"sensor.mode must be one of {sorted(_VALID_MODES)}")
    if cfg.sensor.sim_scenario not in _VALID_SCENARIOS:
        errs.append(f"sensor.sim_scenario must be one of {sorted(_VALID_SCENARIOS)}")

    g = cfg.geometry
    if g.mount_height_cm <= 0:
        errs.append("geometry.mount_height_cm must be > 0")
    if not (0 < g.full_line_cm < g.mount_height_cm):
        errs.append("geometry.full_line_cm must be > 0 and < mount_height_cm")
    if g.cross_section_cm2 <= 0:
        errs.append("geometry.cross_section_cm2 must be > 0")

    m = cfg.measurement
    if m.sample_count < 3:
        errs.append("measurement.sample_count must be >= 3 for a meaningful CI")
    if not (1 < m.min_valid_samples <= m.sample_count):
        errs.append("measurement.min_valid_samples must be in (1, sample_count]")
    if not (0.0 < m.confidence_level < 1.0):
        errs.append("measurement.confidence_level must be in (0, 1)")
    if m.mad_k <= 0:
        errs.append("measurement.mad_k must be > 0")
    if m.sensor_min_cm >= m.sensor_max_cm:
        errs.append("measurement.sensor_min_cm must be < sensor_max_cm")

    d = cfg.detection
    if d.sample_interval_s <= 0:
        errs.append("detection.sample_interval_s must be > 0")
    if d.rolling_window_min <= 0:
        errs.append("detection.rolling_window_min must be > 0")
    if d.min_points < 3:
        errs.append("detection.min_points must be >= 3")
    if d.min_leak_rate_cm_per_hr <= 0:
        errs.append("detection.min_leak_rate_cm_per_hr must be > 0")
    if not (0 < d.watch_rate_cm_per_hr <= d.min_leak_rate_cm_per_hr):
        errs.append("detection.watch_rate_cm_per_hr must be in (0, min_leak_rate]")
    if d.refill_min_cm <= 0:
        errs.append("detection.refill_min_cm must be > 0")
    if d.flush_drop_cm <= d.refill_min_cm:
        errs.append("detection.flush_drop_cm must be > refill_min_cm")
    if d.min_refills_for_leak < 1:
        errs.append("detection.min_refills_for_leak must be >= 1")
    if not (0.0 <= d.occupied_confidence_discount <= 1.0):
        errs.append("detection.occupied_confidence_discount must be in [0, 1]")

    t = cfg.telemetry
    if t.transport not in _VALID_TRANSPORTS:
        errs.append(f"telemetry.transport must be one of {sorted(_VALID_TRANSPORTS)}")
    if t.mqtt.qos not in (0, 1, 2):
        errs.append("telemetry.mqtt.qos must be 0, 1, or 2")
    if t.mqtt.port <= 0 or t.mqtt.port > 65535:
        errs.append("telemetry.mqtt.port must be a valid TCP port")
    if t.max_spool_rows <= 0:
        errs.append("telemetry.max_spool_rows must be > 0")

    if errs:
        raise ConfigError("invalid configuration:\n  - " + "\n  - ".join(errs))
