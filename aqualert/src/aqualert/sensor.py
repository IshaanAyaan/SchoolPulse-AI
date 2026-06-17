"""Sensor abstraction with two interchangeable implementations.

  * HCSR04Sensor   - real driver (gpiozero preferred, RPi.GPIO fallback)
  * SimulatedSensor - synthetic waveforms, no hardware

Both expose read_distance() -> Reading. The rest of the pipeline never knows
or cares which one is wired in. Selection happens in build_sensor() from config.
"""

from __future__ import annotations

import abc
import logging
import math
import random
import time
from typing import Callable

from .config import Config
from .models import Reading

log = logging.getLogger(__name__)

# Speed of sound ~343 m/s at 20C => distance(cm) = echo_seconds * 34300 / 2.
_SOUND_CM_PER_S = 34300.0


class Sensor(abc.ABC):
    """Distance sensor interface. One call == one raw round-trip sample."""

    @abc.abstractmethod
    def read_distance(self) -> Reading:
        """Return a single raw distance reading (cm) or Reading.invalid()."""

    def close(self) -> None:  # optional cleanup hook
        return None


# ---------------------------------------------------------------------------
# Real hardware driver
# ---------------------------------------------------------------------------


class HCSR04Sensor(Sensor):
    """HC-SR04 driver using the trigger-pulse / echo-timing loop.

    gpiozero is preferred (it owns the pin lifecycle cleanly); if it is not
    installed we fall back to RPi.GPIO. Both imports are lazy so this module
    imports fine on a laptop with no GPIO libraries present.
    """

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._timeout = cfg.gpio.echo_timeout_s
        self._max_cm = cfg.measurement.sensor_max_cm
        self._backend = None
        self._impl = self._init_backend()

    def _init_backend(self) -> Callable[[], float | None]:
        try:
            from gpiozero import DistanceSensor  # type: ignore

            # gpiozero returns metres; max_distance caps the range.
            self._backend = DistanceSensor(
                echo=self._cfg.gpio.echo_pin,
                trigger=self._cfg.gpio.trig_pin,
                max_distance=self._max_cm / 100.0,
                queue_len=1,
            )
            log.info("HC-SR04 using gpiozero backend")
            return self._read_gpiozero
        except Exception as exc:  # noqa: BLE001 - any import/init failure -> fallback
            log.warning("gpiozero unavailable (%s); trying RPi.GPIO", exc)
            return self._init_rpi_gpio()

    def _init_rpi_gpio(self) -> Callable[[], float | None]:
        import RPi.GPIO as GPIO  # type: ignore

        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._cfg.gpio.trig_pin, GPIO.OUT)
        GPIO.setup(self._cfg.gpio.echo_pin, GPIO.IN)
        GPIO.output(self._cfg.gpio.trig_pin, False)
        time.sleep(0.05)
        log.info("HC-SR04 using RPi.GPIO backend")
        return self._read_rpi_gpio

    def _read_gpiozero(self) -> float | None:
        sensor = self._backend
        # .distance is metres in [0, max_distance]; a pegged max means no echo.
        d_m = sensor.distance  # type: ignore[union-attr]
        if d_m is None or d_m >= sensor.max_distance:  # type: ignore[union-attr]
            return None
        return d_m * 100.0

    def _read_rpi_gpio(self) -> float | None:
        GPIO = self._GPIO
        trig, echo = self._cfg.gpio.trig_pin, self._cfg.gpio.echo_pin
        # 10 us trigger pulse.
        GPIO.output(trig, True)
        time.sleep(1e-5)
        GPIO.output(trig, False)

        start = time.monotonic()
        deadline = start + self._timeout
        # Wait for echo rising edge.
        while GPIO.input(echo) == 0:
            if time.monotonic() > deadline:
                return None
        t0 = time.monotonic()
        # Wait for echo falling edge.
        while GPIO.input(echo) == 1:
            if time.monotonic() > deadline:
                return None
        t1 = time.monotonic()
        return (t1 - t0) * _SOUND_CM_PER_S / 2.0

    def read_distance(self) -> Reading:
        try:
            d = self._impl()
        except Exception as exc:  # noqa: BLE001 - never crash the loop on a bad ping
            log.error("HC-SR04 read failed: %s", exc)
            return Reading.invalid()
        if d is None or not math.isfinite(d):
            return Reading.invalid()
        return Reading(distance_cm=float(d), valid=True)

    def close(self) -> None:
        try:
            if self._backend is not None and hasattr(self._backend, "close"):
                self._backend.close()
            elif hasattr(self, "_GPIO"):
                self._GPIO.cleanup()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass


