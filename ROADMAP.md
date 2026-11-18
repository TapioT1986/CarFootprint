# CarFootprint – kehityssuunnitelma

Laadittu 18.11.2026 (versio 0.63). Pohjana ulkoinen arvio (ChatGPT, 18.11.2026) ja Clauden oma arvio koodista.
Suunnitelma elää: merkitse tehdyt kohdat ja päivitä järjestystä tarpeen mukaan.

## Lähtökohta

Laskentaa ja lähteitä on jo paljon: todellinen kulutus, arvonalenema, rahoitus, verot, vakuutukset, huolto,
päästöt, toimintasäde, kääntöpisteet, oma auto, kaupunki- ja maantieajo. Seuraavaksi ei kannata lisätä uusia
asetuksia vaan tehdä olemassa olevasta luotettavampi ja helpompi ymmärtää. Kolme pääsuuntaa:

1. **Varmista, että luvut ovat oikein** (laskennan omat testit).
2. **Tee laskurista päätöstyökalu** (pidä nykyinen auto vai vaihda).
3. **Näytä epävarmuus rehellisesti** (arvonalenema ja korjaukset, ei vain energian hinta).

Periaatteet pysyvät: AGPL, avoimet lähteet suorine linkkeineen, epäedullisempi oletus kun on valittava,
ei mainoksia eikä seurantaa, tiedot vain käyttäjän selaimessa.

## Arvion kohdat Clauden näkökulmasta

| Arvion väite | Tarkistus koodista | Johtopäätös |
|---|---|---|
| Nykyisen auton arvo ei siirry vaihtohyvitykseksi | Pitää paikkansa: oma raha on yksi yhteinen luku, nykyinen auto lasketaan lainattomaksi | Tärkein seuraava kokonaisuus |
| Vaihtopäätöksen päästöt puuttuvat | Pitää paikkansa: valmistuspäästöt jaetaan elinkaarelle, vaihdon hetken lisäpäästöä ei lasketa | Osa vaihtolaskuria |
| Vaihteluväli kattaa vain energian | Pitää paikkansa; tuloskortissa lukee jo "Energian hintojen vaihtelulla", mutta lisätieto-osion otsikko on yleinen | Pieni tekstikorjaus + uudet skenaariot |
| Laskennalla ei ole omia testejä | Pitää paikkansa: savutestit tarkistavat käyttöliittymän, eivät laskettuja euroja | Tehdään ensimmäisenä, koska seuraavat muutokset koskevat laskentaa |
| Mallikohtaiset kaupunki/maantie-kertoimet | Vaikeaa: VCA:n mallinimet eivät vastaa Suomen rekisterin nimiä | Myöhemmin, jos nimet saadaan yhdistettyä luotettavasti |
| Talvi kustannuksiin | EEA:n mitattu kulutus sisältää eurooppalaisen keskitalven, ei Suomen talvea; sähköautoille kerroin 1,20 on oletus | Tarvitsee lähteen (NAF/Traficom/VTT) ennen toteutusta |
| Palautekanava ja hakukonenäkyvyys | Palautekanava on suunniteltu (CLAUDE.md), hakukoneille sivulla on vain otsikko ja kuvaus | Tehdään ennen käyttäjätestausta |

Omat lisähavainnot:
- **Lähteettömät luvut**: renkaat ja muut (200–250 €/v), arvonaleneman ajomääräkorjaus 0,2 % / 1 000 km, huollon perustaso,
  sähkön toimitusketjun 16 g/kWh (tarkistettu vain toissijaisesta lähteestä). Ne on merkitty sivulle, mutta lähde puuttuu.
- **Kevythybridit** ovat samassa luokassa kuin täyshybridit (H), vaikka käyttäytyvät kuin bensiiniautot.
- **Akun koko** tiedetään vain, kun se on mallin nimessä; useimmille sähköautoille akun koko ei vaikuta toimintasäteeseen.
- **Yksi iso tiedosto**: `tools/template.html` on lähes 1 900 riviä. Toimii, mutta laskennan testaaminen erikseen
  helpottuu, jos laskentafunktiot ovat selvästi erillään käyttöliittymästä.
