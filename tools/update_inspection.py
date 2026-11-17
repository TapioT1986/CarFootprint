#!/usr/bin/env python3
"""Fetch Traficom periodic-inspection statistics into data/inspection.json.

Source: Traficom statistics database (PxWeb API, open, CC BY 4.0),
folder "Katsastuksen vikatilastot":

  010_kats_tau_101  passenger-car periodic inspections by model series and
                    first-use year, inspection years 2017-2022
  040_kats_tau_104  the same for inspection years 2023-2025 (count, mean and
                    median km, rejection %)
  050_kats_tau_105  2023-2025 by fault area: number of faults that led to
                    rejection

What the file holds, per model series (e.g. "Toyota COROLLA"):

  r    latest inspection year: {age: [inspections, rejection %, median km]}
       age = inspection year - first-use year; ages with < MIN_N
       inspections are left out.
  f    latest year, all ages together: rejection-causing faults per main
       fault area (order in AREAS), as counts.
  s    survival from age 10: [[age, share]], the share of cars inspected at
       age 10 that are still inspected at that age. From age 10 on, cars are
       inspected every year, so the yearly count of a cohort tracks how many
       are still in traffic. Ratios count(age a+1) / count(age a) are pooled
       over all first-use years and inspection years 2017-latest and
       multiplied together.
  med  age at which half of the cars inspected at 10 have dropped out, or
       null. Interpolated when the survival curve crosses 0.5 within the
       data; otherwise extrapolated (medx = true): the yearly drop-out
       rate is fitted as a straight line in age over ages 10-19 and continued
       (capped at age 40).
       Not given when imported used cars make the counts rise (survival
       above IMPORT_TOL; imp = true) or when the fit is not usable.

Caveats (also on the page): used imports join cohorts and make survival look
better; cars dropped out before age 10 (crashes, early scrapping, exports)
are not counted; a car that skips an inspection year counts as dropped out
for that year.

Run by hand once a year after Traficom publishes the new year's statistics
(usually in spring), then run tools/build.py:
    py tools/update_inspection.py
"""

import json
import math
import pathlib
import sys
import urllib.request

API = "https://trafi2.stat.fi/PXWeb/api/v1/fi/TraFi/Katsastuksen_vikatilastot/"
PAGE = "https://trafi2.stat.fi/PXWeb/pxweb/fi/TraFi/TraFi__Katsastuksen_vikatilastot/"
OLD, NEW, FAULTS = "010_kats_tau_101.px", "040_kats_tau_104.px", "050_kats_tau_105.px"
TOTAL = "Merkit yhteensä - Mallit yhteensä"
TIMEOUT = 120
CHUNK = 60          # model series per request (keeps each request well under the cell limit)
MIN_N = 50          # smallest cohort shown on the page for a rejection rate
MIN_STEP = 100      # smallest pooled count for one survival step
IMPORT_TOL = 1.05   # survival above this = used imports outweigh drop-outs; no lifetime
AREAS = [           # main fault areas, codes as in table 050
    "Ajoneuvon tunnistus (kaikki kohteet)",
    "Akselistot, pyörät ja jousitus (kaikki kohteet)",
    "Alusta ja kori (kaikki kohteet)",
    "Jarrujärjestelmät (kaikki kohteet)",
    "Kaasuajoneuvot (kaikki kohteet)",
    "Koeajo ja näkyvyys (kaikki kohteet)",
    "Lisätarkastukset (kaikki kohteet)",
    "Muut laitteet ja varusteet (kaikki kohteet)",
    "Ohjauslaitteet (kaikki kohteet)",
    "Sähkö- ja hybridi (kaikki kohteet)",
    "Valaisimet ja sähkölaitteet (kaikki kohteet)",
    "Ympäristöhaitat (kaikki kohteet)",
]
ALL_AREAS = "Kaikki pääkohteet ja kohteet"


