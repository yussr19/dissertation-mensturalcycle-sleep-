
import sqlite3

import json

import time

import paho.mqtt.client as mqtt

DB_PATH = '/home/yussr19/sleep.db'

BROKER = 'mqtt.cetools.org'

PORT = 1884

TOPIC = 'student/CASA0022/yussr/sleepquality'

MQTT_USER = 'student'

MQTT_PASS = 'ce2021-mqtt-forget-whale'

def get_latest():

    conn = sqlite3.connect(DB_PATH)

    row = conn.execute(

        "SELECT date, cycle_day, sleep_quality FROM sleep_log "

        "WHERE sleep_quality IS NOT NULL ORDER BY id DESC LIMIT 1"

    ).fetchone()

    conn.close()

    return row

def get_history():

    conn = sqlite3.connect(DB_PATH)

    rows = conn.execute(

        "SELECT date, cycle_day, sleep_quality FROM sleep_log "

        "WHERE sleep_quality IS NOT NULL ORDER BY id ASC"

    ).fetchall()

    conn.close()

    return rows

client = mqtt.Client()

client.username_pw_set(MQTT_USER, MQTT_PASS)

client.connect(BROKER, PORT, 60)

client.loop_start()

# Publish full history once on startup (retained latest)

for date, day, q in get_history():

    payload = json.dumps({"date": date, "cycle_day": day, "quality": q})

    client.publish(TOPIC + '/history', payload)

    time.sleep(0.1)

# Then publish latest every hour (retained so Nano gets it on subscribe)

while True:

    row = get_latest()

    if row:

        date, day, q = row

        payload = json.dumps({"date": date, "cycle_day": day, "quality": q})

        client.publish(TOPIC, payload, retain=True)

        print("Published:", payload)

    time.sleep(3600)

