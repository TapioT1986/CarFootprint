#!/usr/bin/env python3
"""Build CarFootprint's index.html from the open data sources.

Steps
  1. realworld.json  from data/eea_obfcm_2024_aggregated.csv (committed, small)
  2. catalog.json    from the two large source files below (not committed)
  3. index.html      = tools/template.html with both JSON blobs inlined

Source files, downloaded by hand into --sources (default ./sources):

  TieliikenneAvoinData_*.csv
      Traficom, "Ajoneuvojen avoin data" (CC BY 4.0). The Finnish vehicle
      register: one row per vehicle, ~2.6 M passenger cars.
      https://avoindata.suomi.fi/data/fi/dataset/ajoneuvojen-avoin-data

  eea_fi_*.csv
      EEA, "CO2 emissions from new passenger cars" (CC BY 4.0), filtered to
      Country = FI. Carries z (Wh/km), the WLTP electricity consumption that
      the Finnish register does not record.
      https://co2cars.apps.eea.europa.eu/

Without those two files the script still rebuilds index.html from the JSON
already in data/, so a plain `python3 tools/build.py` always works.

Usage
    python3 tools/build.py [--sources DIR] [--root DIR]
"""

import argparse
import json
import pathlib
import re
import sys
import unicodedata

# --- tuning -----------------------------------------------------------------

MIN_CARS_PER_MODEL = 300      # drop models too rare to be worth listing
MIN_CARS_PER_BRAND_FUEL = 1000  # drop brand averages built on too few cars
FIRST_YEAR, LAST_YEAR = 2008, 2026
# WLTP CO2 (g/km) per litre of fuel burnt, used to turn the register's CO2
# figure into a consumption figure.
CO2_PER_LITRE = {"B": 23.3, "H": 23.3, "D": 26.4}

# Register fuel/hybrid codes -> our powertrain letters.
# 04 = electric; hybrid class 01 = plug-in, 02 = full hybrid; else 01/02 = petrol/diesel.
def powertrain(fuel_code, hybrid_class):
    if fuel_code == "04":
        return "E"
    if hybrid_class == "01":
        return "P"
    if hybrid_class == "02":
        return "H"
    return {"01": "B", "02": "D"}.get(fuel_code)


# Manufacturer names in the EEA data are legal entities ("AUDI AG"), and one
# brand can sit under several of them. Everything a brand's cars are reported
# under is pooled into one average for that brand.
BRAND_TO_MANUFACTURERS = {
    "VOLKSWAGEN": ["VOLKSWAGEN"],
    "AUDI": ["AUDI AG", "AUDI HUNGARIA"],
    "BMW": ["BMW AG"],
    "MINI": ["BMW AG"],
    "MERCEDES-BENZ": ["MERCEDES-BENZ AG"],
    "SKODA": ["SKODA"],
    "SEAT": ["SEAT"],
    "CUPRA": ["SEAT"],
    "VOLVO": ["VOLVO"],
    "TOYOTA": ["TOYOTA", "TOYOTA MOTOR CORPORATION"],
    "LEXUS": ["TOYOTA MOTOR CORPORATION"],
    "KIA": ["KIA", "KIA SLOVAKIA"],
    "HYUNDAI": ["HYUNDAI", "HYUNDAI CZECH", "HYUNDAI ASSAN", "HYUNDAI TURKIYE"],
    "FORD": ["FORD WERKE GMBH"],
    "NISSAN": ["NISSAN AUTOMOTIVE EUROPE"],
    "PEUGEOT": ["AUTOMOBILES PEUGEOT", "PSA", "STELLANTIS AUTO"],
    "CITROEN": ["AUTOMOBILES CITROEN", "PSA", "STELLANTIS AUTO"],
    "DS": ["PSA", "STELLANTIS AUTO"],
    "OPEL": ["OPEL AUTOMOBILE", "STELLANTIS AUTO"],
    "FIAT": ["FIAT GROUP", "STELLANTIS EUROPE"],
    "JEEP": ["CHRYSLER", "STELLANTIS EUROPE"],
    "ALFA ROMEO": ["ALFA ROMEO"],
    "RENAULT": ["RENAULT"],
    "DACIA": ["DACIA"],
    "MAZDA": ["MAZDA", "MAZDA EUROPE"],
    "HONDA": ["HONDA MOTOR CO"],
    "SUZUKI": ["SUZUKI MOTOR CORPORATION", "MAGYAR SUZUKI"],
    "MITSUBISHI": ["MITSUBISHI MOTORS CORPORATION", "MITSUBISHI MOTORS THAILAND"],
    "SUBARU": ["SUBARU"],
    "PORSCHE": ["PORSCHE"],
    "LAND ROVER": ["JAGUAR LAND ROVER LIMITED"],
    "JAGUAR": ["JAGUAR LAND ROVER LIMITED"],
    "MG": ["SAIC MOTOR CORPORATION"],
    "BYD": ["BYD AUTO"],
}

# Brands with no measured data of their own (electric-only makers, and marques
# the EEA subset leaves out) fall back to the fleet average.
EEA_BRAND_ALIASES = {"TESLA MOTORS": "TESLA"}


