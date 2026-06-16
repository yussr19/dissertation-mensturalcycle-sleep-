import sqlite3
import serial
import time
from datetime import datetime

DB_PATH = '/home/yussr19/sleep.db'
CYCLE_DAY = 1

def parse_radar(data):
    try:
        line = data.decode('ascii').strip()
        if line.startswith('$JYBSS'):
            parts = line.split(',')
            presence = int(parts[1].strip())
            return presence
    except:
        pass
    return None

def log_entry(cycle_day, presence, heart_rate=None, hrv=None, sleep_quality=None, energy=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    sql = "INSERT INTO sleep_log (date, cycle_day, sleep_quality, energy, heart_rate, hrv, presence) VALUES (?, ?, ?, ?, ?, ?, ?)"
    c.execute(sql, (datetime.now().strftime('%Y-%m-%d'), cycle_day, sleep_quality, energy, heart_rate, hrv, presence))
    conn.commit()
    conn.close()
    print("Logged: cycle_day={}, presence={}".format(cycle_day, presence))

try:
    ser = serial.Serial('/dev/ttyS0', 115200, timeout=1)
    print("Radar connected. Logging every 30s. Ctrl+C to stop.")
    while True:
        data = ser.read(64)
        presence = parse_radar(data)
        if presence is not None:
            log_entry(CYCLE_DAY, presence)
        time.sleep(30)
except KeyboardInterrupt:
    print("Stopped")
except Exception as e:
    print("Error: {}".format(e))
