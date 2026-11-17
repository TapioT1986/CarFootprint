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
import hashlib
import json
import pathlib
import re
import sys
import unicodedata

# --- tuning -----------------------------------------------------------------

MIN_CARS_PER_MODEL = 300      # drop models too rare to be worth listing
MIN_CARS_PER_BRAND_FUEL = 1000  # drop brand averages built on too few cars
MIN_CARS_PER_NEDC_YEAR = 30   # a model's NEDC figure for one year needs this many cars
LAST_NEDC_YEAR = 2017         # WLTP applied to all new registrations from September 2018
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
    # Plain Python on purpose: the default build (without the large source CSVs)
    # then needs no third-party packages at all.
    path = root / "data" / "eea_obfcm_2024_aggregated.csv"
    df = []
    for l in path.read_text(encoding="utf-8").splitlines():
        if not l.strip() or l.startswith("#") or l.startswith("year|"):
            continue
        year, man, fuel, n, obfcm, wltp, gap = l.split("|")
        df.append({"man": man, "fuel": fuel, "n": int(n),
                   "obfcm": float(obfcm), "wltp": float(wltp), "gap": float(gap)})

    # Sanity check: every row's own gap % must follow from its two consumption
    # figures. A row that fails was mis-transcribed, so drop it.
    def consistent(r):
        implied = (r["obfcm"] / r["wltp"] - 1) * 100
        rounding = max(1.5, (0.006 / r["wltp"] + 0.006 / r["obfcm"]) * 100
                       * (r["obfcm"] / r["wltp"]) + 0.6)
        return abs(implied - r["gap"]) <= rounding
    bad = sum(1 for r in df if not consistent(r))
    if bad:
        print(f"  dropped {bad} inconsistent row(s)", file=sys.stderr)
    df = [r for r in df if consistent(r)]

    def pooled(sub):
        n = sum(r["n"] for r in sub)
        return (n, sum(r["obfcm"] * r["n"] for r in sub) / n,
                sum(r["wltp"] * r["n"] for r in sub) / n)

    # "PE" pools plug-in petrol and plug-in diesel; both behave the same way.
    groups = {"P": ["P"], "D": ["D"], "PE": ["PE", "DE"]}
    fleet = {}
    for key, codes in groups.items():
        n, ob, wl = pooled([r for r in df if r["fuel"] in codes])
        fleet[key] = {"n": n, "ob": round(ob, 2), "wl": round(wl, 2), "k": round(ob / wl, 3)}

    brands = {}
    for brand, makers in BRAND_TO_MANUFACTURERS.items():
        entry = {}
        for key, codes in groups.items():
            sub = [r for r in df if r["man"] in makers and r["fuel"] in codes]
            if sub and sum(r["n"] for r in sub) >= MIN_CARS_PER_BRAND_FUEL:
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

    # Cars first registered up to 2017 were type-approved with the older NEDC
    # test, whose figures are much further from real-world consumption than
    # WLTP's. Keep their own NEDC figure per model and year, so the page can
    # use it with an NEDC-specific correction instead of the WLTP one.
    old = df[(df.year <= LAST_NEDC_YEAR) & df.pt.isin(["B", "D", "H"]) & df.NEDC_Co2.between(50, 400)]
    per_year = old.groupby(["brand", "model", "pt", "year"]).NEDC_Co2.agg(["median", "size"]).reset_index()
    per_year = per_year[per_year["size"] >= MIN_CARS_PER_NEDC_YEAR]
    nedc = {}
    for r in per_year.itertuples():
        litres = round(r.median / CO2_PER_LITRE[r.pt], 1)
        nedc.setdefault((r.brand, r.model, r.pt), []).append([int(r.year), litres])
    return catalog, nedc


def attach_nedc(catalog, nedc):
    """Append each row's [[year, NEDC l/100 km], ...] list (empty when none)."""
    return [r + [sorted(nedc.get((r[0], r[1], r[2]), []))] for r in catalog]


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


