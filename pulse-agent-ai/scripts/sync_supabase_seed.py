from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import requests

from app.config import REPO_ROOT, SYNTHETIC_DIR


TABLE_MODULES = {
    "energy_logs.csv": "energy",
    "water_logs.csv": "water",
    "waste_logs.csv": "waste",
    "event_logs.csv": "events",
    "transport_plans.csv": "transportation",
}


def post_sync(kind: str, records: list[dict]) -> dict:
    sync_url = os.getenv("SUPABASE_SYNC_URL")
    secret_key = os.getenv("SUPABASE_SECRET_KEY")
    if not sync_url or not secret_key:
        raise RuntimeError("Set SUPABASE_SYNC_URL and SUPABASE_SECRET_KEY.")

    response = requests.post(
        sync_url,
        headers={"Content-Type": "application/json", "apikey": secret_key},
        json={"kind": kind, "records": records},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def read_csv_records(path: Path, module: str) -> list[dict]:
    with path.open(newline="") as handle:
        return [
            {
                "module": module,
                "source": path.name,
                "payload": row,
                "event_time": row.get("timestamp") or row.get("date"),
            }
            for row in csv.DictReader(handle)
        ]


def source_documents() -> list[dict]:
    candidates = [
        REPO_ROOT / "context" / "README.md",
        REPO_ROOT / "context" / "source-notes" / "google-doc-final-idea.md",
        REPO_ROOT / "info" / "email-summary.md",
        REPO_ROOT / "README.md",
    ]
    records = []
    for path in candidates:
        if path.exists():
            records.append(
                {
                    "source_type": "repo_context",
                    "title": path.stem.replace("-", " ").title(),
                    "url": str(path.relative_to(REPO_ROOT)),
                    "content": path.read_text(encoding="utf-8"),
                    "metadata": {"path": str(path.relative_to(REPO_ROOT))},
                }
            )
    return records


def main() -> None:
    all_logs = []
    for filename, module in TABLE_MODULES.items():
        path = SYNTHETIC_DIR / filename
        if path.exists():
            all_logs.extend(read_csv_records(path, module))

    if all_logs:
        print(json.dumps(post_sync("operations_logs", all_logs), indent=2))

    docs = source_documents()
    if docs:
        print(json.dumps(post_sync("source_documents", docs), indent=2))


if __name__ == "__main__":
    main()
