import RPi.GPIO as GPIO
import time

FAN_PIN = 23

GPIO.setmode(GPIO.BCM)
GPIO.setup(FAN_PIN, GPIO.OUT)

print("Turning fan ON for 5 seconds")
GPIO.output(FAN_PIN, GPIO.HIGH)
time.sleep(5)

print("Turning fan OFF")
GPIO.output(FAN_PIN, GPIO.LOW)

GPIO.cleanup()
