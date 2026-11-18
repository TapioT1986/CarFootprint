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

Per model: each catalogue row (data/catalog.json) is matched to VCA rows of the same make, the same first
word of the model name ("Corolla Hatchback ..." -> COROLLA) and the same powertrain group (petrol and diesel
without hybrids, hybrids incl. mild hybrids, plug-in hybrids, electric). With at least 3 matching versions the
row gets their median ratio; otherwise the powertrain median. VCA's own mild/full hybrid labels are not used,
because they are inconsistent (e.g. Golf eTSI listed as a full hybrid); the measured phase values decide.

    py tools/city_ratio.py           # print the medians and how many catalogue rows got a model figure
    py tools/city_ratio.py --write   # write data/city_ratio.json for build.py
"""
import csv
import io
import json
import pathlib
import statistics
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import EEA_BRAND_ALIASES, norm  # noqa: E402

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


MIN_VERSIONS = 3


GENERIC = {"MODEL", "NEW", "ALL", "THE"}  # "Model 3", "New Kuga": the next word names the model


def first_word(t, make=""):
    w = norm(t).replace(",", " ").split()
    if w and make and w[0] == make:
        w = w[1:]                       # "MAZDA CX-30" -> CX-30
    if len(w) > 1 and w[0] in GENERIC:
        return w[0] + " " + w[1]
    return w[0] if w else ""


def page_group(g):
    return {"B (petrol)": "B", "D (diesel)": "D", "H (full hybrid)": "H", "mild hybrid": "H",
            "P (plug-in hybrid, fuel)": "P", "E (battery electric)": "E"}.get(g)


def main():
    src = next(iter(sorted((ROOT / "sources").glob("vca_euro6_latest_*.zip"))), None)
    if src is None:
        sys.exit("no sources/vca_euro6_latest_*.zip")
    z = zipfile.ZipFile(src)
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    groups, by_model = {}, {}
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
            make = norm(r["Manufacturer"])
            make = EEA_BRAND_ALIASES.get(make, make)
            by_model.setdefault((make, first_word(r["Model"], make), page_group(g)), []).append(cc / ch)
    print(f"{src.name} ({name})")
    for g, v in sorted(groups.items()):
        q = statistics.quantiles(v, n=4)
        print(f"{g:26} n={len(v):5}  median {statistics.median(v):.2f}  quartiles {q[0]:.2f}-{q[2]:.2f}")
    med = {page_group(g): round(statistics.median(v), 2) for g, v in groups.items() if g != "mild hybrid"}
    med["M"] = round(statistics.median(groups["mild hybrid"]), 2)
    catalog = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    model, n = [], []
    for c in catalog:
        make = norm(c[0])
        make = EEA_BRAND_ALIASES.get(make, make)
        name = norm(c[1])
        if name.startswith(make + " "):
            name = name[len(make) + 1:]
        v = by_model.get((make, first_word(name, make), c[2]), [])
        if len(v) >= MIN_VERSIONS:
            model.append(round(statistics.median(v), 2))
            n.append(len(v))
        else:
            model.append(0)
            n.append(0)
    hits = sum(1 for x in model if x)
    print(f"model-specific ratio for {hits} of {len(catalog)} catalogue rows")
    for pt in "BDHPE":
        rows = [(c[0], c[1], m) for c, m in zip(catalog, model) if c[2] == pt and m]
        print(f"  {pt}: {len(rows)} rows, e.g. " + ", ".join(f"{a} {b} {m}" for a, b, m in rows[:4]))
    if "--write" in sys.argv:
        out = ROOT / "data" / "city_ratio.json"
        out.write_text(json.dumps({
            "description": "City/highway consumption ratio from WLTP phases (city = Low+Medium, highway = High+Extra High). "
                           "'ratios' = medians per powertrain (M = mild hybrids, information only); 'model' = per catalogue row "
                           "(same order as data/catalog.json), 0 = fewer than 3 matching versions, use the powertrain median.",
            "source": f"UK Vehicle Certification Agency, car fuel data, {src.name}; Open Government Licence. Made by tools/city_ratio.py.",
            "ratios": med, "model": model, "versions": n}, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
