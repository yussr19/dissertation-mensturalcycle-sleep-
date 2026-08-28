import json, time
from datetime import date
import paho.mqtt.client as mqtt

BROKER = "mqtt.cetools.org"
PORT = 1884
USER = "student"
PASSWD = "ce2021-mqtt-forget-whale"
TOPIC = "student/CASA0022/yussr/sleepquality"

SYNTHETIC = [5,4,4,4,6,8,8,7,7,6,7,8,6,6,6,6,5,6,7,5,7,6,6,5,6,4,4,4]
START = date(2026, 7, 15)

client = mqtt.Client()
client.username_pw_set(USER, PASSWD)
client.connect(BROKER, PORT)
client.loop_start()

while True:
    day_index = (date.today() - START).days % 28
    payload = json.dumps({"date": str(date.today()), "cycle_day": day_index + 1, "quality": SYNTHETIC[day_index]})
    client.publish(TOPIC, payload, retain=True)
    print("Published:", payload)
    time.sleep(3600)
