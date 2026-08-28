/* hrvlog — beat-to-beat HRV logger for Bangle.js 2
 *
 * Subscribes to the HRM-raw event and captures the firmware's own peak
 * detection flag (isBeat) to build a series of inter-beat intervals (IBIs).
 * Writes every beat to CSV in Storage, and shows rolling RMSSD / SDNN
 * on screen so you can sanity-check the signal while recording.
 *
 * Requires firmware 2v13 or later.
 */

var CONF = {
  pollMs         : 20,   // HRM sample interval in ms. 20 = 50Hz, 40 = 25Hz default.
                         // Lower = finer IBI resolution, higher power draw.
  minIBI         : 300,  // ms — reject anything faster than 200 bpm
  maxIBI         : 2000, // ms — reject anything slower than 30 bpm
  maxDelta       : 0.25, // reject beat if IBI differs >25% from previous accepted
  minConfidence  : 50,   // firmware confidence gate (0-100)
  window         : 120,  // number of accepted IBIs in the rolling metric window
  wearDetect     : true  // false = keep logging even if watch thinks it's off-wrist
};

var logFile = null;
var logName = "";
var lastBeat = 0;      // timestamp of previous beat
var lastIBI  = 0;      // previous ACCEPTED interval, for the delta test
var ibis     = [];     // rolling window of accepted IBIs
var nAccept  = 0;
var nReject  = 0;
var live     = { bpm: 0, conf: 0 };

// ---------------------------------------------------------------- logging

function pad(n) { return ("0" + n).substr(-2); }

function makeName() {
  var d = new Date();
  // 21 chars — Bangle filenames are limited to 28
  return "hrv_" + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) +
         "_" + pad(d.getHours()) + pad(d.getMinutes()) + ".csv";
}

function startLog() {
  logName = makeName();
  logFile = require("Storage").open(logName, "w");
  logFile.write("t_ms,ibi_ms,bpm_inst,confidence,accel_mag,accepted\n");
}

function stopLog() {
  logFile = null;
  Bangle.removeListener("HRM-raw", onRaw);
  Bangle.setHRMPower(0, "hrvlog");
}

// ------------------------------------------------------------ beat capture

function onRaw(h) {
  live.bpm  = h.bpm;
  live.conf = h.confidence;

  if (!h.isBeat) return;          // only act on firmware-detected peaks

  var t = Date.now();
  if (!lastBeat) { lastBeat = t; return; }   // first beat has no interval

  var ibi = t - lastBeat;
  lastBeat = t;

  // --- artefact rejection -------------------------------------------------
  // Three independent gates: physiological plausibility, algorithm
  // confidence, and beat-to-beat continuity. The continuity test is the
  // standard ectopic/missed-beat filter — a dropped beat roughly doubles
  // the interval, a spurious one roughly halves it.
  var ok = (ibi >= CONF.minIBI) &&
           (ibi <= CONF.maxIBI) &&
           (h.confidence >= CONF.minConfidence);

  if (ok && lastIBI) {
    ok = Math.abs(ibi - lastIBI) / lastIBI <= CONF.maxDelta;
  }

  if (ok) {
    lastIBI = ibi;
    ibis.push(ibi);
    if (ibis.length > CONF.window) ibis.shift();
    nAccept++;
  } else {
    nReject++;
  }

  // Accelerometer magnitude is logged alongside every beat so motion
  // artefacts can be excluded again in post-processing.
  var a = Bangle.getAccel();

  if (logFile) {
    logFile.write([
      t,
      ibi,
      Math.round(60000 / ibi),
      h.confidence,
      a.mag.toFixed(3),
      ok ? 1 : 0
    ].join(",") + "\n");
  }
}

// ---------------------------------------------------------------- metrics

function metrics() {
  var n = ibis.length;
  if (n < 5) return null;

  var i, sum = 0;
  for (i = 0; i < n; i++) sum += ibis[i];
  var mean = sum / n;

  var sq = 0;
  for (i = 0; i < n; i++) sq += (ibis[i] - mean) * (ibis[i] - mean);
  var sdnn = Math.sqrt(sq / (n - 1));

  var d = 0;
  for (i = 1; i < n; i++) {
    var df = ibis[i] - ibis[i - 1];
    d += df * df;
  }
  var rmssd = Math.sqrt(d / (n - 1));

  return { rmssd: rmssd, sdnn: sdnn, hr: 60000 / mean, n: n };
}

// ----------------------------------------------------------------- display

function draw() {
  var m = metrics();
  g.reset().clearRect(0, 24, g.getWidth(), g.getHeight());
  g.setFontAlign(0, 0);

  g.setFont("6x8", 1).drawString(logName, g.getWidth() / 2, 36);

  if (!m) {
    g.setFont("6x8", 2).drawString("acquiring...", g.getWidth() / 2, 90);
    g.setFont("6x8", 1).drawString("conf " + live.conf + "%", g.getWidth() / 2, 120);
  } else {
    g.setFont("6x8", 3).drawString(m.hr.toFixed(0), g.getWidth() / 2, 70);
    g.setFont("6x8", 1).drawString("bpm", g.getWidth() / 2, 92);

    g.setFontAlign(-1, 0);
    g.setFont("6x8", 1);
    g.drawString("RMSSD  " + m.rmssd.toFixed(1) + " ms", 12, 120);
    g.drawString("SDNN   " + m.sdnn.toFixed(1) + " ms", 12, 134);
    g.drawString("beats  " + nAccept + " ok / " + nReject + " rej", 12, 148);
    g.drawString("conf   " + live.conf + "%", 12, 162);
    g.setFontAlign(0, 0);
  }
  Bangle.drawWidgets();
}

// -------------------------------------------------------------------- init

g.clear();
Bangle.loadWidgets();

// hrmPollInterval must be set BEFORE the sensor is powered on.
Bangle.setOptions({
  hrmPollInterval : CONF.pollMs,
  hrmWearDetect   : CONF.wearDetect
});

startLog();
Bangle.setHRMPower(1, "hrvlog");
Bangle.on("HRM-raw", onRaw);

var drawTimer = setInterval(draw, 1000);
draw();

// Clean shutdown when the app is exited (long-press) or the watch reboots.
E.on("kill", function () {
  if (drawTimer) clearInterval(drawTimer);
  stopLog();
});
