#!/usr/bin/env python3
"""
compute_sleep_metrics.py

Derives nightly sleep metrics from the radar_sample table and writes them
back to sleep_log.

Database:
    /home/yussr19/analysis/finalsleep_.db

Metrics:
    time_in_bed_min
    sleep_duration_min
    sleep_efficiency
    waso_min
    movement_pct

Usage:
    python3 compute_sleep_metrics.py --inspect
    python3 compute_sleep_metrics.py --dry-run
    python3 compute_sleep_metrics.py
"""

import sqlite3
import sys
from datetime import datetime, timedelta


DB_PATH = "/home/yussr19/analysis/finalsleep_.db"

SAMPLE_TABLE = "radar_sample"
TS_COL = "timestamp"
PRESENCE_COL = "presence"
MOVEMENT_COL = "movement"
NIGHT_COL = "night"

SAMPLE_SECS = 30

NIGHT_START_HOUR = 20
NIGHT_END_HOUR = 12

ONSET_STILL_MIN = 10
MIN_TIB_MIN = 120
GAP_WARN_RATIO = 0.5


def parse_ts(value):
    """Convert a stored timestamp into a Python datetime."""

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)

    s = str(value)

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue

    return None


def inspect(conn):
    """
    Inspect the configured radar table only.

    This avoids incorrectly treating sleep_log as a raw radar sample table.
    """

    print(f"Database: {DB_PATH}\n")
    print("Tables and columns found:\n")

    tables = [
        row[0]
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            ORDER BY name
            """
        ).fetchall()
    ]

    for table in tables:
        cols = [
            row[1]
            for row in conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        ]

        count = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        marker = (
            "  <- configured radar sample table"
            if table == SAMPLE_TABLE
            else ""
        )

        print(f"  {table} ({count} rows){marker}")
        print(f"      {', '.join(cols)}")
        print()

    if SAMPLE_TABLE not in tables:
        print(
            f"ERROR: configured radar table '{SAMPLE_TABLE}' does not exist."
        )
        return

    cols = [
        row[1]
        for row in conn.execute(
            f"PRAGMA table_info({SAMPLE_TABLE})"
        ).fetchall()
    ]

    required = {
        TS_COL,
        PRESENCE_COL,
        MOVEMENT_COL,
    }

    if NIGHT_COL:
        required.add(NIGHT_COL)

    missing = required - set(cols)

    print(f"--- {SAMPLE_TABLE} validation ---")

    if missing:
        print(
            "ERROR: required columns missing: "
            + ", ".join(sorted(missing))
        )
        return

    print("Required columns found: YES")
    print(f"Timestamp column: {TS_COL}")
    print(f"Presence column:  {PRESENCE_COL}")
    print(f"Movement column:  {MOVEMENT_COL}")

    if NIGHT_COL:
        print(f"Night column:     {NIGHT_COL}")

    print("\nFirst 3 radar samples:")

    fields = [
        TS_COL,
        PRESENCE_COL,
        MOVEMENT_COL,
    ]

    if NIGHT_COL and NIGHT_COL in cols:
        fields.append(NIGHT_COL)

    rows = conn.execute(
        f"""
        SELECT {', '.join(fields)}
        FROM {SAMPLE_TABLE}
        ORDER BY {TS_COL}
        LIMIT 3
        """
    ).fetchall()

    for row in rows:
        print(" ", row)

    if NIGHT_COL and NIGHT_COL in cols:
        night_expr = NIGHT_COL
    else:
        night_expr = f"date({TS_COL})"

    counts = conn.execute(
        f"""
        SELECT {night_expr} AS night_key,
               COUNT(*)
        FROM {SAMPLE_TABLE}
        GROUP BY night_key
        ORDER BY night_key
        """
    ).fetchall()

    print("\nSamples per night:")

    for night, count in counts:
        print(f"  {night}: {count}")

    timestamps = conn.execute(
        f"""
        SELECT {TS_COL}
        FROM {SAMPLE_TABLE}
        ORDER BY {TS_COL}
        LIMIT 20
        """
    ).fetchall()

    parsed = [
        parse_ts(row[0])
        for row in timestamps
    ]

    parsed = [
        t
        for t in parsed
        if t is not None
    ]

    if len(parsed) >= 2:
        gaps = [
            (parsed[i] - parsed[i - 1]).total_seconds()
            for i in range(1, len(parsed))
        ]

        typical_gap = min(gaps)

        print(
            f"\nObserved sample interval: {typical_gap:.0f} seconds"
        )

        if abs(typical_gap - SAMPLE_SECS) <= 1:
            print(
                f"Matches configured SAMPLE_SECS ({SAMPLE_SECS}s): YES"
            )
        else:
            print(
                f"WARNING: configured SAMPLE_SECS is {SAMPLE_SECS}s."
            )

    if "sleep_log" in tables and NIGHT_COL in cols:

        unmatched = conn.execute(
            f"""
            SELECT DISTINCT r.{NIGHT_COL}
            FROM {SAMPLE_TABLE} r
            LEFT JOIN sleep_log s
                ON s.date = r.{NIGHT_COL}
            WHERE s.date IS NULL
            ORDER BY r.{NIGHT_COL}
            """
        ).fetchall()

        sleep_rows = conn.execute(
            "SELECT COUNT(*) FROM sleep_log"
        ).fetchone()[0]

        radar_nights = conn.execute(
            f"""
            SELECT COUNT(DISTINCT {NIGHT_COL})
            FROM {SAMPLE_TABLE}
            """
        ).fetchone()[0]

        print("\nDatabase alignment:")
        print(f"  sleep_log rows: {sleep_rows}")
        print(f"  radar nights:   {radar_nights}")

        if unmatched:
            print(
                "  WARNING: radar nights without matching sleep_log dates:"
            )

            for row in unmatched:
                print(f"    {row[0]}")
        else:
            print(
                "  All radar nights match sleep_log dates: YES"
            )

    print("\nInspection complete.")


def load_samples(conn):
    """
    Load radar samples.

    Returns:
        samples:
            list of
            (datetime, presence, movement, night)

        use_night:
            True if radar_sample has an explicit night column
    """

    cols = [
        row[1]
        for row in conn.execute(
            f"PRAGMA table_info({SAMPLE_TABLE})"
        ).fetchall()
    ]

    use_night = (
        bool(NIGHT_COL)
        and NIGHT_COL in cols
    )

    fields = (
        f"{TS_COL}, "
        f"{PRESENCE_COL}, "
        f"{MOVEMENT_COL}"
    )

    if use_night:
        fields += f", {NIGHT_COL}"

    query = (
        f"SELECT {fields} "
        f"FROM {SAMPLE_TABLE} "
        f"ORDER BY {TS_COL} ASC"
    )

    output = []

    for row in conn.execute(query).fetchall():

        t = parse_ts(row[0])

        if t is None:
            continue

        night = (
            row[3]
            if use_night
            else None
        )

        output.append(
            (
                t,
                int(row[1] or 0),
                int(row[2] or 0),
                night,
            )
        )

    return output, use_night


def night_key(t):
    """
    Convert a timestamp into its sleep-night date.

    20:00 onward:
        same date

    before 12:00:
        previous date

    12:00-19:59:
        outside sleep window
    """

    if t.hour >= NIGHT_START_HOUR:
        return t.date().isoformat()

    if t.hour < NIGHT_END_HOUR:
        return (
            t - timedelta(days=1)
        ).date().isoformat()

    return None


def metrics_for_night(samples):
    """
    Calculate nightly metrics.

    samples must be sorted:
        (timestamp, presence, movement)
    """

    in_bed = [
        sample
        for sample in samples
        if sample[1] == 1
    ]

    if len(in_bed) < 2:
        return None

    tib_min = (
        len(in_bed)
        * SAMPLE_SECS
        / 60
    )

    if tib_min < MIN_TIB_MIN:
        return None

    # ---------------------------------------------------------
    # Sleep onset
    # First continuous period of stillness lasting 10 minutes
    # ---------------------------------------------------------

    needed_samples = int(
        ONSET_STILL_MIN
        * 60
        / SAMPLE_SECS
    )

    onset_i = None
    run = 0

    for i, sample in enumerate(in_bed):

        if sample[2] == 0:
            run += 1
        else:
            run = 0

        if run >= needed_samples:
            onset_i = i - needed_samples + 1
            break

    if onset_i is None:
        return None

    # ---------------------------------------------------------
    # Final waking
    # Last movement sample while presence is still detected
    # ---------------------------------------------------------

    final_i = max(
        (
            i
            for i, sample in enumerate(in_bed)
            if sample[2] == 1
        ),
        default=len(in_bed) - 1,
    )

    if final_i <= onset_i:
        final_i = len(in_bed) - 1

    span = in_bed[
        onset_i:final_i + 1
    ]

    # ---------------------------------------------------------
    # WASO
    # Movement-flagged time after sleep onset
    # ---------------------------------------------------------

    waso_min = (
        sum(
            1
            for sample in span
            if sample[2] == 1
        )
        * SAMPLE_SECS
        / 60
    )

    span_min = (
        len(span)
        * SAMPLE_SECS
        / 60
    )

    # ---------------------------------------------------------
    # Sleep duration
    # ---------------------------------------------------------

    duration_min = max(
        span_min - waso_min,
        0
    )

    # ---------------------------------------------------------
    # Sleep efficiency
    # ---------------------------------------------------------

    efficiency = (
        duration_min
        / tib_min
        * 100
        if tib_min
        else 0
    )

    # ---------------------------------------------------------
    # Movement percentage
    # ---------------------------------------------------------

    movement_pct = (
        sum(
            1
            for sample in in_bed
            if sample[2] == 1
        )
        / len(in_bed)
        * 100
    )

    # ---------------------------------------------------------
    # Coverage check
    # ---------------------------------------------------------

    elapsed_min = (
        (
            in_bed[-1][0]
            - in_bed[0][0]
        ).total_seconds()
        / 60
    )

    coverage = (
        tib_min / elapsed_min
        if elapsed_min > 0
        else 1.0
    )

    return {
        "time_in_bed_min":
            round(tib_min, 1),

        "sleep_duration_min":
            round(duration_min, 1),

        "sleep_efficiency":
            round(efficiency, 1),

        "waso_min":
            round(waso_min, 1),

        "movement_pct":
            round(movement_pct, 1),

        "_coverage":
            coverage,
    }


def main():

    conn = sqlite3.connect(DB_PATH)

    if "--inspect" in sys.argv:
        inspect(conn)
        conn.close()
        return

    dry_run = (
        "--dry-run"
        in sys.argv
    )

    # ---------------------------------------------------------
    # Verify required tables exist
    # ---------------------------------------------------------

    tables = {
        row[0]
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            """
        ).fetchall()
    }

    if "sleep_log" not in tables:
        print(
            "ERROR: sleep_log table not found."
        )
        conn.close()
        return

    if SAMPLE_TABLE not in tables:
        print(
            f"ERROR: {SAMPLE_TABLE} table not found."
        )
        conn.close()
        return

    # ---------------------------------------------------------
    # Add output columns if missing
    # ---------------------------------------------------------

    existing = [
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(sleep_log)"
        ).fetchall()
    ]

    required_columns = [
        ("sleep_duration_min", "REAL"),
        ("sleep_efficiency", "REAL"),
        ("waso_min", "REAL"),
        ("time_in_bed_min", "REAL"),
        ("movement_pct", "REAL"),
    ]

    for col, col_type in required_columns:

        if col not in existing:

            conn.execute(
                f"""
                ALTER TABLE sleep_log
                ADD COLUMN {col} {col_type}
                """
            )

            print(
                f"Added column: {col}"
            )

    conn.commit()

    # ---------------------------------------------------------
    # Load radar data
    # ---------------------------------------------------------

    try:
        samples, use_night = load_samples(
            conn
        )

    except sqlite3.OperationalError as e:

        print(
            f"Could not read radar samples: {e}"
        )

        conn.close()
        return

    if not samples:

        print(
            "No radar samples found."
        )

        conn.close()
        return

    print(
        f"Loaded {len(samples)} samples."
    )

    print(
        "Night key source: "
        + (
            NIGHT_COL
            if use_night
            else "timestamps"
        )
    )

    print()

    # ---------------------------------------------------------
    # Group by night
    # ---------------------------------------------------------

    nights = {}

    for t, presence, movement, night in samples:

        key = (
            night
            if use_night
            else night_key(t)
        )

        if key:
            nights.setdefault(
                str(key),
                []
            ).append(
                (
                    t,
                    presence,
                    movement,
                )
            )

    # ---------------------------------------------------------
    # Calculate metrics
    # ---------------------------------------------------------

    results = {}
    sparse = []

    for date, rows in sorted(
        nights.items()
    ):

        metrics = metrics_for_night(
            rows
        )

        if metrics:

            if (
                metrics["_coverage"]
                < GAP_WARN_RATIO
            ):
                sparse.append(date)

            results[date] = metrics

    # ---------------------------------------------------------
    # Print nightly results
    # ---------------------------------------------------------

    for date, metrics in results.items():

        flag = (
            " <- sparse"
            if metrics["_coverage"]
            < GAP_WARN_RATIO
            else ""
        )

        print(
            f"{date}  "
            f"TIB {metrics['time_in_bed_min']:>6.1f}m  "
            f"sleep {metrics['sleep_duration_min']:>6.1f}m  "
            f"WASO {metrics['waso_min']:>5.1f}m  "
            f"eff {metrics['sleep_efficiency']:>5.1f}%  "
            f"move {metrics['movement_pct']:>4.1f}%"
            f"{flag}"
        )

    print()

    print(
        f"{len(results)} nights scored "
        f"from {len(nights)} candidate nights."
    )

    if sparse:

        print(
            f"WARNING: {len(sparse)} "
            "night(s) had low radar coverage."
        )

    # ---------------------------------------------------------
    # Stop before writing if dry-run
    # ---------------------------------------------------------

    if dry_run:

        print(
            "\nDry run — nothing written."
        )

        conn.close()
        return

    # ---------------------------------------------------------
    # Write calculated values to sleep_log
    # ---------------------------------------------------------

    written = 0
    unmatched = []

    for date, metrics in results.items():

        cursor = conn.execute(
            """
            UPDATE sleep_log
            SET
                sleep_duration_min = ?,
                sleep_efficiency = ?,
                waso_min = ?,
                time_in_bed_min = ?,
                movement_pct = ?
            WHERE date = ?
            """,
            (
                metrics[
                    "sleep_duration_min"
                ],
                metrics[
                    "sleep_efficiency"
                ],
                metrics[
                    "waso_min"
                ],
                metrics[
                    "time_in_bed_min"
                ],
                metrics[
                    "movement_pct"
                ],
                date,
            ),
        )

        if cursor.rowcount:
            written += cursor.rowcount
        else:
            unmatched.append(date)

    conn.commit()
    conn.close()

    print(
        f"\nUpdated {written} rows "
        "in sleep_log."
    )

    if unmatched:

        print(
            "Radar nights without a matching "
            "sleep_log date:"
        )

        for date in unmatched:
            print(
                f"  {date}"
            )


if __name__ == "__main__":
    main()