def fill_old_electricity(catalog, root):
    """Fill missing kWh/100 km from data/eea_ev_consumption_fi_2020_2022.csv.

    The 2025 EEA extract only covers models still sold new in 2025, so older
    electric cars such as the Nissan Leaf 40 kWh or Renault Zoe got a default.
    The fallback file carries their WLTP figure from Finnish registrations in
    2020-2022. A model must match exactly, or be the only model starting with
    the catalogue's name, so a generic "LEAF" never borrows a 62 kWh figure.
    """
    path = root / "data" / "eea_ev_consumption_fi_2020_2022.csv"
    if not path.exists():
        return catalog, 0
    table = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("make|") or not line.strip():
            continue
        make, model, pt, _years, rows, wh = line.split("|")
        table.setdefault((norm(make), pt), []).append((norm(model), int(rows), int(wh)))

    filled = 0
    out = []
    for r in catalog:
        r = list(r)
        if r[2] in "EP" and r[7] is None:
            cands = table.get((norm(r[0]), r[2]), [])
            model = norm(r[1])
            hit = [c for c in cands if c[0] == model] or \
                  [c for c in cands if c[0].startswith(model + " ")]
            if len(hit) == 1:
                r[7], r[8] = round(hit[0][2] / 10, 1), hit[0][1]
                filled += 1
        out.append(r)
    return out, filled


# --- model-level real-world consumption -------------------------------------

MIN_VEHICLES_PER_MODEL = 50     # below this the model average is too noisy
FACTOR_RANGE = (0.85, 2.0)      # a factor outside this means we matched the wrong car
PT_TO_EEA = {"B": "p", "H": "p", "D": "d"}


def attach_model_realworld(catalog, root):
    """Append each model's measured consumption to its catalogue row.

    data/eea_obfcm_2024_models.csv holds litres per 100 km measured from the
    cars' own fuel meters, pooled per make + model + fuel. For petrol, diesel
    and hybrids we store the ratio measured/WLTP, because the page multiplies a
    model's WLTP figure by it. For plug-in hybrids we store the measured litres
    themselves, since their WLTP figure assumes a full battery and means little.

    Rows keep two extra fields: the value and the number of vehicles behind it,
    or None and 0 when no model-level match was good enough.
    """
    path = root / "data" / "eea_obfcm_2024_models.csv"
    if not path.exists():
        return [r + [None, 0] for r in catalog]

    measured = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("make|") or not line.strip():
            continue
        make, model, fuel, n, l100 = line.split("|")
        measured[(norm(make), norm(model), fuel)] = (int(n), float(l100))

    def look_up(brand, model, fuels):
        """Exact model first, then the model family ("ID.4 PRO" -> "ID.4")."""
        for f in fuels:
            hit = measured.get((brand, model, f))
            if hit and hit[0] >= MIN_VEHICLES_PER_MODEL:
                return hit
        family = model.split(" ")[0]
        if len(family) < 2:
            return None
        pooled_n, pooled_sum = 0, 0.0
        for (mk, cn, f), (n, l100) in measured.items():
            if mk == brand and f in fuels and (cn == family or cn.startswith(family + " ")):
                pooled_n += n
                pooled_sum += l100 * n
        if pooled_n >= MIN_VEHICLES_PER_MODEL:
            return pooled_n, pooled_sum / pooled_n
        return None

    out, exact = [], 0
    for r in catalog:
        brand, model, pt, wltp = norm(EEA_BRAND_ALIASES.get(norm(r[0]), r[0])), norm(r[1]), r[2], r[3]
        value, n = None, 0
        if pt == "P":
            hit = look_up(brand, model, ("pe", "de"))
            if hit:
                n, value = hit[0], round(hit[1], 2)
        elif pt in PT_TO_EEA:
            hit = look_up(brand, model, (PT_TO_EEA[pt],))
            if hit and wltp:
                factor = hit[1] / wltp
                if FACTOR_RANGE[0] <= factor <= FACTOR_RANGE[1]:
                    n, value = hit[0], round(factor, 3)
        exact += value is not None
        out.append(r + [value, n])
    print(f"   model-level consumption for {exact} of {len(catalog)} models", file=sys.stderr)
    return out


# --- prices -----------------------------------------------------------------

MONTHS_FI = ["tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu",
             "heinäkuu", "elokuu", "syyskuu", "lokakuu", "marraskuu", "joulukuu"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June",
             "July", "August", "September", "October", "November", "December"]
FALLBACK_PRICES = {"petrol": {"value": 1.85}, "diesel": {"value": 1.75},
                   "electricity": {"value": 0.15}}


