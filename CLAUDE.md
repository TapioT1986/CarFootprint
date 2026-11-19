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
- He prefers that Claude commits and pushes for him. Standing permission (owner 2026-11-18): push automatically
  after testing; ask first only for especially large or radical changes (a short summary is enough). A push that
  changes the page itself raises the version number (see below); docs/tests/tools-only pushes do not (owner 2026-11-19). Commit messages: short English summary line, optional body.

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
- **Direct links to the exact source.** Every claim, assumption and average on the page links as directly as possible
  to the reliable source it comes from: the specific release, table, PDF or page that states the number (e.g. the Bank
  of Finland release of 30.6.2026 for the vehicle-loan rate), not a site's front page or a statistics index. Give the
  date of the figure and, where the source offers alternatives, name them ("new loans 4.08 %").
- **Keep the information on the page, fold it away (owner 2026-11-19).** Details, explanations and source references stay
  on the page as text (names, dates, table ids), so they still help if a link breaks; tidy the view for casual users by
  putting them behind "Lisätietoja"/details toggles, not by deleting them.
- **Pessimistic default when choosing.** When sources give several defensible values, use by default the one less
  favourable to the car (higher cost or emissions), say so on the page and show the other value. Example: loan rate
  4.40 % (stock of vehicle loans) rather than 4.08 % (new loans); return on own money 2.48 % (new term deposits)
  rather than 0.82 % (all deposits), because a higher return makes tied-up money cost more.

## Layout

