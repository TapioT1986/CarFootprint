#!/usr/bin/env python3
"""Official WLTP electric range per model, from the EEA register extract for Finland.

Source: EEA, Monitoring of CO2 emissions from passenger cars (Regulation (EU) 2019/631),
CC BY 4.0. The extract is the EEA data viewer's "Download search results (CSV)" for
Country = FI, Registration year = 2025, Status = Provisional (co2cars.apps.eea.europa.eu),
saved as sources/eea_fi_*range*.csv (about 11 MB, not committed).

Each row is one registered car. For electric and plug-in hybrid cars this writes the
median "Electric range (km)" and the number of cars per make, commercial name and
powertrain into data/eea_ev_range_fi_2025.csv. build.py matches it to the model list
the same way as the electricity consumption.

Plain Python (no pandas), so it runs on the owner's PC:
    py tools/ev_range.py
"""
import csv
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import EEA_BRAND_ALIASES, norm  # noqa: E402

PT = {"electric": "E", "petrol/electric": "P", "diesel/electric": "P"}
SANE = (10, 1200)  # km; a value outside this is a reporting error


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    src = next(iter(sorted((root / "sources").glob("eea_fi_*range*.csv"))), None)
    if src is None:
        print("no sources/eea_fi_*range*.csv found", file=sys.stderr)
        return 1
    groups, rows, years = {}, 0, set()
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
            groups.setdefault((brand, model, pt), []).append(km)
            years.add(r.get("year"))
    out = root / "data" / "eea_ev_range_fi_2025.csv"
    lines = [
        "# Official WLTP electric range (km) of electric and plug-in hybrid cars registered in Finland,",
        "# median per make, commercial name and powertrain (E = electric, P = plug-in hybrid), n = cars.",
        "# Source: EEA, Monitoring of CO2 emissions from passenger cars (Regulation (EU) 2019/631), CC BY 4.0,",
        f"# data viewer co2cars.apps.eea.europa.eu, Country FI, year {'/'.join(sorted(y for y in years if y))},"
        f" provisional; {src.name}, {rows} rows. Made by tools/ev_range.py.",
        "make|model|pt|range_km|n",
    ]
    for (b, m, p), v in sorted(groups.items()):
        lines.append(f"{b}|{m}|{p}|{round(statistics.median(v))}|{len(v)}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(groups)} models from {rows} rows -> {out.relative_to(root)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
