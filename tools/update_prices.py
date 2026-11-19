#!/usr/bin/env python3
"""Fetch current Finnish fuel and electricity prices into data/prices.json.

Source: Statistics Finland's StatFin PxWeb API (CC BY 4.0).

  khi/11xx  Polttonesteiden keskihintoja, kuukausitiedot
        Average consumer prices of liquid fuels, EUR/l, VAT included. Updated
        with each monthly consumer price index release, so it runs only a few
        weeks behind. (ehi/12ge has the same series but is updated quarterly,
        which left the page months out of date.)
  ehi/13rb  Sähkön hinta kuluttajatyypeittäin
        Electricity price by consumer type, snt/kWh, monthly. We take the
        total price (energy + network + taxes) for a household using
        5 000-15 000 kWh a year, which is the bracket a home that charges
        a car falls into.

  khi/11xs  Kuluttajahintaindeksin kokonaisindeksit, kuukausitiedot (2005=100)
        Consumer price index (2005=100), used only to turn past prices into today's money
        for the price ranges below.

Price ranges ("ranges" in prices.json): for each energy, the lowest and highest
12-month average price over the last RANGE_YEARS years, in today's money (each
month's price x latest CPI / that month's CPI). The page uses them to show what
the yearly cost would have been at the cheapest and dearest energy prices of that
period. 12-month averages, because a car's energy bill builds up over the year
and a single expensive month does not describe it.

Fuel prices lag by a few weeks, electricity prices by a few months, so the
figures are the most recent official ones rather than today's pump price. Every value carries
the month it describes, and the page shows it.

Run by .github/workflows/update-prices.yml, or by hand:
    python3 tools/update_prices.py
"""

import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.request

API = "https://pxdata.stat.fi/PxWeb/api/v1/fi/StatFin"
PAGE = "https://pxdata.stat.fi/PxWeb/pxweb/fi/StatFin"
TIMEOUT = 60

FUEL_TABLE = "khi/11xx.px"
FUEL_URL = f"{PAGE}/StatFin__khi/11xx.px/"
FUEL_ROWS = {"petrol": "0700200", "diesel": "0700100"}   # 95 E10, diesel
ELEC_TABLE = "ehi/13rb.px"
ELEC_URL = f"{PAGE}/StatFin__ehi/13rb.px/"
ELEC_COMPONENT = "SSS"                           # Kokonaishinta / total price
ELEC_CONSUMER = "D"                              # household, 5 000-15 000 kWh/yr
CPI_TABLE = "khi/11xs.px"
CPI_URL = f"{PAGE}/StatFin__khi/11xs.px/"
CPI_CODE = "ip_0_2005"                            # Pisteluku, 2005=100 (the 2015 base starts only in 2015)
RANGE_YEARS = 15

# Refuse a value outside these bounds: a unit change upstream should fail
# loudly, not quietly put an absurd default in front of users.
SANE = {"petrol": (0.8, 4.0), "diesel": (0.8, 4.0), "electricity": (0.03, 1.0)}


