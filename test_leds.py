import time
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

print("LED test started - turning all LEDs purple")
for i in range(strip.numPixels()):
    strip.setPixelColor(i, Color(128, 0, 128))
strip.show()

time.sleep(5)

print("Turning off")
for i in range(strip.numPixels()):
    strip.setPixelColor(i, Color(0, 0, 0))
strip.show()
