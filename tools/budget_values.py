#!/usr/bin/env python3
"""Value when new (v0) of the example cars, from the Finnish Tax Administration's taxation values.

Source: Verohallinto, "Ajoneuvojen sovellettuja verotusarvoja" (vero.fi): every car tax decision for a
passenger car imported into Finland, with the taxation value = the car's general retail value in Finland.
Save the yearly files as sources/henkiloautojen-sovelletut-verotusarvot-<year>.xls (2025: 10 MB,
2026: 9 MB; not committed). Needs xlrd (pure Python): py -m pip install xlrd

Method: for each tax decision of the model (filter in data/budget_cars.json, "vero"),
v0 = taxation value / depreciation(age), where depreciation is the page's AGE_DEP curve
(data/depreciation.json) and age = decision date - first registration in years, fractional
years using that year's rate. v0 = median, rounded to 100 euros. The script also prints, for each
model year with at least 5 decisions, the real median taxation value next to the page's estimate
v0 x depreciation(median age), as a check.

    py tools/budget_values.py            # print the results
    py tools/budget_values.py --write    # also write v0 and decisions into data/budget_cars.json
"""
import datetime as dt
import json
import pathlib
import statistics
import sys

import xlrd

ROOT = pathlib.Path(__file__).resolve().parent.parent


def age_dep():
    d = json.loads((ROOT / "data" / "depreciation.json").read_text(encoding="utf-8"))
    return [tuple(x) for x in d["used_by_page"]]


AGE_DEP = age_dep()


def rate_at(a):
    r = AGE_DEP[0][1]
    for x, q in AGE_DEP:
        if a >= x:
            r = q
    return r


def dep_factor(age):
    d, t = 1.0, 0
    while t + 1 <= age:
        d *= 1 - rate_at(t)
        t += 1
    return d * (1 - rate_at(t)) ** (age - t)


def day(s):
    s = str(s).split(".")[0]
    return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def decisions():
    files = sorted((ROOT / "sources").glob("henkiloautojen-sovelletut-verotusarvot-*.xls"))
    if not files:
        sys.exit("no sources/henkiloautojen-sovelletut-verotusarvot-*.xls")
    out = []
    for f in files:
        book = xlrd.open_workbook(str(f), on_demand=True)
        for name in book.sheet_names()[1:]:  # first sheet is the cover page
            sh = book.sheet_by_name(name)
            if sh.nrows < 2:
                continue
            col = {h: i for i, h in enumerate(sh.row_values(0))}
            for r in range(1, sh.nrows):
                v = sh.row_values(r)
                try:
                    dec, reg = day(v[col["Päätöspäivä"]]), day(v[col["Ensirekisteröintipäivä"]])
                    out.append({"make": str(v[col["Merkki"]]).upper().strip(),
                                "model": str(v[col["Malli"]]).upper().strip(),
                                "fuel": str(v[col["Käyttövoima"]]).strip(),
                                "kw": float(v[col["Kw"]] or 0), "pct": float(v[col["Veroprosentti"]] or 0),
                                "value": float(v[col["Verotusarvo"]]), "reg": reg,
                                "age": (dec - reg).days / 365.25})
                except (ValueError, KeyError, TypeError):
                    continue
    return files, out


def match(r, f):
    if r["make"] != f["make"] or r["fuel"] != f["fuel"] or r["value"] <= 0 or r["age"] < 0:
        return False
    if r["model"] not in f["models"] and not any(r["model"].startswith(m + " ") for m in f.get("model_prefixes", [])):
        return False
    if "kw_max" in f and r["kw"] > f["kw_max"]:
        return False
    if "kw" in f and r["kw"] not in f["kw"]:
        return False
    if "pct_min" in f and r["pct"] < f["pct_min"]:
        return False
    if "reg_from" in f and r["reg"].year < f["reg_from"]:
        return False
    return True


def main():
    path = ROOT / "data" / "budget_cars.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    files, rows = decisions()
    print(f"{len(rows)} tax decisions from {', '.join(f.name for f in files)}")
    for c in data["candidates"]:
        sel = [r for r in rows if match(r, c["vero"])]
        if not sel:
            print(f"\n{c['label']}: no decisions")
            continue
        v0 = round(statistics.median(r["value"] / dep_factor(r["age"]) for r in sel) / 100) * 100
        print(f"\n{c['label']}: {len(sel)} decisions, v0 {v0} (was {c['v0']})")
        by = {}
        for r in sel:
            by.setdefault(r["reg"].year, []).append(r)
        for y in sorted(by):
            L = by[y]
            if len(L) < 5:
                continue
            real = statistics.median(r["value"] for r in L)
            a = statistics.median(r["age"] for r in L)
            est = v0 * dep_factor(a)
            print(f"  {y}: n={len(L):4d}  real median {real:7.0f}  page estimate {est:7.0f} at {a:4.1f} yr  {100 * (est / real - 1):+4.0f} %")
        c["v0"], c["decisions"] = v0, len(sel)
    if "--write" in sys.argv:
        data["source"]["files"] = [f.name for f in files]
        data["source"]["read"] = dt.date.today().isoformat()
        data["method"] = ("v0 = median over the model's tax decisions (filter 'vero') of taxation value / depreciation(age), "
                          "age = decision date - first registration, depreciation = the page's AGE_DEP curve; rounded to 100. "
                          "Computed by tools/budget_values.py. Model years available come from the Traficom register "
                          "(catalogue field 'years', 5th-95th percentile of first registration); a discontinued model's last "
                          "model year caps the range (e-Golf 2020, Auris 2019), because the register's 95th percentile also "
                          "includes later imports.")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"\nwrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
