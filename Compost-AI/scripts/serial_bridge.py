import sys
import time
import threading
import serial
import requests

PORT        = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BASE_URL    = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "http://localhost:3000"
BAUD        = 9600
TRIGGER_URL = f"{BASE_URL}/api/trigger"
SERVO_URL   = f"{BASE_URL}/api/servo-command"


def servo_poller(ser: serial.Serial) -> None:
    """Background thread: polls /api/servo-command and writes to Arduino."""
    while True:
        try:
            r = requests.get(SERVO_URL, timeout=10)
            cmd = r.json().get("command")
            if cmd:
                print(f"[bridge] servo → {cmd}")
                ser.write((cmd + "\n").encode())
        except requests.RequestException:
            pass  # Next.js may not be up yet; keep retrying
        time.sleep(0.5)


def main() -> None:
    print(f"[bridge] opening {PORT} at {BAUD} baud …")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except serial.SerialException as e:
        sys.exit(f"[bridge] ERROR: could not open {PORT}: {e}\n"
                 "  → Check Device Manager → Ports for the right COM number.\n"
                 "  → Close the Arduino IDE Serial Monitor if it's open.")

    time.sleep(2)  # Arduino resets on connect; wait for it to be ready
    ser.reset_input_buffer()
    print(f"[bridge] ready  ITEM_DETECTED → {TRIGGER_URL}")
    print(f"[bridge]        servo commands ← {SERVO_URL}")

    # Start servo polling on a daemon thread so it exits when the main thread does.
    t = threading.Thread(target=servo_poller, args=(ser,), daemon=True)
    t.start()

    # Main thread: read lines from Arduino and forward ITEM_DETECTED.
    while True:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
        except serial.SerialException as e:
            sys.exit(f"[bridge] Serial read error: {e}")

        if not line:
            continue

        print(f"[bridge] serial: {line}")

        if line == "ITEM_DETECTED":
            print("[bridge] triggering capture …")
            try:
                r = requests.post(TRIGGER_URL, timeout=10)
                print(f"[bridge] → {r.status_code}")
            except requests.ConnectionError:
                print(f"[bridge] WARNING: could not reach {TRIGGER_URL} "
                      "(is `npm run dev` running?)")
            except requests.Timeout:
                print("[bridge] WARNING: trigger request timed out")


if __name__ == "__main__":
    main()
