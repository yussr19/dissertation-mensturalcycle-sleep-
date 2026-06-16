import time
from datetime import datetime
from rpi_ws281x import PixelStrip, Color

LED_COUNT = 28
LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_BRIGHTNESS = 100
LED_INVERT = False
LED_CHANNEL = 0

strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()

def set_all(color):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
    strip.show()

def get_color(cycle_phase):
    hour = datetime.now().hour
    if hour >= 21:
        return Color(180, 0, 0)      # red - wind down
    elif hour >= 20:
        return Color(180, 80, 0)     # amber - prepare
    elif cycle_phase == 'luteal':
        return Color(128, 0, 128)    # purple
    else:
        return Color(0, 180, 180)    # teal - follicular

# Set cycle_phase to 'luteal' or 'follicular' manually for now
cycle_phase = 'follicular'

print("Bedtime LED logic running. Ctrl+C to stop.")
try:
    while True:
        color = get_color(cycle_phase)
        set_all(color)
        time.sleep(60)
except KeyboardInterrupt:
    set_all(Color(0, 0, 0))
    print("Stopped")