```
index.html            BUILT FILE – never edit by hand; run tools/build.py
tools/template.html   the page source: HTML, CSS, JS, FI/EN texts (I18N), placeholders
tools/build.py        builds data/*.json and index.html (plain Python; pandas only with --sources)
tools/city_ratio.py   city/highway consumption ratios from UK VCA WLTP phase data (sources/, ~0.1 MB)
tools/update_prices.py  fuel and electricity prices from StatFin (khi/11xx, ehi/13rb) + 15-year ranges (CPI khi/11xs)
.github/workflows/update-prices.yml  runs update_prices + build on the 5th of each month
.github/workflows/update-inspection.yml  runs update_inspection + build on 20 May/June/July (Traficom's spring release)
data/catalog.json     588 models: [brand, model, pt, WLTP l/100km, count, "years", km/yr,
                      kWh/100km, kWh n, model real-world factor, its n, [[year, NEDC l/100km]...]]
data/realworld.json   brand/fleet real-world factors (EEA OBFCM)
data/prices.json      default prices; the page shows their month
data/version.json     page version number and date (header); raised by build.py --release (0.01) or --patch (0.001)
data/depreciation.json  depreciation by age from Tax Administration values, with method
data/budget_cars.json   example-car candidates and value-when-new (v0)
data/vehicle_tax.json   vehicle tax tables 1 / 1 A (c/day per g CO2) + propulsion rates;
                      from tools/vehicle_tax.py (Finlex open data, act 814/2024). Re-run when the law changes.
data/eea_ev_range_fi.csv  WLTP electric range per model (EEA, Finland 2025 and 2020-2024), from tools/ev_range.py
data/inspection.json  Traficom periodic inspections per model series: failure % by age (latest year), fault
                      areas, survival from age 10; from tools/update_inspection.py (PxWeb API, stdlib). Yearly.
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
  WLTP consumption is measured at the socket, so it already includes normal charging losses; the `loss` field (10 %)
  is an extra for household-socket charging (ADAC 8/2026: socket ~15 %, wallbox < 7 %), labelled as such on the page.
- Example cars follow the maximum price (budget): Golf petrol, Toyota hybrid, most common EV that fits.
  Petrol slot: petrol Golf (register ends at 2020) or Golf eTSI (BUDGET_CARS 7th field = register pt 'H'),
  youngest that fits, petrol Golf on a tie; name gets "(kevythybridi)".
- Example-car values when new (v0): tools/budget_values.py (xlrd, pure Python) reads the Tax Administration's
  taxation-value files in sources/ and each candidate's "vero" filter in data/budget_cars.json (Golf ≤ 110 kW, Corolla
  without Corolla Cross, Leaf 110 kW = 40 kWh, Golf eTSI = 'Bensiini ja sähkö' with tax rate ≥ 6 %), writes v0 with
  --write and prints real median value per model year vs the page's estimate. build.py injects BUDGET_CARS from the
  JSON (`__BUDGET_CARS__`); do not hard-code values in the template.
- Picking a model (autoPriceAge): fills age (youngest model year whose estimate fits the budget), price (MV0 = v0 per
  catalogue row from data/model_values.json, made by tools/budget_values.py --write with name matching incl. BMW
  "320D" -> "320", "I 30" = "I30"; >= 5 decisions, else 0) and odometer (age x the model's median km/yr), unless the
  user typed them (car.own.{price,age,odo}). c.priceAuto marks an estimate (unit text says so); age edits move an
  auto price and an auto odometer. Rerun budget_values.py --write when the catalogue changes (build zeroes a
  length mismatch).
  Each candidate also has `list_price` (importer price list, cheapest version, source and date) as a cross-check only;
  check by hand about once a year (Toyota PDFs use obfuscated fonts, VW lists are on api.k-auto.fi, Tesla's configurator
  needs JS).
- Vehicle tax (`vehicleTax()`): base tax from CO2 = official l/100km × 23.3 (petrol) / 26.4 (diesel),
  table 1 if NEDC (model year ≤ 2017) else 1 A; EV model year ≥ 2022 + 17.80 c/day; PHEV lowest band.
  Propulsion tax D 5.5 / E 1.9 / P 0.95 c/day per started 100 kg of total mass; mass is a per-powertrain
  assumption (c.mass, editable). Car field `tax` empty = automatic. "Other costs" no longer include tax
  (EX_VERSION 5 subtracts the old tax default from older saves).
- Manufacturing (car fields `make` = car without battery, `batt` = kWh for E/P): ICCT 2025 Table 1 (8.2 t
  B/D/H, 8.6 t P, 7.5 t E) + batt × 72.8 kg/kWh; default batt = battDef(row, pt): kWh in the model name (battFromName),
  else for E battEst = EVR km x row kWh/100 (EEA WLTP; 5-20 % above real gross, pessimistic), for P max(battEst, 13.3);
  no figures: 53.4 / 13.3. EX_VERSION 10 moves saved E/P cars whose batt equals the old PT default to battDef. Spread over `life` years. EX_VERSION 7 replaces old defaults (7/8/8/10/12 t) and keeps
  custom values (batt 0).
- Servicing and repairs (car field `serv`, level below 80 000 km): × servFactor() = average over the
  ownership km [odo, odo + km·years] of Consumer Reports 2020 band factors: ICE/hybrids 1 / 2.14 / 2.82,
  EV 1 / 2.33 / 3.58 (bands 0–80 467, –160 934, beyond). "Other costs" (`other`) = tyres and other
  (EX_VERSION 6 subtracts the servicing default from older saves). Battery wear adds no cost.
- Insurance: car fields `traf` (motor liability) and `kasko` (comprehensive), added to other costs in calc(). Defaults
  INS_DEF = Taloustaito comparisons 24.9.2026 and 20.10.2022, the higher average of the two: traf 200 (E 205), kasko
  B/D/H 520, P 700, E 835. PT_DEF.ins is the old combined default, kept only for splitIns(). EX_VERSION 8: splitIns()
  splits an old default `other` and leaves a custom one whole with traf = kasko = 0; y-links before v8 with X get the
  same in carFromShare(). EX_VERSION 9: untouched old defaults (traf 200, kasko = OLD_KASKO) move to INS_DEF.
  Share letters Y = traf, Z = kasko.
- Insurance choice (global `insKind`, last in GIDS so old link letters stay): full / partial / none comprehensive, in
  More settings above Financing with visible sources (ins_src). kaskoDef(pt) = INS_DEF kasko, x 0.37 for partial
  (Taloustaito 26.9.2025: partial 86 vs full 231 EUR/yr, 4 insurers; ratio chosen as the pessimistic option), 0 for none.
  Changing it moves cars whose kasko equals the previous default (insPrev, set in update()). The cost table shows the
  chosen cover and a source link (or 'assumption, no source') on every row.
- Tipping points (`tipping()`, `#sens`): winnerOf(totals) is the cheapest car; for km, pB/pD/pE (only if some car uses it),
  years and a common depreciation factor, tipSearch() scans 48 steps (years: whole years) from the current value each way
  and bisects the first change; the two nearest (relative distance) are shown, rounded towards the tipping side (finer when
  within 5 %; "nearly even" under 2 %). Search limits are labelled as limits, not ranges. Ranges (e.g. 4 200–5 100 €/yr)
  only with a sourced basis for each bound.
