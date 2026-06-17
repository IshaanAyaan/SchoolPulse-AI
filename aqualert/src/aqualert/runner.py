"""Main run loop: sensor -> measurement -> detector -> telemetry.

Usage:
    python -m aqualert.runner --config config.yaml

Runs forever, sampling at detection.sample_interval_s. Works identically with
the real HC-SR04 (mode: real) or the simulator (mode: sim).
"""

from __future__ import annotations

import argparse
import logging
import time
import uuid
from datetime import datetime, timezone

from .config import Config, load_config
from .detector import Detector
from .measurement import MeasurementEngine
from .models import Detection, Measurement, TelemetryMsg
from .sensor import build_sensor
from .telemetry import TelemetryClient

log = logging.getLogger("aqualert.runner")


def build_message(cfg: Config, det: Detection, m: Measurement) -> TelemetryMsg:
    """Assemble the wire payload from a detection + its source measurement."""
    return TelemetryMsg(
        msg_id=uuid.uuid4().hex,
        device_id=cfg.device_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        level_cm=m.level_cm,
        level_ci=m.level_ci,
        state=det.state.value,
        confidence=det.confidence,
        slope_cm_per_hr=det.slope_cm_per_hr,
        slope_ci=det.slope_ci,
        refill_events=det.refill_events,
        est_waste_gpd=det.est_waste_gpd,
        config_version=cfg.config_version,
        firmware_version=cfg.firmware_version,
    )


def run(config_path: str) -> None:
    cfg = load_config(config_path)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info(
        "starting Aqualert device=%s mode=%s scenario=%s",
        cfg.device_id, cfg.sensor.mode, cfg.sensor.sim_scenario,
    )

    sensor = build_sensor(cfg)  # real-time clock for both real and sim
    engine = MeasurementEngine(cfg, sensor)
    detector = Detector(cfg)
    telemetry = TelemetryClient.from_config(cfg)

    interval = cfg.detection.sample_interval_s
    try:
        while True:
            now = datetime.now()  # local time -> idle-window check
            measurement = engine.measure(now)
            detection = detector.update(measurement)
            msg = build_message(cfg, detection, measurement)
            delivered = telemetry.send(msg)
            log.info(
                "%s | delivered=%s pending=%d",
                detection.summary(), delivered, telemetry.pending_count(),
            )
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        sensor.close()
        telemetry.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Aqualert leak-detector run loop")
    ap.add_argument("--config", default="config.yaml", help="path to config.yaml")
    run(ap.parse_args().config)


if __name__ == "__main__":
    main()
