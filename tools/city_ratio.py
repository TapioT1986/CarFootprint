#!/usr/bin/env python3
"""City / highway consumption ratio per powertrain, from WLTP phase results.

Source: UK Vehicle Certification Agency (VCA), "Car fuel data, CO2 and vehicle tax tools", latest data
download (carfueldata.vehicle-certification-agency.gov.uk -> Download -> latest data, Euro 6 CSV in a ZIP,
Open Government Licence). Save the ZIP as sources/vca_euro6_latest_<date>.zip (about 0.1 MB, not committed).

Each row is one model version with its WLTP fuel consumption per phase (l/100 km): Low, Medium, High,
Extra High. City = Low + Medium phases, highway = High + Extra High, each weighted by the phase
distance of the class 3 WLTC (3.095, 4.756, 7.162, 8.254 km). The ratio is city / highway consumption.
Battery-electric cars have no phase values; for them the ratio comes from the WLTP electric range in
the city (Low + Medium) and combined: city consumption = 1/city range, combined = 1/combined range,
highway = (23.266 x combined - 7.851 x city) / 15.416.

The page (tools/template.html, CITY_R) uses the medians printed here:
    py tools/city_ratio.py
"""
import csv
import io
import pathlib
import statistics
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = {"Low": 3.095, "Medium": 4.756, "High": 7.162, "Extra High": 8.254}
CITY_KM, HWY_KM, ALL_KM = 7.851, 15.416, 23.266


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def group(row):
    pt, fuel = row["Powertrain"], row["Fuel Type"]
    if "Battery Electric" in pt:
        return "E (battery electric)"
    if "Plug-in" in pt:
        return "P (plug-in hybrid, fuel)"
    if "(HEV)" in pt:
        return "H (full hybrid)"
    if "Mild" in pt:
        return "mild hybrid"
    if pt.startswith("Internal Combustion") and fuel == "Petrol":
        return "B (petrol)"
    if pt.startswith("Internal Combustion") and fuel == "Diesel":
        return "D (diesel)"
    return None


def main():
    src = next(iter(sorted((ROOT / "sources").glob("vca_euro6_latest_*.zip"))), None)
    if src is None:
        sys.exit("no sources/vca_euro6_latest_*.zip")
    z = zipfile.ZipFile(src)
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    groups = {}
    for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="latin-1")):
        g = group(r)
        if g is None:
            continue
        if g.startswith("E"):
            rc, ra = num(r["Electric Range City Km"]), num(r["Equivalent All Electric Range KM"]) or num(r["Maximum range (Km)"])
            if rc <= 0 or ra <= 0:
                continue
            cc, ca = 1 / rc, 1 / ra
            ch = (ALL_KM * ca - CITY_KM * cc) / HWY_KM
        else:
            ph = {k: num(r["WLTP Metric " + k]) for k in DIST}
            if min(ph.values()) <= 0:
                continue
            cc = (DIST["Low"] * ph["Low"] + DIST["Medium"] * ph["Medium"]) / CITY_KM
            ch = (DIST["High"] * ph["High"] + DIST["Extra High"] * ph["Extra High"]) / HWY_KM
        if ch > 0:
            groups.setdefault(g, []).append(cc / ch)
    print(f"{src.name} ({name})")
    for g, v in sorted(groups.items()):
        q = statistics.quantiles(v, n=4)
        print(f"{g:26} n={len(v):5}  median {statistics.median(v):.2f}  quartiles {q[0]:.2f}-{q[2]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
