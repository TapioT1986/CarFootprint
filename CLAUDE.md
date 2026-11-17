# CarFootprint – notes for Claude

## What this is

A single-page calculator (index.html) that compares what cars really cost per year and how much
CO₂ they emit, at the user's own annual mileage. New and used cars; petrol, diesel, hybrid,
plug-in hybrid and electric. Prices, taxes, grid emissions and the model list describe Finland.

- Live site: https://tapiot1986.github.io/CarFootprint/ (GitHub Pages, branch `main`, root)
- Repository: https://github.com/TapioT1986/CarFootprint
- Owner: Tapio (GitHub TapioT1986). A hobby and climate-activism project: no ads, no sponsors,
  no tracking.

## Working with the owner

- He writes in Finnish; answer in Finnish. Code comments in the page are Finnish, README and
  build scripts are English. The page itself is bilingual (FI/EN).
- He is new to Git and coding. Explain in plain language, keep answers short, and say what he
  needs to do (if anything) at the end.
- He prefers that Claude commits and pushes for him. Ask before pushing; a short summary of
  what changes is enough. Commit messages: short English summary line, optional body.

## Values that decide design questions

- **Licence AGPL-3.0, on purpose.** Keeping everything open fits his values; commercial
  companies can build their own calculators. Do not suggest relicensing.
- **Real, open, authoritative data** wherever possible (Traficom, EEA, Statistics Finland,
  Bank of Finland, Finnish Tax Administration, ICCT). Prefer reading data directly from the
  source over shipping big files.
- **Sources and links visibly on the page**, without hurting usability (the "Näin laskenta
  toimii" section, hints under inputs). Every new number needs a source or is labelled an
  assumption.
- Be honest about uncertainty and about results that do not favour electric cars.

## Layout

```
index.html            BUILT FILE – never edit by hand; run tools/build.py
tools/template.html   the page source: HTML, CSS, JS, FI/EN texts (I18N), placeholders
tools/build.py        builds data/*.json and index.html (plain Python; pandas only with --sources)
tools/update_prices.py  fuel and electricity prices from StatFin (khi/11xx, ehi/13rb)
.github/workflows/update-prices.yml  runs update_prices + build on the 5th of each month
data/catalog.json     588 models: [brand, model, pt, WLTP l/100km, count, "years", km/yr,
                      kWh/100km, kWh n, model real-world factor, its n, [[year, NEDC l/100km]...]]
data/realworld.json   brand/fleet real-world factors (EEA OBFCM)
data/prices.json      default prices; the page shows their month
data/depreciation.json  depreciation by age from Tax Administration values, with method
data/budget_cars.json   example-car candidates and value-when-new (v0)
data/eea_*.csv        source tables with provenance headers
```

Build: `python tools/build.py` (rebuilds index.html from data/). With the large source CSVs in
`sources/` (not committed): `python tools/build.py --sources sources`.

## How the calculation works (keep README and the page notes in sync when changing it)

- Depreciation: AGE_DEP by average age during ownership, from Tax Administration values
  (within-model comparison, data/depreciation.json); extra mileage over 15 000 km/yr lowers value.
- Financing: loan = price − own money (incl. trade-in); annuity loan, interest + monthly fees
  over the ownership period; own money tied up earns the "return on own money" rate.
- Real-world consumption: WLTP × EEA OBFCM factor (model, else brand, else fleet).
  Cars of model year ≤ 2017 use their own NEDC figure × (1 + ICCT gap by year).
- Electric: WLTP kWh from the EEA register (2025, or 2020–2022 for discontinued models) × 1.20.
- Example cars follow the maximum price (budget): Golf petrol, Toyota hybrid, most common EV that fits.
- Monthly budget (optional, field `monthly`): cash flow = loan payment incl. fees + (energy + other)/12
  while the loan runs; depreciation and return on own money are not cash. Shown on the summary
  card and flagged only when a budget is entered.

## Gotchas learned the hard way

- Browsers restore form values on reload by field position. The page resets every input to its
  HTML default (`defaultInputs()`) before applying saved settings. Keep it that way.
- Saved state lives in localStorage `carfootprint.v1`. When defaults or examples change in a
  way old saves would break, bump `EX_VERSION` and handle older saves explicitly.
- Default prices are tracked separately (PRICE_DEF) so untouched defaults update.
- Line endings are LF (.gitattributes). Keep files UTF-8, LF.
- index.html julkaistaan GitHub Pagesissa sellaisenaan – doctype, charset ja viewport-meta on oltava
  templatessa itsessään.
- On the owner's Windows PC Python runs as `py` (Python install manager), and Smart App Control
  blocks pandas DLLs. So the default build must stay free of third-party packages; do not ask him
  to turn Smart App Control off.
- Test in a real browser (FI and EN, phone width 390 px) and check the numbers by hand for at
  least one car before committing.

## Open ideas (not started)

- Age-dependent repair costs and EV battery health in the model.
- A "what the same yearly money buys" view, once the above exist.
- Golf mild-hybrids (2020+) as the petrol example for large budgets.