def norm(s):
    """Upper-case, strip accents, squeeze spaces — for matching names."""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.upper()).strip()


# --- step 1: measured real-world consumption --------------------------------

def build_realworld(root):
    """Pool the EEA's per-manufacturer OBFCM averages into per-brand factors.

    For petrol/diesel/hybrid the useful number is the ratio measured/WLTP,
    because the calculator multiplies a model's WLTP figure by it.
    For plug-in hybrids the ratio is meaningless (WLTP assumes a full battery),
    so the measured litres/100 km is carried through instead.
    """
    import pandas as pd

    path = root / "data" / "eea_obfcm_2024_aggregated.csv"
    rows = [l.rstrip("\n").split("|") for l in path.read_text().splitlines()
            if l.strip() and not l.startswith("#") and not l.startswith("year|")]
    df = pd.DataFrame(rows, columns=["year", "man", "fuel", "n", "obfcm", "wltp", "gap"])
    df = df.astype({"n": int, "obfcm": float, "wltp": float, "gap": float})

    # Sanity check: every row's own gap % must follow from its two consumption
    # figures. A row that fails was mis-transcribed, so drop it.
    implied = (df.obfcm / df.wltp - 1) * 100
    rounding = ((0.006 / df.wltp + 0.006 / df.obfcm) * 100 * (df.obfcm / df.wltp) + 0.6).clip(lower=1.5)
    bad = (implied - df.gap).abs() > rounding
    if bad.any():
        print(f"  dropped {int(bad.sum())} inconsistent row(s)", file=sys.stderr)
    df = df[~bad]

    def pooled(sub):
        n = sub.n.sum()
        return int(n), (sub.obfcm * sub.n).sum() / n, (sub.wltp * sub.n).sum() / n

    # "PE" pools plug-in petrol and plug-in diesel; both behave the same way.
    groups = {"P": ["P"], "D": ["D"], "PE": ["PE", "DE"]}
    fleet = {}
    for key, codes in groups.items():
        n, ob, wl = pooled(df[df.fuel.isin(codes)])
        fleet[key] = {"n": n, "ob": round(ob, 2), "wl": round(wl, 2), "k": round(ob / wl, 3)}

    brands = {}
    for brand, makers in BRAND_TO_MANUFACTURERS.items():
        entry = {}
        for key, codes in groups.items():
            sub = df[df.man.isin(makers) & df.fuel.isin(codes)]
            if len(sub) and sub.n.sum() >= MIN_CARS_PER_BRAND_FUEL:
                n, ob, wl = pooled(sub)
                entry[key] = [round(ob, 2) if key == "PE" else round(ob / wl, 3), n]
        if entry:
            brands[brand] = entry
    return {"fleet": fleet, "brand": brands}


# --- step 2: the model catalogue --------------------------------------------

def build_catalog(sources):
    """One row per brand + model + powertrain, from the Finnish register."""
    import numpy as np
    import pandas as pd

    reg = next(iter(sorted(sources.glob("TieliikenneAvoinData_*.csv"))), None)
    if reg is None:
        return None
    print(f"  reading {reg.name} (slow, ~2.6 M rows)", file=sys.stderr)

    cols = ["ajoneuvoluokka", "ensirekisterointipvm", "kayttovoima", "sahkohybridinluokka",
            "merkkiSelvakielinen", "kaupallinenNimi", "suurinNettoteho", "omamassa",
            "WLTP_Co2", "NEDC_Co2", "matkamittarilukema"]
    df = pd.read_csv(reg, sep=";", encoding="latin-1", usecols=cols, dtype=str, low_memory=False)
    df = df[df.ajoneuvoluokka == "M1"]  # passenger cars only

    for c in ["WLTP_Co2", "NEDC_Co2", "matkamittarilukema"]:
        df[c] = pd.to_numeric(df[c].str.replace(",", "."), errors="coerce")
    df["year"] = pd.to_numeric(df.ensirekisterointipvm.str[-4:], errors="coerce")
    df["pt"] = [powertrain(f, h) for f, h in zip(df.kayttovoima, df.sahkohybridinluokka)]
    df = df[df.pt.notna() & df.year.between(FIRST_YEAR, LAST_YEAR)]

    # Odometer / age gives the mileage these cars are actually driven.
    df["age"] = LAST_YEAR + 0.5 - df.year
    km = df.matkamittarilukema
    df["km_per_year"] = np.where((df.age >= 1) & km.between(1000, 1_500_000), km / df.age, np.nan)

    df["brand"] = df.merkkiSelvakielinen.fillna("").str.replace(r",\s*VW$", "", regex=True).str.strip()

    def model_name(brand, commercial):
        name = str(commercial).strip().upper()
        for prefix in (brand.upper() + " ", norm(brand) + " "):
            if name.startswith(prefix):
                name = name[len(prefix):]
        name = re.sub(r"\s+(HYBRID|PLUG-IN|PHEV)$", "", name)
        if len(name) <= 4 or re.search(r"[\d\-]", name):
            return name          # "ID.4", "A3", "C-HR" stay upper-case
        return name.title()

    df["model"] = [model_name(b, n) for b, n in zip(df.brand, df.kaupallinenNimi)]
    df = df[df.model.str.len() > 0]

    grouped = df.groupby(["brand", "model", "pt"]).agg(
        count=("year", "size"),
        year_lo=("year", lambda s: int(s.quantile(0.05))),
        year_hi=("year", lambda s: int(s.quantile(0.95))),
        wltp=("WLTP_Co2", "median"),
        km_per_year=("km_per_year", "median"),
    ).reset_index()
    grouped = grouped[grouped["count"] >= MIN_CARS_PER_MODEL].sort_values("count", ascending=False)

    catalog = []
    for r in grouped.itertuples():
        factor = CO2_PER_LITRE.get(r.pt)
        litres = round(r.wltp / factor, 1) if factor and pd.notna(r.wltp) else None
        km_year = None if pd.isna(r.km_per_year) else int(round(r.km_per_year, -2))
        catalog.append([r.brand, r.model, r.pt, litres, int(r.count),
                        f"{r.year_lo}–{r.year_hi}", km_year])

    # An electric or plug-in model with no electricity figure is useless here.
    catalog = [c for c in catalog if c[2] in "EP" or c[3] is not None]
    catalog.sort(key=lambda c: (c[0], c[1], c[2]))
    return catalog


