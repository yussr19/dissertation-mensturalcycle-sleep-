
# Luna — menstrual cycle and sleep sensing

A bedside sensing system that records sleep across a menstrual cycle and
renders the result as a physical drawing.

An LDC2410C mmWave radar and a Bangle.js 2 smartwatch log sleep to a
Raspberry Pi beside the bed. Nightly aggregation produces a sleep quality
score from 1 to 10, which is published over MQTT. An Arduino Nano 33 IoT
subscribes to that topic and drives a pen arm and a rotating disc, tracing
28 days of sleep as a spiral.

The recorder borrows its pen from a barograph — an instrument that has
drawn atmospheric pressure onto rotating paper since the nineteenth
century. Luna applies the same mechanism to a different cycle.

---

## Contents

- [How it works](#how-it-works)
- [Bill of materials](#bill-of-materials)
- [Repository layout](#repository-layout)
- [Part 1 — Bedside device](#part-1--bedside-device)
- [Part 2 — Luna recorder](#part-2--luna-recorder)
- [Part 3 — Exhibition mode](#part-3--exhibition-mode)
- [Enclosures](#enclosures)
- [Datasets](#datasets)
- [Analysis](#analysis)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)

---

## How it works

```
Bangle.js 2                      LDC2410C radar
HR, IBI, survey                  presence, movement
     |                                 |
     | BLE                             | UART
     v                                 v
        Bedside Pi  —  sleeppi
        finalsleep.db · log_sleep.py · log_radar.py
        compute_sleep_metrics.py · compute_composite.py
        publish_sleep.py
                      |
                      | publish
                      v
        MQTT broker — mqtt.cetools.org:1884
        student/CASA0022/yussr/sleepquality
                      |
                      | subscribe
                      v
        Luna recorder — Arduino Nano 33 IoT
                   |            |
            SG90 pen arm    28BYJ-48 disc
          traces quality    1 turn / 28 days
```

The radar gives binary presence and movement. The Bangle gives heart rate
and inter-beat intervals. Together these produce sleep duration, efficiency,
wake after sleep onset (WASO) and movement percentage, which are combined
into a single 1–10 composite score per night.

---

## Bill of materials

### Bedside device

| Item | Qty | Notes | Approx. cost |
|------|-----|-------|--------------|
| Raspberry Pi 3 Model A+ | 1 | Runs logging and nightly aggregation | £23 |
| microSD card, 32GB+ | 1 | Raspberry Pi OS | £8 |
| Official Pi power supply | 1 | Underpowered supplies cause boot failures | £10 |
| LDC2410C mmWave radar | 1 | UART presence/movement sensor | £6–10 |
| Bangle.js 2 smartwatch | 1 | Heart rate, IBI, morning survey | £99.60 |
| Jumper wires, female-female | 4 | Radar to Pi GPIO | £6 per pack |
| 3D printed sleep enclosure | 1 | `fusion/sleep enclousre final.stl` | filament only |

Subtotal: roughly **£153–157**, dominated by the smartwatch.

The Pi 3 Model A+ has 512MB of RAM and no Ethernet port. It is adequate for
logging and nightly aggregation, but it will not comfortably run a desktop
environment or a remote code editor alongside the sensing scripts. Work on
it over plain SSH rather than VS Code Remote, and keep anything non-essential
off it while it is recording.

### Luna recorder

| Item | Qty | Notes | Approx. cost |
|------|-----|-------|--------------|
| Arduino Nano 33 IoT | 1 | WiFi + MQTT subscriber | £20–25 |
| SG90 micro servo | 1 | Pen arm, radial position | £3 |
| 28BYJ-48 stepper + ULN2003 driver | 1 | Usually sold as a pair | £5 |
| WS2812B LED strip, 28 LEDs | 1 | Exhibition lighting | £10 |
| Metcheck black fibre tip recording pen | 1 | Barograph nib, SKU MET-FIBRENIB | £16.50 |
| Paper discs | — | Cut to fit the turntable | £3 |
| 5V 2A power supply | 1 | Servo and stepper draw more than USB supplies | £10 |
| 3D printed recorder body | 1 | `fusion/luna recorder final.stl` | filament only |
| 3D printed pen dial and holder | 1 | `fusion/pen dial and holder.stl` | filament only |

Subtotal: roughly **£68–73**, excluding filament.

### Total

**Roughly £221–230** for the complete system.

Prices are UK retail including VAT, correct as of August 2026. The Bangle.js
2 figure comes from Espruino's shop and The Pi Hut; the recording pen from
Metcheck. Remaining figures are typical hobbyist supplier prices.

### The pen

The pen is a barograph nib rather than an ordinary fineliner. It is 20.3mm
long and 4mm wide, with two dovetail grooves on the back that slot onto a
recording arm, and the nib lasts around twelve months of continuous use.
The pen holder in `fusion/pen dial and holder.stl` is dimensioned for these
grooves — an ordinary pen will not seat correctly without modifying the
model.

### Wiring — Luna recorder

| Component | Pin |
|-----------|-----|
| SG90 servo signal | D6 |
| 28BYJ-48 via ULN2003 IN1 | D8 |
| 28BYJ-48 via ULN2003 IN2 | D10 |
| 28BYJ-48 via ULN2003 IN3 | D9 |
| 28BYJ-48 via ULN2003 IN4 | D11 |

Note the IN2/IN3 ordering — it is not sequential. This matches the
`Stepper disc(STEPS_PER_REV, 8, 10, 9, 11)` declaration in the sketch.

### Wiring — LDC2410C to Raspberry Pi

| LDC2410C | Pi header pin |
|----------|---------------|
| VCC | 2 or 4 (5V) |
| GND | 6 |
| TX | 10 (GPIO15, Pi RX) |
| RX | 8 (GPIO14, Pi TX) |

Diagrams and placement notes are in `sketches/`.

---

## Repository layout

| Path | Contents |
|------|----------|
| `final_code/bedside_device/` | Logging, metrics and publishing on the bedside Pi |
| `final_code/exhibition/` | Exhibition publisher and the Arduino sketch |
| `test_code/` | Hardware sanity-check scripts |
| `analysis/` | Statistics and figure generation |
| `datasets/` | Exported sleep, radar and survey data |
| `fusion/` | Fusion 360 sources and STL exports |
| `sketches/` | Diagrams and design notes |

---

## Part 1 — Bedside device

### Prepare the Pi

Flash Raspberry Pi OS, then free the serial port for the radar:

```bash
sudo raspi-config
# Interface Options -> Serial Port
#   login shell over serial?      -> No
#   serial port hardware enabled? -> Yes
sudo reboot
```

### Install dependencies

```bash
sudo apt update
sudo apt install -y python3-pip sqlite3
pip3 install pyserial paho-mqtt bleak
```

### Clone and test

```bash
git clone https://github.com/yussr19/dissertation-mensturalcycle-sleep-.git
cd dissertation-mensturalcycle-sleep-
python3 test_code/test_radar.py
```

Walk in front of the sensor. You should see `presence=True movement=True`,
then `movement=False` when you sit still. If nothing prints, see
[Troubleshooting](#troubleshooting).

### The pipeline

| Script | Purpose |
|--------|---------|
| `log_radar.py` | Logs presence and movement to `finalsleep.db` |
| `log_sleep.py` | Logs Bangle.js data to `finalsleep.db` |
| `sync_bangle.py` | Pulls JSON off the watch over BLE into SQLite |
| `compute_sleep_metrics.py` | Duration, efficiency, WASO, movement % |
| `compute_composite.py` | Combines metrics into a 1–10 score |
| `publish_sleep.py` | Publishes the score to MQTT |

`log_radar.py` runs continuously overnight. The compute and publish steps
run once per day after waking.

To schedule them, add entries to the Pi's crontab with `crontab -e`. For
example, to run the daily chain at 10am:

```
0 10 * * * cd /home/USER/dissertation-mensturalcycle-sleep-/final_code/bedside_device && /usr/bin/python3 compute_sleep_metrics.py
5 10 * * * cd /home/USER/dissertation-mensturalcycle-sleep-/final_code/bedside_device && /usr/bin/python3 compute_composite.py
10 10 * * * cd /home/USER/dissertation-mensturalcycle-sleep-/final_code/bedside_device && /usr/bin/python3 publish_sleep.py
```

Use absolute paths — cron does not inherit your shell environment, and
relative paths are the most common reason a scheduled script works by hand
but silently fails overnight.

---

## Part 2 — Luna recorder

### Arduino setup

Install the Arduino IDE, add the **Arduino SAMD Boards** package, select
**Arduino Nano 33 IoT**, and install these libraries via Library Manager:

- WiFiNINA
- PubSubClient
- Servo
- Stepper
- ArduinoJson

### Credentials

The sketch reads credentials from `config.h`, which is not in this
repository. Create it from the template:

```bash
cd final_code/exhibition/final_exhib
cp config.example.h config.h
```

Fill in your MQTT username and password and up to two WiFi networks. The
sketch tries them in order, which is useful when moving between a home
network and a venue.

### Calibration

Two constants in the sketch set where the pen sits:

```cpp
const int ANGLE_Q1  = 20;   // sleep quality 1  — inner ring
const int ANGLE_Q10 = 160;  // sleep quality 10 — outer ring
```

Adjust these after assembly so the pen reaches the inner and outer edges of
the paper without binding.

### Flash and check

Upload the sketch, open Serial Monitor at 9600 baud. You should see the WiFi
and MQTT connections succeed, then `Waiting for sleep-quality data...`.

---

## Part 3 — Exhibition mode

For an exhibition the bedside Pi is not present, so a second Pi replays a
recorded 28-day cycle from the database.

```bash
export MQTT_USER="your_username"
export MQTT_PASS="your_password"

cd final_code/exhibition
python3 publish_exhibition.py --inspect        # check the data first
python3 publish_exhibition.py --seed           # fill the recorder history
python3 publish_exhibition.py --interval 10    # fast test
python3 publish_exhibition.py                  # live: one day per 10 min
```

The publisher sends one small JSON message per day:

```json
{"quality": 7, "cycle_day": 12}
```

Messages are retained, so a recorder that is power-cycled mid-exhibition
picks up the current value immediately rather than standing still.

Put the credentials in `~/.bashrc` so they survive reboots:

```bash
echo 'export MQTT_USER="your_username"' >> ~/.bashrc
echo 'export MQTT_PASS="your_password"' >> ~/.bashrc
source ~/.bashrc
```

---

## Enclosures

`fusion/` holds both Fusion 360 sources and STL exports.

| File | Part |
|------|------|
| `luna recorder final.stl` | Recorder body |
| `pen dial and holder.stl` | Pen arm and dial |
| `sleep enclousre final.stl` | Bedside sensor housing |

The `.f3d` and `.f3z` files are the editable Fusion 360 sources. The STLs
are ready to slice.

---

## Datasets

| File | Contents |
|------|----------|
| `datasets/sleep_log.csv` | Nightly sleep records and composite scores |
| `datasets/radar_sample.csv` | Radar output samples |
| `datasets/survey_responses.csv` | 17 exhibition visitor responses |

Survey responses record date, gender, age band and one comprehension
question. They carry no names, emails or precise timestamps.

---

## Analysis

```bash
cd analysis
python3 results_statistics.py
python3 make_figure_5_1.py
```

`make_figure_5_1.py` produces the 28-day circular visualisation.

Both scripts read from the sleep database. If you are reproducing this
without the original database, point them at `datasets/sleep_log.csv`
instead by editing the path at the top of each script.

---

## Troubleshooting

**Radar prints nothing.** Almost always baud rate or the serial console.
The LDC2410C defaults to 256000, though some boards ship at 115200. Confirm
the serial console is disabled in `raspi-config`.

**Presence flickers.** A single frame reading "no target" mid-sleep is
normal. Aggregation applies a hold timer so a brief dropout is not read as
someone leaving the bed.

**Sitting still reads as absent.** Stationary detection depends on the
per-gate sensitivity thresholds and on what is behind the person. This is
tuning, not a fault.

**Recorder connects but never moves.** Check the payload keys are exactly
`quality` and `cycle_day`. The sketch uses `StaticJsonDocument<128>`, so an
oversized message fails to deserialize and is silently ignored.

**Recorder drops off MQTT during replay.** `replayHistory()` blocks while
it sweeps, during which `mqtt.loop()` does not run. Long sweeps can exceed
the keepalive. It reconnects, but messages arriving mid-sweep are lost.

**Scheduled scripts work by hand but not overnight.** Cron runs with a
minimal environment. Use absolute paths and check `/var/log/syslog`.

---

## Known limitations

- The LDC2410C reports presence along a single beam. It does not count people
  or track position, so the system assumes one occupant.
- Sleep staging is inferred from movement and heart rate, not EEG. Values are
  relative indicators rather than clinical measurements.
- The disc advances during replay as well as on its own schedule; over a long
  exhibition these two can drift out of step.
- MQTT credentials are transmitted without TLS on port 1884.
- The recorder holds 28 days in memory with no persistence. A power cycle
  loses the history until the publisher re-seeds it.

---

## License

MIT.
