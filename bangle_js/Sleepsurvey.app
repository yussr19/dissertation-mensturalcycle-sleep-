/* sleepsurvey — morning self-report app for Bangle.js 2
 *
 * Shows the current cycle day and phase (derived from a fixed last-period
 * start date), prompts for sleep quality and energy on 1-10 scales, and
 * transmits the responses as a single JSON packet over the Nordic UART
 * Service, where they are received by the Pi (sync_bangle.py) and written
 * to sleep.db.
 *
 * Installed to the launcher with:
 *   require("Storage").write("sleepsurvey.info",
 *     {"id":"sleepsurvey","name":"Sleep Survey","src":"sleepsurvey.app.js"});
 */

var answers = {};

// Calculate cycle day based on last period start
var lastPeriod = new Date(2026, 5, 1); // June 1 2026 (month is 0-indexed)
var today = new Date();
var cycleDay = Math.floor((today - lastPeriod) / (1000 * 60 * 60 * 24)) + 1;

// Determine phase
var phase = "follicular";
if (cycleDay >= 14 && cycleDay <= 16) phase = "ovulation";
if (cycleDay >= 17 && cycleDay <= 28) phase = "luteal";
if (cycleDay <= 5) phase = "menstrual";

answers.cycle_day = cycleDay;
answers.phase = phase;

function showCycleInfo() {
  E.showMessage("Cycle Day: " + cycleDay + "\nPhase: " + phase, "Cycle Info");
  setTimeout(function() {
    askSleepQuality();
  }, 3000);
}

function askSleepQuality() {
  var val = 5;
  E.showMenu({
    "": { title: "Sleep Quality?" },
    "Rating: 1-10": {
      value: val, min: 1, max: 10,
      onchange: function(v) { val = v; }
    },
    "Confirm": function() {
      answers.sleep_quality = val;
      E.showMenu();
      askEnergy();
    }
  });
}

function askEnergy() {
  var val = 5;
  E.showMenu({
    "": { title: "Energy Level?" },
    "Rating: 1-10": {
      value: val, min: 1, max: 10,
      onchange: function(v) { val = v; }
    },
    "Confirm": function() {
      answers.energy = val;
      E.showMenu();
      sendData();
    }
  });
}

function sendData() {
  var msg = JSON.stringify(answers) + "\n";
  Bluetooth.println(msg);
  E.showMessage("Data sent!\nDay " + cycleDay + " | " + phase);
  setTimeout(function() {
    E.showMenu();   // known issue: leaves a blank screen on exit.
                    // load() returns cleanly to the launcher instead.
  }, 3000);
}

showCycleInfo();
