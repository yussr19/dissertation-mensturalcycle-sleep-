import serial

ser = serial.Serial('/dev/ttyAMA0', 256000, timeout=1)
print("LD2410 test started. Listening...")

buf = b''
while True:
    buf += ser.read(64)
    # data frames start F4 F3 F2 F1 and end F8 F7 F6 F5
    while True:
        start = buf.find(b'\xf4\xf3\xf2\xf1')
        if start < 0:
            buf = buf[-4:]
            break
        end = buf.find(b'\xf8\xf7\xf6\xf5', start)
        if end < 0:
            buf = buf[start:]
            break
        frame = buf[start:end+4]
        buf = buf[end+4:]
        if len(frame) >= 13:
            state = frame[8]
            presence = 1 if state in (1, 2, 3) else 0
            print(f"presence: {presence} (state {state})")