def apply_prices(page, root):
    """Put the latest official prices into the page as its default values."""
    path = root / "data" / "prices.json"
    prices = json.loads(path.read_text(encoding="utf-8")) if path.exists() else dict(FALLBACK_PRICES)

    def month_name(period, names):
        # "2026M06" -> "kesäkuu 2026"
        try:
            y, m = period.split("M")
            return f"{names[int(m) - 1]} {y}"
        except (ValueError, IndexError, AttributeError):
            return period

    fuel, elec = prices.get("petrol", {}), prices.get("electricity", {})
    fallback_url = prices.get("source", {}).get("url", "")

    def a(item, text):
        url = item.get("url") or fallback_url
        return f'<a href="{url}" target="_blank" rel="noopener">{text}</a>'

    if fuel.get("period") and elec.get("period") and fallback_url:
        fi = (f'Oletushinnat Tilastokeskukselta: polttoaineet '
              f'{a(fuel, month_name(fuel["period"], MONTHS_FI))}, sähkö '
              f'{a(elec, month_name(elec["period"], MONTHS_FI))}. '
              f'Vaihda omiin hintoihisi, jos ne poikkeavat.')
        en = (f'Default prices from Statistics Finland: fuel '
              f'{a(fuel, month_name(fuel["period"], MONTHS_EN))}, electricity '
              f'{a(elec, month_name(elec["period"], MONTHS_EN))}. '
              f'Change them to your own if they differ.')
    else:
        fi = "Oletushinnat ovat arvioita. Vaihda omiin hintoihisi."
        en = "Default prices are estimates. Change them to your own."

    for token, key in (("__P_PETROL__", "petrol"), ("__P_DIESEL__", "diesel"),
                       ("__P_ELEC__", "electricity")):
        page = page.replace(token, str(prices[key]["value"]))
    # "Beta - updated <month year>": the month the data was last refreshed (prices.json "checked",
    # set by the monthly price workflow), so a rebuild of the same commit gives the same page.
    checked = str(prices.get("checked", ""))
    upd_fi = month_name(checked[:4] + "M" + checked[5:7], MONTHS_FI) if len(checked) >= 7 else ""
    upd_en = month_name(checked[:4] + "M" + checked[5:7], MONTHS_EN) if len(checked) >= 7 else ""
    upd_fi = upd_fi.replace("kuu ", "kuussa ") if upd_fi else upd_fi
    page = page.replace("Beta – päivitetty __UPDATED_FI__", f"Beta – päivitetty {upd_fi}" if upd_fi else "Beta")
    page = page.replace("Beta – updated __UPDATED_EN__", f"Beta – updated {upd_en}" if upd_en else "Beta")
    return page.replace("__PRICES_NOTE_FI__", fi).replace("__PRICES_NOTE_EN__", en)


