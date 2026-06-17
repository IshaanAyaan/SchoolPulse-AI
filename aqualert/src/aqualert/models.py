"""Core data structures passed between pipeline stages.

Everything here is a plain dataclass or enum so it is trivially serializable,
easy to log, and easy to assert on in tests.
"""

from __future__ import annotations

import enum
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


class MeasurementStatus(str, enum.Enum):
    """Outcome of a single logical measurement."""

    OK = "OK"
    TURBULENT = "TURBULENT"          # surface churning (e.g. mid-refill); skip it
    SENSOR_FAULT = "SENSOR_FAULT"    # too few valid samples / no echo


class DetectionState(str, enum.Enum):
    """State machine output. These are the only four states by design."""

    NORMAL = "NORMAL"
    WATCH = "WATCH"                  # weak-but-real anomaly, never silently dropped
    LEAK_SUSPECTED = "LEAK_SUSPECTED"
    SENSOR_FAULT = "SENSOR_FAULT"


@dataclass(slots=True)
class Reading:
    """One raw ultrasonic sample."""

    distance_cm: float | None        # None == no echo / out of range
    valid: bool

    @classmethod
    def invalid(cls) -> "Reading":
        return cls(distance_cm=None, valid=False)


@dataclass(slots=True)
class Measurement:
    """Aggregated result of N rapid samples for one time point.

    level_cm and its CI are only meaningful when status == OK.
    """

    timestamp: datetime
    status: MeasurementStatus
    level_cm: float | None = None
    level_ci: tuple[float, float] | None = None   # (low, high), same units as level
    distance_cm: float | None = None
    n_samples: int = 0
    n_valid: int = 0
    n_rejected: int = 0
    robust_spread_cm: float | None = None         # MAD-based spread of kept samples

    @property
    def is_usable(self) -> bool:
        return self.status is MeasurementStatus.OK and self.level_cm is not None


@dataclass(slots=True)
class Detection:
    """Detector output with a full, auditable reasoning trace."""

    timestamp: datetime
    state: DetectionState
    confidence: float                              # [0, 1], confidence in `state`
    level_cm: float | None
    slope_cm_per_hr: float | None                  # negative => declining
    slope_ci: tuple[float, float] | None
    refill_events: int
    human_use_detected: bool
    in_idle_window: bool
    est_waste_gpd: tuple[float, float]             # (low, high) gallons/day range
    reasoning: dict = field(default_factory=dict)  # numeric trace for humans

    def summary(self) -> str:
        slope = "n/a" if self.slope_cm_per_hr is None else f"{self.slope_cm_per_hr:+.3f}"
        return (
            f"[{self.state.value}] conf={self.confidence:.2f} "
            f"slope={slope} cm/hr refills={self.refill_events} "
            f"waste={self.est_waste_gpd[0]:.1f}-{self.est_waste_gpd[1]:.1f} gpd "
            f"idle={self.in_idle_window}"
        )


@dataclass(slots=True)
class TelemetryMsg:
    """Wire payload. msg_id + timestamp let the server dedupe idempotently."""

    msg_id: str
    device_id: str
    timestamp_utc: str                             # ISO-8601
    level_cm: float | None
    level_ci: tuple[float, float] | None
    state: str
    confidence: float
    slope_cm_per_hr: float | None
    slope_ci: tuple[float, float] | None
    refill_events: int
    est_waste_gpd: tuple[float, float]
    config_version: str
    firmware_version: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @staticmethod
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
