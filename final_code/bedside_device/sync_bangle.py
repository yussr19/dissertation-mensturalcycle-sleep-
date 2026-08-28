import asyncio
import json
import sqlite3
from datetime import datetime
from bleak import BleakClient

ADDRESS = "D5:66:5B:CD:64:A9"
UART_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
DB_PATH = "/home/yussr19/sleep.db"

buffer = ""
done = asyncio.Event()


def log_entry(cycle_day, sleep_quality, energy, heart_rate=None, hrv=None, presence=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    sql = ("INSERT INTO sleep_log "
           "(date, cycle_day, sleep_quality, energy, heart_rate, hrv, presence) "
           "VALUES (?, ?, ?, ?, ?, ?, ?)")
    c.execute(sql, (datetime.now().strftime('%Y-%m-%d'), cycle_day,
                    sleep_quality, energy, heart_rate, hrv, presence))
    conn.commit()
    conn.close()
    print("Logged: cycle_day={}, sleep_quality={}, energy={}".format(
        cycle_day, sleep_quality, energy))


def handle_packet(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print("Ignored non-JSON line:", repr(text))
        return
    cycle_day = data.get("cycle_day")
    sleep_quality = data.get("sleep_quality")
    energy = data.get("energy")
    phase = data.get("phase")
    print("Received: day={}, phase={}, sleep={}, energy={}".format(
        cycle_day, phase, sleep_quality, energy))
    log_entry(cycle_day, sleep_quality, energy)
    done.set()


def notification_handler(sender, data):
    global buffer
    buffer += data.decode("utf-8", errors="ignore")
    while "\n" in buffer:
        line, buffer = buffer.split("\n", 1)
        line = line.strip().lstrip(">").strip()
        if line:
            handle_packet(line)


async def main():
    print("Connecting to Bangle.js...")
    async with BleakClient(ADDRESS) as client:
        print("Connected:", client.is_connected)
        await client.start_notify(UART_TX_UUID, notification_handler)
        print("Listening. Complete the morning survey on the Bangle to send data.")
        await done.wait()
        await client.stop_notify(UART_TX_UUID)
        print("Sync complete.")


asyncio.run(main())
