# Aqualert Instructions

This setup uses:

- `Arduino UNO R4 Minima`
- `HC-SR04`
- the Arduino sketch in `aqualert-ai/arduino/aquaalert_uno_r4/aquaalert_uno_r4.ino`
- the USB serial bridge in `aqualert-ai/scripts/serial_reader.py`
- the Vercel frontend in `aqualert-frontend/`

## Wiring

Use these exact connections:

| HC-SR04 | Arduino UNO R4 Minima |
| --- | --- |
| `VCC` | `5V` |
| `GND` | `GND` |
| `TRIG` | `D9` |
| `ECHO` | `D10` |

## How The Live Flow Works

1. The Arduino reads the HC-SR04 and prints one JSON reading over USB serial.
2. `serial_reader.py` opens the USB serial port directly, so you do not open Arduino Serial Monitor at the same time.
3. `serial_reader.py` posts each reading to your Vercel app at `POST /api/ingest`.
4. The Vercel app stores the latest reading and recent history in KV.
5. The Vercel page polls `GET /api/latest` every 2 seconds and updates the live dashboard.

Important:

- The machine running `serial_reader.py` must be physically connected to the Arduino by USB.
- If the Arduino is plugged into your laptop, run the script on your laptop.
- If the Arduino is plugged into the Ubuntu server, run the script on the Ubuntu server.
- Do not open Arduino Serial Monitor while the Python bridge is running, because both programs compete for the same serial port.

## Step 1: Flash The Arduino

Open the Arduino IDE and upload:

- `aqualert-ai/arduino/aquaalert_uno_r4/aquaalert_uno_r4.ino`

The sketch currently:

- uses `D9` and `D10`
- emits JSON over Serial
- uses `115200` baud
- sends `distance_cm`, `fill_percent`, `status`, `confidence`, `sample_count`, and `spread_cm`

After the first hardware test, update these calibration constants in the sketch:

- `FULL_DISTANCE_CM`
- `EMPTY_DISTANCE_CM`

## Step 2: Configure The Vercel Frontend

In Vercel, set the `aqualert-frontend` project environment variables:

- `KV_REST_API_URL`
- `KV_REST_API_TOKEN`
- `INGEST_SECRET`
- `NEXT_PUBLIC_ALERT_THRESHOLD`
- `NEXT_PUBLIC_WARN_THRESHOLD`

`INGEST_SECRET` must match the same value used by `serial_reader.py`.

The live API routes are:

- `POST /api/ingest`
- `GET /api/latest`

## Step 3: Run The Serial Bridge On The USB-Connected Machine

Install Python dependencies:

```bash
cd aqualert-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

Create the bridge env file:

```bash
cp scripts/.env.example scripts/.env
```

Set these values in `aqualert-ai/scripts/.env`:

```bash
VERCEL_INGEST_URL=https://<your-vercel-app>/api/ingest
INGEST_SECRET=<same-secret-as-vercel>
SERIAL_PORT=
BAUD_RATE=115200
DEVICE_ID=aqualert-uno-r4
PUSH_INTERVAL=1.0
```

Notes:

- Leave `SERIAL_PORT` blank to auto-detect the Arduino.
- If auto-detect fails, set it manually.
- Common ports:
  - macOS: `/dev/cu.usbmodem*`
  - Linux: `/dev/ttyACM0` or `/dev/ttyUSB0`

Run the bridge:

```bash
python scripts/serial_reader.py
```

Expected behavior:

- the terminal prints each serial line
- the script parses the Arduino JSON
- the script posts `distance_cm` to Vercel as the live chart value
- the dashboard shows live status, fill level, confidence, and recent history

## Step 4: Verify The Dashboard

Open the Vercel app and confirm:

- the header shows `LIVE`
- the main sensor value changes when water level changes
- `Device Status` shows values like `normal`, `low`, `critical`, `watch`, or `sensor_fault`
- `Fill Level` and `Confidence` populate
- the sparkline chart updates

## Optional: Run It On The Ubuntu Server

Use this only if the Arduino is physically plugged into the Ubuntu server by USB.

Server setup commands:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
git clone https://github.com/vignesh-nagarajan-vn/SchoolPulse-AI.git
cd SchoolPulse-AI/aqualert-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
cp scripts/.env.example scripts/.env
python scripts/serial_reader.py
```

If the Arduino is attached to the server, find its device path with:

```bash
ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null
```

Then set `SERIAL_PORT` in `scripts/.env`.

## Current Repo Behavior

These files are the important ones for this path:

- `aqualert-ai/arduino/aquaalert_uno_r4/aquaalert_uno_r4.ino`
- `aqualert-ai/scripts/serial_reader.py`
- `aqualert-ai/scripts/.env.example`
- `aqualert-frontend/app/api/ingest/route.js`
- `aqualert-frontend/app/api/latest/route.js`
- `aqualert-frontend/app/page.jsx`

## Current Blocker For Remote SSH Setup

The Ubuntu server `64.181.227.9` currently rejects SSH from this machine with:

```text
Permission denied (publickey)
```

So I could not log in from this environment to run the server-side steps directly.

To let me finish the remote setup, add my current machine's SSH public key to the server or provide the correct private key/config for:

```bash
ssh ubuntu@64.181.227.9
```
