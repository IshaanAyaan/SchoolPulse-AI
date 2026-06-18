from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from .config import DATABASE_PATH, MODELS_DIR, SYNTHETIC_DIR
from .data_normalization import normalize_frame
from .database import get_connection


@dataclass
class DataFrames:
    energy: pd.DataFrame
    events: pd.DataFrame
    water: pd.DataFrame
    waste: pd.DataFrame
    transport: pd.DataFrame


class AnalyticsService:
    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self.energy_model_path = MODELS_DIR / "energy_waste_classifier.joblib"
        self.event_model_path = MODELS_DIR / "event_servings_regressor.joblib"

    def _read_table(self, table: str, fallback_csv: str) -> pd.DataFrame:
        if self.db_path.exists():
            with get_connection(self.db_path) as connection:
                return normalize_frame(table, pd.read_sql_query(f"SELECT * FROM {table}", connection))
        path = SYNTHETIC_DIR / fallback_csv
        return normalize_frame(table, pd.read_csv(path)) if path.exists() else pd.DataFrame()

    def load_frames(self) -> DataFrames:
        return DataFrames(
            energy=self._read_table("energy_logs", "energy_logs.csv"),
            events=self._read_table("event_logs", "event_logs.csv"),
            water=self._read_table("water_logs", "water_logs.csv"),
            waste=self._read_table("waste_logs", "waste_logs.csv"),
            transport=self._read_table("transport_plans", "transport_plans.csv"),
        )

    def overview(self) -> dict:
        frames = self.load_frames()
        energy_summary = self.energy_summary(frames.energy)
        water_summary = self.water_summary(frames.water)
        waste_summary = self.waste_summary(frames.waste)
        events_summary = self.events_summary(frames.events, frames.transport)

        cards = []
        cards.extend(energy_summary["top_cards"][:2])
        cards.extend(water_summary["top_cards"][:2])
        cards.extend(waste_summary["top_cards"][:2])
        cards.extend(events_summary["top_cards"][:2])
        cards = sorted(cards, key=lambda card: card["confidence"], reverse=True)[:6]

        return {
            "mission": "Turn hidden school footprint patterns into human-checkable actions.",
            "impact_totals": {
                "estimated_wasted_kwh": round(float(energy_summary["estimated_wasted_kwh"]), 1),
                "open_water_gallons_at_risk": round(float(water_summary["open_gallons_at_risk"]), 1),
                "food_waste_lbs_logged": round(float(waste_summary["food_waste_lbs"]), 1),
                "events_analyzed": int(events_summary["events_analyzed"]),
            },
            "top_action_cards": cards,
        }

    def energy_summary(self, energy: pd.DataFrame | None = None) -> dict:
        if energy is None:
            energy = self.load_frames().energy
        if energy.empty:
            return {"estimated_wasted_kwh": 0, "top_cards": [], "rows": []}

        frame = energy.copy()
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame["wasted_kwh"] = (frame["actual_kwh"] - frame["expected_kwh"]).clip(lower=0)
        frame["is_anomaly_rule"] = (frame["wasted_kwh"] >= 4.0) | (frame["actual_kwh"] >= frame["expected_kwh"] * 1.3)
        anomalies = frame[frame["is_anomaly_rule"]].sort_values("wasted_kwh", ascending=False).head(10)

        cards = []
        for _, row in anomalies.head(4).iterrows():
            cards.append(
                {
                    "module": "Energy",
                    "priority": "high" if row["wasted_kwh"] >= 8 else "medium",
                    "title": "After-hours energy spike",
                    "location": str(row["zone"]),
                    "recommendation": "Check room schedule, lights, HVAC setpoint, and event teardown checklist.",
                    "evidence": f"{row['actual_kwh']:.1f} kWh actual vs {row['expected_kwh']:.1f} kWh expected.",
                    "estimated_impact": f"About {row['wasted_kwh']:.1f} kWh potentially wasted in this hour.",
                    "confidence": min(0.98, 0.72 + float(row["wasted_kwh"]) / 40),
                    "human_check": "Facilities staff confirms whether the room was actually occupied before changing controls.",
                }
            )

        return {
            "estimated_wasted_kwh": float(frame["wasted_kwh"].sum()),
            "top_cards": cards,
            "rows": anomalies.to_dict(orient="records"),
        }

    def water_summary(self, water: pd.DataFrame | None = None) -> dict:
        if water is None:
            water = self.load_frames().water
        if water.empty:
            return {"open_gallons_at_risk": 0, "top_cards": [], "rows": []}

        frame = water.copy()
        open_alerts = frame[frame["status"].isin(["open", "needs_verification"])].copy()
        open_alerts = open_alerts.sort_values(["estimated_gallons", "confidence"], ascending=False)

        cards = []
        for _, row in open_alerts.head(3).iterrows():
            cards.append(
                {
                    "module": "Water",
                    "priority": "high" if row["estimated_gallons"] >= 75 else "medium",
                    "title": f"Possible leak at {row['location']}",
                    "location": str(row["location"]),
                    "recommendation": "Send a custodian to listen/check the fixture before opening a repair ticket.",
                    "evidence": f"{row['duration_min']} min continuous-flow pattern, confidence {row['confidence']:.0%}.",
                    "estimated_impact": f"About {row['estimated_gallons']:.0f} gallons at risk.",
                    "confidence": float(row["confidence"]),
                    "human_check": "Custodian confirms a visible leak or stuck fixture before escalation.",
                }
            )

        return {
            "open_gallons_at_risk": float(open_alerts["estimated_gallons"].sum()),
            "top_cards": cards,
            "rows": open_alerts.head(10).to_dict(orient="records"),
        }

    def waste_summary(self, waste: pd.DataFrame | None = None) -> dict:
        if waste is None:
            waste = self.load_frames().waste
        if waste.empty:
            return {"food_waste_lbs": 0, "top_cards": [], "rows": []}

        frame = waste.copy()
        frame["needs_review"] = (frame["confidence"] < 0.65) | frame["contamination_flag"].astype(bool)
        review = frame[frame["needs_review"]].sort_values(["weight_lbs", "confidence"], ascending=[False, True])
        food_waste = frame[frame["category"].isin(["compost", "unopened_food"])]["weight_lbs"].sum()

        cards = []
        for _, row in review.head(3).iterrows():
            cards.append(
                {
                    "module": "Waste",
                    "priority": "medium",
                    "title": f"Review {row['item']} sorting decision",
                    "location": str(row["source"]),
                    "recommendation": "Ask cafeteria or green-team reviewer to confirm the bin label and update the log.",
                    "evidence": f"Category={row['category']}, confidence {row['confidence']:.0%}, contamination={bool(row['contamination_flag'])}.",
                    "estimated_impact": f"{row['weight_lbs']:.1f} lb item can improve compost/recycling accuracy.",
                    "confidence": max(0.45, 1 - float(row["confidence"])),
                    "human_check": "Human reviewer confirms or corrects the sort so future reports stay trustworthy.",
                }
            )

        return {
            "food_waste_lbs": float(food_waste),
            "top_cards": cards,
            "rows": review.head(10).to_dict(orient="records"),
        }

    def events_summary(self, events: pd.DataFrame | None = None, transport: pd.DataFrame | None = None) -> dict:
        frames = self.load_frames()
        if events is None:
            events = frames.events
        if transport is None:
            transport = frames.transport
        if events.empty:
            return {"events_analyzed": 0, "top_cards": [], "rows": []}

        frame = events.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        frame["food_waste_rate"] = frame["food_waste_lbs"] / frame["food_ordered_servings"].clip(lower=1)
        high_waste = frame.sort_values("food_waste_rate", ascending=False).head(3)

        transport_lookup = {}
        if not transport.empty:
            transport_lookup = transport.set_index("event_id").to_dict(orient="index")

        cards = []
        for _, row in high_waste.iterrows():
            transport_note = transport_lookup.get(row["event_id"], {}).get("recommendation", "Use last event attendance as the starting plan.")
            cards.append(
                {
                    "module": "Events",
                    "priority": "medium",
                    "title": f"Reduce footprint for future {row['category']} events",
                    "location": str(row["rooms"]),
                    "recommendation": f"Order closer to forecast attendance and reuse transport note: {transport_note}",
                    "evidence": f"{row['name']} had {row['actual_attendance']} attendees and {row['food_waste_lbs']:.1f} lb food waste.",
                    "estimated_impact": "Can reduce over-ordering, room energy runtime, and pickup idling.",
                    "confidence": 0.78,
                    "human_check": "Event lead approves final food order, room schedule, and traffic plan.",
                }
            )

        return {
            "events_analyzed": int(len(frame)),
            "top_cards": cards,
            "rows": frame.sort_values("date", ascending=False).head(10).to_dict(orient="records"),
        }

    def recommend_event_plan(self, event_type: str, expected_attendance: int, duration_hr: float) -> dict:
        model_path = self.event_model_path
        if model_path.exists():
            bundle = joblib.load(model_path)
            model = bundle["model"]
            categories = bundle["categories"]
            row = {f"category_{category}": 1 if category == event_type else 0 for category in categories}
            row["expected_attendance"] = expected_attendance
            row["duration_hr"] = duration_hr
            features = pd.DataFrame([row]).reindex(columns=bundle["feature_columns"], fill_value=0)
            servings = int(round(float(model.predict(features)[0])))
        else:
            servings = int(round(expected_attendance * 0.9))

        return {
            "event_type": event_type,
            "expected_attendance": expected_attendance,
            "recommended_servings": max(0, servings),
            "energy_note": "Schedule HVAC/lights to start 45 minutes before arrival and shut down 20 minutes after teardown.",
            "waste_note": "Log actual attendance, leftovers, compost, and trash bags after the event to improve next forecast.",
            "human_check": "Event lead reviews the order and facilities schedule before anything is purchased or changed.",
        }
