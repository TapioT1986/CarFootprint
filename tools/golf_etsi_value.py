#!/usr/bin/env python3
"""Value when new (v0) of the Volkswagen Golf eTSI (mild hybrid, 2020-), for the petrol example car.

Source: Finnish Tax Administration, applied taxation values of passenger cars 2025 and 2026
(vero.fi, "Ajoneuvojen sovellettuja verotusarvoja"), saved as
sources/henkiloautojen-sovelletut-verotusarvot-2025.xls and -2026.xls (about 19 MB, not committed).

Method, as for the other example cars in data/budget_cars.json: for each tax decision,
v0 = taxation value / depreciation(age), where depreciation follows the page's AGE_DEP curve
and age = decision date - first registration in years (fractional years between whole ones
use that year's rate). v0 is the median. The mild hybrid is "Bensiini ja sähkö" with a tax
rate of 6 % or more (plug-in hybrids pay about 3 %), first registered 2020 or later.
The same calculation for petrol Golfs is printed as a check against the existing v0.

Needs xlrd (pure Python): py -m pip install xlrd
    py tools/golf_etsi_value.py
"""
import datetime as dt
import pathlib
import statistics
import sys

import xlrd

AGE_DEP = [(0, .17), (3, .10), (6, .11), (10, .12), (20, .10)]  # as in template.html


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


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    files = sorted((root / "sources").glob("henkiloautojen-sovelletut-verotusarvot-*.xls"))
    if not files:
        print("no sources/henkiloautojen-sovelletut-verotusarvot-*.xls", file=sys.stderr)
        return 1
    etsi, petrol = [], []
    for f in files:
        book = xlrd.open_workbook(str(f), on_demand=True)
        for name in book.sheet_names()[1:]:
            sh = book.sheet_by_name(name)
            if sh.nrows < 2:
                continue
            head = sh.row_values(0)
            col = {h: i for i, h in enumerate(head)}
            for r in range(1, sh.nrows):
                v = sh.row_values(r)
                if str(v[col["Merkki"]]).upper() != "VOLKSWAGEN" or str(v[col["Malli"]]).upper().strip() != "GOLF":
                    continue
                try:
                    age = (day(v[col["Päätöspäivä"]]) - day(v[col["Ensirekisteröintipäivä"]])).days / 365.25
                    value, pct = float(v[col["Verotusarvo"]]), float(v[col["Veroprosentti"]])
                except (ValueError, KeyError):
                    continue
                if age < 0 or value <= 0:
                    continue
                fuel, year = v[col["Käyttövoima"]], day(v[col["Ensirekisteröintipäivä"]]).year
                if fuel == "Bensiini ja sähkö" and pct >= 6 and year >= 2020:
                    etsi.append(value / dep_factor(age))
                elif fuel == "Bensiini":
                    petrol.append(value / dep_factor(age))
    print(f"files: {', '.join(f.name for f in files)}")
    print(f"Golf eTSI (mild hybrid, 2020-): {len(etsi)} decisions, v0 median {statistics.median(etsi):.0f}")
    print(f"check, petrol Golf: {len(petrol)} decisions, v0 median {statistics.median(petrol):.0f}"
          " (data/budget_cars.json has 33400 from 116 decisions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
