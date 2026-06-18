from __future__ import annotations

import re

import pandas as pd


COLUMN_RENAMES = {
    "ID": "id",
    "Timestamp": "timestamp",
    "Date": "date",
    "Name": "name",
    "Event Category": "category",
    "Start Time": "start_time",
    "Duration": "duration_hr",
    "Room": "rooms",
    "Expected Attendance": "expected_attendance",
    "Actual Attendance": "actual_attendance",
    "Food Servings Count": "food_ordered_servings",
    "Food Wasted Count": "food_waste_lbs",
    "Energy Consumption (kwh)": "energy_kwh",
    "Zone": "zone",
    "Hour": "hour",
    "Weekday": "weekday",
    "Outdoor Temperature (°F)": "outdoor_temp_f",
    "Expected Occupancy": "occupancy_expected",
    "Expected Energy Consumption (kwh)": "expected_kwh",
    "Actual Energy Consumption (kwh)": "actual_kwh",
    "Wasted?": "is_energy_waste",
    "Location": "location",
    "State": "state",
    "Confidence Level": "confidence",
    "Water Decline (cm/hr)": "water_decline_cm_hr",
    "Waste Item": "item",
    "Disposal Bin": "category",
}


def snake_case(value: str) -> str:
    value = value.strip().replace("°", "")
    value = re.sub(r"[^0-9a-zA-Z]+", "_", value)
    return value.strip("_").lower()


def parse_percent(value) -> float:
    if pd.isna(value):
        return 0.0
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            parsed = float(cleaned)
        except ValueError:
            return 0.0
        return parsed / 100 if parsed > 1 else parsed
    parsed = float(value)
    return parsed / 100 if parsed > 1 else parsed


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.rename(columns=COLUMN_RENAMES).copy()
    renamed.columns = [snake_case(column) for column in renamed.columns]
    return renamed


def normalize_frame(table: str, frame: pd.DataFrame) -> pd.DataFrame:
    frame = normalize_columns(frame)

    if "confidence" in frame.columns:
        frame["confidence"] = frame["confidence"].map(parse_percent)

    if table == "event_logs":
        if "id" in frame.columns and "event_id" not in frame.columns:
            frame["event_id"] = frame["id"].map(lambda value: f"EVT-{int(value):03d}" if pd.notna(value) else "")
        if "start_time" in frame.columns and "start_hour" not in frame.columns:
            parsed = pd.to_datetime(frame["start_time"], format="%I:%M %p", errors="coerce")
            frame["start_hour"] = parsed.dt.hour.fillna(0).astype(int)
        if "category" in frame.columns:
            frame["category"] = frame["category"].astype(str).str.lower().str.replace(" ", "_")

    if table == "water_logs":
        if "state" in frame.columns and "status" not in frame.columns:
            state = frame["state"].astype(str).str.lower()
            frame["status"] = state.map(
                {
                    "healthy": "closed",
                    "attention needed": "needs_verification",
                    "leaking": "open",
                }
            ).fillna("needs_verification")
        if "water_decline_cm_hr" in frame.columns and "estimated_gallons" not in frame.columns:
            frame["estimated_gallons"] = frame["water_decline_cm_hr"].abs() * 80
        if "duration_min" not in frame.columns:
            frame["duration_min"] = frame["status"].map({"open": 20, "needs_verification": 10}).fillna(1).astype(int)

    if table == "waste_logs":
        if "location" in frame.columns and "source" not in frame.columns:
            frame["source"] = frame["location"]
        if "category" in frame.columns:
            frame["category"] = frame["category"].astype(str).str.lower()
        if "weight_lbs" not in frame.columns:
            frame["weight_lbs"] = frame["category"].map({"compost": 1.0, "garbage": 0.4, "recycling": 0.25}).fillna(0.5)
        if "contamination_flag" not in frame.columns:
            frame["contamination_flag"] = False

    return frame

