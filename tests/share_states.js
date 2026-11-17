// Builds three comparison states for testing shared links (run inside the page):
// 1. the default view, 2. one example car edited, 3. four own cars from the register.
// Returns [{name, code, sums}] where sums is the visible result text.
async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);
  const fire = (el, v) => { el.value = v; el.dispatchEvent(new Event('input', {bubbles: true})); };
  const card = (i, k) => document.querySelector(`#cars .car[data-i="${i}"] [data-k="${k}"]`);
  const pickModel = async (i, label) => { fire($('pick' + i), label); await wait(30); };
  const label = (b, m, pt) => { const r = CATALOG.find(r => r[0] === b && r[1] === m && r[2] === pt); return labelOf(r); };
  const sums = () => $('sums').innerText.replace(/\s+/g, ' ').trim();
  const out = [];
  const snap = async name => { await wait(30); out.push({name, code: await encodeShare(shareState()), sums: sums()}); };

  defaultInputs(); cars = examples(); renderCars(); update();
  await snap('default view');

  fire(card(0, 'price'), '15000'); await wait(30);
  await snap('one edited car');

  defaultInputs(); cars = examples(); renderCars(); update();
  fire($('km'), '22000'); fire($('budget'), '25000'); await wait(30);
  await pickModel(0, label('Skoda', 'Octavia', 'D'));
  await pickModel(1, label('Toyota', 'RAV4', 'H'));
  await pickModel(2, label('Tesla', 'MODEL 3', 'E'));
  $('add').click(); await wait(30);
  await pickModel(3, label('Mitsubishi', 'Outlander', 'P'));
  fire(card(0, 'age'), '6'); fire(card(0, 'price'), '17500'); fire(card(0, 'odo'), '110000');
  fire(card(2, 'age'), '3'); fire(card(2, 'price'), '29900');
  await snap('four own cars');
  return out;
}
