"""Measurement layer: turn N noisy raw samples into one level estimate + CI.

Pipeline per logical measurement:
  1. Take N rapid samples from the sensor.
  2. Reject outliers with the median-absolute-deviation (MAD) modified z-score.
  3. If too few valid samples survive  -> SENSOR_FAULT (never fabricate a value).
  4. If the surviving spread is large   -> TURBULENT (surface churning; skip it).
  5. Otherwise report mean level + a Student's-t (1-alpha) confidence interval.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence

import numpy as np
from scipy import stats

from .config import Config
from .models import Measurement, MeasurementStatus
from .sensor import Sensor

log = logging.getLogger(__name__)

# 0.6745 scales MAD to be a consistent estimator of sigma for normal data.
_MAD_SCALE = 0.6745


def mad_filter(values: Sequence[float], k: float) -> tuple[np.ndarray, np.ndarray]:
    """Split values into (kept, rejected) using the modified z-score.

    modified_z = 0.6745 * (x - median) / MAD. |modified_z| > k is an outlier.
    MAD==0 (all identical) keeps everything. Robust to up to ~50% contamination.
    """
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr, arr
    median = np.median(arr)
    mad = np.median(np.abs(arr - median))
    if mad == 0.0:
        return arr, np.array([], dtype=float)
    mod_z = _MAD_SCALE * (arr - median) / mad
    keep_mask = np.abs(mod_z) <= k
    return arr[keep_mask], arr[~keep_mask]


def mean_t_ci(values: Sequence[float], confidence: float) -> tuple[float, tuple[float, float], float]:
    """Return (mean, (ci_low, ci_high), sample_std) using Student's t.

    CI = mean +/- t(1-alpha/2, df=n-1) * s / sqrt(n).  For n == 1 the interval
    collapses to the point (no spread information).
    """
    arr = np.asarray(values, dtype=float)
    n = arr.size
    mean = float(np.mean(arr))
    if n < 2:
        return mean, (mean, mean), 0.0
    s = float(np.std(arr, ddof=1))
    se = s / np.sqrt(n)
    tcrit = float(stats.t.ppf(0.5 + confidence / 2.0, df=n - 1))
    half = tcrit * se
    return mean, (mean - half, mean + half), s


class MeasurementEngine:
    """Owns the sensor and produces Measurement objects on demand."""

    def __init__(self, cfg: Config, sensor: Sensor) -> None:
        self._cfg = cfg
        self._sensor = sensor
        self._mount = cfg.geometry.mount_height_cm

    def measure(self, now: datetime) -> Measurement:
        m = self._cfg.measurement
        raw: list[float] = []
        for _ in range(m.sample_count):
            r = self._sensor.read_distance()
            if r.valid and r.distance_cm is not None:
                # Discard anything outside the sensor's physical range.
                if m.sensor_min_cm <= r.distance_cm <= m.sensor_max_cm:
                    raw.append(r.distance_cm)

        n_valid = len(raw)
        if n_valid < m.min_valid_samples:
            log.warning(
                "SENSOR_FAULT: only %d/%d valid samples at %s",
                n_valid, m.sample_count, now.isoformat(),
            )
            return Measurement(
                timestamp=now,
                status=MeasurementStatus.SENSOR_FAULT,
                n_samples=m.sample_count,
                n_valid=n_valid,
            )

        kept, rejected = mad_filter(raw, m.mad_k)
        if kept.size < m.min_valid_samples:
            # Outlier rejection left too little to trust.
            return Measurement(
                timestamp=now,
                status=MeasurementStatus.SENSOR_FAULT,
                n_samples=m.sample_count,
                n_valid=n_valid,
                n_rejected=int(rejected.size),
            )

        dist_mean, dist_ci, std = mean_t_ci(kept, m.confidence_level)

        # Turbulence gate: a churning surface scatters the echo and inflates
        # spread. Flag and skip rather than guess through the noise.
        if std > m.turbulence_cm:
            log.info("TURBULENT measurement skipped (spread %.2f cm) at %s", std, now.isoformat())
            return Measurement(
                timestamp=now,
                status=MeasurementStatus.TURBULENT,
                n_samples=m.sample_count,
                n_valid=n_valid,
                n_rejected=int(rejected.size),
                robust_spread_cm=std,
            )

        # Convert distance -> level. Level CI flips the distance CI bounds
        # (level = mount - distance, so a higher distance is a lower level).
        level = self._mount - dist_mean
        level_ci = (self._mount - dist_ci[1], self._mount - dist_ci[0])

        return Measurement(
            timestamp=now,
            status=MeasurementStatus.OK,
            level_cm=level,
            level_ci=level_ci,
            distance_cm=dist_mean,
            n_samples=m.sample_count,
            n_valid=n_valid,
            n_rejected=int(rejected.size),
            robust_spread_cm=std,
        )
