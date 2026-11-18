#!/usr/bin/env python3
"""Official WLTP electric range per model, from the EEA register extracts for Finland.

Source: EEA, Monitoring of CO2 emissions from passenger cars (Regulation (EU) 2019/631),
CC BY 4.0. Each extract is the EEA data viewer's "Download search results (CSV)" for
Country = FI and one registration year (co2cars.apps.eea.europa.eu), saved as
sources/eea_fi_<year><F|P>*range*.csv (F = final, P = provisional; 11-21 MB each, not committed):
2025 provisional, and 2020-2024 final for models no longer sold new.

Each row is one registered car. For electric and plug-in hybrid cars this writes the
median "Electric range (km)" and the number of cars per make, commercial name and
powertrain into data/eea_ev_range_fi.csv, in two periods: "2025" (the latest year) and
"2020-2024" (older years). build.py uses the 2025 figure when the model is there and the
older one otherwise, matching the model list the same way as the electricity consumption.

Plain Python (no pandas), so it runs on the owner's PC:
    py tools/ev_range.py
"""
import csv
import pathlib
import re
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import EEA_BRAND_ALIASES, norm  # noqa: E402

PT = {"electric": "E", "petrol/electric": "P", "diesel/electric": "P"}
SANE = (10, 1200)  # km; a value outside this is a reporting error
LATEST = "2025"


def read(src, groups, period):
    rows = 0
    with src.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows += 1
            pt = PT.get((r.get("Ft") or "").strip().lower())
            if r.get("Country") != "FI" or not pt:
                continue
            try:
                km = float(r.get("Electric range (km)") or "nan")
            except ValueError:
                continue
            if not SANE[0] <= km <= SANE[1]:
                continue
            brand = norm(r["Mk"])
            brand = EEA_BRAND_ALIASES.get(brand, brand)
            model = norm(r["Cn"])
            if model.startswith(brand + " "):  # "VOLVO EX40" -> "EX40"
                model = model[len(brand) + 1:]
            groups.setdefault((period, brand, model, pt), []).append(km)
    return rows


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    files = sorted((root / "sources").glob("eea_fi_*range*.csv"))
    if not files:
        print("no sources/eea_fi_*range*.csv found", file=sys.stderr)
        return 1
    groups, used = {}, []
    for src in files:
        m = re.match(r"eea_fi_(\d{4})([FP])", src.name)
        if not m:
            continue
        year, status = m.groups()
        period = LATEST if year == LATEST else "2020-2024" if "2020" <= year <= "2024" else None
        if period is None:
            continue
        rows = read(src, groups, period)
        used.append(f"{year} {'final' if status == 'F' else 'provisional'} ({src.name}, {rows} rows)")
        print(f"  {src.name}: {rows} rows", file=sys.stderr)
    out = root / "data" / "eea_ev_range_fi.csv"
    lines = [
        "# Official WLTP electric range (km) of electric and plug-in hybrid cars registered in Finland,",
        "# median per period, make, commercial name and powertrain (E = electric, P = plug-in hybrid), n = cars.",
        "# Source: EEA, Monitoring of CO2 emissions from passenger cars (Regulation (EU) 2019/631), CC BY 4.0,",
        "# data viewer co2cars.apps.eea.europa.eu, Country FI: " + "; ".join(used) + ".",
        "# Made by tools/ev_range.py.",
        "period|make|model|pt|range_km|n",
    ]
    for (per, b, m, p), v in sorted(groups.items()):
        lines.append(f"{per}|{b}|{m}|{p}|{round(statistics.median(v))}|{len(v)}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(groups)} model groups from {len(used)} files -> {out.relative_to(root)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
