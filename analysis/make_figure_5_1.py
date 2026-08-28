#!/usr/bin/env python3

"""
make_figure_5_1.py

Generates Figure 5.1 for the dissertation.

Circular 28-day plot comparing:
    - self-reported sleep quality
    - device-derived composite sleep score

The device composite contains:
    - heart rate
    - HRV
    - movement
    - sleep duration
    - sleep efficiency

Sleep quality and energy are NOT included in the device composite.

Cycle windows:
    Menses = days 1-5
    Late luteal = days 24-28

Where more than one observation exists for a cycle day,
the mean value is plotted.

Usage:
    python3 /home/yussr19/make_figure_5_1.py --inspect
    python3 /home/yussr19/make_figure_5_1.py
"""

import argparse
import sqlite3
import sys
import os


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "/home/yussr19/analysis/finalsleep_.db"

TABLE = "sleep_log"

COL_CYCLE_DAY = "cycle_day"
COL_SERIES_A = "sleep_quality"
COL_SERIES_B = "composite_quality"

LABEL_A = "Self-reported sleep quality"
LABEL_B = "Device-derived composite"

CYCLE_LENGTH = 28

MENSES = (1, 5)
LATE_LUTEAL = (24, 28)

OUT_PATH = "/home/yussr19/analysis/figure_5_1.png"

DPI = 300

COLOR_A = "#2a78d6"
COLOR_B = "#eb6834"

COLOR_MENSES = "#d9d5cc"
COLOR_LATE_LUTEAL = "#eee6dc"


# ============================================================
# INSPECT DATABASE
# ============================================================

