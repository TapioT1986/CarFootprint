# CarFootprint

Compare what cars really cost per year and how much CO₂ they emit, at your own annual mileage.

CarFootprint is a single-page calculator for people choosing between cars: new or used, petrol, diesel, hybrid, plug-in hybrid or electric. It is a hobby and climate project with no ads and no sponsors. The interface is available in Finnish and English.

**Status:** first working version. Prices, taxes, grid emissions and the model list describe Finland. The method works for any EU country once those inputs are changed.

## What it calculates

For up to four cars side by side:

- **Annual cost** (€/year, €/month, €/km): depreciation, cost of capital, energy, and other costs (tax, insurance, servicing, tyres).
- **Annual emissions** (kg CO₂e/year, g/km): driving emissions plus manufacturing emissions spread over the car's lifetime.
- **Break-even mileage:** the annual mileage at which one car becomes cheaper than another.

Every assumption is visible and editable.

## How it works

- **Depreciation:** residual value = price × (1 − rate)^years. If no rate is given, it is chosen by the car's average age during ownership (18% per year for a new car, down to 5% for a car of 15 years or more). Above-average mileage lowers the residual value further.
- **Real-world consumption:** the WLTP figure is multiplied by a brand-specific factor measured from cars' on-board fuel consumption meters (EEA data, about 9 million cars registered in the EU in 2021–2024). On average petrol cars use 20% and diesels 18% more than WLTP.
- **Plug-in hybrids:** default consumption matches the measured brand average (6.0 l/100 km across the EU, against a WLTP figure of 1.4).
- **Electric cars:** WLTP electricity consumption per model from the EEA register. Measured consumption is not collected from battery-electric cars, so the real-world factor of 1.20 is an assumption.
- **Electricity:** no source counts as zero-emission. Lifecycle values per generation type follow IPCC and UNECE.

## Known limitations

- Real-world factors are EU-wide brand averages. They are not model-specific and do not account for Finnish winters.
- The same factor is applied to cars registered before 2021, which the measurements do not cover.
- Manufacturing emissions, insurance and servicing costs are rough assumptions.
- The depreciation model is generic, not calibrated against used-car prices.
- 51 of the 216 electric and plug-in models have no model-specific electricity figure and fall back to a default.
- This is a draft, not a verified comparison.

## Data sources

| Data | Source | Licence |
| --- | --- | --- |
| Model list, CO₂ values, actual mileages | [Traficom open vehicle data](https://avoindata.suomi.fi/data/fi/dataset/ajoneuvojen-avoin-data), 30 June 2026 | CC BY 4.0 |
| Measured real-world fuel consumption | [EEA, Real-world CO₂ emissions from new cars and vans](https://climate-energy.eea.europa.eu/topics/transport/real-world-emissions/additional_information), reporting year 2024 | CC BY 4.0 |
| Electricity consumption of EVs and plug-in hybrids | [EEA, CO₂ emissions from new passenger cars](https://co2cars.apps.eea.europa.eu/), Finland 2025 | CC BY 4.0 |
| Grid emission factor | Finnish Energy (Energiateollisuus), 2025; Finnish Climate Change Panel | |
| Lifecycle emissions by generation type | IPCC AR5 (2014), UNECE (2021) | |

## Running it

Open `index.html` in a browser. No build step, no server, no tracking. Your inputs are stored in your own browser only.

## Repository layout

```
index.html                           the whole app, data included
LICENSE                              GNU AGPL-3.0
tools/template.html                  the page with __CATALOG__ / __RW__ placeholders
tools/build.py                       rebuilds index.html from the data
data/catalog.json                    588 car models
data/realworld.json                  measured consumption per brand
data/eea_obfcm_2024_aggregated.csv   EEA measured-consumption table (source data)
```

## Rebuilding the data

`python3 tools/build.py` rebuilds `index.html` from the JSON files in `data/` and needs only pandas.

To rebuild the model list from the original registers, download the two large source files into `sources/` and run `python3 tools/build.py --sources sources`:

- `TieliikenneAvoinData_*.csv` — the Finnish vehicle register, from [Traficom](https://avoindata.suomi.fi/data/fi/dataset/ajoneuvojen-avoin-data) (about 200 MB zipped).
- `eea_fi_*.csv` — [EEA new-car data](https://co2cars.apps.eea.europa.eu/) filtered to Country = FI. It carries the WLTP electricity consumption that the Finnish register does not record.

Both are too large to keep in the repository, so `sources/` is not committed.

## Licence

[GNU AGPL-3.0](LICENSE). You may use, study, change and share this freely. If you run a
modified version as a public service, you must publish your changes under the same licence.
The aim is that improvements to the calculation stay open to everyone.

## Suomeksi

CarFootprint vertaa, mitä autot oikeasti maksavat vuodessa ja paljonko ne päästävät omalla ajomäärälläsi. Mukana ovat uudet ja käytetyt autot, arvonalenema ja autojen omista mittareista mitattu todellinen kulutus. Avaa `index.html` selaimessa ja valitse kieleksi suomi.
