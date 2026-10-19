"""Download summary counts of dental device adverse event reports from openFDA.

The openFDA "count" feature adds up millions of reports on FDA's side and returns
small tables, so we never need to download millions of individual reports.

Run from the project folder:
    python src/01_download_counts.py

Optional: set an OPENFDA_API_KEY environment variable for higher rate limits.
Without a key openFDA allows about 1,000 requests a day, which is plenty here.
"""

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

# SETTINGS
PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
API_URL = "https://api.fda.gov/device/event.json"

# DENTAL FILTER: openFDA links each report's product code to FDA's device
# classification, which records the review panel. "Dental" means the device is
# classified under 21 CFR Part 872 (Dental Devices).
DENTAL_FILTER = 'device.openfda.medical_specialty_description.exact:"Dental"'

# ROOT-FORM DENTAL IMPLANTS (PRODUCT CODE DZE) MAKE UP MOST REPORTS, SO SOME
# QUERIES ALSO LOOK AT EVERYTHING ELSE
IMPLANT_CODE = "DZE"
NOT_IMPLANT_FILTER = f'{DENTAL_FILTER} AND NOT device.device_report_product_code.exact:"{IMPLANT_CODE}"'

QUERIES = {
    "total": {"search": DENTAL_FILTER, "limit": 1},
    "by_day": {"search": DENTAL_FILTER, "count": "date_received"},
    "by_day_without_implants": {"search": NOT_IMPLANT_FILTER, "count": "date_received"},
    "device_types": {"search": DENTAL_FILTER, "count": "device.openfda.device_name.exact", "limit": 100},
    "event_types": {"search": DENTAL_FILTER, "count": "event_type.exact"},
    "product_problems": {"search": DENTAL_FILTER, "count": "product_problems.exact", "limit": 100},
    "regulation_numbers": {
        "search": DENTAL_FILTER, "count": "device.openfda.regulation_number.exact", "limit": 100,
    },
}


def get_openfda(params, attempts=3, wait_seconds=5, timeout=60):
    """Call openFDA and return the JSON body.

    openFDA answers "404 NOT_FOUND" when nothing matches. That is not an error for us:
    it means zero reports, so we return an empty result instead of failing.
    """
    params = dict(params)
    api_key = os.environ.get("OPENFDA_API_KEY")
    if api_key:
        params["api_key"] = api_key

    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(API_URL, params=params, timeout=timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return {"meta": {}, "results": []}
            if response.status_code == 400:
                raise RuntimeError(f"openFDA rejected the query (HTTP 400): {response.text[:300]}")
            last_error = f"HTTP status {response.status_code}"
        except requests.RequestException as error:
            last_error = str(error)

        print(f"  Attempt {attempt} of {attempts} failed: {last_error}")
        if attempt < attempts:
            time.sleep(wait_seconds)

    raise RuntimeError(f"Could not reach openFDA after {attempts} attempts. Last error: {last_error}")


def save_result(name, params, body, raw_dir):
    """Save one API answer with the query that produced it.

    For the "total" query we only keep meta (which holds the total). The single
    example report that comes with it is not needed.
    """
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    results = body.get("results", []) if "count" in params else []
    payload = {
        "name": name,
        "query": params,
        "downloaded_on": date.today().isoformat(),
        "meta": body.get("meta", {}),
        "results": results,
    }
    path = raw_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def total_reports(meta):
    """Read the total number of matching reports from an openFDA meta section."""
    return meta.get("results", {}).get("total", 0)


def main():
    for name, params in QUERIES.items():
        print(f"Requesting {name}")
        try:
            body = get_openfda(params)
        except RuntimeError as error:
            print(f"ERROR: {error}")
            print("Fix: check your internet connection and try again in a few minutes.")
            sys.exit(1)

        if not body.get("results"):
            print(f"  WARNING: openFDA returned no results for {name}.")
        path = save_result(name, params, body, RAW_DIR)
        print(f"  Saved {path}")

    # STOP EARLY IF THE MAIN QUERY FOUND NOTHING
    total_file = json.loads((RAW_DIR / "total.json").read_text(encoding="utf-8"))
    if total_reports(total_file["meta"]) == 0:
        print("ERROR: openFDA found no dental device reports. Check the DENTAL_FILTER setting.")
        sys.exit(1)
    print(f"Done. openFDA holds {total_reports(total_file['meta']):,} dental device reports.")


if __name__ == "__main__":
    main()