- **Aineistojen päivitys** on osin käsityötä (EEA, Verohallinto, VCA, Taloustaito). Tarvitaan vuosikalenteri.

## Vaihe 1 – Perusta kuntoon (seuraavaksi)

### 1.1 Laskennan testisarja · koko S–M · ✅ tehty 18.11.2026 (versio 0.65)
- Tiedosto `tests/calc_cases.json` + tarkistus `smoke_checks.js`:iin: 5–8 käsin laskettua esimerkkiä
  (käteisosto, osittain laina, laina pidempi kuin omistus, sähköauto, lataushybridi, vanha NEDC-auto, nykyinen auto, osakasko).
- Jokaiselle odotetut arvot: arvonalenema, jäännösarvo, rahoitus, energia, vero, huolto, vakuutus, yhteensä, päästöt.
  Laskelma kirjoitetaan auki (kaava ja luvut), jotta sen voi tarkistaa ilman koodia.
- Valmis, kun GitHubin testiajo kaatuu, jos jokin laskettu luku muuttuu tahattomasti.

### 1.2 Pienet rehellisyyskorjaukset · koko S
- "Lisätietoja vaihteluväleistä" → "Energian hinnan vaihtelu" (otsikko kertoo, mitä väli kattaa).
- Kevythybridit omaksi luokakseen tai vähintään oikea kaupunkikerroin (1,13) mallinimen perusteella, jos se on tunnistettavissa.

## Vaihe 2 – Autonvaihtolaskuri (tärkein uusi kokonaisuus)

Tavoite: vastata kysymykseen "kannattaako nykyinen auto pitää vai vaihtaa, rahassa ja päästöissä".

### 2.1 Raha · koko M
- Nykyiselle autolle kentät: **jäljellä oleva laina** ja (valinnaisesti) **odotettavissa olevat korjaukset**.
- Vaihtoehtoautoille: nykyisen auton **myyntiarvo − jäljellä oleva laina** siirtyy automaattisesti omaksi rahaksi
  (vaihtohyvitys), ellei käyttäjä anna omaa summaa.
- Tuloskortissa: "Jos vaihdat: +X €/v" ja omistusajan yhteenlaskettu ero.

### 2.2 Päästöt kahdella tavalla · koko M
- **Elinkaarivertailu** (nykyinen): valmistus jaettuna elinkaarelle + käyttö.
- **Vaihtopäätöksen vaikutus**: pidä = vain käytön päästöt; vaihda uuteen = uuden auton valmistus nyt + käyttö;
  vaihda käytettyyn = rajaus kerrottava (käytetyn auton ostaminen ei synnytä uutta autoa, mutta vaikuttaa ketjuun).
  Laskentarajaus ja lähteet näkyviin, ja nämä kaksi tulosta erotellaan selvästi toisistaan.
- Päätettävä yhdessä: miten käytetyn auton ostoon kohdistetaan valmistuspäästöt (vaihtoehdot kirjataan sivulle).

## Vaihe 3 – Epävarmuus

### 3.1 Arvonalenema- ja korjausskenaariot · koko M
- Kaksi lisäskenaariota energian hinnan rinnalle: **jälleenmyynti ±X %** ja **yksi iso korjaus** (esim. vaihdelaatikko,
  akku). X ja korjaussummat vain lähteistetyistä luvuista (Verohallinnon verotusarvojen hajonta saman mallin ja iän sisällä
  on hyvä ehdokas; korjauksille Traficomin katsastusdata ei riitä, tarvitaan muu lähde).
- Näytetään kääntöpisteinä: "järjestys vaihtuu, jos Golfin jälleenmyyntiarvo on 18 % pienempi".

