#!/usr/bin/env python3
"""
HLK-LD2410C presence / movement test.

Prints two booleans:
    presence  - someone is there (moving OR stationary)
    movement  - someone is there AND moving

Usage:
    python3 ld2410_presence_test.py                  # print on change only
    python3 ld2410_presence_test.py --all            # print every frame
    python3 ld2410_presence_test.py --port /dev/serial0 --baud 256000

Wiring (LD2410C -> Pi 40-pin header):
    VCC -> pin 2  (5V)
    GND -> pin 6
    TX  -> pin 10 (GPIO15, Pi RX)
    RX  -> pin 8  (GPIO14, Pi TX)

Free the serial port first:
    sudo raspi-config -> Interface Options -> Serial Port
      login shell over serial?  -> No
      serial port hardware?     -> Yes
    sudo reboot

Install:
    pip3 install pyserial
"""

import argparse
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed. Run: pip3 install pyserial")


HEAD = b"\xf4\xf3\xf2\xf1"
TAIL = b"\xf8\xf7\xf6\xf5"

# Target state byte, bit 0 = moving, bit 1 = stationary
STATE_NONE = 0x00
STATE_MOVING = 0x01
STATE_STATIONARY = 0x02
STATE_BOTH = 0x03

STATE_NAMES = {
    STATE_NONE: "no target",
    STATE_MOVING: "moving",
    STATE_STATIONARY: "stationary",
    STATE_BOTH: "moving + stationary",
}


def parse_frame(data):
    """
    Decode the data section of a report frame.
    Returns a dict, or None if this isn't a basic/engineering target frame.

    Basic target data layout:
        [0]    0x02  data type (0x01 = engineering, 0x02 = basic)
        [1]    0xAA  head
        [2]    target state
        [3:5]  moving target distance, cm, uint16 LE
        [5]    moving target energy
        [6:8]  stationary target distance, cm, uint16 LE
        [8]    stationary target energy
        [9:11] detection distance, cm, uint16 LE
    """
    if len(data) < 11:
        return None
    if data[0] not in (0x01, 0x02) or data[1] != 0xAA:
        return None

    state = data[2]
    return {
        "state": state,
        "state_name": STATE_NAMES.get(state, f"unknown ({state:#04x})"),
        "presence": state != STATE_NONE,
        "movement": bool(state & STATE_MOVING),
        "stationary": bool(state & STATE_STATIONARY),
        "moving_cm": int.from_bytes(data[3:5], "little"),
        "moving_energy": data[5],
        "stationary_cm": int.from_bytes(data[6:8], "little"),
        "stationary_energy": data[8],
        "detect_cm": int.from_bytes(data[9:11], "little"),
    }


def frames(ser):
    """Yield decoded frames from the serial stream."""
    buf = bytearray()

    while True:
        chunk = ser.read(64)
        if chunk:
            buf.extend(chunk)

        while True:
            start = buf.find(HEAD)
            if start == -1:
                if len(buf) > 256:
                    del buf[:-3]
                break

            if len(buf) - start < 6:
                break

            length = int.from_bytes(buf[start + 4:start + 6], "little")
            total = 4 + 2 + length + 4
            if len(buf) - start < total:
                break

            frame = bytes(buf[start:start + total])
            del buf[:start + total]

            if not frame.endswith(TAIL):
                continue

            parsed = parse_frame(frame[6:6 + length])
            if parsed:
                yield parsed


def main():
    p = argparse.ArgumentParser(description="LD2410C presence test")
    p.add_argument("--port", default="/dev/serial0")
    p.add_argument("--baud", type=int, default=256000)
    p.add_argument("--all", action="store_true",
                   help="print every frame instead of only on change")
    args = p.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1.0)
    except serial.SerialException as e:
        sys.exit(f"Could not open {args.port} at {args.baud}: {e}")

    time.sleep(0.1)
    ser.reset_input_buffer()
    print(f"Listening on {args.port} at {args.baud}. Ctrl-C to stop.\n")

    last = None
    last_frame_time = time.time()

    try:
        for f in frames(ser):
            last_frame_time = time.time()
            key = (f["presence"], f["movement"])

            if args.all or key != last:
                stamp = time.strftime("%H:%M:%S")
                print(
                    f"{stamp}  presence={str(f['presence']):<5} "
                    f"movement={str(f['movement']):<5} "
                    f"[{f['state_name']}]  "
                    f"moving={f['moving_cm']:>3}cm(e{f['moving_energy']:>3}) "
                    f"still={f['stationary_cm']:>3}cm(e{f['stationary_energy']:>3})"
                )
                last = key

            if time.time() - last_frame_time > 3:
                print("[no frames for 3s - check wiring, baud, serial console]")
                last_frame_time = time.time()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
