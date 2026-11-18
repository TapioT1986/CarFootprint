// Smoke checks for index.html, run inside the page (by tests/smoke.py, or pasted
// into a browser console). Returns a list of problems; an empty list means OK.
async () => {
  const problems = [];
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const fire = (el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); };
  const lang = document.documentElement.lang;

  // 1. Cards, summary cards and the cost chart show the same cars
  function sameCars(when) {
    const cards = [...document.querySelectorAll('#cars .car .head input')].map(e => e.value.trim());
    const sums = [...document.querySelectorAll('#sums .nm')].map(e => e.innerText.trim());
    if (!cards.length) problems.push(`${lang} ${when}: no car cards`);
    if (JSON.stringify(cards) !== JSON.stringify(sums))
      problems.push(`${lang} ${when}: cards ${JSON.stringify(cards)} but results ${JSON.stringify(sums)}`);
    const bars = document.querySelectorAll('#costChart svg circle').length;
    if (bars !== cards.length) problems.push(`${lang} ${when}: cost chart has ${bars} cars, cards ${cards.length}`);
    document.querySelectorAll('#sums .big').forEach((e, i) => {
      const v = parseFloat(e.textContent.replace(/[^\d,.-]/g, '').replace(',', '.'));
      if (!(v > 0)) problems.push(`${lang} ${when}: result ${i + 1} is "${e.textContent}"`);
    });
  }
  // 2. Nothing wider than the screen (the break-even chart scrolls in its own box)
  function fits(when) {
    const vw = document.documentElement.clientWidth;
    if (document.documentElement.scrollWidth > vw + 1)
      problems.push(`${lang} ${when}: page is ${document.documentElement.scrollWidth}px wide on a ${vw}px screen`);
    const wide = [...document.querySelectorAll('body *')]
      .filter(e => !e.closest('#beChart') && !e.closest('[hidden]'))
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > vw + 1; })
      .slice(0, 3).map(e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''));
    if (wide.length) problems.push(`${lang} ${when}: elements over the right edge: ${wide.join(', ')}`);
  }

  // 6. Phone summary bar: same cars and yearly costs as the result cards, each value fits its cell
  function dockOk(when) {
    const dock = $('dock');
    if (!dock || document.documentElement.clientWidth > 900) return;
    if (getComputedStyle(dock).position !== 'fixed') { problems.push(`${lang} ${when}: summary bar is not fixed`); return; }
    const vals = [...dock.querySelectorAll('.dv')].map(e => e.firstChild.textContent.trim());
    const bigs = [...document.querySelectorAll('#sums .big')].map(e => e.textContent.trim());
    if (JSON.stringify(vals) !== JSON.stringify(bigs))
      problems.push(`${lang} ${when}: summary bar shows ${JSON.stringify(vals)}, results ${JSON.stringify(bigs)}`);
    dock.querySelectorAll('.dc').forEach((c, i) => { const v = c.querySelector('.dv');
      if (v.scrollWidth > c.clientWidth + 1) problems.push(`${lang} ${when}: summary bar value ${i + 1} does not fit`); });
  }
  // 7. Tipping points: shown whenever there are two or more cars, and each one really changes the cheapest car
  function tipsOk(when) {
    const sens = $('sens');
    if (!sens || typeof tipping !== 'function') return;
    if (cars.length > 1 && !sens.textContent.trim()) problems.push(`${lang} ${when}: no "how firm is the ranking" line`);
    const G = g(), w0 = winnerOf(cars.map(c => calc(c, G).total)), rates = cars.map(c => calc(c, G).rate);
    for (const t of tipping(G) || []) {
      const x = t.k === 'years' ? t.x : t.x + t.dir * (t.k === 'km' ? 60 : t.k === 'dep' ? 0.004 : 0.002);
      const w = t.k === 'km' ? winnerOf(cars.map(c => calc(c, G, x).total))
        : t.k === 'dep' ? winnerOf(cars.map((c, i) => calc({...c, dep: rates[i] * x * 100}, G).total))
        : winnerOf(cars.map(c => calc(c, {...G, [t.k]: x}).total));
      if (w === w0) problems.push(`${lang} ${when}: tipping point ${t.k} = ${t.x} does not change the cheapest car`);
    }
  }
  // 8. Energy price range: each car's yearly cost lies inside its range (rounded to 10 €)
  function rangeOk(when) {
    if (typeof energyRange !== 'function' || !PRANGE) return;
    const G = g();
    cars.forEach((c, i) => { const r = energyRange(c, G), t = calc(c, G).total;
      if (!r || r[0] > t + 5 || r[1] < t - 5) problems.push(`${lang} ${when}: car ${i + 1} cost ${Math.round(t)} outside its range ${r}`); });
  }
  const _sameCars = sameCars;
  sameCars = when => { _sameCars(when); dockOk(when); tipsOk(when); rangeOk(when); };
  const info = $('rangeInfo'); if (info) info.open = true; // the range table must fit the screen too

  sameCars('on load'); fits('on load');

  // 9. Each mileage shortcut sets exactly its own value (a slider step once rounded 11 800 to 12 000)
  const km0 = g().km;
  document.querySelectorAll('.chip[data-km]').forEach(b => { b.click();
    if (g().km !== +b.dataset.km) problems.push(`${lang}: shortcut ${b.dataset.km} km sets ${g().km} km`);
    const sl = $('kmSlider'); if (sl && +sl.value !== g().km) problems.push(`${lang}: slider shows ${sl.value} km, field ${g().km} km`); });
  // the typed mileage moves the slider, and the slider fills the field
  fire($('km'), '23400'); await wait(30);
  if ($('kmSlider') && $('kmSlider').value !== '23400') problems.push(`${lang}: typing 23400 km moves the slider to ${$('kmSlider').value}`);
  if ($('kmSlider')) { fire($('kmSlider'), '31000'); await wait(30);
    if ($('km').value !== '31000') problems.push(`${lang}: slider at 31000 km but the field shows ${$('km').value}`); }
  const kmEl = $('km'); kmEl.value = km0; kmEl.dispatchEvent(new Event('input', {bubbles: true})); await wait(50);

  // 3. Example cars follow the maximum price, and results follow the cards
  const budget = $('budget'), before = budget.value;
  for (const v of ['30000', '6000']) {
    fire(budget, v); await wait(50);
    sameCars(`maximum price ${v}`); fits(`maximum price ${v}`);
  }
  fire(budget, before); await wait(50);

  // 4. Model search shows a visible list and picking a model updates everything
  const pick = $('pick0');
  if (pick) {
    pick.focus(); fire(pick, 'golf'); await wait(50);
    const box = $('sg0'), opt = box && box.querySelector('button');
    if (!box || box.hidden || !opt) problems.push(`${lang}: model search shows no suggestions for "golf"`);
    else {
      const bg = getComputedStyle(box).backgroundColor;
      if (bg === 'transparent' || /rgba\(.*,\s*0\)$/.test(bg)) problems.push(`${lang}: model suggestion list is transparent`);
      const label = opt.textContent; opt.click(); await wait(50);
      const name = $('cars').querySelector('.car .head input').value;
      if (!label.toUpperCase().includes(name.toUpperCase().split(' ')[1] || '#'))
        problems.push(`${lang}: picked "${label}" but the card is "${name}"`);
      sameCars('after picking a model'); fits('after picking a model');
    }
  }
  // 5. A shared link brings back the same cars and results
  if (typeof encodeShare === 'function') {
    const names = () => [...document.querySelectorAll('#sums .nm')].map(e => e.innerText.trim());
    const totals = () => [...document.querySelectorAll('#sums .big')].map(e => e.textContent);
    const fields = () => JSON.stringify(cars.map(c => SHARE_KEYS.map(k => typeof c[k] === 'number' ? +c[k].toFixed(6) : c[k])));
    const before = [names(), totals(), fields()];
    const code = await encodeShare(shareState());
    if (code.length > 300) problems.push(`${lang}: shared link is long (${code.length} characters): ${code}`);
    applyShared(await decodeShare(code)); renderCars(); update(); await wait(50);
    const after = [names(), totals(), fields()];
    if (JSON.stringify(before) !== JSON.stringify(after))
      problems.push(`${lang}: shared link ${code} gives ${JSON.stringify(after)} instead of ${JSON.stringify(before)}`);
    sameCars('after opening a shared link');
    // Old links (before the short 'y' format) still open with the same cars
    const old = await (await fetch('tests/old_share_links.json')).json();
    for (const o of old) {
      applyShared(await decodeShare(o.code)); renderCars(); update(); await wait(50);
      if (JSON.stringify(names()) !== JSON.stringify(o.cars))
        problems.push(`${lang}: old link "${o.name}" opens ${JSON.stringify(names())} instead of ${JSON.stringify(o.cars)}`);
      sameCars(`after opening the old link "${o.name}"`);
    }
  }
  return problems;
}
