#!/usr/bin/env python3
"""Run the full Aqualert pipeline on synthetic data -- no hardware, no waiting.

A VirtualClock starts inside the overnight idle window and advances by the
configured sample interval each step, so hours of monitoring compress into a
fraction of a second. The same MeasurementEngine and Detector used in
production are exercised end to end.

    python scripts/simulate.py --scenario leak_slow
    python scripts/simulate.py --scenario normal --json

Scenarios: normal | leak_slow | leak_fast | sensor_fault
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aqualert.config import load_config  # noqa: E402
from aqualert.detector import Detector  # noqa: E402
from aqualert.measurement import MeasurementEngine  # noqa: E402
from aqualert.runner import build_message  # noqa: E402
from aqualert.sensor import VirtualClock, build_sensor  # noqa: E402

_DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "..", "config.example.yaml")


def run_simulation(scenario: str, config_path: str, steps: int, show_json: bool) -> int:
    cfg = load_config(config_path)
    cfg.sensor.mode = "sim"
    cfg.sensor.sim_scenario = scenario

    # Start at 23:30 local so the whole run sits in the idle window
    # (no legitimate use -> single-window high-confidence detection).
    start_dt = datetime.now().replace(hour=23, minute=30, second=0, microsecond=0)
    clock = VirtualClock(start_dt.timestamp())

    sensor = build_sensor(cfg, clock=clock.now)
    engine = MeasurementEngine(cfg, sensor)
    detector = Detector(cfg)

    interval = cfg.detection.sample_interval_s
    detection = None
    print(f"== Aqualert simulation: scenario='{scenario}', {steps} steps "
          f"@ {interval:.0f}s ==\n")
    for i in range(steps):
        now = datetime.fromtimestamp(clock.now())
        measurement = engine.measure(now)
        detection = detector.update(measurement)
        if i % 30 == 0 or i == steps - 1:
            clk = now.strftime("%H:%M")
            print(f"  t+{i:03d} ({clk})  {detection.summary()}")
        clock.advance(interval)

    assert detection is not None
    print("\n-- final detection --")
    print(detection.summary())
    print("\n-- reasoning trace --")
    print(json.dumps(detection.reasoning, indent=2, default=str))

    msg = build_message(cfg, detection, measurement)
    if show_json:
        print("\n-- telemetry payload --")
        print(json.dumps(json.loads(msg.to_json()), indent=2))

    sensor.close()
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Aqualert simulation")
    ap.add_argument(
        "--scenario",
        default="normal",
        choices=["normal", "leak_slow", "leak_fast", "sensor_fault"],
    )
    ap.add_argument("--config", default=_DEFAULT_CONFIG)
    ap.add_argument("--steps", type=int, default=180, help="number of logical measurements")
    ap.add_argument("--json", action="store_true", help="also print the telemetry payload")
    args = ap.parse_args()
    raise SystemExit(run_simulation(args.scenario, args.config, args.steps, args.json))


if __name__ == "__main__":
    main()
