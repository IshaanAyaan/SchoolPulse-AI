# Aqualert — Edge Leak Detector

Aqualert is a small edge-AI device that watches a tank-type toilet and flags a
**running / leaking toilet** (worn flapper or fill valve that won't fully seat)
before it wastes hundreds of gallons. A Raspberry Pi reads water level with an
ultrasonic sensor mounted above the tank, decides locally whether there is a
leak — with an explicit confidence and error margin — and ships that verdict to
a server. It is **advisory only**: it never shuts off water or takes any
irreversible action.

The entire pipeline runs **end to end in simulation with zero hardware**, so you
can evaluate it on a laptop.

---

## How detection works

Level is `L = mount_height_cm − measured_distance_cm` (water rising shortens the
echo distance). A healthy tank holds a flat line between flushes. A leaking tank
shows a slow **sawtooth**: the level creeps down as water seeps into the bowl,
and the fill valve periodically tops it back up (a *micro-refill*).

1. **Measurement** — each cycle takes 7 rapid samples, rejects outliers with a
   MAD modified-z-score, and reports the mean level with a Student's-t 95%
   confidence interval. Too few valid echoes → `SENSOR_FAULT` (never a guess);
   a churning surface (high spread) → `TURBULENT` and the sample is skipped.
2. **Trend** — over a rolling window the detector classifies discrete steps
   (flushes, micro-refills, flush recoveries) and *unwraps* them, turning the
   sawtooth into the underlying slow decline. It then OLS-fits level vs time and
   reports the **slope and its confidence interval**.
3. **Decision** — a leak is flagged only when the *upper* bound of the slope CI
   is below a negative rate threshold (real beyond noise **and** big enough to
   matter), corroborated by refill count. A weak-but-real decline is never
   dropped silently — it surfaces as `WATCH`. Overnight (idle window) evidence
   is high confidence; daytime evidence must sustain across windows first.
4. **Impact** — the decline-rate CI is converted to an estimated **gallons/day**
   wasted, reported as a range.

States: `NORMAL`, `WATCH`, `LEAK_SUSPECTED`, `SENSOR_FAULT`. Every detection
carries a full numeric reasoning trace.

---

## Wiring (HC-SR04 → Raspberry Pi)

| HC-SR04 | Pi pin | GPIO (BCM) | Notes |
|---------|--------|-----------|-------|
| VCC     | Pin 2  | 5V        | sensor needs 5V |
| GND     | Pin 6  | GND       | common ground |
| Trig    | Pin 16 | GPIO23    | 3.3V trigger, direct |
| Echo    | Pin 18 | GPIO24    | **through a 1k/2k divider** (5V→3.3V) |

The Pi's GPIO is **not** 5V-tolerant. The Echo line *must* go through a voltage
divider (e.g. 1 kΩ in series, 2 kΩ to ground) to drop the 5V echo to ~3.3V.

Mount the sensor on the tank lid facing straight down at the water surface, with
a clear path and no obstruction from the fill/flush hardware.

---

## Install

```bash
python -m pip install -r requirements.txt          # laptop / server
# On the Raspberry Pi also install the GPIO backends:
python -m pip install gpiozero RPi.GPIO
```

`gpiozero` / `RPi.GPIO` are intentionally **not** hard dependencies — they are
imported lazily only by the real driver, so everything imports and runs in
simulation on a machine with no GPIO.

---

## Configure

Copy the template and edit:

```bash
cp config.example.yaml config.yaml
```

Credentials are **never** stored in the file. Export them:

```bash
export AQUALERT_MQTT_USERNAME=...   # MQTT broker user
export AQUALERT_MQTT_PASSWORD=...   # MQTT broker password
export AQUALERT_REST_TOKEN=...      # bearer token for the REST fallback
```

Config is validated on load and fails loudly on any bad value.

---

## Usage

**Calibrate on the Pi** (full, settled tank):

```bash
python scripts/calibrate.py --config config.yaml --empty   # empty tank: mount height
python scripts/calibrate.py --config config.yaml           # full tank: full line
```

**Run on the Pi** (real sensor — set `sensor.mode: real` in config):

```bash
python -m aqualert.runner --config config.yaml
```

**Run in simulation** (no hardware):

```bash
python scripts/simulate.py --scenario normal
python scripts/simulate.py --scenario leak_slow --json
python scripts/simulate.py --scenario leak_fast
python scripts/simulate.py --scenario sensor_fault
```

**Run the server** (MQTT subscriber + JSON read API):

```bash
python server/receiver.py --config config.yaml --db telemetry.sqlite
# read endpoints:
#   GET /health
#   GET /devices/<device_id>/latest
#   GET /devices/<device_id>/history?limit=100
# (use --no-mqtt to run only the read API)
```

**Run the tests:**

```bash
python -m pytest
```

---

## Telemetry payload (JSON)

```json
{
  "msg_id": "f3a1...",
  "device_id": "aqualert-dev-001",
  "timestamp_utc": "2026-01-01T07:30:00+00:00",
  "level_cm": 17.4,
  "level_ci": [17.31, 17.49],
  "state": "LEAK_SUSPECTED",
  "confidence": 0.94,
  "slope_cm_per_hr": -1.23,
  "slope_ci": [-1.31, -1.15],
  "refill_events": 3,
  "est_waste_gpd": [6.5, 7.1],
  "config_version": "1.0.0",
  "firmware_version": "1.0.0"
}
```

Each message has a `msg_id`. The device persists every message to a local
SQLite spool and forwards oldest-first; the server upserts on `msg_id`, so the
at-least-once delivery survives outages with **no loss and no duplicates**.

---

## Assumptions

- **Geometry defaults** (override in config): `mount_height_cm = 30`,
  `full_line_cm = 18`, `cross_section_cm2 = 900`. The waste estimate scales
  linearly with `cross_section_cm2`, so calibrate it to your tank's surface area.
- **Measurement:** 7 samples/cycle, 95% CI, MAD k = 3.5, turbulence gate at
  0.8 cm robust spread, valid range 2–400 cm, ≥3 valid samples required.
- **Detection:** 60 s sample interval, 120 min rolling window, ≥8 points before
  a trend is trusted, leak threshold 0.5 cm/hr, watch threshold 0.1 cm/hr,
  refill jump ≥0.6 cm, flush drop ≥6 cm, ≥2 unexplained refills = strong
  evidence.
- **Idle window 23:00–05:00** is evaluated against the device's **local** time
  (the runner passes local time to the detector); telemetry timestamps are UTC.
- **Occupied-hours gating:** during the day a leak must sustain for 3 consecutive
  windows before escalating from `WATCH` to `LEAK_SUSPECTED`; overnight a single
  window suffices. (3 is an internal constant, documented here.)
- **REST fallback uses the standard-library `urllib`**, not `requests`, to avoid
  an extra dependency on a constrained device.
- The simulator is **seeded** (`sensor.sim_seed`) so demo runs are reproducible.

---

## Responsible AI

| Risk | Mitigation |
|------|-----------|
| **False alarm** annoys staff, erodes trust | Conservative two-sided gate (flag only when the *upper* slope-CI bound clears the threshold); daytime trends must sustain; every alert ships its confidence + CI. |
| **Missed leak** wastes water | Weak-but-real declines are surfaced as `WATCH`, never dropped; refill evidence corroborates the slope. |
| **Acting on a broken sensor** | Insufficient/again invalid echoes return `SENSOR_FAULT` — a value is never fabricated; turbulence is skipped, not guessed. |
| **Over-automation** | The device is **advisory only**. It never closes a valve or shuts off water. A human reviews alerts and decides. |
| **Privacy / overreach** | It measures only tank water level — no audio, no images, no occupancy tracking. |
| **Credential leakage** | Secrets come from environment variables only; none are stored in code or config. |

Confidence is a calibrated signal to a human, not a license to act
autonomously. When in doubt the system says so (`WATCH`, `SENSOR_FAULT`) rather
than overclaiming.

---

## Layout

```
aqualert/
├─ config.example.yaml      # template (copy to config.yaml)
├─ requirements.txt
├─ src/aqualert/
│  ├─ config.py             # load + strict validation
│  ├─ models.py             # Reading / Measurement / Detection / TelemetryMsg
│  ├─ sensor.py             # HC-SR04 driver + SimulatedSensor + VirtualClock
│  ├─ measurement.py        # MAD rejection + Student's-t CI
│  ├─ detector.py           # unwrap + OLS slope CI + state machine
│  ├─ telemetry.py          # MQTT/TLS + REST + SQLite store-and-forward
│  └─ runner.py             # main loop
├─ server/
│  ├─ schema.sql            # telemetry table (idempotent on msg_id)
│  └─ receiver.py           # MQTT subscriber + Flask read API
├─ scripts/
│  ├─ calibrate.py
│  └─ simulate.py
└─ tests/                   # pytest: measurement, detector, telemetry, server
```
