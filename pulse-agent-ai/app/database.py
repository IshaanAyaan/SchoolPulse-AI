from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .config import DATABASE_PATH, SYNTHETIC_DIR
from .data_normalization import normalize_frame


TABLE_FILES = {
    "energy_logs": "energy_logs.csv",
    "event_logs": "event_logs.csv",
    "water_logs": "water_logs.csv",
    "waste_logs": "waste_logs.csv",
    "transport_plans": "transport_plans.csv",
}


def get_connection(db_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_database(db_path: Path = DATABASE_PATH, synthetic_dir: Path = SYNTHETIC_DIR) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as connection:
        for table, filename in TABLE_FILES.items():
            csv_path = synthetic_dir / filename
            if not csv_path.exists():
                continue
            frame = normalize_frame(table, pd.read_csv(csv_path))
            frame.to_sql(table, connection, if_exists="replace", index=False)
        create_index_if_columns_exist(connection, "energy_logs", "idx_energy_timestamp", ["timestamp"])
        create_index_if_columns_exist(connection, "energy_logs", "idx_energy_zone", ["zone"])
        create_index_if_columns_exist(connection, "water_logs", "idx_water_status", ["status"])
        create_index_if_columns_exist(connection, "waste_logs", "idx_waste_event", ["event_id"])
        connection.commit()


def create_index_if_columns_exist(connection: sqlite3.Connection, table: str, index_name: str, columns: list[str]) -> None:
    table_columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if not set(columns).issubset(table_columns):
        return
    column_sql = ", ".join(columns)
    connection.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column_sql})")


def ensure_database() -> None:
    if not DATABASE_PATH.exists():
        init_database()


def fetch_all(table: str) -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(row) for row in rows]
