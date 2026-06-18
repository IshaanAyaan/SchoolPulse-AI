from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "synthetic"
RANDOM_SEED = 42


ZONES = [
    "A-Wing Classrooms",
    "B-Wing Bathrooms",
    "Cafeteria",
    "Gym",
    "Auditorium",
    "Science Lab",
    "Library",
]

EVENT_CATEGORIES = ["sports", "club", "assembly", "testing", "arts", "family_night", "competition"]
EVENT_NAMES = {
    "sports": ["Volleyball Game", "Basketball Game", "Soccer Banquet"],
    "club": ["Robotics Meeting", "Green Team Workshop", "NHS Service Night"],
    "assembly": ["Awards Assembly", "Guest Speaker", "College Night"],
    "testing": ["Practice SAT", "AP Review Session", "Mock Exams"],
    "arts": ["Band Concert", "Theater Showcase", "Art Walk"],
    "family_night": ["Open House", "Curriculum Night", "STEM Family Night"],
    "competition": ["Robotics Tournament", "Science Olympiad", "Math Competition"],
}


def daterange_hours(start: datetime, end: datetime):
    current = start
    while current <= end:
        yield current
        current += timedelta(hours=1)


def make_events() -> pd.DataFrame:
    rows = []
    start = datetime(2026, 3, 1)
    for event_num in range(1, 41):
        category = random.choice(EVENT_CATEGORIES)
        date = start + timedelta(days=random.randint(0, 95))
        if date.weekday() >= 5:
            start_hour = random.choice([9, 10, 13, 17])
        else:
            start_hour = random.choice([15, 16, 17, 18])

        room = random.choice(["Gym", "Auditorium", "Cafeteria", "Library", "Science Lab"])
        expected_attendance = int(np.clip(np.random.normal(180, 85), 25, 520))
        duration_hr = round(float(np.clip(np.random.normal(2.4, 0.9), 1.0, 6.0)), 1)
        actual_attendance = int(expected_attendance * np.clip(np.random.normal(0.92, 0.16), 0.45, 1.25))
        food_ordered_servings = int(expected_attendance * random.choice([0.8, 0.9, 1.0, 1.1]))
        leftover_servings = max(0, food_ordered_servings - int(actual_attendance * random.uniform(0.55, 0.92)))
        food_waste_lbs = round(leftover_servings * random.uniform(0.18, 0.34), 1)
        energy_kwh = round(duration_hr * (8 + expected_attendance * 0.035 + random.uniform(0, 5)), 1)

        rows.append(
            {
                "event_id": f"EVT-{event_num:03d}",
                "name": random.choice(EVENT_NAMES[category]),
                "category": category,
                "date": date.date().isoformat(),
                "start_hour": start_hour,
                "duration_hr": duration_hr,
                "rooms": room,
                "expected_attendance": expected_attendance,
                "actual_attendance": actual_attendance,
                "food_ordered_servings": food_ordered_servings,
                "food_waste_lbs": food_waste_lbs,
                "energy_kwh": energy_kwh,
                "notes": "Synthetic event outcome used to demonstrate year-over-year planning memory.",
            }
        )
    return pd.DataFrame(rows).sort_values(["date", "start_hour"])


def make_energy_logs(events: pd.DataFrame) -> pd.DataFrame:
    event_lookup = {}
    for _, event in events.iterrows():
        event_date = event["date"]
        room = event["rooms"]
        start_hour = int(event["start_hour"])
        end_hour = start_hour + math.ceil(float(event["duration_hr"]))
        for hour in range(start_hour, end_hour + 1):
            event_lookup[(event_date, room, hour)] = event

    base_load = {
        "A-Wing Classrooms": 7.5,
        "B-Wing Bathrooms": 2.2,
        "Cafeteria": 9.8,
        "Gym": 10.5,
        "Auditorium": 6.5,
        "Science Lab": 8.2,
        "Library": 5.8,
    }

    rows = []
    start = datetime(2026, 3, 1)
    end = datetime(2026, 6, 7, 23)
    for timestamp in daterange_hours(start, end):
        day_of_year = timestamp.timetuple().tm_yday
        outdoor_temp = 73 + 12 * math.sin(day_of_year / 365 * 2 * math.pi) + random.gauss(0, 4)
        school_hours = timestamp.weekday() < 5 and 7 <= timestamp.hour <= 16

        for zone in ZONES:
            expected_occupancy = 1 if school_hours and zone not in ["Gym", "Auditorium"] else 0
            event = event_lookup.get((timestamp.date().isoformat(), zone, timestamp.hour))
            event_id = ""
            event_boost = 0.0
            if event is not None:
                expected_occupancy = 1
                event_id = event["event_id"]
                event_boost = 3.0 + float(event["expected_attendance"]) * 0.025

            temp_factor = max(outdoor_temp - 78, 0) * 0.22 + max(62 - outdoor_temp, 0) * 0.12
            occupied_factor = 3.5 if expected_occupancy else 0.7
            expected = base_load[zone] + occupied_factor + temp_factor + event_boost

            is_waste = 0
            reason = "normal"
            extra = 0.0
            after_hours = not school_hours and event is None
            if after_hours and random.random() < 0.012:
                is_waste = 1
                reason = random.choice(["lights_left_on", "hvac_after_hours", "projector_or_lab_load"])
                extra = random.uniform(4.5, 15.0)
            if zone in ["Gym", "Auditorium"] and timestamp.hour in [21, 22, 23] and random.random() < 0.035:
                is_waste = 1
                reason = "post_event_shutdown_missed"
                extra = random.uniform(8.0, 18.0)

            actual = max(0.4, expected + extra + random.gauss(0, 0.8))
            rows.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "zone": zone,
                    "hour": timestamp.hour,
                    "weekday": timestamp.weekday(),
                    "outdoor_temp_f": round(outdoor_temp, 1),
                    "occupancy_expected": expected_occupancy,
                    "event_id": event_id,
                    "expected_kwh": round(expected, 2),
                    "actual_kwh": round(actual, 2),
                    "is_energy_waste": is_waste,
                    "waste_reason": reason,
                }
            )
    return pd.DataFrame(rows)


