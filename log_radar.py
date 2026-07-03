import sqlite3
import serial
import time
from datetime import datetime

DB_PATH = '/home/yussr19/sleep.db'
CYCLE_DAY = 1  # update per cycle, or read from bangle sync

def parse_frame(data):
    # LD2410C frame: F4 F3 F2 F1 ... AA <state> ... F8 F7 F6 F5
    h = data.find(b'\xf4\xf3\xf2\xf1')
    if h == -1:
        return None
    aa = data.find(b'\xaa', h)
    if aa == -1 or aa + 1 >= len(data):
        return None
    state = data[aa + 1]
    presence = 1 if state > 0 else 0
    movement = 1 if state in (1, 3) else 0  # 1=moving,3=both -> moving
    return presence, movement

def log_entry(cycle_day, presence, movement):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    sql = ("INSERT INTO sleep_log (date, cycle_day, presence, movement) "
           "VALUES (?, ?, ?, ?)")
    c.execute(sql, (datetime.now().strftime('%Y-%m-%d'), cycle_day, presence, movement))
    conn.commit()
    conn.close()
    print("Logged: presence={}, movement={}".format(presence, movement))

try:
    ser = serial.Serial('/dev/ttyS0', 256000, timeout=1)
    print("Radar connected. Logging every 30s. Ctrl+C to stop.")
    while True:
        data = ser.read(64)
        result = parse_frame(data)
        if result is not None:
            presence, movement = result
            log_entry(CYCLE_DAY, presence, movement)
        time.sleep(30)
except KeyboardInterrupt:
    print("Stopped")
except Exception as e:
    print("Error: {}".format(e))
