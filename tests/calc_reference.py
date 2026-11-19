#!/usr/bin/env python3
"""Reference calculation for CarFootprint, written separately from the page's JavaScript.

The cases in tests/calc_cases.json describe cars and settings with every input given explicitly
(no catalogue lookups). This script computes the expected yearly figures from the documented
method (README "How the calculation works"), and tests/smoke_checks.js checks that the page's
calc() gives the same numbers. If either side changes the method, the check fails.

    py tests/calc_reference.py           # check that calc_cases.json matches this reference
    py tests/calc_reference.py --write   # recompute "expected" in calc_cases.json after an intended change
    py tests/calc_reference.py --explain # print case 1 step by step (the hand calculation)

Plain Python, no packages. Units: euros, km, litres, kWh, kg CO2e, all per year unless noted.
"""
import datetime as dt
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = ROOT / "tests" / "calc_cases.json"

# Method constants (README; tools/template.html has the same values with their sources)
AGE_DEP = [(0, .17), (3, .10), (6, .11), (10, .12), (20, .10)]   # depreciation by average age, Tax Administration
KM_ADJ = 0.002              # residual value -0.2 % per 1 000 km/yr above 15 000 km, per year (assumption)
SERV_KM = [80467, 160934]   # Consumer Reports bands, 50 000 and 100 000 miles
SERV_F = {"ice": [1, .060 / .028, .079 / .028], "ev": [1, .028 / .012, .043 / .012]}
CO2_PER_L = {"B": 23.3, "H": 23.3, "D": 26.4}
BATT_T_PER_KWH = 0.0728
CITY0 = 0.39
TYRES = json.loads((ROOT / "data" / "tyres.json").read_text(encoding="utf-8"))
CITY_R = json.loads((ROOT / "data" / "city_ratio.json").read_text(encoding="utf-8"))["ratios"]  # powertrain medians
LAST_NEDC = 2017
TOL = 0.5                   # euros or kg: rounding noise allowed between the two implementations


def dep_rate(age, years, dep):
    if dep not in ("", None):
        return float(dep) / 100
    mid, rate = age + years / 2, AGE_DEP[0][1]
    for a, r in AGE_DEP:
        if mid >= a:
            rate = r
    return rate


def loan_cost(principal, rate, fee, loan_years, own_years):
    """Annuity loan: interest and fees per ownership year, average balance, monthly payment incl. fee."""
    if principal <= 0:
        return 0.0, 0.0, 0.0
    n, m, i = round(loan_years * 12), round(own_years * 12), rate / 12
    pay = principal * i / (1 - (1 + i) ** -n) if i > 0 else principal / n
    bal, interest, fees, bal_sum = principal, 0.0, 0.0, 0.0
    for _ in range(m):
        bal_sum += bal
        if bal <= 0:
            continue
        it = bal * i
        interest += it
        fees += fee
        bal = max(0.0, bal - (pay - it))
    return (interest + fees) / own_years, bal_sum / m, pay + fee


def serv_factor(pt, a, b):
    f, edges = SERV_F["ev" if pt == "E" else "ice"], [0, *SERV_KM, math.inf]
    total = sum(max(0, min(b, edges[k + 1]) - max(a, edges[k])) * f[k] for k in range(len(f)))
    return total / (b - a)


def vehicle_tax(car, vtax, cur_year):
    pt, g = car["pt"], 0
    reg_year = cur_year - round(car["age"])
    table = vtax["t1a"]
    if pt in "BDH":
        g = round(car["fuel"] * CO2_PER_L[pt])
        if reg_year <= LAST_NEDC:
            table = vtax["t1"]
    base = table[max(0, min(400, g))]
    if pt == "E" and reg_year >= 2022:
        base += vtax["ev_new_add"]
    prop = vtax["propulsion_per_100kg"].get(pt, 0) * math.ceil(max(0, car["mass"]) / 100)
    return (base + prop) * 3.65   # cents per day -> euros per year


def tyre_cost(c, km):
    """Summer + winter set at the rim size; each set covers half the km; replaced when worn out or at max age."""
    rim = c.get("rim", TYRES["default_rim"])
    if not rim:
        return 0.0
    ratio = TYRES["rim_ratio"][str(min(20, max(15, round(rim))))]
    wear = km / 2 / TYRES["life_km"] * (TYRES["ev_factor"] if c["pt"] == "E" else 1)
    return 4 * (TYRES["anchor"]["summer_eur"] + TYRES["anchor"]["winter_eur"]) * ratio * max(wear, 1 / TYRES["max_age_years"])


def city_mix(share, r):
    return (share * r + 1 - share) / (CITY0 * r + 1 - CITY0)


