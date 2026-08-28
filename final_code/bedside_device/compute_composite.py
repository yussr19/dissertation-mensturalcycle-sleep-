#!/usr/bin/env python3

"""
compute_composite.py

Derives an equal-weight DEVICE-ONLY composite sleep index from
nightly measures stored in sleep_log.

The composite uses:
    - heart_rate
    - hrv
    - movement_pct
    - sleep_duration_min
    - sleep_efficiency

Subjective measures are deliberately excluded:
    - sleep_quality
    - energy

Each contributing measure is:
  1. z-scored across the full record
  2. reversed if high values mean worse sleep
  3. equally averaged
  4. rescaled to 1-10

This keeps the composite independent from the subjective app
and diary data so that device-derived and subjective measures
can be compared in the Results.

Usage:
    python3 compute_composite.py --dry-run
    python3 compute_composite.py
"""

import sqlite3
import sys
import statistics


DB_PATH = "/home/yussr19/analysis/finalsleep_.db"


# --------------------------------------------------
# DEVICE-ONLY CONTRIBUTORS
# --------------------------------------------------

CONTRIBUTORS = [

    (
        "heart_rate",
        False
    ),

    (
        "hrv",
        True
    ),

    (
        "movement_pct",
        False
    ),

    (
        "sleep_duration_min",
        True
    ),

    (
        "sleep_efficiency",
        True
    ),

]


# Subjective sleep quality is NOT included.
INCLUDE_SELF_REPORT = False

# A night may be missing at most one usable
# contributor before being excluded.
MAX_MISSING = 1


def existing_columns(conn):
    """Return sleep_log column names."""

    return {
        r[1]
        for r in conn.execute(
            "PRAGMA table_info(sleep_log)"
        ).fetchall()
    }


def fetch_rows(conn, contributors):
    """Load nightly rows."""

    cols = [
        "id",
        "date",
        "cycle_day",
        "sleep_quality",
        "energy",
    ] + [
        c
        for c, _
        in contributors
    ]

    # Remove duplicates while preserving order.
    cols = list(
        dict.fromkeys(cols)
    )

    q = (
        f"SELECT "
        f"{', '.join(cols)} "
        f"FROM sleep_log "
        f"ORDER BY id ASC"
    )

    return [
        dict(
            zip(cols, r)
        )
        for r
        in conn.execute(q).fetchall()
    ]


def zscores(values):
    """
    Return a function mapping a raw value
    to its z-score.

    Returns None if there are fewer than
    two usable values or no variation.
    """

    clean = [
        v
        for v in values
        if v is not None
    ]

    if len(clean) < 2:
        return None

    mean = statistics.mean(clean)
    sd = statistics.pstdev(clean)

    if sd == 0:
        return None

    return lambda v: (
        v - mean
    ) / sd