def get(table, query=None):
    data = json.dumps({"query": query, "response": {"format": "json-stat2"}}).encode() if query else None
    req = urllib.request.Request(API + table, data=data,
                                 headers={"Content-Type": "application/json", "User-Agent": "CarFootprint/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def cells(d):
    """Yield ({dimension: code}, value) for a json-stat2 dataset."""
    dims = [(i, sorted(d["dimension"][i]["category"]["index"].items(), key=lambda kv: kv[1])) for i in d["id"]]
    sizes = d["size"]
    for n, v in enumerate(d["value"]):
        key, rest = {}, n
        for (name, cats), size in zip(reversed(dims), reversed(sizes)):
            key[name] = cats[rest % size][0]
            rest //= size
        yield key, v


def fetch(table, models, extra):
    """Model code -> rows, in chunks."""
    for i in range(0, len(models), CHUNK):
        q = [{"code": "Merkki ja mallisarja", "selection": {"filter": "item", "values": models[i:i + CHUNK]}}] + extra
        yield from cells(get(table, q))


def series_name(code):
    """Make model names comparable across tables: 'BMW 3' / 'BMW - 3-sarja' -> 'BMW 3-sarja'."""
    return code.replace(" - ", " ", 1)


def survival(counts):
    """counts: {(inspection_year, first_use_year): n} -> [[age, S]], pooled steps."""
    steps = {}
    for (iy, cy), n in counts.items():
        a, nxt = iy - cy, counts.get((iy + 1, cy))
        if a >= 10 and nxt is not None and n >= 20:
            s = steps.setdefault(a, [0, 0])
            s[0] += n
            s[1] += nxt
    out, S, a = [], 1.0, 10
    while a in steps and steps[a][0] >= MIN_STEP:
        S *= steps[a][1] / steps[a][0]
        out.append([a + 1, round(S, 3)])
        a += 1
    return out, steps


def median_life(surv, steps):
    """Age when S (from age 10) reaches 0.5, and whether it is extrapolated."""
    if not surv or max(s for _, s in surv) > IMPORT_TOL:
        return None, False
    prev_a, prev_s = 10, 1.0
    for a, s in surv:
        if s <= 0.5:
            return round(prev_a + (prev_s - 0.5) / (prev_s - s), 1), False
        prev_a, prev_s = a, s
    # Extrapolation: the yearly drop-out rate h(a) = -ln(ratio) grows roughly
    # linearly with age; fit h = alpha + beta * a over ages 10-19, weighted by
    # cohort size, and continue the curve until it reaches 0.5.
    pts = [(a, -math.log(steps[a][1] / steps[a][0]), steps[a][0]) for a in steps
           if 10 <= a <= 19 and steps[a][0] >= MIN_STEP]
    if len(pts) < 6 or surv[-1][0] < 18:
        return None, False
    w = sum(p[2] for p in pts)
    ma = sum(p[0] * p[2] for p in pts) / w
    mh = sum(p[1] * p[2] for p in pts) / w
    sxx = sum(p[2] * (p[0] - ma) ** 2 for p in pts)
    beta = sum(p[2] * (p[0] - ma) * (p[1] - mh) for p in pts) / sxx
    alpha = mh - beta * ma
    if beta <= 0:
        return None, False
    a, S = surv[-1]
    while S > 0.5 and a < 40:
        h = max(0.0, alpha + beta * a)
        S_next = S * math.exp(-h)
        if S_next <= 0.5:
            return round(a + (S - 0.5) / (S - S_next), 1), True
        a, S = a + 1, S_next
    return None, False


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    meta_new, meta_old, meta_f = get(NEW), get(OLD), get(FAULTS)
    years_new = meta_new["variables"][0]["values"]
    latest = max(years_new)
    models_new = meta_new["variables"][1]["values"]
    models_old = meta_old["variables"][1]["values"]
    models_f = meta_f["variables"][1]["values"]
    # 'BMW 3' (2017-2022) -> 'BMW 3-sarja' (2023-)
    known = {series_name(m) for m in models_new}
    old_map = {m: (m + "-sarja" if m + "-sarja" in known else m) for m in models_old}
    keep = lambda m: m == TOTAL or not m.endswith("Mallit yhteensä")

    counts, rej = {}, {}
    print("fetching", OLD, file=sys.stderr)
    for k, v in fetch(OLD, [m for m in models_old if keep(m)], [{"code": "Tiedot", "selection": {"filter": "item", "values": ["Lkm"]}}]):
        if v is None or not k["Käyttöönottovuosi"].isdigit():
            continue
        name = series_name(old_map[k["Merkki ja mallisarja"]])
        counts.setdefault(name, {})[(int(k["Katsastusvuosi"]), int(k["Käyttöönottovuosi"]))] = v
    print("fetching", NEW, file=sys.stderr)
    for k, v in fetch(NEW, [m for m in models_new if keep(m)],
                      [{"code": "Tiedot", "selection": {"filter": "item", "values": ["Lkm", "Hylkaysprosentti", "Mediaani"]}}]):
        if v is None or not k["Käyttöönottovuosi"].isdigit():
            continue
        name, iy, cy = series_name(k["Merkki ja mallisarja"]), int(k["Katsastusvuosi"]), int(k["Käyttöönottovuosi"])
        if k["Tiedot"] == "Lkm":
            counts.setdefault(name, {})[(iy, cy)] = v
        if str(iy) == latest:
            rej.setdefault(name, {}).setdefault(iy - cy, {})[k["Tiedot"]] = v
    print("fetching", FAULTS, file=sys.stderr)
    faults = {}
    for k, v in fetch(FAULTS, [m for m in models_f if keep(m)],
                      [{"code": "Katsastusvuosi", "selection": {"filter": "item", "values": [latest]}},
                       {"code": "Käyttöönottovuosi", "selection": {"filter": "item", "values": ["Vuodet yhteensä"]}},
                       {"code": "Vian pääkohde ja kohde", "selection": {"filter": "item", "values": [ALL_AREAS] + AREAS}},
                       {"code": "Tiedot", "selection": {"filter": "item", "values": ["Hylkaykset"]}}]):
        name = series_name(k["Merkki ja mallisarja"])
        faults.setdefault(name, {})[k["Vian pääkohde ja kohde"]] = v or 0

    out = {}
    for name in sorted(set(counts) | set(rej)):
        e = {}
        r = {str(a): [d["Lkm"], d.get("Hylkaysprosentti"), d.get("Mediaani")]
             for a, d in sorted(rej.get(name, {}).items()) if (d.get("Lkm") or 0) >= MIN_N}
        if r:
            e["r"] = r
        f = faults.get(name)
        if f and f.get(ALL_AREAS):
            e["f"] = [f.get(a, 0) for a in AREAS]
        surv, steps = survival(counts.get(name, {}))
        if surv:
            e["s"] = surv
            if max(v for _, v in surv) > IMPORT_TOL:
                e["imp"] = True
            med, ex = median_life(surv, steps)
            if med is not None:
                e["med"] = med
                if ex:
                    e["medx"] = True
        if e:
            out[name] = e
    total = out.pop(series_name(TOTAL), None)
    years = sorted({iy for c in counts.values() for iy, _ in c})
    doc = {
        "source": "Traficom, Katsastuksen vikatilastot (PxWeb), CC BY 4.0",
        "url": PAGE,
        "year": int(latest),
        "years": [years[0], years[-1]],
        "areas": AREAS,
        "all": total,
        "models": out,
    }
    path = root / "data" / "inspection.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"wrote {path} ({len(out)} model series, inspection year {latest})", file=sys.stderr)


if __name__ == "__main__":
    main()
