#!/usr/bin/env python3

import sqlite3
import statistics
import math

DB = "/home/yussr19/analysis/finalsleep_.db"


def pearson_r(xs, ys):
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return None

    mx = statistics.mean(xs)
    my = statistics.mean(ys)

    num = sum(
        (x - mx) * (y - my)
        for x, y in zip(xs, ys)
    )

    den = math.sqrt(
        sum((x - mx) ** 2 for x in xs)
        *
        sum((y - my) ** 2 for y in ys)
    )

    if den == 0:
        return None

    return num / den


def describe(rows, column):
    vals = [
        row[column]
        for row in rows
        if row[column] is not None
    ]

    if not vals:
        return None

    return {
        "n": len(vals),
        "mean": statistics.mean(vals),
        "sd": statistics.stdev(vals) if len(vals) > 1 else 0,
        "min": min(vals),
        "max": max(vals),
    }


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
        SELECT
            date,
            cycle_day,
            sleep_quality,
            energy,
            heart_rate,
            hrv,
            sleep_duration_min,
            sleep_efficiency,
            waso_min,
            movement_pct,
            composite_quality
        FROM sleep_log
        ORDER BY date
    """).fetchall()

    print("\n=== RECORD ===")
    print("N nights:", len(rows))

    if rows:
        print(
            "Dates:",
            rows[0]["date"],
            "to",
            rows[-1]["date"]
        )

    measures = [
        "sleep_quality",
        "energy",
        "heart_rate",
        "hrv",
        "sleep_duration_min",
        "sleep_efficiency",
        "waso_min",
        "movement_pct",
        "composite_quality",
    ]

    print("\n=== OVERALL DESCRIPTIVES ===")

    for column in measures:
        d = describe(rows, column)

        if d is None:
            print(f"{column:22s} no data")
            continue

        print(
            f"{column:22s} "
            f"N={d['n']:2d}  "
            f"mean={d['mean']:7.2f}  "
            f"SD={d['sd']:7.2f}  "
            f"min={d['min']:7.2f}  "
            f"max={d['max']:7.2f}"
        )

    # --------------------------------------------------
    # Self-report vs composite
    # --------------------------------------------------

    paired = [
        (
            row["sleep_quality"],
            row["composite_quality"]
        )
        for row in rows
        if row["sleep_quality"] is not None
        and row["composite_quality"] is not None
    ]

    x = [a for a, b in paired]
    y = [b for a, b in paired]

    print("\n=== SELF-REPORT vs COMPOSITE ===")

    print("Paired nights:", len(paired))

    if paired:
        r = pearson_r(x, y)

        print(
            "Pearson r:",
            round(r, 3) if r is not None else "NA"
        )

        print(
            "Mean self-report:",
            round(statistics.mean(x), 2)
        )

        print(
            "Mean composite:",
            round(statistics.mean(y), 2)
        )

        diffs = [
            a - b
            for a, b in paired
        ]

        print(
            "Mean absolute difference:",
            round(
                statistics.mean(
                    abs(d)
                    for d in diffs
                ),
                2
            )
        )

        for threshold in (1, 2, 3):
            n = sum(
                abs(d) >= threshold
                for d in diffs
            )

            print(
                f"|difference| >= {threshold}: {n}"
            )

        print(
            "Self-report higher by >=2:",
            sum(
                d >= 2
                for d in diffs
            )
        )

        print(
            "Composite higher by >=2:",
            sum(
                d <= -2
                for d in diffs
            )
        )

    # --------------------------------------------------
    # Missing composite nights
    # --------------------------------------------------

    print("\n=== MISSING COMPOSITES ===")

    missing = [
        row
        for row in rows
        if row["composite_quality"] is None
    ]

    if not missing:
        print("None")
    else:
        for row in missing:
            print(
                row["date"],
                "cycle_day", row["cycle_day"],
                "HR", row["heart_rate"],
                "HRV", row["hrv"]
            )

    # --------------------------------------------------
    # Phase comparison
    #
    # Follicular = cycle days 1-14
    # Luteal     = cycle days 15-28
    # --------------------------------------------------

    print("\n=== PHASE COMPARISON ===")
    print("Definition: follicular = days 1-14; luteal = days 15-28")

    phase_measures = [
        "sleep_quality",
        "energy",
        "heart_rate",
        "hrv",
        "sleep_duration_min",
        "sleep_efficiency",
        "waso_min",
        "movement_pct",
        "composite_quality",
    ]

    follicular_rows = [
        row
        for row in rows
        if row["cycle_day"] is not None
        and 1 <= row["cycle_day"] <= 14
    ]

    luteal_rows = [
        row
        for row in rows
        if row["cycle_day"] is not None
        and 15 <= row["cycle_day"] <= 28
    ]

    for column in phase_measures:
        fvals = [
            row[column]
            for row in follicular_rows
            if row[column] is not None
        ]

        lvals = [
            row[column]
            for row in luteal_rows
            if row[column] is not None
        ]

        if not fvals or not lvals:
            print(
                f"{column:22s} insufficient data"
            )
            continue

        fmean = statistics.mean(fvals)
        lmean = statistics.mean(lvals)
        diff = lmean - fmean

        print(
            f"{column:22s} "
            f"follicular N={len(fvals):2d} mean={fmean:7.2f}  "
            f"luteal N={len(lvals):2d} mean={lmean:7.2f}  "
            f"diff(L-F)={diff:+7.2f}"
        )

    con.close()


if __name__ == "__main__":
    main()
