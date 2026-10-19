"""Turn the openFDA count downloads into tables and write results/summary.md.

Run from the project folder:
    python src/02_build_tables.py
"""

import json
import sys
from pathlib import Path

import pandas as pd

# SETTINGS
PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
TABLES_DIR = PROJECT_DIR / "results" / "tables"
SUMMARY_PATH = PROJECT_DIR / "results" / "summary.md"
RAW_FILES = ["total", "by_day", "by_day_without_implants", "device_types",
             "event_types", "product_problems", "regulation_numbers"]
TOP_N = 15


def load_raw(raw_dir, name):
    """Read one saved openFDA answer."""
    return json.loads((Path(raw_dir) / f"{name}.json").read_text(encoding="utf-8"))


def total_reports(payload):
    """Total number of matching reports, from the meta section."""
    return payload.get("meta", {}).get("results", {}).get("total", 0)


def daily_to_yearly(results):
    """openFDA gives one row per day ({'time': '20240115', 'count': 12}). Add them up by year."""
    if not results:
        return pd.DataFrame(columns=["year", "reports"])
    df = pd.DataFrame(results)
    df["year"] = df["time"].str[:4].astype(int)
    return df.groupby("year", as_index=False)["count"].sum().rename(columns={"count": "reports"})


def yearly_table(all_results, without_implant_results, last_year):
    """Reports per year: all dental, without root-form implants, and implants alone."""
    all_years = daily_to_yearly(all_results)
    others = daily_to_yearly(without_implant_results).rename(columns={"reports": "reports_without_implants"})
    table = all_years.merge(others, on="year", how="left").fillna({"reports_without_implants": 0})
    table["reports_without_implants"] = table["reports_without_implants"].astype(int)
    # A REPORT THAT MENTIONS A ROOT-FORM IMPLANT LANDS IN THE IMPLANT COLUMN
    table["implant_reports"] = table["reports"] - table["reports_without_implants"]
    table["is_partial_year"] = (table["year"] == last_year).astype(int)
    return table


def counts_table(results, label_column, total, top_n=None):
    """Turn [{'term': ..., 'count': ...}] into a table with a percent of all dental reports."""
    df = pd.DataFrame(results, columns=["term", "count"])
    df = df.rename(columns={"term": label_column, "count": "reports"})
    df[label_column] = df[label_column].replace("", "Not recorded")
    df = df.sort_values("reports", ascending=False).reset_index(drop=True)
    if top_n is not None:
        df = df.head(top_n)
    df["pct_of_dental_reports"] = (100 * df["reports"] / total).round(2) if total else 0.0
    return df


def regulation_check(results):
    """Check that the dental filter really picks dental devices.

    Dental devices are regulated under 21 CFR Part 872, so their regulation numbers start
    with "872.". Returns how many counted device rows fall inside and outside Part 872.
    """
    df = pd.DataFrame(results, columns=["term", "count"])
    in_872 = int(df.loc[df["term"].str.startswith("872."), "count"].sum())
    outside = int(df.loc[~df["term"].str.startswith("872."), "count"].sum())
    share = round(100 * in_872 / (in_872 + outside), 3) if (in_872 + outside) else 0.0
    return pd.DataFrame([{
        "device_rows_in_part_872": in_872,
        "device_rows_outside_part_872": outside,
        "pct_in_part_872": share,
    }])


def to_markdown_table(df):
    """Turn a DataFrame into a simple Markdown table (no extra packages needed)."""
    if df.empty:
        return "_No rows._"
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    divider = "| " + " | ".join("---" for _ in df.columns) + " |"
    rows = []
    # ASTYPE(OBJECT) KEEPS WHOLE NUMBERS LOOKING LIKE 8 INSTEAD OF 8.0
    for row in df.astype(object).values.tolist():
        cells = ["" if pd.isna(value) else str(value) for value in row]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, divider] + rows)


def key_findings(total, tables):
    """Plain-language sentences built from the tables."""
    lines = [f"openFDA holds {total:,} adverse event reports for devices classified as dental."]

    devices = tables["device_types"]
    if not devices.empty:
        lines.append(
            f"The most reported device type is \"{devices.at[0, 'device_type']}\" with "
            f"{devices.at[0, 'reports']:,} reports ({devices.at[0, 'pct_of_dental_reports']}% of dental reports)."
        )

    events = tables["event_types"].set_index("event_type")
    for event in ["Injury", "Malfunction", "Death"]:
        if event in events.index:
            lines.append(f"{event}: {events.at[event, 'reports']:,} reports ({events.at[event, 'pct_of_dental_reports']}%).")

    yearly = tables["reports_per_year"].set_index("year")
    for year in [2018, 2019]:
        if year in yearly.index:
            lines.append(
                f"{year}: {yearly.at[year, 'reports']:,} reports in total, "
                f"{yearly.at[year, 'reports_without_implants']:,} without root-form implants."
            )
    complete = tables["reports_per_year"][tables["reports_per_year"]["is_partial_year"] == 0]
    if not complete.empty:
        last = complete.iloc[-1]
        lines.append(
            f"{int(last['year'])} (latest complete year): {int(last['reports']):,} reports in total, "
            f"{int(last['reports_without_implants']):,} without root-form implants."
        )
    return lines


def main():
    missing = [name for name in RAW_FILES if not (RAW_DIR / f"{name}.json").exists()]
    if missing:
        print(f"ERROR: missing downloads in {RAW_DIR}: {', '.join(missing)}")
        print("Fix: run  python src/01_download_counts.py  first.")
        sys.exit(1)

    raw = {name: load_raw(RAW_DIR, name) for name in RAW_FILES}
    total = total_reports(raw["total"])
    if total == 0:
        print("ERROR: the download says there are no dental reports. Nothing to analyze.")
        sys.exit(1)

    # THE DATA IS UPDATED WEEKLY, SO THE YEAR OF THE LAST UPDATE IS A PARTIAL YEAR
    last_updated = raw["total"]["meta"].get("last_updated", raw["total"]["downloaded_on"])
    last_year = int(last_updated[:4])

    tables = {
        "reports_per_year": yearly_table(raw["by_day"]["results"], raw["by_day_without_implants"]["results"], last_year),
        "device_types": counts_table(raw["device_types"]["results"], "device_type", total, TOP_N),
        "event_types": counts_table(raw["event_types"]["results"], "event_type", total),
        "product_problems": counts_table(raw["product_problems"]["results"], "product_problem", total, TOP_N),
        "filter_check": regulation_check(raw["regulation_numbers"]["results"]),
    }

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(TABLES_DIR / f"{name}.csv", index=False)
        print(f"Saved results/tables/{name}.csv")

    # WRITE THE SUMMARY
    yearly_sum = int(tables["reports_per_year"]["reports"].sum())
    parts = [
        "# Results summary",
        "",
        f"Generated automatically by src/02_build_tables.py. Data downloaded on "
        f"{raw['total']['downloaded_on']}; openFDA last updated {last_updated}.",
        "",
        "Reminder: these are voluntary and mandatory reports sent to FDA. Counts show reporting",
        "patterns, not how often devices fail.",
        "",
        "## Key numbers",
        "",
    ]
    parts += [f"- {line}" for line in key_findings(total, tables)]
    parts += [
        "",
        f"Check: the yearly table adds up to {yearly_sum:,} reports (total from openFDA: {total:,}).",
        "",
    ]
    for name, table in tables.items():
        parts += [f"## {name}", "", to_markdown_table(table), ""]
    SUMMARY_PATH.write_text("\n".join(parts), encoding="utf-8")
    print("Summary written to results/summary.md")


if __name__ == "__main__":
    main()