def api(table, payload):
    req = urllib.request.Request(
        f"{API}/{table}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "CarFootprint/1.0"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def metadata(table):
    req = urllib.request.Request(f"{API}/{table}", headers={"User-Agent": "CarFootprint/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def latest_month(table):
    return metadata(table)["variables"][0]["values"][-1]


def item(code, values):
    return {"code": code, "selection": {"filter": "item", "values": values}}


def fetch_fuel():
    month = latest_month(FUEL_TABLE)
    codes = list(FUEL_ROWS.values())
    data = api(FUEL_TABLE, {
        "query": [item("timeperiod_m", [month]),
                  item("coicop_13_20160512", codes),
                  item("contentscode", ["khi-keskihinta"])],
        "response": {"format": "json-stat2"}})
    # json-stat2 names its dimensions differently between PxWeb versions, so
    # find the one whose categories are the fuel codes rather than guessing.
    order = next(d["category"]["index"] for d in data["dimension"].values()
                 if isinstance(d.get("category", {}).get("index"), dict)
                 and set(codes) <= set(d["category"]["index"]))
    out = {}
    for name, code in FUEL_ROWS.items():
        eur = data["value"][order[code]]
        if eur is None:
            raise ValueError(f"{name}: no value for {month}")
        out[name] = {"value": round(eur, 3), "unit": "EUR/l", "period": month, "url": FUEL_URL}
    return out


def fetch_electricity():
    month = latest_month(ELEC_TABLE)
    data = api(ELEC_TABLE, {
        "query": [item("timeperiod_m", [month]),
                  item("energia_48_20220905", [ELEC_COMPONENT]),
                  item("energia_49_20220905", [ELEC_CONSUMER]),
                  item("contentscode", ["hinta_snt_kwh"])],
        "response": {"format": "json-stat2"}})
    snt = data["value"][0]
    if snt is None:
        raise ValueError(f"electricity: no value for {month}")
    return {"electricity": {"value": round(snt / 100, 4), "unit": "EUR/kWh", "period": month,
                            "url": ELEC_URL}}


def monthly(table, query):
    """Whole monthly series of one selection, as {"2026M10": value}."""
    data = api(table, {"query": query, "response": {"format": "json-stat2"}})
    tdim = next(k for k in data["id"] if k.startswith("timeperiod"))
    index = data["dimension"][tdim]["category"]["index"]
    months = sorted(index, key=index.get) if isinstance(index, dict) else index
    if len(data["value"]) != len(months):
        raise ValueError(f"{table}: expected one value per month")
    return {m: v for m, v in zip(months, data["value"]) if v is not None}


def next_month(m):
    y, k = int(m[:4]), int(m[5:])
    return f"{y + (k == 12)}M{(k % 12) + 1:02d}"


def fetch_ranges():
    cpi = monthly(CPI_TABLE, [item("contentscode", [CPI_CODE])])
    last_cpi = max(cpi)
    series = {name: monthly(FUEL_TABLE, [item("coicop_13_20160512", [code]),
                                         item("contentscode", ["khi-keskihinta"])])
              for name, code in FUEL_ROWS.items()}
    series["electricity"] = {m: v / 100 for m, v in monthly(ELEC_TABLE, [
        item("energia_48_20220905", [ELEC_COMPONENT]),
        item("energia_49_20220905", [ELEC_CONSUMER]),
        item("contentscode", ["hinta_snt_kwh"])]).items()}
    out = {}
    for name, s in series.items():
        last = max(s)
        start = f"{int(last[:4]) - RANGE_YEARS}{last[4:]}"
        months = [m for m in sorted(s) if m > start and m in cpi]
        real = {m: s[m] * cpi[last_cpi] / cpi[m] for m in months}
        avgs = {}  # 12-month averages, only over 12 consecutive months
        for i in range(11, len(months)):
            win = months[i - 11:i + 1]
            if all(next_month(a) == b for a, b in zip(win, win[1:])):
                avgs[months[i]] = sum(real[m] for m in win) / 12
        if len(avgs) < 12 * (RANGE_YEARS - 2):
            raise ValueError(f"{name}: too few months for a {RANGE_YEARS}-year range")
        lo_end, hi_end = min(avgs, key=avgs.get), max(avgs, key=avgs.get)
        d = 4 if name == "electricity" else 3
        out[name] = {"lo": round(avgs[lo_end], d), "hi": round(avgs[hi_end], d),
                     "lo_end": lo_end, "hi_end": hi_end, "from": months[0], "to": last}
    out["cpi_month"] = last_cpi
    out["cpi_url"] = CPI_URL
    out["years"] = RANGE_YEARS
    out["method"] = ("Lowest and highest 12-month average price over the period, in the money of "
                     "cpi_month (price x CPI[cpi_month] / CPI[month], CPI 2005=100).")
    return out


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    out = root / "data" / "prices.json"

    try:
        prices = {**fetch_fuel(), **fetch_electricity()}
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
        print(f"price update failed: {e}", file=sys.stderr)
        return 1  # keep whatever is already committed
    try:
        prices["ranges"] = fetch_ranges()
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
        # the current prices are still worth updating; keep the previous ranges
        print(f"price range update failed, keeping the old ranges: {e}", file=sys.stderr)
        old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        if "ranges" not in old:
            return 1
        prices["ranges"] = old["ranges"]

    for name, (lo, hi) in SANE.items():
        for v in (prices[name]["value"], prices["ranges"][name]["lo"], prices["ranges"][name]["hi"]):
            if not lo <= v <= hi:
                print(f"{name} = {v} is outside {lo}-{hi}, refusing to write", file=sys.stderr)
                return 1

    prices["checked"] = dt.date.today().isoformat()
    prices["source"] = {
        "name": "Tilastokeskus / Statistics Finland, StatFin",
        "tables": [FUEL_TABLE.removesuffix(".px"), ELEC_TABLE.removesuffix(".px"),
                   CPI_TABLE.removesuffix(".px")],
        "url": FUEL_URL,
        "licence": "CC BY 4.0",
    }

    if out.exists():
        before = json.loads(out.read_text())
        if {k: v for k, v in before.items() if k != "checked"} == \
           {k: v for k, v in prices.items() if k != "checked"}:
            print("prices unchanged, file left alone", file=sys.stderr)
            return 0
    out.write_text(json.dumps(prices, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    for k in ("petrol", "diesel", "electricity"):
        print(f"  {k:<12} {prices[k]['value']} {prices[k]['unit']}  ({prices[k]['period']})",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