def add_electricity(catalog, sources):
    """Append WLTP kWh/100 km to electric and plug-in rows, from the EEA file."""
    import pandas as pd

    eea = next(iter(sorted(sources.glob("eea_fi_*.csv"))), None)
    if eea is None or catalog is None:
        return catalog
    print(f"  reading {eea.name}", file=sys.stderr)

    e = pd.read_csv(eea, low_memory=False)
    e["brand"] = e.Mk.map(norm)
    e["model"] = e.Cn.map(norm)
    # The commercial name sometimes repeats the brand ("VOLVO EX40").
    e["model"] = [m[len(b) + 1:] if m.startswith(b + " ") else m for b, m in zip(e.brand, e.model)]
    e["pt"] = e.Ft.map({"electric": "E", "petrol/electric": "P", "diesel/electric": "P"})
    e["wh_km"] = e["z (Wh/km)"]
    e = e[e.pt.notna() & e.wh_km.between(80, 400)]

    ev_default = round(float(e[e.pt == "E"].wh_km.median()) / 10, 1)
    phev_default = round(float(e[e.pt == "P"].wh_km.median()) / 10, 1)

    out = []
    for row in catalog:
        brand, model, pt = EEA_BRAND_ALIASES.get(norm(row[0]), norm(row[0])), norm(row[1]), row[2]
        kwh, matched = None, 0
        if pt in "EP":
            same = e[(e.brand == brand) & (e.pt == pt)]
            hit = same[(same.model == model) | same.model.str.startswith(model + " ")]
            if not len(hit):
                # Fall back to the model family: "ID.4 PRO 150 KW" -> "ID.4".
                family = model.split(" ")[0]
                if len(family) >= 2:
                    wider = same[(same.model == family) | same.model.str.startswith(family + " ")]
                    hit = wider if len(wider) >= 5 else hit
            if len(hit):
                kwh, matched = round(float(hit.wh_km.median()) / 10, 1), len(hit)
        out.append(row + [kwh, matched])
    return out, ev_default, phev_default


# --- step 3: assemble the page ----------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=pathlib.Path(__file__).resolve().parent.parent)
    ap.add_argument("--sources", default=None, help="folder holding the large source CSVs")
    args = ap.parse_args()
    root = pathlib.Path(args.root)
    sources = pathlib.Path(args.sources) if args.sources else root / "sources"

    print("1. real-world consumption", file=sys.stderr)
    realworld = build_realworld(root)

    print("2. model catalogue", file=sys.stderr)
    catalog = None
    if sources.is_dir():
        catalog = build_catalog(sources)
        if catalog is not None:
            catalog, ev_default, phev_default = add_electricity(catalog, sources)
            realworld["evMedian"], realworld["phevMedian"] = ev_default, phev_default
    if catalog is None:
        print("   no source CSVs found, keeping data/catalog.json", file=sys.stderr)
        catalog = json.loads((root / "data" / "catalog.json").read_text())
        old = json.loads((root / "data" / "realworld.json").read_text())
        realworld["evMedian"], realworld["phevMedian"] = old["evMedian"], old["phevMedian"]

    (root / "data" / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1))
    (root / "data" / "realworld.json").write_text(json.dumps(realworld, ensure_ascii=False, indent=1))

    print("3. index.html", file=sys.stderr)
    page = (root / "tools" / "template.html").read_text()
    page = page.replace("__CATALOG__", json.dumps(catalog, ensure_ascii=False, separators=(",", ":")))
    page = page.replace("__RW__", json.dumps(realworld, ensure_ascii=False, separators=(",", ":")))
    (root / "index.html").write_text(page)
    print(f"   {len(catalog)} models, {len(realworld['brand'])} brands, "
          f"{len(page) // 1024} KiB", file=sys.stderr)


if __name__ == "__main__":
    main()