def compute(case, vtax, cur_year):
    G, c = case["g"], case["car"]
    km, n, pt = G["km"], G["years"], c["pt"]
    el = 1.0 if pt == "E" else min(1, max(0, c["share"] / 100)) if pt == "P" else 0.0
    rate = dep_rate(c["age"], n, c.get("dep", ""))
    km_adj = max(0, 1 - KM_ADJ * max(0, km - 15000) / 1000 * n)
    resid = max(0, c["price"] * (1 - rate) ** n * km_adj * G.get("residK", 1))
    dep = (c["price"] - resid) / n
    # current car: its own remaining loan; other cars: own money + current car's net value (trade-in)
    if c.get("mine"):
        loan, loan_years = max(0, c.get("debt", 0)), (float(c.get("debtYears") or 0) or G["loanYears"])
    else:
        loan, loan_years = max(0, c["price"] - max(0, G["own"] + G.get("trade", 0))), G["loanYears"]
    per_year, avg_bal, pay = loan_cost(loan, G["loanRate"], G["loanFee"], loan_years, n)
    own_tied = max(0, (c["price"] + resid) / 2 - avg_bal)
    cap = per_year + own_tied * G["rate"]
    fuel_r = CITY_R["B" if pt == "E" else pt]
    litres = km / 100 * c["fuel"] * c["real"] * (1 - el) * city_mix(G["city"], fuel_r)
    kwh = km / 100 * c["kwh"] * c["real"] * el * (1 + G["loss"]) * city_mix(G["city"], CITY_R["E"])
    energy = litres * (G["pD"] if pt == "D" else G["pB"]) + kwh * G["pE"]
    tax = vehicle_tax(c, vtax, cur_year) if c["tax"] in ("", None) else float(c["tax"])
    # left out of the comparison by the user: "s" = servicing, "o" = tyres and other
    ex = G.get("excl", "")
    # price levels from the "Other costs" settings (share of the default; 1 = default)
    serv = 0 if "s" in ex else c["serv"] * serv_factor(pt, c["odo"], c["odo"] + km * n) * G.get("servL", 1)
    tyres = 0 if "t" in ex else tyre_cost(c, km) * G.get("tyreL", 1)
    other = tyres + (0 if "o" in ex else c["other"]) + c["traf"] + c["kasko"] + tax + serv
    total = dep + cap + energy + other
    drive = litres * (G["eD"] if pt == "D" else G["eB"]) + kwh * G["eEl"]
    batt = c["batt"] if pt in "EP" else 0
    make_t = (c["make"] + batt * BATT_T_PER_KWH) * 1000
    make = make_t / c["life"]
    # switching decision over the whole ownership: current car 0, new car (age < 1) all, used car years / remaining life
    sw_make = 0 if c.get("mine") else make_t if c["age"] < 1 else make_t * n / max(n, c["life"] - c["age"])
    cash = pay + (energy + other) / 12
    r = dict(dep=dep, resid=resid, cap=cap, energy=energy, tax=tax, serv=serv, tyres=tyres, other=other, total=total,
             drive=drive, make=make, em=drive + make, swMake=sw_make, swEm=drive * n + sw_make, pay=pay, cash=cash)
    return {k: round(v, 2) for k, v in r.items()}


def explain(case, vtax, cur_year):
    G, c = case["g"], case["car"]
    n = G["years"]
    rate = dep_rate(c["age"], n, c.get("dep", ""))
    print(f"Case: {case['name']}")
    print(f"Depreciation rate at average age {c['age'] + n / 2} = {rate:.0%}")
    resid = c["price"] * (1 - rate) ** n
    print(f"Residual value {c['price']} x (1 - {rate}) ^ {n} = {resid:.2f}; depreciation ({c['price']} - {resid:.2f}) / {n} = {(c['price'] - resid) / n:.2f} /yr")
    print(f"No loan (own money {G['own']} >= price): own money tied up on average ({c['price']} + {resid:.2f}) / 2 = {(c['price'] + resid) / 2:.2f},"
          f" lost return x {G['rate']} = {(c['price'] + resid) / 2 * G['rate']:.2f} /yr")
    litres = G["km"] / 100 * c["fuel"] * c["real"]
    print(f"Fuel {G['km']} / 100 x {c['fuel']} x {c['real']} = {litres:.1f} l x {G['pB']} = {litres * G['pB']:.2f} /yr (city share = default, factor 1)")
    sf = serv_factor(c["pt"], c["odo"], c["odo"] + G["km"] * n)
    print(f"Servicing {c['serv']} x band factor {sf:.4f} (odometer {c['odo']}-{c['odo'] + G['km'] * n} km) = {c['serv'] * sf:.2f} /yr")
    print(f"Other: tyres {c['other']} + motor liability {c['traf']} + comprehensive {c['kasko']} + tax {c['tax']} + servicing")
    print(f"Driving CO2e {litres:.1f} l x {G['eB']} = {litres * G['eB']:.1f} kg; manufacturing {c['make']} t / {c['life']} yr = {c['make'] * 1000 / c['life']:.1f} kg")
    print(json.dumps(compute(case, vtax, cur_year), indent=1))


def main():
    vtax = json.loads((ROOT / "data" / "vehicle_tax.json").read_text(encoding="utf-8"))
    data = json.loads(CASES.read_text(encoding="utf-8"))
    cur_year = dt.date.today().year
    if "--explain" in sys.argv:
        explain(data["cases"][0], vtax, cur_year)
        return 0
    bad = []
    for case in data["cases"]:
        got = compute(case, vtax, cur_year)
        if "--write" in sys.argv:
            case["expected"] = got
            continue
        for k, v in case.get("expected", {}).items():
            if abs(got[k] - v) > TOL:
                bad.append(f"{case['name']}: {k} expected {v}, reference gives {got[k]}")
    if "--write" in sys.argv:
        CASES.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {len(data['cases'])} cases to {CASES.relative_to(ROOT)}")
        return 0
    for b in bad:
        print(b)
    print(f"{len(data['cases'])} cases, {'OK' if not bad else f'{len(bad)} problem(s)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
