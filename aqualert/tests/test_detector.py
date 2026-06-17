"""Detector tests: scenario classification, unwrap correctness, sustained-trend gating."""

from datetime import datetime

import numpy as np

from aqualert.detector import Detector
from aqualert.measurement import MeasurementEngine
from aqualert.models import DetectionState
from aqualert.sensor import VirtualClock, build_sensor


def _run(cfg, scenario, steps=180, start_hour=23, start_min=30):
    """Run the full pipeline in sim and return (final_detection, [states])."""
    cfg.sensor.mode = "sim"
    cfg.sensor.sim_scenario = scenario
    start = datetime.now().replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    clock = VirtualClock(start.timestamp())
    sensor = build_sensor(cfg, clock=clock.now)
    engine = MeasurementEngine(cfg, sensor)
    detector = Detector(cfg)
    states = []
    det = None
    for _ in range(steps):
        now = datetime.fromtimestamp(clock.now())
        det = detector.update(engine.measure(now))
        states.append(det.state)
        clock.advance(cfg.detection.sample_interval_s)
    return det, states


def test_normal_stays_normal(cfg):
    det, _ = _run(cfg, "normal")
    assert det.state is DetectionState.NORMAL
    assert det.confidence > 0.8
    assert det.refill_events == 0


def test_leak_slow_flagged(cfg):
    det, _ = _run(cfg, "leak_slow")
    assert det.state is DetectionState.LEAK_SUSPECTED
    assert det.slope_cm_per_hr < 0
    assert det.refill_events >= 1
    assert det.est_waste_gpd[1] > 0  # a real waste range is reported


def test_leak_fast_flagged_and_steeper(cfg):
    slow, _ = _run(cfg, "leak_slow")
    fast, _ = _run(cfg, "leak_fast")
    assert fast.state is DetectionState.LEAK_SUSPECTED
    assert fast.slope_cm_per_hr < slow.slope_cm_per_hr  # steeper decline
    assert fast.est_waste_gpd[1] > slow.est_waste_gpd[1]


def test_sensor_fault_never_fabricates(cfg):
    det, _ = _run(cfg, "sensor_fault")
    assert det.state is DetectionState.SENSOR_FAULT
    assert det.slope_cm_per_hr is None
    assert det.level_cm is None


def test_unwrap_removes_refills(cfg):
    det = Detector(cfg)
    # Sawtooth: decline then a +1.0 refill jump, twice.
    levels = np.array([18.0, 17.6, 17.2, 18.2, 17.8, 17.4, 18.4])
    refills, human_use, unwrapped = det._unwrap(levels)
    assert refills == 2          # two upward jumps >= refill_min
    assert not human_use
    # Unwrapped should be (near) monotonically non-increasing: refills removed.
    diffs = np.diff(unwrapped)
    assert np.all(diffs <= 1e-9)


def test_unwrap_flat_has_no_refills(cfg):
    det = Detector(cfg)
    levels = np.array([18.0, 18.01, 17.99, 18.0, 18.02, 17.98, 18.0])
    refills, human_use, _ = det._unwrap(levels)
    assert refills == 0
    assert not human_use


def test_occupied_hours_require_sustained_trend(cfg):
    # Same leak, but during the day: the FIRST escalation must be WATCH,
    # and LEAK_SUSPECTED only appears after the trend sustains.
    det, states = _run(cfg, "leak_fast", start_hour=12, start_min=0)
    non_normal = [s for s in states if s is not DetectionState.NORMAL]
    assert non_normal, "a daytime leak should still raise at least a WATCH"
    assert non_normal[0] is DetectionState.WATCH
    assert DetectionState.LEAK_SUSPECTED in states  # eventually sustained


def test_idle_more_confident_than_occupied(cfg):
    idle, _ = _run(cfg, "leak_fast", start_hour=23, start_min=30)
    occ, _ = _run(cfg, "leak_fast", start_hour=12, start_min=0)
    assert idle.confidence >= occ.confidence
