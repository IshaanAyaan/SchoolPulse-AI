from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from urllib import error, request

import serial


log = logging.getLogger("aqualert.serial_bridge")


def post_json(url: str, payload: dict, timeout_s: float) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout_s) as response:
        response.read()
        if response.status >= 400:
            raise RuntimeError(f"backend returned HTTP {response.status}")


def parse_json_line(raw_line: str) -> dict | None:
    try:
        data = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def enrich_payload(serial_payload: dict, device_id: str, location: str) -> dict | None:
    if (
        "distance_cm" not in serial_payload
        and "fill_percent" not in serial_payload
        and serial_payload.get("status") != "sensor_fault"
    ):
        return None

    enriched = dict(serial_payload)
    enriched["device_id"] = device_id
    enriched["location"] = location
    enriched["recorded_at"] = datetime.now(timezone.utc).isoformat()
    enriched["reading_source"] = "arduino-serial"
    return enriched


def run_bridge(args: argparse.Namespace) -> None:
    with serial.Serial(args.port, args.baud, timeout=1) as connection:
        log.info("connected to %s at %s baud", args.port, args.baud)
        time.sleep(args.startup_delay_s)

        while True:
            raw_line = connection.readline().decode("utf-8", errors="ignore").strip()
            if not raw_line:
                continue

            serial_payload = parse_json_line(raw_line)
            if serial_payload is None:
                log.debug("ignored non-json line: %s", raw_line)
                continue

            payload = enrich_payload(serial_payload, args.device_id, args.location)
            if payload is None:
                log.debug("ignored serial event: %s", serial_payload)
                continue

            log.info(
                "reading seq=%s fill=%s%% distance=%scm status=%s",
                payload.get("arduino_sequence"),
                payload.get("fill_percent"),
                payload.get("distance_cm"),
                payload.get("status"),
            )

            if args.dry_run:
                continue

            try:
                post_json(args.backend_url, payload, args.timeout_s)
            except (RuntimeError, error.URLError, error.HTTPError, TimeoutError) as exc:
                log.warning("failed to forward reading to %s: %s", args.backend_url, exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forward Arduino UNO water readings to the Pulse Agent backend.")
    parser.add_argument("--port", required=True, help="Serial port for the Arduino, for example /dev/tty.usbmodem1101")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8010/api/water/live")
    parser.add_argument("--device-id", default="aqualert-uno-r4")
    parser.add_argument("--location", default="Hackathon tank demo")
    parser.add_argument("--timeout-s", type=float, default=5.0)
    parser.add_argument("--startup-delay-s", type=float, default=2.0, help="Wait for the UNO auto-reset before reading.")
    parser.add_argument("--dry-run", action="store_true", help="Read and log serial JSON without posting to the backend.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_bridge(args)


if __name__ == "__main__":
    main()
