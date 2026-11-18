#!/usr/bin/env python3
"""How much a single used car's value differs from its model's typical value, from the Tax Administration data.

Source: the same Verohallinto taxation-value files as tools/budget_values.py (sources/henkiloautojen-
sovelletut-verotusarvot-<year>.xls): every car tax decision for a passenger car imported into Finland,
with the taxation value = the car's general retail value in Finland.

Method: decisions are grouped by make, model and fuel (groups with at least MIN_GROUP decisions). Within a
group each decision's value is first moved to "value when new" with the page's depreciation curve
(value / depreciation(age), as in budget_values.py), so cars of different ages are comparable. The ratio of
each car to its group median then shows how far an individual car sits from the typical one (equipment,
condition, mileage, version). The percentiles of that ratio over all groups are written to
data/resale_spread.json; the page uses the 25th and 75th percentiles as the resale-value scenario
("half of the cars fall in this range").

    py tools/resale_spread.py            # print the percentiles
    py tools/resale_spread.py --write    # also write data/resale_spread.json
"""
import json
import statistics
import sys

from budget_values import ROOT, decisions, dep_factor

MIN_GROUP = 20


def main():
    files, rows = decisions()
    groups = {}
    for r in rows:
        if r["value"] > 0 and r["age"] >= 0:
            groups.setdefault((r["make"], r["model"], r["fuel"]), []).append(r["value"] / dep_factor(r["age"]))
    ratios = []
    used = 0
    for v in groups.values():
        if len(v) < MIN_GROUP:
            continue
        med = statistics.median(v)
        ratios += [x / med for x in v]
        used += 1
    q = statistics.quantiles(ratios, n=20)  # 5 % steps
    pct = {"p10": q[1], "p25": q[4], "p50": q[9], "p75": q[14], "p90": q[17]}
    pct = {k: round(v, 3) for k, v in pct.items()}
    print(f"{len(ratios)} decisions in {used} model groups (>= {MIN_GROUP} decisions) from {', '.join(f.name for f in files)}")
    print("value of a single car / its model's median:", pct)
    if "--write" in sys.argv:
        out = ROOT / "data" / "resale_spread.json"
        out.write_text(json.dumps({
            "description": "Spread of a single car's value around its model's median (Tax Administration taxation values, "
                           "ages made comparable with the page's depreciation curve). p25/p75 = middle half of the cars.",
            "source": [f.name for f in files], "method": "tools/resale_spread.py",
            "decisions": len(ratios), "groups": used, "percentiles": pct}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
        print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