def make_water_alerts() -> pd.DataFrame:
    locations = [
        "B-Wing Bathroom Sink 2",
        "B-Wing Bathroom Toilet 3",
        "Gym Locker Room Shower",
        "Cafeteria Handwash Sink",
        "Main Supply Closet",
        "Science Lab Sink 4",
    ]
    rows = []
    start = datetime(2026, 3, 1)
    for alert_num in range(1, 71):
        timestamp = start + timedelta(days=random.randint(0, 98), hours=random.randint(6, 22))
        duration = int(np.clip(np.random.gamma(2.2, 18), 4, 190))
        confidence = float(np.clip(np.random.normal(0.76, 0.13), 0.42, 0.98))
        is_leak = confidence > 0.68 and duration > 18
        status = random.choice(["open", "needs_verification", "resolved"]) if is_leak else random.choice(["resolved", "false_alarm"])
        gallons = duration * random.uniform(0.45, 1.9) if is_leak else duration * random.uniform(0.05, 0.2)
        rows.append(
            {
                "alert_id": f"WTR-{alert_num:03d}",
                "timestamp": timestamp.isoformat(),
                "location": random.choice(locations),
                "duration_min": duration,
                "confidence": round(confidence, 3),
                "estimated_gallons": round(gallons, 1),
                "status": status,
                "model_reason": "continuous audio/vibration pattern" if is_leak else "short fixture-use pattern",
                "human_verified": int(status == "resolved" and is_leak),
            }
        )
    return pd.DataFrame(rows)


def make_waste_logs(events: pd.DataFrame) -> pd.DataFrame:
    items = [
        ("apple cores", "compost"),
        ("pizza crust", "compost"),
        ("milk carton", "recycling"),
        ("plastic wrapper", "landfill"),
        ("unopened granola bar", "unopened_food"),
        ("salad leftovers", "compost"),
        ("paper tray", "compost"),
        ("foil pouch", "landfill"),
        ("water bottle", "recycling"),
    ]
    sources = ["Cafeteria Bin 1", "Cafeteria Bin 2", "Event Cleanup", "Compost AI Demo Bin"]
    event_ids = [""] + events["event_id"].sample(n=min(22, len(events)), random_state=RANDOM_SEED).tolist()
    rows = []
    for log_num in range(1, 901):
        item, category = random.choice(items)
        confidence = float(np.clip(np.random.normal(0.78, 0.16), 0.25, 0.99))
        contamination = int((category in ["compost", "recycling"] and random.random() < 0.08) or confidence < 0.48)
        rows.append(
            {
                "log_id": f"WST-{log_num:04d}",
                "timestamp": (datetime(2026, 3, 1) + timedelta(days=random.randint(0, 98), minutes=random.randint(0, 1439))).isoformat(),
                "source": random.choice(sources),
                "event_id": random.choice(event_ids),
                "item": item,
                "category": category,
                "confidence": round(confidence, 3),
                "weight_lbs": round(float(np.clip(np.random.gamma(1.6, 0.34), 0.05, 4.5)), 2),
                "contamination_flag": contamination,
            }
        )
    return pd.DataFrame(rows)


def make_transport_plans(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, event in events.iterrows():
        attendance = int(event["expected_attendance"])
        idle_risk = min(0.95, max(0.1, attendance / 650 + random.uniform(-0.08, 0.16)))
        gates = "front loop" if attendance < 160 else "front loop + north lot"
        if attendance > 350:
            gates = "front loop + north lot + gym exit"
        rows.append(
            {
                "event_id": event["event_id"],
                "expected_attendance": attendance,
                "gates_used": gates,
                "pickup_window_min": int(np.clip(attendance / 8 + random.gauss(0, 8), 15, 90)),
                "idle_risk": round(idle_risk, 3),
                "recommendation": "stagger pickup messages and use student volunteers for wayfinding"
                if idle_risk > 0.55
                else "standard pickup plan is enough",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    events = make_events()
    energy = make_energy_logs(events)
    water = make_water_alerts()
    waste = make_waste_logs(events)
    transport = make_transport_plans(events)

    events.to_csv(OUT / "event_logs.csv", index=False)
    energy.to_csv(OUT / "energy_logs.csv", index=False)
    water.to_csv(OUT / "water_logs.csv", index=False)
    waste.to_csv(OUT / "waste_logs.csv", index=False)
    transport.to_csv(OUT / "transport_plans.csv", index=False)

    print(f"Wrote synthetic data to {OUT}")
    print(f"energy_logs={len(energy)} event_logs={len(events)} water_logs={len(water)} waste_logs={len(waste)}")


if __name__ == "__main__":
    main()