### 3.2 Talvi kustannuksiin · koko S–M, vaatii lähteen
- Kuukausittainen sähkönkulutuksen kerroin Suomen lämpötiloille (lähde-ehdokkaat: NAF, VTT, Traficom/Motiva).
  Toteutetaan vain, jos lähde antaa vuositason vaikutuksen.

## Vaihe 4 – Käyttäjät mukaan

### 4.1 Palautekanava · koko M (omistajan tunnus tarvitaan)
- Suunnitelma valmiina CLAUDE.md:ssä: 👍/👎 + vapaaehtoinen teksti, vastaanotin esim. Cloudflare Workers, ei seurantaa.

### 4.2 Käyttäjätestaus · omistajan työ, Claude valmistelee
- 5 oikeaa autonostajaa, sama tehtävä kaikille ("vertaa nykyistä autoasi kahteen vaihtoehtoon").
- Claude laatii tehtävät ja kysymyslistan; tulokset palautekanavaan tai muistiinpanoina.

### 4.3 Hakukonenäkyvyys · koko S
- Staattinen lyhyt selitys ja laskentaperiaatteet HTML:ään (ei vain JavaScriptillä), `noscript`-teksti,
  jäsennelty data (WebApplication), englanninkielinen kuvaus.

## Vaihe 5 – Tarkkuus (kun edelliset ovat valmiina)

- Katsastuksiin perustuva käyttöikä `life`-oletukseksi (avoin idea).
- Mallikohtainen kokonaismassa Traficomin rekisteristä käyttövoimaveroon (vaatii ~200 Mt tiedoston).
- Suomalainen tai eurooppalainen lähde huollon kasvukertoimille (nyt Consumer Reports, USA).
- Lähde renkaille ja muille kuluille, arvonaleneman ajomääräkorjaukselle ja huollon perustasolle.
- Mallikohtaiset kaupunki/maantie-kertoimet, jos VCA:n ja rekisterin mallinimet saadaan yhdistettyä.
- Akun koko useammalle sähköautomallille (lähde puuttuu; rekisterissä sitä ei ole).
- €/km → lisäkilometrin hinta, kun huollon ja arvonaleneman kilometririippuvuudelle on lähteet.

## Ylläpitokalenteri

| Milloin | Mitä | Miten |
|---|---|---|
| Kuukausittain 5. pv | Polttoaine- ja sähköhinnat | Automaattinen (GitHub Actions) |
| Touko–heinäkuu | Katsastustilasto | Automaattinen (20. pv) |
| Kerran vuodessa, alkuvuosi | Verohallinnon verotusarvot → hinta-arviot | `tools/budget_values.py --write`, tiedostot latauksena |
| Kerran vuodessa, syksy | EEA:n rekisteri (kulutus, toimintasäde) | Tietokatselimen CSV:t, `tools/ev_range.py` |
| Kerran vuodessa | VCA:n WLTP-vaiheet | `tools/city_ratio.py` |
| Kerran vuodessa | Vakuutusvertailut, maahantuojien hinnastot, Suomen Pankin korot | Käsin, lähdelinkit päivitetään |
| Lain muuttuessa | Ajoneuvoverotaulukot | `tools/vehicle_tax.py` |

## Mitä ei tehdä nyt

- Ei uusia asetuksia ilman, että ne liittyvät yllä oleviin kokonaisuuksiin.
- Ei kaupallisia rajapintoja, mainoksia, seurantaa tai kirjautumista.
- Ei lukuja ilman lähdettä; jos lähdettä ei ole, oletus merkitään oletukseksi.

## Ehdotettu järjestys

1. Laskennan testisarja (1.1) ja pienet korjaukset (1.2).
2. Autonvaihtolaskuri, raha (2.1).
3. Autonvaihtolaskuri, päästöt (2.2) – vaatii omistajan päätöksen rajauksesta.
4. Palautekanava (4.1) ja hakukonenäkyvyys (4.3).
5. Epävarmuusskenaariot (3.1).
6. Käyttäjätestaus (4.2) – tulokset ohjaavat vaiheita 3.2 ja 5.
