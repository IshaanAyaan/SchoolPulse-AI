#!/usr/bin/env python3
"""Calibrate the sensor geometry for a specific tank.

Two physical reference points are needed:
  1. EMPTY tank -> the measured distance IS the mount height (sensor to bottom).
  2. FULL tank  -> full_line_cm = mount_height - measured_distance.

Run on the Pi next to the toilet:
    python scripts/calibrate.py --config config.yaml --write

In simulation it still works end-to-end (the simulated full tank reads the
configured full line), which is useful for a dry run of the procedure.
"""

from __future__ import annotations

import argparse
import os
import sys
from statistics import mean, pstdev

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import yaml  # noqa: E402

from aqualert.config import load_config  # noqa: E402
from aqualert.measurement import MeasurementEngine  # noqa: E402
from aqualert.models import MeasurementStatus  # noqa: E402
from aqualert.sensor import build_sensor  # noqa: E402


def _averaged_distance(engine: MeasurementEngine, n: int) -> float:
    """Take n logical measurements and return the mean distance (cm)."""
    from datetime import datetime

    distances: list[float] = []
    for _ in range(n):
        m = engine.measure(datetime.now())
        if m.status is MeasurementStatus.OK and m.distance_cm is not None:
            distances.append(m.distance_cm)
    if not distances:
        raise SystemExit("calibration failed: no valid measurements (check wiring)")
    spread = pstdev(distances) if len(distances) > 1 else 0.0
    print(f"  -> {len(distances)} readings, mean {mean(distances):.2f} cm "
          f"(sd {spread:.2f} cm)")
    return mean(distances)


def main() -> None:
    ap = argparse.ArgumentParser(description="Aqualert sensor calibration")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--samples", type=int, default=10, help="logical measurements per step")
    ap.add_argument("--write", action="store_true", help="persist results to the config file")
    ap.add_argument("--yes", action="store_true", help="skip interactive prompts (sim/dry-run)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sensor = build_sensor(cfg)
    engine = MeasurementEngine(cfg, sensor)

    try:
        if not args.yes:
            input("Step 1/2: EMPTY the tank completely, then press Enter...")
        print("Measuring mount height (empty tank)...")
        mount_height = _averaged_distance(engine, args.samples)

        if not args.yes:
            input("Step 2/2: let the tank refill to FULL, then press Enter...")
        print("Measuring full line (full tank)...")
        full_distance = _averaged_distance(engine, args.samples)
    finally:
        sensor.close()

    full_line = mount_height - full_distance
    print("\nCalibration result:")
    print(f"  mount_height_cm : {mount_height:.2f}")
    print(f"  full_line_cm    : {full_line:.2f}")

    if full_line <= 0 or full_line >= mount_height:
        raise SystemExit(
            "implausible geometry (full_line must be >0 and <mount_height); "
            "re-run and confirm the tank was actually empty then full."
        )

    if args.write:
        with open(args.config, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        raw["geometry"]["mount_height_cm"] = round(mount_height, 2)
        raw["geometry"]["full_line_cm"] = round(full_line, 2)
        with open(args.config, "w", encoding="utf-8") as fh:
            yaml.safe_dump(raw, fh, sort_keys=False)
        print(f"\nWrote geometry to {args.config} (note: YAML comments are not preserved).")
    else:
        print("\n(dry run) re-run with --write to persist these values.")


if __name__ == "__main__":
    main()
