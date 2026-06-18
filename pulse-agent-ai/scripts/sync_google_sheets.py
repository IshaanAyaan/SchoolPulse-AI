from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Iterable

from app.config import SYNTHETIC_DIR


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
TABLE_FILES = {
    "energy_logs": "energy_logs.csv",
    "water_logs": "water_logs.csv",
    "waste_logs": "waste_logs.csv",
    "event_logs": "event_logs.csv",
    "transport_plans": "transport_plans.csv",
}


def load_credentials():
    from google.oauth2 import service_account

    raw_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    json_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if raw_json:
        return service_account.Credentials.from_service_account_info(json.loads(raw_json), scopes=SCOPES)
    if json_file:
        return service_account.Credentials.from_service_account_file(json_file, scopes=SCOPES)
    raise RuntimeError("Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE.")


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open(newline="") as handle:
        return [row for row in csv.reader(handle)]


def chunked(rows: list[list[str]], size: int = 5000) -> Iterable[list[list[str]]]:
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def ensure_sheet(service, spreadsheet_id: str, title: str, existing_titles: set[str]) -> None:
    if title in existing_titles:
        return
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    ).execute()
    existing_titles.add(title)


def sync_tab(service, spreadsheet_id: str, tab_name: str, rows: list[list[str]]) -> None:
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab_name}'!A:ZZ",
        body={},
    ).execute()

    start_row = 1
    for part in chunked(rows):
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{tab_name}'!A{start_row}",
            valueInputOption="RAW",
            body={"values": part},
        ).execute()
        start_row += len(part)


def main() -> None:
    spreadsheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("Set GOOGLE_SHEET_ID to the destination spreadsheet id.")

    from googleapiclient.discovery import build

    service = build("sheets", "v4", credentials=load_credentials())
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing_titles = {sheet["properties"]["title"] for sheet in metadata.get("sheets", [])}

    for tab_name, filename in TABLE_FILES.items():
        csv_path = SYNTHETIC_DIR / filename
        if not csv_path.exists():
            continue
        ensure_sheet(service, spreadsheet_id, tab_name, existing_titles)
        sync_tab(service, spreadsheet_id, tab_name, read_csv_rows(csv_path))
        print(f"synced {tab_name} from {csv_path}")


if __name__ == "__main__":
    main()
