"""Draw four charts from the tables made by 02_build_tables.py.

Run from the project folder:
    python src/03_make_charts.py
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # DRAW TO FILES, NO WINDOW NEEDED
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

# SETTINGS
PROJECT_DIR = Path(__file__).resolve().parent.parent
TABLES_DIR = PROJECT_DIR / "results" / "tables"
CHARTS_DIR = PROJECT_DIR / "results" / "charts"
BLUE = "#2a78d6"
LIGHT_BLUE = "#a9c8ee"
ORANGE = "#eb6834"
GREY = "#8a8985"
TEXT = "#52514e"
IMPLANT_NAME = "Implant, Endosseous, Root-Form"
FIRST_YEAR = 2000
NEEDED_TABLES = ["reports_per_year", "device_types", "event_types", "product_problems"]


def thousands(value, position):
    """Axis label formatter: 250000 becomes 250,000."""
    return f"{value:,.0f}"


def style_axes(ax, grid_axis="y"):
    """Light, quiet axes so the data stands out."""
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(GREY)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=TEXT)
    ax.grid(axis=grid_axis, color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)


def shorten(label, max_length=45):
    """Cut very long device names so the chart stays readable."""
    return label if len(label) <= max_length else label[: max_length - 3] + "..."


def horizontal_bar_chart(labels, values, title, xlabel, path, log_scale=False, subtitle=None):
    """Horizontal bars, first item at the top, with the count printed on each bar."""
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(labels) + 1.9))
    positions = list(range(len(labels)))[::-1]
    bars = ax.barh(positions, values, color=BLUE, height=0.65)
    ax.set_yticks(positions)
    ax.set_yticklabels([shorten(label) for label in labels])
    ax.bar_label(bars, labels=[f"{v:,}" for v in values], padding=3, color=TEXT, fontsize=9)
    style_axes(ax, grid_axis="x")
    if log_scale:
        ax.set_xscale("log")
        ax.set_xlim(1, max(values) * 20)
        ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    else:
        ax.set_xlim(0, max(values) * 1.2)
        ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontsize=13)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=TEXT)
        ax.set_title(title, loc="left", fontsize=13, pad=22)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def chart_device_types(df, path):
    """Top 10 device types, leaving out root-form implants (named in the subtitle)."""
    implant_row = df[df["device_type"] == IMPLANT_NAME]
    others = df[df["device_type"] != IMPLANT_NAME].head(10)
    subtitle = None
    if not implant_row.empty:
        subtitle = (f"Not shown: {IMPLANT_NAME} with {int(implant_row['reports'].iloc[0]):,} reports "
                    f"({implant_row['pct_of_dental_reports'].iloc[0]}% of all dental reports)")
    horizontal_bar_chart(
        others["device_type"].tolist(), others["reports"].tolist(),
        "Top dental device types, excluding root-form implants",
        "Reports", path, subtitle=subtitle,
    )


def chart_reports_per_year(df, path):
    """Two stacked panels: all dental reports, and reports without root-form implants."""
    df = df[df["year"] >= FIRST_YEAR]
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)

    for ax, column, title in [
        (top, "reports", "All dental device reports"),
        (bottom, "reports_without_implants", "Dental device reports excluding root-form implants"),
    ]:
        colors = [LIGHT_BLUE if partial else BLUE for partial in df["is_partial_year"]]
        ax.bar(df["year"], df[column], color=colors, width=0.75)
        style_axes(ax)
        ax.yaxis.set_major_formatter(FuncFormatter(thousands))
        ax.set_ylabel("Reports")
        ax.set_title(title, loc="left", fontsize=12)

    # MARK 2019, WHEN FDA ENDED ITS SUMMARY REPORTING PROGRAM
    if 2019 in df["year"].values:
        top.axvline(2018.5, color=ORANGE, linewidth=1.5, linestyle="--")
        top.text(2018.3, top.get_ylim()[1] * 0.9, "2019: FDA ends summary\nreporting exemptions",
                 ha="right", va="top", fontsize=9, color=TEXT)

    bottom.set_xlabel("Year FDA received the report (lighter bar = partial year)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    missing = [name for name in NEEDED_TABLES if not (TABLES_DIR / f"{name}.csv").exists()]
    if missing:
        print(f"ERROR: missing result tables: {', '.join(missing)}")
        print("Fix: run  python src/02_build_tables.py  first.")
        sys.exit(1)

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    tables = {name: pd.read_csv(TABLES_DIR / f"{name}.csv", keep_default_na=False) for name in NEEDED_TABLES}

    # 1 DEVICE TYPES
    chart_device_types(tables["device_types"], CHARTS_DIR / "01_top_device_types.png")

    # 2 EVENT TYPES (LOG SCALE BECAUSE INJURY IS ABOUT 18,000 TIMES DEATH)
    events = tables["event_types"]
    horizontal_bar_chart(
        events["event_type"].tolist(), events["reports"].tolist(),
        "Dental device reports by event type", "Reports (log scale: each gridline is 10 times the last)",
        CHARTS_DIR / "02_event_types.png", log_scale=True,
    )

    # 3 REPORTS PER YEAR
    chart_reports_per_year(tables["reports_per_year"], CHARTS_DIR / "03_reports_per_year.png")

    # 4 PRODUCT PROBLEMS
    problems = tables["product_problems"].head(10)
    horizontal_bar_chart(
        problems["product_problem"].tolist(), problems["reports"].tolist(),
        "Most reported device problems", "Reports (a report can list more than one problem)",
        CHARTS_DIR / "04_top_product_problems.png",
    )

    for path in sorted(CHARTS_DIR.glob("*.png")):
        print(f"Saved {path.relative_to(PROJECT_DIR)}")


if __name__ == "__main__":
    main()
