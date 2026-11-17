# CarFootprint

Compare what cars really cost per year and how much CO₂ they emit, at your own annual mileage.

CarFootprint is a single-page calculator for people choosing between cars: new or used, petrol, diesel, hybrid, plug-in hybrid or electric. It is a hobby and climate project with no ads and no sponsors. The interface is available in Finnish and English.

**Status:** first working version. Prices, taxes, grid emissions and the model list describe Finland. The method works for any EU country once those inputs are changed.

## What it calculates

For up to four cars side by side:

- **Annual cost** (€/year, €/month, €/km): depreciation, financing, energy, and vehicle tax, servicing and repairs, and other costs (insurance, tyres).
- **Annual emissions** (kg CO₂e/year, g/km): driving emissions plus manufacturing emissions spread over the car's lifetime.
- **Break-even mileage:** the annual mileage at which one car becomes cheaper than another.

Every assumption is visible and editable.

## How it works

- **Depreciation:** residual value = price × (1 − rate)^years. If no rate is given, it is chosen by the car's average age during ownership: 17% a year under 3 years, 10–12% from 3 to 19 years, 10% after that. The rates are estimated from the Finnish Tax Administration's taxation values of 114,000 used cars imported in 2024–2026, comparing cars of the same model at different ages (method in `data/depreciation.json`). Above-average mileage lowers the residual value further.
- **Real-world consumption:** the WLTP figure is multiplied by a factor measured from cars' on-board fuel consumption meters (EEA data, cars registered in the EU 2021–2024). The factor is model-specific for 367 of the 588 models; the rest fall back to a brand or powertrain average, and the page says which one it used. On average petrol cars use 20% and diesels 18% more than WLTP, but individual models range from about 5% to over 40%.
- **Financing:** the part of the price not covered by your own money and trade-in is an annuity loan. Its cost is the interest and monthly fees paid during ownership; a loan still running when the car is sold is repaid from the sale. Own money tied up in the car is charged the return it would earn elsewhere. Defaults: 4.1% loan interest (Bank of Finland, new vehicle loans, May 2026), €12.50/month in fees, 2.5% return on own money (Bank of Finland, new term deposits, June 2026). Cars above your maximum price are flagged.
- **Vehicle tax:** the 2026 tables of the Vehicle Tax Act (amendment 814/2024, fetched from Finlex open data by `tools/vehicle_tax.py`). The base tax follows the official CO₂ figure, worked out from the model's official consumption: NEDC table 1 for model years up to 2017, WLTP table 1 A after that. Electric cars from model year 2022 on are treated as first registered after 1 October 2021 and pay the higher EV base tax; plug-in hybrids pay the lowest band. Diesel, electric and plug-in hybrid cars also pay the propulsion tax per started 100 kg of total mass. Total mass is not in the model list yet, so it is an editable assumption by powertrain (diesel 2,000 kg, electric 2,200 kg, plug-in hybrid 2,300 kg).
- **Servicing and repairs rise with mileage:** the car's value is the level below 80,000 km (a rough assumption). Per kilometre it is multiplied by 2.1 between 80,000 and 160,000 km and 2.8 beyond for combustion cars and hybrids, and by 2.3 and 3.6 for electric cars (from a lower starting level), averaged over the distance driven during ownership. The factors come from Consumer Reports owner surveys (US, 2020); only the rise is taken from them, not the dollar amounts.
- **Inspections and lifetime (information only):** each car card shows the model's periodic-inspection failure rate at the car's age (latest year, Traficom), the fault areas that most often caused failures, and how many of the cars inspected at 10 years were still inspected at 20. From 10 years on, cars are inspected every year, so a model year's inspection count tracks how many are still on the road; ratios from year to year are pooled over all model years (inspections 2017–2025). When more than half are still on the road at 20, the age at which half have left is an estimate: the yearly drop-out rate is extended as a straight line fitted over ages 10–19. Traficom groups models by series (all powertrains together); cars imported used raise the counts, and models whose counts rise more than 5% get no lifetime. The Lifetime field used for manufacturing emissions is unchanged.
- **Monthly budget (optional):** monthly outgoings are what leaves your account each month while the loan runs: the loan payment with fees, plus energy and other costs spread over the months. Depreciation and the lost return on own money are not monthly bills, so they are left out; monthly outgoings therefore differ from the annual cost / 12. If the loan is shorter than the ownership period, the page also shows the outgoings after it. Cars over the monthly budget are flagged.
- **Example cars follow the maximum price:** a Golf (Finland's typical car), a Toyota full hybrid and the most common electric model that fits the budget, each the youngest model year whose estimated price fits. Prices are estimated from the Tax Administration's taxation values (`data/budget_cars.json`).
- **Older cars:** cars first registered up to 2017 were rated on the old NEDC test. For them the page uses the model's own NEDC figure for that year from the Finnish register, and adds the NEDC-to-real-world gap measured by the ICCT (8% for 2001 cars, 38% for 2014, 40% for 2016, linear in between).
- **Plug-in hybrids:** default consumption matches the measured brand average (6.0 l/100 km across the EU, against a WLTP figure of 1.4).
- **Electric cars:** WLTP electricity consumption per model from the EEA register (Finnish registrations 2025; 2020–2022 for models no longer sold new). Measured consumption is not collected from battery-electric cars, so the real-world factor of 1.20 is an assumption. Battery wear is not modelled; the page reminds users to check the battery of an older car.
- **Manufacturing emissions** follow the ICCT's 2025 EU life-cycle study for a medium-size car: making and recycling the car without its battery is 8.2 t CO₂e for petrol, diesel and hybrid cars, 8.6 t for plug-in hybrids and 7.5 t for electric cars. The battery adds 72.8 kg CO₂e per kWh (NMC622 cells weighted by where they are made). Default battery sizes are the EU 2023 averages for medium-size cars (53.4 kWh electric, 13.3 kWh plug-in hybrid), or the size in the model name where the register gives one (e.g. Nissan Leaf 40 kWh); users can change it.
- **Electricity:** no source counts as zero-emission. Lifecycle values per generation type follow IPCC and UNECE.
- **Energy price range:** each result card also shows the yearly cost at the cheapest and dearest energy prices of the last 15 years: the lowest and highest 12-month average price of petrol, diesel and home electricity (Statistics Finland khi/11xx and ehi/13rb), converted into today's money with the consumer price index (khi/11xs, 2005=100). `tools/update_prices.py` computes them monthly into `data/prices.json` (`ranges`). The low end puts every energy at its cheapest at once and the high end at its dearest; a current price outside the range widens it. Other costs have no sourced range yet, so they are not varied. "More about the ranges" under the results lists the figures, periods, sources and assumptions.
- **How firm is the ranking:** under the results the page changes one input at a time and finds the nearest value at which the cheapest car changes (bisection), showing the two nearest, e.g. "the cheapest changes if electricity costs over €0.35/kWh". Searched: mileage 2,000–50,000 km, fuel and electricity prices from half to double, ownership 1–20 years, depreciation from half to double (one factor for all cars). These are search limits, not forecasts; no ranges are shown, because there is no sourced basis for other costs yet.
- **Shareable link:** "Share comparison" puts the changed settings and the cars into the part of the link after `#`, in a short readable form (`y7~a22000~eB~pc771_P17500_A6`): untouched example cars are just their slot, register models are a row number with a checksum, and only values the user changed are stored; everything derived (real-world consumption, NEDC data) is recalculated. A typical link is 15–100 characters. Older compressed links (`z`/`j`) still open. Browsers never send that part to the server, and the page collects nothing. Opening a shared link keeps the opener's own saved cars so they can be restored.
- **On phones:** a summary bar at the bottom shows each car's yearly cost (and which is cheapest and lowest-emission) until the result cards are on screen; tapping it scrolls to them. Financing and energy settings sit in one collapsed "More settings" section, whose heading says how many values differ from the defaults.
- **Simple default view:** the page is laid out as steps 1 (your driving), 2 (cars to compare) and 3 (result). Fields worth filling in yourself are marked in blue with a dot (mileage, maximum price, payment; each car's model, price, age and odometer). Everything else on a car card (powertrain, consumption, costs, emissions, inspection data) is under "Fine-tune", whose heading counts values that differ from the model's defaults. About 20 controls show by default instead of 60.
- **Simple start:** "Your driving" asks only for annual mileage, maximum price and payment: cash (own money = maximum price), partly on loan (the default €6,000) or fully on loan (0). The choice only sets the own-money field, so it is worked out from that field and needs no saved value of its own; ownership period, monthly budget and the exact amount are under More settings.

Feedback and bug reports: [GitHub issues](https://github.com/TapioT1986/CarFootprint/issues/new). The page is a beta; its header shows the version number and the date of the latest release (`data/version.json`, raised by `python tools/build.py --release`).

## Known limitations

- Real-world factors are EU-wide and do not account for Finnish winters.
- Model-level consumption comes from a 13.7% sample of the 2.1 GB per-vehicle file (12 evenly spaced slices), not the whole of it. Models below 50 sampled vehicles fall back to a brand average.
- The EEA measurements cover cars registered 2021–2024. WLTP cars from 2018–2020 get the same factor; NEDC cars get the ICCT gap instead, which is an EU average, not model-specific.
- Manufacturing emissions are for a medium-size car; small cars take less to make and large ones more. Insurance and the starting level of servicing costs are rough assumptions.
- The mileage factors for servicing and repairs come from US data. Battery wear adds no cost: it shortens the range but barely raises consumption.
- Total mass for the propulsion tax is an assumption by powertrain, not the model's own mass. Pending government proposal HE 173/2026 (about €6 a year less base tax for combustion cars over 10 years old) is not included.
- Depreciation is calibrated on imported used cars, which tend to be in better condition than the average car sold in Finland. It is one rate for all models.
- 10 of the 216 electric and plug-in models have no model-specific electricity figure and fall back to a default.
- The example cars' prices are estimates from the Tax Administration's taxation values of imported used cars, not live market prices.
- This is a draft, not a verified comparison.

## Data sources

| Data | Source | Licence |
| --- | --- | --- |
| Model list, CO₂ values, actual mileages | [Traficom open vehicle data](https://avoindata.suomi.fi/data/fi/dataset/ajoneuvojen-avoin-data), 30 June 2026 | CC BY 4.0 |
| Measured real-world fuel consumption, per brand and per model | [EEA, Real-world CO₂ emissions from new cars and vans](https://climate-energy.eea.europa.eu/topics/transport/real-world-emissions/additional_information), reporting year 2024 | CC BY 4.0 |
| Electricity consumption of EVs and plug-in hybrids | [EEA, CO₂ emissions from new passenger cars](https://co2cars.apps.eea.europa.eu/), Finland 2025, and 2020–2022 via [Discodata](https://discodata.eea.europa.eu/) | CC BY 4.0 |
| Vehicle tax tables (2026) | [Vehicle Tax Act 1281/2003, amendment 814/2024 (Finlex)](https://www.finlex.fi/fi/lainsaadanto/saadoskokoelma/2024/814) |
| Periodic inspections by model and age, fault areas, lifetime estimate | [Traficom, Katsastuksen vikatilastot (PxWeb)](https://trafi2.stat.fi/PXWeb/pxweb/fi/TraFi/TraFi__Katsastuksen_vikatilastot/), inspections 2017–2025 | CC BY 4.0 |
| Rise of servicing and repair costs with mileage | [Consumer Reports, EV ownership cost, chapter 2 (2020)](https://advocacy.consumerreports.org/wp-content/uploads/2020/10/TCO-Fact-Sheet-Chapter-2-FINAL.pdf) |
| Depreciation by age | [Finnish Tax Administration, applied taxation values of used cars](https://www.vero.fi/henkiloasiakkaat/omaisuus/autovero/autoveron-maara/ajoneuvojen-sovellettuja-verotusarvoja/), 2024–2026 | |
| Manufacturing and battery emissions | [ICCT, Life-cycle GHG emissions from passenger cars in the EU, 2025 update](https://theicct.org/publication/electric-cars-life-cycle-analysis-emissions-europe-jul25/) | |
| NEDC-to-real-world gap | [ICCT, From laboratory to road: a 2018 update](https://theicct.org/publication/from-laboratory-to-road-a-2018-update/) | |
| Fuel prices | [Statistics Finland, StatFin table 11xx](https://pxdata.stat.fi/PxWeb/pxweb/fi/StatFin/StatFin__khi/statfin_khi_pxt_11xx.px/), monthly | CC BY 4.0 |
| Electricity prices | [Statistics Finland, StatFin table 13rb](https://pxdata.stat.fi/PxWeb/pxweb/fi/StatFin/StatFin__ehi/statfin_ehi_pxt_13rb.px/), monthly | CC BY 4.0 |
| Grid emission factor | Finnish Energy (Energiateollisuus), 2025; Finnish Climate Change Panel | |
| Lifecycle emissions by generation type | IPCC AR5 (2014), UNECE (2021) | |

## Running it

Open `index.html` in a browser. No build step, no server, no tracking. Your inputs are stored in your own browser only.

## Repository layout

```
index.html                           the whole app, data included
og-image.png                         social preview image
LICENSE                              GNU AGPL-3.0
tools/template.html                  the page with __CATALOG__ / __RW__ / __VTAX__ placeholders
tools/build.py                       rebuilds index.html from the data
tools/update_prices.py               fetches prices from Statistics Finland
tools/vehicle_tax.py                 fetches the vehicle tax tables from Finlex (run when the law changes)
tools/update_inspection.py           fetches Traficom inspection statistics (GitHub runs it each spring)
tools/og-image.html                  source for the preview image
tools/render_og.py                   renders og-image.png (needs playwright)
.github/workflows/update-prices.yml  monthly price refresh
data/catalog.json                    588 car models
data/prices.json                     latest fuel and electricity prices
data/version.json                    page version number and release date
data/eea_obfcm_2024_models.csv       measured consumption per model
data/realworld.json                  measured consumption per brand
data/eea_obfcm_2024_aggregated.csv   EEA measured-consumption table (source data)
data/eea_ev_consumption_fi_2020_2022.csv  electricity use of models no longer sold new
data/depreciation.json               depreciation rates by age, with method and caveats
data/budget_cars.json                example-car candidates and their estimated value when new
data/vehicle_tax.json                vehicle tax tables 1 and 1 A and propulsion tax rates, with source
data/inspection.json                 inspection failure rates, fault areas and survival by model series
```

## Price updates

`tools/update_prices.py` pulls the current consumer prices of petrol, diesel and household
electricity from Statistics Finland's StatFin API into `data/prices.json`, and
`tools/build.py` bakes them into the page as its default values. A GitHub Action runs both
on the 5th of each month and commits the result if anything changed.

- **Fuel:** [table 11xx](https://pxdata.stat.fi/PxWeb/pxweb/fi/StatFin/StatFin__khi/statfin_khi_pxt_11xx.px/),
  average prices of 95 E10 petrol and diesel, published with the monthly consumer price
  index, a few weeks after the month ends.
- **Electricity:** [table 13rb](https://pxdata.stat.fi/PxWeb/pxweb/fi/StatFin/StatFin__ehi/statfin_ehi_pxt_13rb.px/),
  the total price including network charges and taxes for a household using
  5 000-15 000 kWh a year. Updated quarterly, so it runs a few months behind.

The page shows which month each price describes.

## Rebuilding the data

`python3 tools/build.py` rebuilds `index.html` from the JSON files in `data/` and needs only Python 3.10+, no extra packages.

To rebuild the model list from the original registers, download the two large source files into `sources/` and run `python3 tools/build.py --sources sources` (this needs pandas):

- `TieliikenneAvoinData_*.csv` — the Finnish vehicle register, from [Traficom](https://avoindata.suomi.fi/data/fi/dataset/ajoneuvojen-avoin-data) (about 200 MB zipped).
- `eea_fi_*.csv` — [EEA new-car data](https://co2cars.apps.eea.europa.eu/) filtered to Country = FI. It carries the WLTP electricity consumption that the Finnish register does not record.

Both are too large to keep in the repository, so `sources/` is not committed.

Inspection statistics come straight from Traficom's statistics API, no download needed: `python3 tools/update_inspection.py` (standard library only) writes `data/inspection.json`; then rebuild. Traficom publishes a new year each spring; `.github/workflows/update-inspection.yml` does this automatically on 20 May, June and July and commits only if the figures changed.

## Licence

[GNU AGPL-3.0](LICENSE). You may use, study, change and share this freely. If you run a
modified version as a public service, you must publish your changes under the same licence.
The aim is that improvements to the calculation stay open to everyone.

## Suomeksi

CarFootprint vertaa, mitä autot oikeasti maksavat vuodessa ja paljonko ne päästävät omalla ajomäärälläsi. Mukana ovat uudet ja käytetyt autot, arvonalenema ja autojen omista mittareista mitattu todellinen kulutus. Avaa `index.html` selaimessa ja valitse kieleksi suomi.