# ---------------------------------------------------------------------------
# Simulated sensor
# ---------------------------------------------------------------------------


class VirtualClock:
    """Controllable clock for simulation. Returns seconds since an epoch."""

    def __init__(self, start_epoch_s: float) -> None:
        self._t = float(start_epoch_s)

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += float(seconds)


class SimulatedSensor(Sensor):
    """Synthetic HC-SR04 with realistic flush/refill/flat cycles.

    Models the *level* deterministically as a function of simulated time, then
    converts to distance and adds Gaussian noise plus occasional spurious
    out-of-range pings. Scenarios:

      normal       - flat at full line, sensor noise only
      leak_slow    - slow flapper leak with periodic fill-valve top-offs
                     (sawtooth); ~1.2 cm/hr underlying decline
      leak_fast    - faster leak, more frequent refills; ~4.0 cm/hr
      sensor_fault - no echo on every ping (all readings invalid)

    The fill valve tops the level back up by `deadband` cm whenever the leak
    has drained that far, producing the sawtooth + micro-refill signature.
    """

    _DEADBAND_CM = 1.0          # how far level drops before the valve tops off
    _LEAK_SLOW_CM_PER_HR = 1.2
    _LEAK_FAST_CM_PER_HR = 4.0
    _NOISE_SIGMA_CM = 0.12      # per-sample Gaussian noise
    _SPURIOUS_PROB = 0.03       # chance of a wild out-of-range ping (non-fault)

    def __init__(self, cfg: Config, clock: Callable[[], float]) -> None:
        self._cfg = cfg
        self._clock = clock
        self._scenario = cfg.sensor.sim_scenario
        self._start = clock()
        self._mount = cfg.geometry.mount_height_cm
        self._full = cfg.geometry.full_line_cm
        self._min_cm = cfg.measurement.sensor_min_cm
        self._max_cm = cfg.measurement.sensor_max_cm
        self._rng = random.Random(cfg.sensor.sim_seed)

    # -- waveform ----------------------------------------------------------

    def _level_cm(self, t_hours: float) -> float:
        """Underlying true water level at elapsed time t_hours."""
        if self._scenario in ("normal", "sensor_fault"):
            return self._full
        rate = (
            self._LEAK_SLOW_CM_PER_HR
            if self._scenario == "leak_slow"
            else self._LEAK_FAST_CM_PER_HR
        )
        # Sawtooth: drain by `rate` until deadband reached, then valve refills.
        drained = (rate * t_hours) % self._DEADBAND_CM
        return self._full - drained

    def read_distance(self) -> Reading:
        if self._scenario == "sensor_fault":
            return Reading.invalid()

        # Spurious echo: wild value, far outside plausible level range.
        if self._rng.random() < self._SPURIOUS_PROB:
            spurious = self._rng.choice(
                [self._rng.uniform(0.0, self._min_cm),       # too close
                 self._rng.uniform(self._max_cm, self._max_cm + 50.0)]  # too far
            )
            return self._finalize(spurious)

        t_hours = (self._clock() - self._start) / 3600.0
        level = self._level_cm(t_hours)
        distance = self._mount - level + self._rng.gauss(0.0, self._NOISE_SIGMA_CM)
        return self._finalize(distance)

    def _finalize(self, distance: float) -> Reading:
        # Out-of-range pings are reported as no-echo, exactly like real hardware.
        if not (self._min_cm <= distance <= self._max_cm):
            return Reading.invalid()
        return Reading(distance_cm=float(distance), valid=True)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_sensor(cfg: Config, clock: Callable[[], float] | None = None) -> Sensor:
    """Construct the sensor selected by config.

    `clock` is required only for simulation (defaults to wall-clock time).
    """
    if cfg.sensor.mode == "sim":
        clk = clock if clock is not None else time.time
        return SimulatedSensor(cfg, clk)
    return HCSR04Sensor(cfg)