def inspection_for_page(catalog, root):
    """Link each catalogue row to a Traficom inspection model series.

    data/inspection.json comes from tools/update_inspection.py. Traficom groups
    cars by model series ("Toyota COROLLA", "BMW 3-sarja", "Mercedes-Benz C"),
    all powertrains together; the catalogue has commercial names ("320D",
    "C 300 E", "ID.3 PRO 150 KW"). A row matches the longest series name that
    its model name starts with, at a word or number boundary.
    """
    path = root / "data" / "inspection.json"
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    brand_key = lambda b: {"bmw i": "bmw", "tesla motors": "tesla", "ford-cng-technik": "ford"}.get(b.lower(), b.lower())
    by_brand = {}
    for name in doc["models"]:
        for b in sorted({r[0] for r in catalog} | {"BMW", "Tesla", "Ford"}, key=len, reverse=True):
            if name.lower().startswith(b.lower() + " "):
                by_brand.setdefault(brand_key(b), []).append((name[len(b) + 1:].upper(), name))
                break
    for v in by_brand.values():
        v.sort(key=lambda s: len(s[0]), reverse=True)
    squash = lambda s: re.sub(r"[\s.]+", "", s)

    # New electric models that share a name with an older, different car
    different_car = [("renault", "MEGANE E-TECH"), ("renault", "SCENIC E-TECH"),
                     ("porsche", "MACAN 4"), ("ford", "EXPLORER")]

    def match(brand, model, pt):
        m = re.sub(r"^MAZDA(?=\d)", "", model.upper().replace("-KLASSE", ""))
        if any(brand_key(brand) == b and m.startswith(p) for b, p in different_car):
            return None
        if brand_key(brand) == "bmw" and m[:1].isdigit():
            m = m[0] + "-SARJA"
        first = m.split(" ")[0]
        for s, name in by_brand.get(brand_key(brand), []):
            if m == s or m.startswith(s + " "):
                return name
            ms, ss = squash(m), squash(s)
            # "C 300 E" -> C, "NX300H" -> NX, but "IX1" is not IX and "IONIQ6" is not IONIQ
            if ms.startswith(ss) and (len(ms) == len(ss) or not ms[len(ss)].isalpha()) \
                    and not re.fullmatch(re.escape(s) + r"\d", first):
                return name
        return None

    idx = [match(r[0], r[1], r[2]) for r in catalog]
    used = sorted({n for n in idx if n})
    return {"y": doc["year"], "ys": doc["years"], "url": doc["url"], "all": doc["all"],
            "m": {n: doc["models"][n] for n in used}, "idx": idx}


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
    built = build_catalog(sources) if sources.is_dir() else None
    if built is not None:
        catalog, nedc = built
        catalog, ev_default, phev_default = add_electricity(catalog, sources)
        realworld["evMedian"], realworld["phevMedian"] = ev_default, phev_default
        catalog, filled = fill_old_electricity(catalog, root)
        catalog = attach_model_realworld(catalog, root)
        catalog = attach_nedc(catalog, nedc)
    else:
        print("   no source CSVs found, keeping data/catalog.json", file=sys.stderr)
        catalog = json.loads((root / "data" / "catalog.json").read_text(encoding="utf-8"))
        nedc = {(r[0], r[1], r[2]): r[11] for r in catalog if len(r) > 11}
        catalog, filled = fill_old_electricity([r[:9] for r in catalog], root)
        catalog = attach_model_realworld(catalog, root)
        catalog = attach_nedc(catalog, nedc)
        old = json.loads((root / "data" / "realworld.json").read_text(encoding="utf-8"))
        realworld["evMedian"], realworld["phevMedian"] = old["evMedian"], old["phevMedian"]
    print(f"   electricity from the 2020-2022 register for {filled} older models", file=sys.stderr)
    print(f"   NEDC figures for {sum(1 for r in catalog if r[11])} models", file=sys.stderr)

    # Explicit UTF-8 and LF, so a build on Windows gives the same files as on Linux.
    (root / "data" / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (root / "data" / "realworld.json").write_text(
        json.dumps(realworld, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    print("3. index.html", file=sys.stderr)
    page = (root / "tools" / "template.html").read_text(encoding="utf-8")
    page = apply_prices(page, root)
    page = page.replace("__CATALOG__", json.dumps(catalog, ensure_ascii=False, separators=(",", ":")))
    page = page.replace("__RW__", json.dumps(realworld, ensure_ascii=False, separators=(",", ":")))
    # Vehicle tax tables, fetched by tools/vehicle_tax.py from Finlex
    vtax = json.loads((root / "data" / "vehicle_tax.json").read_text(encoding="utf-8"))
    vtax = {k: vtax[k] for k in ("t1", "t1a", "ev_new_add", "propulsion_per_100kg")}
    page = page.replace("__VTAX__", json.dumps(vtax, separators=(",", ":")))
    # Periodic inspections and model lifetime, fetched by tools/update_inspection.py
    insp = inspection_for_page(catalog, root)
    if insp:
        print(f"   inspection data for {sum(1 for n in insp['idx'] if n)} of {len(catalog)} models "
              f"({len(insp['m'])} model series, {insp['y']})", file=sys.stderr)
    page = page.replace("__INSP__", json.dumps(insp, ensure_ascii=False, separators=(",", ":")))
    # Version id = hash of the page; the page compares it with the server copy to escape stale caches
    page = page.replace("__BUILD__", hashlib.sha256(page.encode("utf-8")).hexdigest()[:12])
    (root / "index.html").write_text(page, encoding="utf-8", newline="\n")
    print(f"   {len(catalog)} models, {len(realworld['brand'])} brands, "
          f"{len(page) // 1024} KiB", file=sys.stderr)


if __name__ == "__main__":
    main()
