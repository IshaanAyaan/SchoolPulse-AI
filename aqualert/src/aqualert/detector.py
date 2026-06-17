"""Detection layer: transparent statistics + a small state machine.

No machine learning. The reasoning is fully auditable: every Detection carries
the slope, its confidence interval, the refill count, the idle-window context,
and the intermediate confidence terms.

Method, over a rolling window of usable Measurements:
  1. Walk consecutive levels and classify discrete events:
       - drop  >= flush_drop_cm           -> flush (human use)
       - rise  in [refill_min, flush_drop) -> fill-valve micro-refill
       - any |step| >= refill_min          -> removed from the trend
  2. "Unwrap" by subtracting those discrete steps, turning the leak sawtooth
     into the underlying continuous decline. (A healthy tank stays flat, so the
     unwrapped series is flat too.)
  3. OLS-fit unwrapped level vs time -> slope + standard error -> a t-based CI.
  4. State machine with a two-sided conservative policy:
       - flag a LEAK only when the *upper* bound of the slope CI is below a
         negative rate threshold (real beyond noise AND big enough to matter),
       - never silently drop a weak-but-real decline: surface it as WATCH,
       - idle-window evidence is high confidence; occupied hours require a
         sustained multi-window trend.
  5. Confidence in [0,1] from the slope t-statistic, blended with refill
     evidence and idle context.
  6. Impact: decline-rate CI -> estimated gallons/day wasted, as a range.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timedelta

import numpy as np
from scipy import stats

from .config import Config
from .models import Detection, DetectionState, Measurement, MeasurementStatus

log = logging.getLogger(__name__)

_CM3_PER_GALLON = 3785.411784
_HOURS_PER_DAY = 24.0

# Occupied-hours flags need a sustained trend before escalating to LEAK.
_OCCUPIED_SUSTAIN_WINDOWS = 3

# Confidence blend weights (slope evidence vs refill evidence).
_W_SLOPE = 0.6
_W_REFILL = 0.4


class Detector:
    """Stateful detector. Feed it Measurements; it returns a Detection each call."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._window: deque[Measurement] = deque()
        self._occupied_leak_streak = 0

    # -- public API --------------------------------------------------------

    def update(self, m: Measurement) -> Detection:
        """Ingest one measurement and return the current Detection."""
        if m.status is MeasurementStatus.SENSOR_FAULT:
            return self._fault(m.timestamp)
        if m.status is MeasurementStatus.TURBULENT:
            # Skip the churned sample; re-evaluate on existing history.
            return self._evaluate(m.timestamp, turbulent_skipped=True)
        # OK measurement: add to window and evaluate.
        self._window.append(m)
        self._prune(m.timestamp)
        return self._evaluate(m.timestamp, turbulent_skipped=False)

    # -- internals ---------------------------------------------------------

    def _prune(self, now: datetime) -> None:
        cutoff = now - timedelta(minutes=self._cfg.detection.rolling_window_min)
        while self._window and self._window[0].timestamp < cutoff:
            self._window.popleft()

    def _fault(self, now: datetime) -> Detection:
        return Detection(
            timestamp=now,
            state=DetectionState.SENSOR_FAULT,
            confidence=1.0,
            level_cm=None,
            slope_cm_per_hr=None,
            slope_ci=None,
            refill_events=0,
            human_use_detected=False,
            in_idle_window=self._in_idle(now),
            est_waste_gpd=(0.0, 0.0),
            reasoning={"reason": "insufficient_valid_samples_or_no_echo"},
        )

    def _in_idle(self, now: datetime) -> bool:
        return self._cfg.detection.idle_window.contains(now.time())

    def _waste_gpd(self, rate_cm_per_hr: float) -> float:
        """Convert a decline rate (cm/hr, >=0) to gallons/day wasted."""
        rate = max(0.0, rate_cm_per_hr)
        cm3_per_hr = rate * self._cfg.geometry.cross_section_cm2
        return cm3_per_hr * _HOURS_PER_DAY / _CM3_PER_GALLON

    def _evaluate(self, now: datetime, *, turbulent_skipped: bool) -> Detection:
        d = self._cfg.detection
        in_idle = self._in_idle(now)
        usable = [mm for mm in self._window if mm.is_usable]

        if len(usable) < d.min_points:
            # Explicit "not enough data yet" -- never a silent confident pass.
            level = usable[-1].level_cm if usable else None
            return Detection(
                timestamp=now,
                state=DetectionState.NORMAL,
                confidence=0.0,
                level_cm=level,
                slope_cm_per_hr=None,
                slope_ci=None,
                refill_events=0,
                human_use_detected=False,
                in_idle_window=in_idle,
                est_waste_gpd=(0.0, 0.0),
                reasoning={
                    "insufficient_data": True,
                    "n_points": len(usable),
                    "min_points": d.min_points,
                    "turbulent_skipped": turbulent_skipped,
                },
            )

        t0 = usable[0].timestamp
        t_hours = np.array(
            [(mm.timestamp - t0).total_seconds() / 3600.0 for mm in usable], dtype=float
        )
        levels = np.array([mm.level_cm for mm in usable], dtype=float)

        refills, human_use, unwrapped = self._unwrap(levels)

        slope, stderr, slope_ci, conf_level = self._fit_slope(t_hours, unwrapped)
        df = max(1, len(usable) - 2)
        decline = -slope  # positive when declining
        slope_upper = slope_ci[1]  # least-negative bound

        # --- statistical confidence the decline truly exceeds the threshold ---
        if stderr > 0:
            tstat = (decline - d.min_leak_rate_cm_per_hr) / stderr
            stat_conf = float(stats.t.cdf(tstat, df=df))
        else:
            stat_conf = 1.0 if decline > d.min_leak_rate_cm_per_hr else 0.0

        refill_signal = 0.0
        if not human_use and refills > 0:
            refill_signal = min(1.0, refills / float(d.min_refills_for_leak))

        evidence = _W_SLOPE * stat_conf + _W_REFILL * refill_signal

        # --- conservative two-sided gating ---
        slope_leak = slope_upper < -d.min_leak_rate_cm_per_hr
        refill_leak = (refills >= d.min_refills_for_leak) and (not human_use)
        weak_anomaly = (slope_upper < -d.watch_rate_cm_per_hr) or (
            refills >= 1 and not human_use
        )

        state, confidence = self._decide(
            in_idle=in_idle,
            slope_leak=slope_leak,
            refill_leak=refill_leak,
            weak_anomaly=weak_anomaly,
            evidence=evidence,
        )

        # --- impact range from the slope CI ---
        decline_low = max(0.0, -slope_ci[1])   # least-negative slope -> slowest leak
        decline_high = max(0.0, -slope_ci[0])  # most-negative slope -> fastest leak
        waste = (self._waste_gpd(decline_low), self._waste_gpd(decline_high))

        reasoning = {
            "n_points": len(usable),
            "window_min": d.rolling_window_min,
            "slope_cm_per_hr": round(slope, 4),
            "slope_se": round(stderr, 4),
            "slope_ci": [round(slope_ci[0], 4), round(slope_ci[1], 4)],
            "confidence_level": conf_level,
            "decline_cm_per_hr": round(decline, 4),
            "min_leak_rate": d.min_leak_rate_cm_per_hr,
            "watch_rate": d.watch_rate_cm_per_hr,
            "refill_events": refills,
            "min_refills_for_leak": d.min_refills_for_leak,
            "human_use_detected": human_use,
            "in_idle_window": in_idle,
            "stat_conf": round(stat_conf, 4),
            "refill_signal": round(refill_signal, 4),
            "evidence": round(evidence, 4),
            "noise_gate_slope_leak": slope_leak,
            "refill_leak": refill_leak,
            "occupied_leak_streak": self._occupied_leak_streak,
            "turbulent_skipped": turbulent_skipped,
        }

        det = Detection(
            timestamp=now,
            state=state,
            confidence=round(confidence, 4),
            level_cm=float(levels[-1]),
            slope_cm_per_hr=round(slope, 4),
            slope_ci=(round(slope_ci[0], 4), round(slope_ci[1], 4)),
            refill_events=refills,
            human_use_detected=human_use,
            in_idle_window=in_idle,
            est_waste_gpd=(round(waste[0], 3), round(waste[1], 3)),
            reasoning=reasoning,
        )
        log.debug("detection: %s", det.summary())
        return det

    def _unwrap(self, levels: np.ndarray) -> tuple[int, bool, np.ndarray]:
        """Remove discrete events, recovering the underlying slow trend.

        Returns (micro_refill_count, human_use_flag, unwrapped_levels).
        """
        d = self._cfg.detection
        offset = 0.0
        unwrapped = [float(levels[0])]
        refills = 0
        human_use = False
        for i in range(1, len(levels)):
            delta = float(levels[i] - levels[i - 1])
            if delta <= -d.flush_drop_cm:
                human_use = True               # a flush: legitimate large draw
            elif d.refill_min_cm <= delta < d.flush_drop_cm:
                refills += 1                    # fill-valve micro-refill
            # Remove any large discrete step (refill, flush, or flush recovery)
            # from the trend so only the slow leak drift remains.
            if abs(delta) >= d.refill_min_cm:
                offset += delta
            unwrapped.append(float(levels[i]) - offset)
        return refills, human_use, np.asarray(unwrapped, dtype=float)

    def _fit_slope(
        self, t_hours: np.ndarray, unwrapped: np.ndarray
    ) -> tuple[float, float, tuple[float, float], float]:
        """OLS slope of level vs time with a Student's-t confidence interval."""
        conf = self._cfg.measurement.confidence_level
        res = stats.linregress(t_hours, unwrapped)
        slope = float(res.slope)
        stderr = float(res.stderr)  # SE of the slope
        n = t_hours.size
        df = max(1, n - 2)
        tcrit = float(stats.t.ppf(0.5 + conf / 2.0, df=df))
        half = tcrit * stderr
        return slope, stderr, (slope - half, slope + half), conf

    def _decide(
        self,
        *,
        in_idle: bool,
        slope_leak: bool,
        refill_leak: bool,
        weak_anomaly: bool,
        evidence: float,
    ) -> tuple[DetectionState, float]:
        """Map evidence to a state + confidence, applying context weighting."""
        leak_candidate = slope_leak or refill_leak

        if in_idle:
            # No legitimate use overnight: act on a single window, high confidence.
            self._occupied_leak_streak = 0
            if leak_candidate:
                return DetectionState.LEAK_SUSPECTED, _clamp(evidence)
            if weak_anomaly:
                return DetectionState.WATCH, _clamp(evidence)
            return DetectionState.NORMAL, _clamp(1.0 - evidence)

        # Occupied hours: require a sustained multi-window trend before flagging.
        if leak_candidate:
            self._occupied_leak_streak += 1
            occ_conf = _clamp(evidence * self._cfg.detection.occupied_confidence_discount)
            if self._occupied_leak_streak >= _OCCUPIED_SUSTAIN_WINDOWS:
                return DetectionState.LEAK_SUSPECTED, occ_conf
            return DetectionState.WATCH, occ_conf  # real signal, not yet sustained
        self._occupied_leak_streak = 0
        if weak_anomaly:
            return DetectionState.WATCH, _clamp(
                evidence * self._cfg.detection.occupied_confidence_discount
            )
        return DetectionState.NORMAL, _clamp(1.0 - evidence)


def _clamp(x: float) -> float:
    return float(min(1.0, max(0.0, x)))
