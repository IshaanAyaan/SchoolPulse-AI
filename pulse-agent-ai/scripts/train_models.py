from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, precision_score, recall_score
from sklearn.model_selection import train_test_split

from app.data_normalization import normalize_frame


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"
MODELS = ROOT / "models"


def train_energy_model() -> dict:
    frame = normalize_frame("energy_logs", pd.read_csv(DATA / "energy_logs.csv"))
    features = frame[["zone", "hour", "weekday", "outdoor_temp_f", "occupancy_expected", "expected_kwh", "actual_kwh"]].copy()
    features["kwh_delta"] = features["actual_kwh"] - features["expected_kwh"]
    features["kwh_ratio"] = features["actual_kwh"] / features["expected_kwh"].clip(lower=0.1)
    features = pd.get_dummies(features, columns=["zone"])
    target = frame["is_energy_waste"]

    x_train, x_test, y_train, y_test = train_test_split(
        features, target, test_size=0.25, random_state=42, stratify=target
    )
    model = RandomForestClassifier(n_estimators=140, max_depth=10, random_state=42, class_weight="balanced")
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    bundle = {"model": model, "feature_columns": features.columns.tolist()}
    joblib.dump(bundle, MODELS / "energy_waste_classifier.joblib")

    return {
        "model": "RandomForestClassifier",
        "rows": int(len(frame)),
        "positive_rate": float(target.mean()),
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, zero_division=0)),
    }


def train_event_model() -> dict:
    frame = normalize_frame("event_logs", pd.read_csv(DATA / "event_logs.csv"))
    target = (frame["actual_attendance"] * 0.92).round().clip(lower=0)
    features = frame[["category", "expected_attendance", "duration_hr", "start_hour"]].copy()
    features = pd.get_dummies(features, columns=["category"])

    x_train, x_test, y_train, y_test = train_test_split(features, target, test_size=0.25, random_state=42)
    model = RandomForestRegressor(n_estimators=120, max_depth=8, random_state=42)
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    categories = sorted(frame["category"].unique().tolist())
    bundle = {"model": model, "feature_columns": features.columns.tolist(), "categories": categories}
    joblib.dump(bundle, MODELS / "event_servings_regressor.joblib")

    return {
        "model": "RandomForestRegressor",
        "rows": int(len(frame)),
        "mae_servings": float(mean_absolute_error(y_test, predictions)),
    }


def main() -> None:
    MODELS.mkdir(parents=True, exist_ok=True)
    metrics = {
        "evaluation_note": "Metrics are for synthetic MVP wiring only. Real school or BDG2 data should be used before claiming real-world accuracy.",
        "energy_waste_classifier": train_energy_model(),
        "event_servings_regressor": train_event_model(),
    }
    (MODELS / "training_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
