# AquaAlert Chat Context

## Hardware Setup Shared In Chat

- Board: Arduino UNO R4 Minima
- Sensor: HC-SR04 ultrasonic sensor
- Breadboard: optional only for power distribution
- ESP32: not connected right now
- Resistors: not needed right now

### Wiring

- `HC-SR04 VCC -> Arduino 5V`
- `HC-SR04 GND -> Arduino GND`
- `HC-SR04 TRIG -> Arduino D9`
- `HC-SR04 ECHO -> Arduino D10`

## User Goal

Build an AquaAlert flow where:

1. The ultrasonic sensor is read by the Arduino.
2. The reading appears through Serial Monitor / USB serial output.
3. The Vercel-hosted webpage updates live from that sensor data.
4. The same reading is stored in Supabase.

The user asked for the Arduino code to be organized inside the AquaAlert folder and for the live webpage update to be added in the place that matched the existing app best.

## Implementation Added In This Session

### Arduino Side

- Added Arduino sketch:
  - `aqualert-ai/arduino/aquaalert_uno_r4/aquaalert_uno_r4.ino`
- The sketch:
  - reads the HC-SR04 from `D9` and `D10`
  - smooths several samples each cycle
  - estimates tank fill percent from calibration constants
  - classifies the reading as `normal`, `low`, `critical`, `watch`, or `sensor_fault`
  - prints one JSON object per reading over Serial at `115200` baud

### Local Bridge

- Added:
  - `aqualert-ai/scripts/serial_bridge.py`
- Purpose:
  - reads Arduino JSON over USB serial from the laptop
  - converts it into a backend payload
  - posts it to the Pulse Agent backend endpoint

### Backend + Dashboard

- Extended the existing `pulse-agent-ai` project instead of creating a separate page.
- Added backend live-water ingestion and storage:
  - `pulse-agent-ai/app/water_live.py`
  - `pulse-agent-ai/app/main.py`
  - `pulse-agent-ai/app/schemas.py`
  - `pulse-agent-ai/app/config.py`
  - `pulse-agent-ai/app/analytics.py`
- Added/updated Water dashboard UI:
  - `pulse-agent-ai/public/index.html`
  - `pulse-agent-ai/app/static/index.html`
  - `pulse-agent-ai/public/static/styles.css`
  - `pulse-agent-ai/app/static/styles.css`
- Added API notes:
  - `pulse-agent-ai/docs/api_contract.md`

### Live Dashboard Behavior

The Water panel now:

- shows the latest live tank fill percent
- shows location, confidence, distance, and water depth
- shows recent ultrasonic readings
- still keeps the existing water alert table
- auto-refreshes every few seconds

### Supabase Path

The backend now supports forwarding live water readings into Supabase through the existing sync endpoint when these environment variables are configured:

- `SUPABASE_SYNC_URL`
- `SUPABASE_SECRET_KEY`
- optional `SUPABASE_SYNC_SOURCE`

## Dependency Update

- Added `pyserial` to:
  - `aqualert-ai/requirements.txt`

## Verification Performed

- Python compile check was run for the new Python files and updated backend modules.
- A full runtime smoke test was not completed in-chat because the environment did not have all Python runtime dependencies installed for the backend.

## Follow-Up Requests Made After Coding

The user then asked to:

- check whether the backend was already running on `ubuntu@129.153.110.167`
- explain how to set up Supabase
- commit and push the changes
- include the context of this chat in a markdown file named `ocntext`

## Important Notes For Next Steps

- The Arduino cannot talk directly to Vercel on its own in the current hardware setup, so the USB serial bridge is the connection between the Arduino and the web backend.
- The calibration constants in the Arduino sketch should be updated after measuring the real full and low tank distances.
- Supabase writes depend on valid project credentials and the deployed Edge Function URL.