def main():

    dry = (
        "--dry-run"
        in sys.argv
    )

    conn = sqlite3.connect(
        DB_PATH
    )

    # --------------------------------------------------
    # Check sleep_log exists
    # --------------------------------------------------

    tables = {
        r[0]
        for r in conn.execute(
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

    present = existing_columns(
        conn
    )

    # --------------------------------------------------
    # Adaptive contributors
    # --------------------------------------------------

    contributors = []

    for col, higher_better in CONTRIBUTORS:

        if col in present:

            contributors.append(
                (
                    col,
                    higher_better
                )
            )

        else:

            print(
                f"(column '{col}' "
                "not in sleep_log - skipped)"
            )

    if (
        INCLUDE_SELF_REPORT
        and
        "sleep_quality" in present
    ):

        contributors.append(
            (
                "sleep_quality",
                True
            )
        )

    if not contributors:

        print(
            "No contributing columns found."
        )

        conn.close()
        return

    # --------------------------------------------------
    # Ensure composite column exists
    # --------------------------------------------------

    if (
        "composite_quality"
        not in present
    ):

        conn.execute(
            """
            ALTER TABLE sleep_log
            ADD COLUMN composite_quality REAL
            """
        )

        conn.commit()

        print(
            "Added column: composite_quality"
        )

    # --------------------------------------------------
    # Load nights
    # --------------------------------------------------

    rows = fetch_rows(
        conn,
        contributors
    )

    if not rows:

        print(
            "No rows in sleep_log."
        )

        conn.close()
        return

    # --------------------------------------------------
    # Build z-score scalers
    # --------------------------------------------------

    scalers = {}

    for col, _ in contributors:

        f = zscores(
            [
                r.get(col)
                for r in rows
            ]
        )

        if f is None:

            print(
                f"(skipping '{col}': "
                "fewer than two values "
                "or no variation)"
            )

        else:

            scalers[col] = f

    if not scalers:

        print(
            "No usable measures."
        )

        conn.close()
        return

    # --------------------------------------------------
    # Mean z-score per night
    # --------------------------------------------------

    raw = {}

    for r in rows:

        zs = []
        missing = 0

        for (
            col,
            higher_better
        ) in contributors:

            if col not in scalers:
                continue

            v = r.get(col)

            if v is None:
                missing += 1
                continue

            z = scalers[col](v)

            if higher_better:
                zs.append(z)
            else:
                zs.append(-z)

        if (
            not zs
            or
            missing > MAX_MISSING
        ):
            continue

        raw[r["id"]] = (
            sum(zs)
            / len(zs)
        )

    if not raw:

        print(
            "\nNo nights met "
            "the completeness rule."
        )

        conn.close()
        return

    # --------------------------------------------------
    # Rescale mean z-score to 1-10
    # --------------------------------------------------

    lo = min(
        raw.values()
    )

    hi = max(
        raw.values()
    )

    span = (
        hi - lo
    ) or 1.0

    scaled = {

        i:
        1
        + 9
        * (
            (v - lo)
            / span
        )

        for i, v
        in raw.items()
    }

    # --------------------------------------------------
    # Print nightly values
    # --------------------------------------------------

    print()

    print(
        "DEVICE-ONLY COMPOSITE"
    )

    print(
        "---------------------"
    )

    for r in rows:

        val = scaled.get(
            r["id"]
        )

        shown = (
            f"{val:.2f}"
            if val is not None
            else "-"
        )

        print(
            f"{r['date']}  "
            f"cycle_day "
            f"{str(r['cycle_day'] or '-'):>3}  "
            f"self "
            f"{str(r['sleep_quality'] or '-'):>3}  "
            f"energy "
            f"{str(r['energy'] or '-'):>3}  "
            f"device_composite "
            f"{shown:>6}"
        )

    print()

    print(
        f"{len(scaled)} "
        f"of {len(rows)} "
        "nights scored."
    )

    print(
        f"{len(rows) - len(scaled)} "
        "nights skipped."
    )

    print(
        f"Device measures used "
        f"({len(scalers)}): "
        f"{', '.join(scalers.keys())}"
    )

    print(
        "Subjective measures excluded: "
        "sleep_quality, energy"
    )

    # --------------------------------------------------
    # Dry run
    # --------------------------------------------------

    if dry:

        print(
            "\nDry run - nothing written."
        )

        conn.close()
        return

    # --------------------------------------------------
    # Clear old composite values first
    #
    # Important because nights excluded by the new
    # calculation should remain NULL rather than retain
    # an older composite value.
    # --------------------------------------------------

    conn.execute(
        """
        UPDATE sleep_log
        SET composite_quality = NULL
        """
    )

    # --------------------------------------------------
    # Write new device-only composite
    # --------------------------------------------------

    for i, v in scaled.items():

        conn.execute(
            """
            UPDATE sleep_log
            SET composite_quality = ?
            WHERE id = ?
            """,
            (
                round(v, 2),
                i,
            ),
        )

    conn.commit()
    conn.close()

    print(
        "\nWritten to "
        "sleep_log.composite_quality"
    )

    print(
        "Composite is now DEVICE-ONLY."
    )


if __name__ == "__main__":
    main()