def inspect(conn):

    cur = conn.cursor()

    print("\nDatabase:")
    print(DB_PATH)

    print("\nTables:")

    for (name,) in cur.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        ORDER BY name
        """
    ):
        print("  -", name)

    print(f"\nColumns in '{TABLE}':")

    cols = cur.execute(
        f"PRAGMA table_info({TABLE})"
    ).fetchall()

    if not cols:

        print(
            f"ERROR: table '{TABLE}' not found."
        )

        return

    names = []

    for c in cols:

        names.append(c[1])

        print(
            f"  - {c[1]} ({c[2]})"
        )

    print("\nRequired-column check:")

    checks = [
        ("Cycle day", COL_CYCLE_DAY),
        (
            "Self-reported sleep quality",
            COL_SERIES_A
        ),
        (
            "Device composite",
            COL_SERIES_B
        ),
    ]

    for label, col in checks:

        status = (
            "OK"
            if col in names
            else "MISSING"
        )

        print(
            f"  [{status}] "
            f"{label}: {col}"
        )

    n = cur.execute(
        f"SELECT COUNT(*) FROM {TABLE}"
    ).fetchone()[0]

    print(
        f"\nTotal sleep_log rows: {n}"
    )

    if COL_CYCLE_DAY in names:

        rows = cur.execute(
            f"""
            SELECT
                {COL_CYCLE_DAY},
                COUNT(*),
                COUNT({COL_SERIES_B})
            FROM {TABLE}
            WHERE {COL_CYCLE_DAY}
                  BETWEEN 1 AND {CYCLE_LENGTH}
            GROUP BY {COL_CYCLE_DAY}
            ORDER BY {COL_CYCLE_DAY}
            """
        ).fetchall()

        print(
            "\nObservations by cycle day:"
        )

        for day, total_n, composite_n in rows:

            print(
                f"  Day {day:2d}: "
                f"{total_n} total, "
                f"{composite_n} composite"
            )

        covered = {
            d
            for d, _, _
            in rows
        }

        missing = [
            d
            for d
            in range(
                1,
                CYCLE_LENGTH + 1
            )
            if d not in covered
        ]

        if missing:

            print(
                "\nCycle days with no data:",
                missing
            )

        else:

            print(
                "\nAll 28 cycle days "
                "have at least one observation."
            )

    print()


# ============================================================
# FETCH CYCLE-DAY MEANS
# ============================================================

def fetch(conn):

    import numpy as np

    cur = conn.cursor()

    sleep_quality = np.full(
        CYCLE_LENGTH,
        np.nan
    )

    device_composite = np.full(
        CYCLE_LENGTH,
        np.nan
    )

    counts = np.zeros(
        CYCLE_LENGTH,
        dtype=int
    )

    composite_counts = np.zeros(
        CYCLE_LENGTH,
        dtype=int
    )

    query = f"""
        SELECT
            {COL_CYCLE_DAY},
            AVG({COL_SERIES_A}),
            AVG({COL_SERIES_B}),
            COUNT(*),
            COUNT({COL_SERIES_B})
        FROM {TABLE}
        WHERE
            {COL_CYCLE_DAY}
            BETWEEN 1 AND {CYCLE_LENGTH}
        GROUP BY
            {COL_CYCLE_DAY}
        ORDER BY
            {COL_CYCLE_DAY}
    """

    for (
        day,
        mean_quality,
        mean_composite,
        n,
        composite_n
    ) in cur.execute(query):

        i = int(day) - 1

        if mean_quality is not None:

            sleep_quality[i] = (
                mean_quality
            )

        if mean_composite is not None:

            device_composite[i] = (
                mean_composite
            )

        counts[i] = n

        composite_counts[i] = (
            composite_n
        )

    return (
        sleep_quality,
        device_composite,
        counts,
        composite_counts,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--inspect",
        action="store_true",
        help=(
            "Inspect database schema "
            "and cycle-day coverage"
        ),
    )

    parser.add_argument(
        "--db",
        default=DB_PATH,
        help="Path to SQLite database",
    )

    args = parser.parse_args()

    db_path = os.path.expanduser(
        args.db
    )

    if not os.path.exists(db_path):

        sys.exit(
            f"Database not found: "
            f"{db_path}"
        )

    conn = sqlite3.connect(
        db_path
    )

    if args.inspect:

        inspect(conn)

        conn.close()

        return

    # --------------------------------------------------------
    # IMPORT PLOTTING LIBRARIES
    # --------------------------------------------------------

    try:

        import numpy as np

        import matplotlib

        matplotlib.use("Agg")

        import matplotlib.pyplot as plt

    except ImportError:

        conn.close()

        sys.exit(
            "\nMissing matplotlib or numpy.\n"
            "Install with:\n\n"
            "python3 -m pip install "
            "matplotlib numpy\n"
        )

    (
        sleep_quality,
        device_composite,
        counts,
        composite_counts,
    ) = fetch(conn)

    conn.close()

    if np.all(
        np.isnan(sleep_quality)
    ):

        sys.exit(
            "No sleep-quality data found."
        )

    if np.all(
        np.isnan(device_composite)
    ):

        sys.exit(
            "No device-composite data found."
        )

    # ========================================================
    # ANGULAR POSITIONS
    # ========================================================

    step = (
        2 * np.pi
        / CYCLE_LENGTH
    )

    theta = (
        np.arange(CYCLE_LENGTH)
        * step
    )

    # Close the lines from day 28 back to day 1.

    theta_closed = np.append(
        theta,
        2 * np.pi
    )

    quality_closed = np.append(
        sleep_quality,
        sleep_quality[0]
    )

    composite_closed = np.append(
        device_composite,
        device_composite[0]
    )

    # ========================================================
    # CREATE FIGURE
    # ========================================================

    fig = plt.figure(
        figsize=(8, 8)
    )

    ax = fig.add_subplot(
        111,
        projection="polar"
    )

    # Day 1 starts at the top.

    ax.set_theta_zero_location(
        "N"
    )

    # Cycle moves clockwise.

    ax.set_theta_direction(
        -1
    )

    # Both series use a 1-10 scale.

    ax.set_ylim(
        0,
        10.5
    )

    # ========================================================
    # SHADED CYCLE WINDOWS
    # ========================================================

    def shade_days(
        start_day,
        end_day,
        color,
        label
    ):

        start_angle = (
            (start_day - 1)
            * step
            - step / 2
        )

        end_angle = (
            (end_day - 1)
            * step
            + step / 2
        )

        angles = np.linspace(
            start_angle,
            end_angle,
            100
        )

        ax.fill_between(
            angles,
            0,
            10.5,
            color=color,
            alpha=0.35,
            linewidth=0,
            label=label,
            zorder=0,
        )

    shade_days(
        MENSES[0],
        MENSES[1],
        COLOR_MENSES,
        "Menses (days 1-5)",
    )

    shade_days(
        LATE_LUTEAL[0],
        LATE_LUTEAL[1],
        COLOR_LATE_LUTEAL,
        "Late luteal (days 24-28)",
    )

    # ========================================================
    # PLOT SELF-REPORTED SLEEP QUALITY
    # ========================================================

    ax.plot(
        theta_closed,
        quality_closed,
        color=COLOR_A,
        linewidth=2.2,
        marker="o",
        markersize=4,
        label=LABEL_A,
        zorder=4,
    )

    # ========================================================
    # PLOT DEVICE COMPOSITE
    # ========================================================

    ax.plot(
        theta_closed,
        composite_closed,
        color=COLOR_B,
        linewidth=2.0,
        linestyle="--",
        marker="s",
        markersize=3.5,
        label=LABEL_B,
        zorder=3,
    )

    # ========================================================
    # CYCLE-DAY LABELS
    # ========================================================

    ax.set_xticks(
        theta
    )

    ax.set_xticklabels(
        [
            str(day)
            for day
            in range(
                1,
                CYCLE_LENGTH + 1
            )
        ],
        fontsize=8
    )

    # ========================================================
    # SCORE LABELS
    # ========================================================

    ax.set_yticks(
        [2, 4, 6, 8, 10]
    )

    ax.set_yticklabels(
        [
            "2",
            "4",
            "6",
            "8",
            "10"
        ],
        fontsize=8
    )

    # ========================================================
    # APPEARANCE
    # ========================================================

    ax.grid(
        linewidth=0.5,
        alpha=0.55
    )

    ax.spines[
        "polar"
    ].set_visible(False)

    # Updated title

    ax.set_title(
        (
            "Self-reported and device-derived "
            "sleep across cycle day"
        ),
        fontsize=13,
        pad=25,
    )

    # ========================================================
    # LEGEND
    # ========================================================

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(
            0.5,
            -0.08
        ),
        ncol=2,
        frameon=False,
        fontsize=8,
    )

    # ========================================================
    # SAVE FIGURE
    # ========================================================

    fig.tight_layout()

    fig.savefig(
        OUT_PATH,
        dpi=DPI,
        bbox_inches="tight",
        facecolor="white",
    )

    plt.close(fig)

    # ========================================================
    # TERMINAL SUMMARY
    # ========================================================

    print()

    print(
        "FIGURE 5.1 COMPLETE"
    )

    print(
        "-------------------"
    )

    print(
        f"Saved to:\n{OUT_PATH}"
    )

    print(
        f"\nResolution: {DPI} dpi"
    )

    print(
        "\nSeries:"
    )

    print(
        "  Solid = "
        "self-reported sleep quality"
    )

    print(
        "  Dashed = "
        "device-derived composite"
    )

    print(
        "\nShaded cycle windows:"
    )

    print(
        "  Days 1-5   = menses"
    )

    print(
        "  Days 24-28 = late luteal"
    )

    print(
        "\nObservations per cycle day:"
    )

    for i, n in enumerate(counts):

        print(
            f"  Day {i+1:2d}: "
            f"n={n}, "
            f"composite n="
            f"{composite_counts[i]}"
        )

    print()

    print(
        "NOTE:"
    )

    print(
        "Cycle days 1-22 occur "
        "across two recorded cycles."
    )

    print(
        "Cycle days 23-28 are represented "
        "only by the first complete cycle."
    )

    print()

    print(
        "The observation counts are reported "
        "here but are not displayed on the figure."
    )


if __name__ == "__main__":

    main()
