import RPi.GPIO as GPIO
import time

FAN_PIN = 23
TEMP_ON = 60.0
TEMP_OFF = 55.0

GPIO.setmode(GPIO.BCM)
GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.output(FAN_PIN, GPIO.LOW)

def get_temp():
    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
        return float(f.read()) / 1000.0

fan_on = False

print("Fan control running. Ctrl+C to stop.")
try:
    while True:
        temp = get_temp()
        if temp >= TEMP_ON and not fan_on:
            GPIO.output(FAN_PIN, GPIO.HIGH)
            fan_on = True
            print("Temp {:.1f}C - Fan ON".format(temp))
        elif temp <= TEMP_OFF and fan_on:
            GPIO.output(FAN_PIN, GPIO.LOW)
            fan_on = False
            print("Temp {:.1f}C - Fan OFF".format(temp))
        else:
            print("Temp {:.1f}C - Fan {}".format(temp, "ON" if fan_on else "OFF"))
        time.sleep(10)
except KeyboardInterrupt:
    GPIO.output(FAN_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("Stopped")
