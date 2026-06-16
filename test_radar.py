import serial
import time

ser = serial.Serial('/dev/ttyS0', 115200, timeout=1)
print("Radar test started. Listening for data...")

try:
    while True:
        data = ser.read(64)
        if data:
            print("Raw data:", data.hex())
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Stopped")
    ser.close()