- Electric range (`evRangeText()`, `#evr<i>`): EVR[catalogue index] = WLTP km from data/eea_ev_range_fi.csv
  (tools/ev_range.py, stdlib, from the EEA data viewer CSVs for FI saved in sources/: 2025 provisional and 2020-2024
  final, `eea_fi_<year><F|P>*range*.csv`, 17-21 MB each; filter Status + year + Country FI and use "Download search
  results (CSV)"). build.py ev_range_for_page() matches like add_electricity and takes the 2025 figure, or 2020-2024
  first for rows whose register years end before 2025 (Golf PHEV 65 km, not the 2025 eHybrid's 128). 209/216 rows. Winter = NAF El Prix averages: mild −18 % (2025, −6…+8 °C), hard frost −38 % (2026,
  −7…−32 °C). Discodata's firewall blocks filtered SQL; use the data viewer's CSV download instead.
  build_catalog() checks for the Traficom file before importing pandas, so a sources/ folder with only small
  extracts keeps the plain build working.
- Resale range (`rsr` in update(), G.residK in calc()): RESALE = data/resale_spread.json from tools/resale_spread.py (Vero
  decisions grouped by make/model/fuel, >= 20 each, values moved to 'when new' with the page's curve; ratio to group median,
  p25 0.926 / p75 1.074). The result card shows the yearly total with the residual value at p75 and p25. Test case 12.
- Energy price range (`energyRange()`, `#rangeInfo`): PRANGE = prices.json `ranges` from update_prices.py: min/max of
  12-month average prices over 15 years in today's money (CPI khi/11xs ip_0_2005; the 2015 base starts only in 2015).
  Low/high = all energies at their extremes at once, widened to include the current price; totals rounded to 10 €.
  If the range fetch fails, update_prices keeps the old ranges and still updates prices.
- Inspections and lifetime (`inspText()`, information only, not in the calculation): build.py links catalogue
  rows to Traficom model series (`inspection_for_page`, longest name prefix; BMW 320D -> 3-sarja; new EVs sharing
  an old name excluded). Survival = pooled year-to-year inspection-count ratios from age 10 (annual inspections);
  median beyond the data = linear drop-out-rate extrapolation (ages 10-19), shown as an estimate, "over 25" above 25.
  Models with counts rising > 5 % (used imports) get no lifetime. The `life` field is still the flat assumption.
- €/km on the result card = driving energy (r.energy / km). Total cost per km and the yearly breakdown sit in the card's
  `details.sumd`. Owner's plan: switch to the cost of an extra km (energy + servicing rise + mileage depreciation) once
  those parts have good sources (the 0.2 % per 1 000 km depreciation adjustment has none yet).
- Monthly figures on the result card (`.mos`): "true cost" = total/12 (incl. depreciation) and "paid out" = cash flow =
  loan payment incl. fees + (energy + other)/12 while the loan runs (r.cash; r.cashAfter after a shorter loan);
  depreciation and return on own money are not cash. Always shown; below them the cash-purchase sum (loan 0) or own money
  + loan. Monthly budget (optional, field `monthly`) only adds the over-budget flag.
- Current car (c.mine, one car at most, share token C): toggle button `data-mine` on the card. Fields debt (share G) and
  debtYears (J, '' = loanYears): calc() gives it only that remaining loan. Global `tradeIn` (yes/no, last in GIDS): g().trade =
  value - debt of the current car, added to own money for the other cars (negative equity raises their loan). Result cards
  show the yearly and whole-period difference. Before 0.67 the current car had no loan at all (its value is own money tied up), labels say current value / age now / km now, it is never replaced by budget
  examples, and the other result cards show the difference to it (€/yr, t CO2e/yr). Data stays in localStorage.
- Switching-decision emissions (calc() swMake/swEm, whole ownership period, kg): current car 0 + driving; other cars: age < 1 = all of makeT,
  else makeT x years / max(years, life - age) (owner chose this pessimistic option B 2026-11-19; option A = 0 is named on the page).
  Shown on result cards only when a current car is marked (sw_keep / sw_vs). Test case 13 (new car).
- Battery health (car field `soh`, share letter H, string like dep/tax: '' = estimate): electric cars only, visible on the
  card. sohAuto = 100 - 2.3 x age (Geotab 28.4.2026, 22,700 EVs; earlier study 1.8 %/yr, pessimistic choice), floor 50.
  Range = WLTP x SOH, winter factors on top. Information only, not in the costs.
- Battery size on electric cars is visible next to SOH (plug-in hybrids keep it under Fine-tune). Range also scales by
  c.batt / battRef(c), where battRef = kWh in the model name (LEAF 40KWH) or battEst; battSrc() picks the unit text (batt_u_ref / batt_u_est /
  batt_u_noref when neither exists).
- Car card head: one field for name and model (`#pick<i>`, value = c.name). Focus selects the text (setTimeout for touch),
  typing searches, picking a model renames the car; leaving without a pick (blur, Escape) restores pickText(c).
  Free name: the pencil button (`data-ren`, `renaming`) edits c.name and sets c.ownName; the head then shows the name and
  the search field the model (pickText). An empty name returns to the model name. A share-link N token that differs
  from the model name restores ownName. newCar() keeps own/priceAuto/ownName/mine from saves.
- Estimates vs typed values: isEst(c,k) marks price/age/odo filled by the calculator (model pick or example car) with class
  `est` (dashed border + 'arvio' chip, explained in req_hint); typing sets c.own[k] and removes it. Share-link tokens P/A/O
  count as own values. The model search hint (`pickh0`) is shown on the first card only.
- Costs itemised (`costTable()`, `#costs`, below the result cards): energy per 100 km and per year, motor liability, comprehensive,
  vehicle tax, servicing, tyres and other, running costs total, then depreciation, financing and the total. On phones each
  row name sits on its own line above the car columns (CSS grid, --n = number of cars). Result cards also show the energy
  price used and its StatFin month (`priceText()`, PRICE_SRC injected by build.py).
- Consumption data quality (`qualText()`, `#q<i>`, visible on the car card): model measurement (n) / brand average /
  powertrain average / NEDC + ICCT gap / EV WLTP register / default / own figure (autoFuel false or kwh differs from the
  row's or PT default).
- Input validation: LIM (key = car field data-k or global id) gives sanity limits, LIM_OPT the fields that may be empty.
  markField() shows the error under the field (aria-invalid, `.errmsg`); an invalid car value is not stored, globals go
  through gv() (last valid value, else HTML default), and saves/links through gRaw(). New numeric fields need a LIM entry.
- City/highway share (global `city`, range 0-100 in step 1, last in GIDS): default 39 % = streets and private roads +
  public roads <= 60 km/h (Statistics Finland 12jx and 12k1, 2025). cityMix(s, r) scales fuel and electricity relative
  to the default, r = city/highway consumption from WLTP phases (city = Low + Medium, highway = High + Extra High,
  distance-weighted; EVs from city vs combined electric range): UK VCA type-approval data, tools/city_ratio.py over
  sources/vca_euro6_latest_<date>.zip, medians B 1.14, D 1.16, H 0.81 (full hybrids), P fuel 1.01, E 0.68, written with
  per-row model ratios (same make + first model word, >= 3 versions; 177 rows) to data/city_ratio.json, injected as
  CITY_R / CITY_M; cityRatio(c, fuel) picks the model figure first. VCA's MHEV/HEV labels are not trusted. Replaced
  the earlier US EPA ratios (owner asked for European WLTP data). At 39 % the measured consumption is unchanged.
- Mileage limits: typed field 1 000-300 000 km (LIM), slider to 100 000 (taxis averaged 61,725 km in 2018,
  Statistics Finland 22.3.2019). Tipping search goes to max(100 000, 2 x km); the break-even chart's axis stretches to
  1.2 x km above 45 000 (kmax, kstep) and its 'cheapest across' title takes the range from cross.range.
- Annual mileage: `#km` is a number field (the saved GIDS value, any typed value; spinner step 500); `#kmSlider` (step 500,
  owner's choice: 100 was too fiddly) shows the nearest step. Shortcut chips set #km exactly (smoke check 9).

## Gotchas learned the hard way

- Browsers restore form values on reload by field position. The page resets every input to its
  HTML default (`defaultInputs()`) before applying saved settings. Keep it that way.
- Shared links: `#s=y<EX_VERSION>~<globals>~<car>~<car>...` (readable, no compression). Globals: changed GIDS only,
  letter = GIDS index + value, `_`-separated. Car: base `eB/eE/eH` (untouched example, rebuilt from budget), `xB..`
  (edited example), `p<row base36><2-char checksum>` (register model), `nB..` (own car), then only fields that differ
  from that base (SHARE_F letters; `U` = consumption edited). Derived fields are recalculated, never stored.
  A new user-editable car field needs a SHARE_F letter. Old 'z'/'j' links (base64url JSON, migrateCars()) must keep
  opening: tests/old_share_links.json + smoke_checks.js check it; tests/share_states.js builds test states.
  Opening a link backs up the opener's save to `carfootprint.v1.prev` and offers a restore button.
- Saved state lives in localStorage `carfootprint.v1`. When defaults or examples change in a
  way old saves would break, bump `EX_VERSION` and handle older saves explicitly.
- Default prices are tracked separately (PRICE_DEF) so untouched defaults update.
- Changed rate defaults: OLD_RATE_DEFS lists old default loanRate/ownRate values; a save holding one gets the new default.
- Line endings are LF (.gitattributes). Keep files UTF-8, LF.
- index.html julkaistaan GitHub Pagesissa sellaisenaan – doctype, charset ja viewport-meta on oltava
  templatessa itsessään.
- On the owner's Windows PC Python runs as `py` (Python install manager), and Smart App Control
  blocks pandas DLLs. So the default build must stay free of third-party packages; do not ask him
  to turn Smart App Control off.
- Phones show stale cached pages (restored tabs), while GitHub Pages only sends max-age=600. build.py puts a
  hash of the page into `const BUILD`; checkFresh() fetches the page with cache:'reload' on load and when the tab
  becomes visible, and reloads once (sessionStorage guard) if the BUILD differs. Keep the `const BUILD = '...'` form.
- The header says "Beta 0.N – updated <date>" from data/version.json. Before each push that changes the page
  (index.html), run `py tools/build.py --release` once for a change in what the page does (raises N by one, 0.83 -> 0.84),
  or `--patch` for a cosmetic fix such as wording, links or layout (third decimal, 0.83 -> 0.831; owner 2026-11-19); both set today's date and include version.json in the last
  commit. A plain build only reads the file, so CI's rebuild check stays deterministic; the monthly price workflow
  does not bump it (the price note shows the price month). <title> and the meta
  description follow the language (applyLang). Feedback: the on-page channel below, or GitHub issues (no e-mail address on the page).
- Fonts are self-hosted in fonts/ (woff2, latin + latin-ext, OFL licences there), @font-face at the top of <style>: no
  Google Fonts, so no visitor IP goes to Google. The page must load nothing from other hosts (smoke check 13).
- Feedback channel (`#fb`, under the charts; done 2026-11-19): 👍/👎 sends at once, then optional text + "attach my comparison"
  (share link) as a comment on the same issue. FEEDBACK_URL in the template ('' hides the section) points to the Cloudflare
  Worker carfootprint-palaute.carfootprint.workers.dev (owner's account; subdomain chosen without his surname). Code in
  tools/feedback-worker/worker.js: the owner pastes it in the dashboard (Edit code -> Deploy) after changes; no GitHub link
  to Cloudflare. It creates issues in the private repo TapioT1986/CarFootprint-palaute with a fine-grained token (secret
  GITHUB_TOKEN, Issues read/write on that repo only, expires 19.11.2027, reminder task carfootprint-palauteavain), text var
  REPO. Stores no IP/cookies/device data; Workers Logs turned off in the dashboard; spam: origin check, honeypot `website`,
  length limits, in-memory rate limit 6/10 min. Testing from the page creates real issues (127.0.0.1:8765 is an allowed origin).
- Search engines: <head> has canonical and schema.org WebApplication JSON-LD; <body> starts with a <noscript> summary
  (FI + EN); sitemap.xml in the root. No analytics or verification tags.
- Phone layout (≤ 900 px): `#dock` is a fixed summary bar filled in update(), hidden (class `off`) by an
  IntersectionObserver while `#sums` is on screen; its height goes to `--dockh` (body padding, scroll-padding).
  `#more` (<details>) holds the financing and energy panels: closed on phones, opened by JS above 900 px;
  moreCount() counts GIDS inside it that differ from their HTML defaults. Closed by default on every screen size.
- Simple default view: `.req` marks the only fields users need to fill: annual mileage and the model search (blue border +
  dot, explained by `req_hint`); maximum price, payment, price, age and odometer are ready defaults or estimates; steps 1-3 are
  `.stepn` headings. Car cards show model search, price, age and odometer; the rest is in `details.carmore` (`cm<i>`),
  whose open state survives re-renders in `carOpen` (indices shifted on delete). carChanged() counts carToShare() tokens
  other than N/P/A/O/U, i.e. fields that differ from the model's defaults.
- Payment choice (`[data-pay]`, payState/setPay/renderPay) is derived from `own` vs `budget` (0 = loan, ≥ budget = cash,
  else part) and is not stored: saves and links keep only `own`. Cash follows budget changes (listener before update).
  `own` counts as changed in moreCount() only in the 'part' state.
- Long hints fold: an I18N string with '¦' shows the part before it and puts the rest (sources included) in
  `details.fold` ("Perustelut ja lähteet"; '¦¦' = user guidance, old name "Lisätietoja ja lähteet", fold_i) via fold(); applyLang and the card/cost-table renders call it. Owner's rule: keep
  information and sources on the page, fold them away. Result card shows total, monthly, financing, emissions; energy price
  and both ranges are in its `details.sumd`. User test guide: docs/kayttajatestit.md.
- Tyres (car field `rim`, share letter Q, 15-20 or 0 = included in "other"; default 17): tyreCost() from data/tyres.json
  (injected as TYRES): 4 x (summer + winter price at 16") x rim ratio x max(km/2 / 30 000 km x 1.2 for EV, 1/6 yr). Prices:
  Rengas Online 10.11.2026 via Easy Garage comparison (dearer shop), rim ratios from Rengas365 Hakkapeliitta R5 medians
  19.11.2026. Field `other` is now "Other costs" (washing etc.), default TYRES.misc_eur 250 (ADAC). EX_VERSION 11: an untouched
  old "tyres and other" default (PT_DEF.tyre) becomes the new default; a custom value keeps its sum with rim 0; old links with X
  get rim 0. Cross-check in the notes: Statistics Finland household survey 14pg (per car 2022: tyres 47, parts 98, servicing
  ~380 EUR; 2016: ~80, 135, ~1 000). Recheck prices about once a year. Test cases 15-17.
- Other-costs levels (globals `tyreLvl` 30-150, `servLvl` 30-200, % of default, last in GIDS = share letters u, v): `#more` section
  'Muut kulut' with sliders + chips `[data-set]` b/m/p from LVL (tyres: data/tyres.json `levels`, Rengas365 205/55 R16 19.11.2026:
  lower quartile 57 %, median 83 %, Premium 100 % = the Nokian anchor, which is the default; servicing: 42 % = Statistics Finland
  14pg 2022 vs 2016, 100 % default, 110 % = dealer ~10 % dearer, Ford/Promira via Taloustaito 31.5.2019) and Leave out chips that
  share `excl` with the cost-table buttons (setExcl); moving a slider re-includes. calc(): serv x G.servL, tyres x G.tyreL. Test case 18.
- 'perustelut' links (`why(k)`, class `why`): each 'Näin laskenta toimii' <li> has id `m-<key>` (dep, ex, fin, city, mine, month,
  km, real, old, phev, ev, serv, tyre, excl, elem, fuelem, src, tax, insp, make, share, range, ekm, loss, pick, var, tip, ins;
  EN also fi). One source list (owner 2026-11-20): sources and reasoning live in the notes items; hints in the calculator
  keep a short sentence + why link. Folds (¦) remain only for user guidance (req_hint, mine_hint, '¦¦'); the cost table
  keeps its short per-row source links and the energy-range panel its own sources.
  Car-field units, cost-table rows and some settings link there; the click handler scrolls, highlights (`.hl`) and adds a
  '← takaisin' link (`.whyback`) back to the field. No hash change (the hash carries share links). New notes items need an id.
- Section bar (`#secnav`, owner 2026-11-20): sticky, buttons [data-go] scroll to s-drive / s-cars / resultsH / s-notes without a
  hash change; scroll spy sets aria-current; on phones (<= 900 px) it hides while scrolling down and returns on scroll up
  (setTimeout throttle: the preview pane runs as a background page, so rAF and scroll events stall there; dispatch
  scroll events by hand when testing). html scroll-padding-top 64px keeps targets clear of it. Topic list `#ntoc` is built
  by buildToc() from the notes items' bold titles; its links are a.why, so they highlight and offer the back link.
- The break-even line chart (`#beChart`, `.charts.befirst`) is the first thing in the results section (owner 2026-11-19).
- Leaving costs out (global `excl`, last in GIDS, share letter t; a hidden text input, because type=hidden keeps no
  defaultValue): "s" servicing, "t" tyres, "o" other costs; buttons `[data-excl]` in the cost table, `#exclNote` under the results,
  calc() zeroes serv / tyre (r.tyre). Applies to all cars. Test case 14.
- Phone touch targets >= 44 px and small text >= 13 px (CSS block at the end of <style>; smoke check 11).
- Calculation tests: tests/calc_reference.py is a separate Python implementation of the method; tests/calc_cases.json holds
  8 cases with explicit inputs and its expected figures. CI runs the reference check, and smoke_checks.js (check 12)
  compares the page's calc() with them (0.5 EUR). When the method changes on purpose, change calc_reference.py the same
  way and run `py tests/calc_reference.py --write`; `--explain` prints case 1 step by step.
- tests/smoke.py runs on GitHub after every push (.github/workflows/test.yml): build check + tests/smoke_checks.js
  in headless Chromium. The same checks can be run in the built-in browser by evaluating smoke_checks.js.
- Test in a real browser (FI and EN, phone width 390 px) and check the numbers by hand for at
  least one car before committing.

## Open ideas (not started)

The prioritised plan is in ROADMAP.md (Finnish, 2026-11-18): calculation test suite first, then the keep-or-switch
calculator (trade-in, remaining loan, switching emissions), uncertainty scenarios, feedback channel and SEO, user testing.


- Use the inspection-based lifetime as the model default for `life` (owner chose information-only first, 2026-11).
- Per-model total mass from the Traficom register (needs the ~200 MB source file) for the propulsion tax.
- A Finnish or European source for the servicing-and-repair rise (now US Consumer Reports factors).
- A "what the same yearly money buys" view, once the above exist.

