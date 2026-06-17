"""Measurement-layer tests: CI correctness, outlier rejection, fault/turbulence."""

import math
from datetime import datetime

import numpy as np
from scipy import stats

from aqualert.measurement import MeasurementEngine, mad_filter, mean_t_ci
from aqualert.models import MeasurementStatus, Reading
from aqualert.sensor import Sensor


class FakeSensor(Sensor):
    """Yields a fixed, cycling list of distances; None entries are no-echo."""

    def __init__(self, distances):
        self._d = list(distances)
        self._i = 0

    def read_distance(self) -> Reading:
        v = self._d[self._i % len(self._d)]
        self._i += 1
        return Reading.invalid() if v is None else Reading(distance_cm=float(v), valid=True)


def test_mean_t_ci_matches_scipy():
    vals = [12.0, 12.4, 11.8, 12.1, 12.3, 11.9, 12.2]
    mean, (lo, hi), std = mean_t_ci(vals, 0.95)
    assert mean == np.mean(vals)
    # Compare against scipy's own interval helper.
    n = len(vals)
    se = np.std(vals, ddof=1) / math.sqrt(n)
    exp_lo, exp_hi = stats.t.interval(0.95, df=n - 1, loc=np.mean(vals), scale=se)
    assert math.isclose(lo, exp_lo, rel_tol=1e-9)
    assert math.isclose(hi, exp_hi, rel_tol=1e-9)
    assert lo < mean < hi


def test_mean_t_ci_single_value_collapses():
    mean, (lo, hi), std = mean_t_ci([7.5], 0.95)
    assert mean == lo == hi == 7.5
    assert std == 0.0


def test_mad_filter_rejects_outlier():
    vals = [10.0, 10.1, 9.9, 10.05, 9.95, 50.0]  # 50 is a wild spike
    kept, rejected = mad_filter(vals, k=3.5)
    assert 50.0 in rejected
    assert 50.0 not in kept
    assert len(kept) == 5


def test_mad_filter_keeps_identical_values():
    kept, rejected = mad_filter([5.0, 5.0, 5.0], k=3.5)
    assert len(kept) == 3 and len(rejected) == 0


def test_measurement_ok_level_and_ci(cfg):
    # Tank "full": distance ~ mount - full_line = 30 - 18 = 12 cm, low noise.
    eng = MeasurementEngine(cfg, FakeSensor([12.0, 12.1, 11.9, 12.05, 11.95, 12.0, 12.0]))
    m = eng.measure(datetime.now())
    assert m.status is MeasurementStatus.OK
    assert math.isclose(m.level_cm, cfg.geometry.full_line_cm, abs_tol=0.2)
    lo, hi = m.level_ci
    assert lo < m.level_cm < hi


def test_measurement_sensor_fault_on_no_echo(cfg):
    eng = MeasurementEngine(cfg, FakeSensor([None]))  # never any echo
    m = eng.measure(datetime.now())
    assert m.status is MeasurementStatus.SENSOR_FAULT
    assert m.level_cm is None  # never fabricated


def test_measurement_turbulent_on_high_spread(cfg):
    # Half the samples 9 cm, half 13 cm -> spread well above turbulence_cm.
    eng = MeasurementEngine(cfg, FakeSensor([9.0, 13.0, 9.0, 13.0, 9.0, 13.0, 9.0]))
    m = eng.measure(datetime.now())
    assert m.status is MeasurementStatus.TURBULENT
    assert m.level_cm is None
