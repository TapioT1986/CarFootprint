"""Fetch the Finnish vehicle tax (ajoneuvovero) tables into data/vehicle_tax.json.

Source: Finlex open data, act 814/2024 amending the Vehicle Tax Act (1281/2003),
annex tables 1 (NEDC and older test methods) and 1 A (WLTP). The act took effect
on 1 January 2025 and its tables apply to tax from 1 January 2026.

The tables give the base tax (perusvero) per CO2 g/km in cents per day, one row
per gram from 0 to 400. The propulsion tax (käyttövoimavero) rates for passenger
cars are in section 11 of the act; they are fixed here with the same citation,
because the act states them in running text.

Plain Python, no third-party packages:
    python tools/vehicle_tax.py
"""
import json
import pathlib
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

ACT = "814/2024"
URL = "https://opendata.finlex.fi/finlex/avoindata/v1/akn/fi/act/statute/2024/814/fin@"
NS = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"


def text(e):
    return re.sub(r"\s+", " ", "".join(e.itertext())).strip()


def cents(s):
    return float(s.replace(",", "."))


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    names, tables = [], []
    for tb in root.iter(NS + "table"):
        rows = [[text(c) for c in tr] for tr in tb.iter(NS + "tr")]
        if len(rows) == 1 and rows[0][0].startswith("VEROTAULUKKO"):
            names.append(rows[0][0])
        elif len(rows) > 400:
            tables.append(rows)
    if names[:2] != ["VEROTAULUKKO 1", "VEROTAULUKKO 1 A"] or len(tables) < 2:
        sys.exit(f"unexpected table layout: {names}")
    out = {}
    for name, rows in zip(["t1", "t1a"], tables[:2]):
        data = [r for r in rows if r and re.match(r"^\d+", r[0])]
        grams = [int(re.match(r"^\d+", r[0]).group()) for r in data]
        if grams != list(range(401)):
            sys.exit(f"{name}: expected rows for 0..400 g/km")
        for r in data:  # euros per 365 days must follow from cents per day
            if abs(cents(r[1]) * 3.65 - cents(r[2])) > 0.01:
                sys.exit(f"{name}: inconsistent row {r}")
        out[name] = [cents(r[1]) for r in data]
    return out


def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    req = urllib.request.Request(URL, headers={"User-Agent": "CarFootprint build script"})
    with urllib.request.urlopen(req, timeout=60) as r:
        tables = parse(r.read())
    data = {
        "source": f"Ajoneuvoverolaki 1281/2003, muutos {ACT} (Finlex), voimassa 1.1.2026 alkaen",
        "url": "https://www.finlex.fi/fi/lainsaadanto/saadoskokoelma/2024/814",
        "note": "Base tax in cents per day for CO2 0..400 g/km (index = g/km; 400 = 400 or more). "
                "t1 = table 1 (NEDC and older methods), t1a = table 1 A (WLTP).",
        "ev_new_add": 17.80,
        "ev_new_from": "2021-10-01",
        "propulsion_per_100kg": {"D": 5.5, "E": 1.9, "P": 0.95},
        "propulsion_note": "Cents per day per started 100 kg of total mass, passenger cars, "
                           "Ajoneuvoverolaki 11 §: diesel 5.5, electricity 1.9, electricity and petrol 0.95.",
        "t1": tables["t1"],
        "t1a": tables["t1a"],
    }
    out = root / "data" / "vehicle_tax.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}: lowest {data['t1a'][0]} c/day, highest {data['t1a'][-1]} c/day")


if __name__ == "__main__":
    main()
