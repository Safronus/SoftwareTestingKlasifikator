# SoftwareTestingKlasifikator

Desktopová aplikace (PySide6) pro klasifikaci studentů předmětu **AP4TS — Testování software** na UTB FAI.

## Funkcionalita

**Evidence a hodnocení**

- import seznamu zapsaných studentů ze STAGu (CSV `getStudentiByRoakce`, kódování Windows-1250),
- evidence bodů z **Testu č. 1** a **Testu č. 2** (každý 0–25, brána 60 % = 15 b., 3 desetinná místa),
- evidence bodů z **Projektu** (0–150, brána 60 % = 90 b.),
- **bonusové body** s automatickým návrhem alokace (přednost do brány, pak maximalizace známky),
- **docházka** (splněno / nesplněno),
- **stav odevzdání projektu** ve čtyřech stavech: 1. pokus / Oprava / Po termínu / Neodevzdal,
- **certifikát ISTQB CTFL** → automatická známka A bez ohledu na zbytek,
- **datum odevzdání**, **deadliny pro řádný a opravný termín**, volný **komentář**,
- výpočet **finální známky A–F** podle pásem převzatých z dosavadní praxe,
- export hodnocení ve formátu STAG (CSV `SeznamStudentuNaPredmetu`, Windows-1250) s vyplněnými `zk_hodnoceni` a `zk_body`.

**Vizualizace a statistika**

- barevné odstupňování známek v tabulce (A zelená → F červená),
- barevné stavy docházky, pokusu a procenta z projektu,
- **stavové barvy testů** — zelená (splněno čistě), žlutá (splněno s bonusem), červená (nesplněno),
- **detekce repetentů** podle osobního čísla z předchozích ročníků (zvýrazněný řádek + ikonka `↻`),
- **top 5** studentů podle Celkem se zlatým / stříbrným / bronzovým odznakem,
- **skrytí ukončených studentů** — checkbox „zakončil studium" v detailu, toggle „Zobrazit ukončené" v toolbar,
- dock se statistikou ročníku: počet známek, splnilo/nesplnilo (včetně počtu splnivších *díky bonusu*), rozpad stavů odevzdání, ISTQB, repetenti, ukončení, deadliny.

## Pravidla klasifikace

| Bod (Celkem) | Známka |
|--------------|--------|
| < 120        | F      |
| 120 – < 136  | E      |
| 136 – < 152  | D      |
| 152 – < 168  | C      |
| 168 – < 184  | B      |
| ≥ 184        | A      |

`Celkem = test1 + test2 + projekt + bonus_test1 + bonus_test2 + bonus_projekt`

Aby student dosáhl jiné známky než **F**, musí současně:

- `test1 + bonus_test1 ≥ 15`,
- `test2 + bonus_test2 ≥ 15`,
- `projekt + bonus_projekt ≥ 90`,
- **mít odevzdaný projekt** (pokus ≠ „Neodevzdal"),
- **mít splněnou docházku**.

**Výjimka:** student s certifikátem **ISTQB CTFL** dostává automaticky **A**, brány se neaplikují.

## Architektura

Vrstvený přístup, doménová logika oddělená od UI.

```
src/softwaretestingklasifikator/
├── config.py                  # konstanty (pásma známek, brány, kódování)
├── domain/
│   ├── models.py              # Student, BonusBreakdown, YearData, YearDeadlines
│   ├── grading.py             # evaluate() — gating + grade-band lookup + ISTQB override
│   ├── bonus.py               # auto-suggest alokace bonusu
│   └── stats.py               # YearStats, top-N, detekce repetentů
├── io/
│   ├── storage.py             # JSON persistence per akademický rok (atomic write)
│   ├── csv_import.py          # STAG roakce CSV (cp1250)
│   └── csv_export.py          # STAG predmet CSV (cp1250)
└── ui/
    ├── main_window.py         # QMainWindow + toolbar + autosave
    ├── student_table_model.py # QAbstractTableModel s počítanými sloupci a barvami
    ├── stats_panel.py         # dock se statistikou ročníku
    ├── bonus_dialog.py        # modální dialog pro nastavení bonusu + auto-rozdělit
    ├── delegates.py           # combobox delegate pro sloupec Pokus
    ├── theme.py               # paleta barev (A→F, docházka, pokus, repetenti, top-5)
    └── year_config_dialog.py  # založení / editace ročníku a deadlinů

scripts/import_excel.py        # jednorázový import historického Excelu
```

## Instalace (macOS, iCloud-friendly)

Repo leží v iCloud-synchronizované složce; **venv proto patří mimo iCloud** (jinak iCloud rozbije symlinky a binární soubory). Postup:

```bash
# 1) Mimo iCloud připrav prostor pro venvy
mkdir -p ~/.venvs

# 2) Postav venv v ~/.venvs/, ne v projektu
cd "/Users/safronus/Desktop/GitHub Projects/SoftwareTestingKlasifikator"
deactivate 2>/dev/null
rm -rf .venv

/opt/homebrew/bin/python3.12 -m venv ~/.venvs/softwaretestingklasifikator

# 3) V projektu vytvoř symlink na ten venv
ln -s ~/.venvs/softwaretestingklasifikator .venv

# 4) Aktivuj a používej jako dosud
source .venv/bin/activate
pip install -e ".[dev]"
python -m softwaretestingklasifikator
```

## Spuštění

```bash
source .venv/bin/activate
python -m softwaretestingklasifikator
# nebo (po `pip install -e .`):
klasifikator
```

## Import historického Excelu

Pokud máš starý hodnoticí sešit s listy pojmenovanými podle let (např. `2023`, `2024`, `2025`), můžeš ho jednorázově převést:

```bash
python scripts/import_excel.py --xlsx "/cesta/k/Hodnoceni.xlsx" --out data/ --verbose
```

Skript automaticky detekuje sloupce podle hlavičky, extrahuje deadliny z buněk pod „Deadliny" a mapuje stavy v sloupci `Pokus` (`1.`, `Oprava`, `Po termínu`, `Neodevzdal`) na odpovídající enum. Pokud Excel obsahuje ručně přepsanou známku, která nesedí s rekonstruovaným výpočtem, uloží se jako `znamka_override` a má přednost.

## Datová bezpečnost

Aplikace ukládá data studentů do složky `data/` v repu (`data/<rok>.json`). **Tato složka je v `.gitignore`** — žádná osobní data se nikdy nedostanou na GitHub. Veřejný je pouze zdrojový kód. Vstupní `.xlsx` a `.csv` jsou rovněž v `.gitignore`.

## Testy

```bash
source .venv/bin/activate
pytest
```

Testy používají pouze syntetická data, žádné reálné studenty.

## Verze

**0.8.4** — Řazení podle **české abecedy** — Č se nyní řadí mezi C a D (ne za Z jak default Unicode). Implementováno přes `locale.strxfrm('cs_CZ.UTF-8')`. Pozor: locale musí být nastaveno **až po** `QApplication()` — Qt jinak reset C locale a strxfrm by se vrátil k default. Sort funguje pro sloupce Příjmení, Jméno, Komentář.
**0.8.3** — Fix grafu známek: čísla nad sloupci se nahoře ořezávala (LABEL_TOP_H byl menší než výška default fontu macOS — 13pt). Zvětšeno na 16px, font explicitně 9pt, FIXED_HEIGHT 80→92, aby text vždy vlezl celý.
**0.8.2** — Bug fix multi-file importu dat odevzdání. Když uživatel naimportoval víc CSV najednou, druhé CSV bez data přepsalo první CSV s datem (a student se omylem označil jako Neodevzdal). Nyní se před `apply` všechny řádky **dedupují** podle slovní množiny celého jména s pravidlem **best wins**: datum > žádné datum, novější > starší. Info dialog už taky neukazuje duplicitní jména v sekci „Nenalezeno".
**0.8.1** — Nové toolbar tlačítko **„✓ Docházka všem"** — označí splněnou docházku všem studentům aktuálního ročníku najednou (s konfirmací). Sloupec **REP** rozšířen z 50 px na 75 px — text „REP" se vedle checkboxu opět vejde.
**0.8.0** — Nové toolbar tlačítko **„📅 Import dat odevzdání (CSV)"**. Otevře dialog pro výběr **více Moodle CSV najednou** (sloupce `Celý název` + `Poslední změna (odevzdaný úkol)`). Pro každý řádek:
- má-li datum (formát „Sobota, 9. května 2026, 20.33") → nastaví studentovi `datum_odevzdani` (jen den) a odvodí `pokus` z deadlinů (řádný / oprava / po termínu),
- má-li `-` → nastaví `datum_odevzdani=None` a `pokus=Neodevzdal`.

Studenti se matchují přes množinu slov celého jména (robustní vůči víceslovným jménům jako „Theodor Jaroslav Krokavec"). Info dialog souhrnuje zpracované soubory, spárované/nenalezené studenty a případné chyby čtení.

Změna výchozího `Pokus` — při importu studentů (CSV roakce i CSV pro nový ročník) a při transferu repetentů se nyní nastavuje `pokus = Neodevzdal` místo `1. pokus`. Reflektuje realitu na začátku ročníku.
**0.7.3** — Další úklid nerelevantních polí. Odebráno `Student.titul_pred`, `Student.titul_za`, `Student.vizualni_id` a `TestScoreRow.vizualni_id`. `display_name()` vrací jen `jmeno + prijmeni`. STAG export do CSV vyplňuje sloupce `titul` a `vizualni_id` prázdně — předpokládáme, že STAG si je doplní jinde, nebo si jejich absenci snese. Import bodů z testů matchuje studenty pouze podle jména + příjmení (vizualni_id z Moodle CSV se přečte, ale ignoruje).
**0.7.2** — Odebrána pole `Student.username` a `Student.email` (importovaly se ze STAGu, ale aplikace je nikde nepoužívala). Stará JSON data se nelámu — `from_dict` neznámé klíče ignoruje, `to_dict` je už nezapisuje.
**0.7.1** — `transfer_from_previous` (transfer při importu nového ročníku i při ručním REP toggle) teď používá **max-pravidlo** i pro body: pokud má student aktuálně lepší body než loňské (+ bonus), zůstanou aktuální. Komentář a docházka se převezmou jen pokud aktuální jsou prázdné; ISTQB lze jen „povýšit", nikdy neztratit. Chrání ručně zadaná data.
**0.7.0** — Sloupec **REP** má teď klikací **checkbox**. Klik:
- **Zaškrtnutí** označí studenta jako repetenta (override auto-detekce), vyhledá ho v předchozích ročnících podle **jména + příjmení** (case + diacritics-insensitive) a pokud najde, přenese body z testů a projektu (`transfer_from_previous` — kombinace s bonusem, clamping, reset stavu). Pokud nenajde, jen označí jako repetenta a status bar zobrazí info.
- **Odškrtnutí** odstraní status repetenta (manuální override `False` přebíjí auto-detekci podle os. čísla — auto-repetent lze „demontnout").

Nový stored field `Student.repetent_override: bool | None` (None = auto, True/False = manuál). `model.is_repetent()` respektuje override.
**0.6.1** — Fix blikajícího malého okna se statistikou po importu. Příčina: `StatsPanel.set_stats()` volal `_inner.setParent(None)` před `deleteLater()`, čímž z widgetu krátce udělal top-level floating okno. Plus `GradeChart` byl vytvářen bez parenta. Nyní `hide()` před `removeWidget` a explicitní parent u GradeChart — žádný flash.
**0.6.0** — Nové toolbar tlačítko **„📊 Import bodů z testů (CSV)"**. Načte Moodle/STAG export (UTF-8, comma-separated, sloupce `Křestní jméno`, `Příjmení`, `Test č. 1`, `Test č. 2`) a zapíše body do studentů aktuálního ročníku. Párování podle **jméno + příjmení** (case-insensitive, bez diakritiky). Pravidlo `max(existing, csv)` — repetent, který už má lepší body z minulého roku, o ně nepřijde. Hodnota `-` znamená nepsal (neaktualizuje). Po importu info dialog ukáže počet spárovaných, nenalezených, aktualizovaných T1/T2 a kolik z nich přes max-pravidlo. Reálná data: 92/94 spárováno.
**0.5.8** — Toolbar pročištěn: odebrána tlačítka **„💾 Uložit"** (autosave běží po každé editaci přes `QTimer.singleShot`) a **„💎 Bonus…"** (bonus se edituje inline v tabulce, auto-rozdělení proběhne přes `suggest_allocation`). `BonusDialog` smazán jako mrtvý kód.
**0.5.7** — Sloupec **Docházka** přesunut za **Pokus** (na konec meta skupiny). Pořadí teď: Odevzdání → Pokus → Docházka.
**0.5.6** — Sloupce **Celkem** a **Známka** přesunuty před **Docházku** (těsně za Bonus). Buňka **Celkem** má teď stejnou barevnou škálu jako Známka (A zelená → F červená) — vizuálně spáruje body s výslednou klasifikací.
**0.5.5** — Revert `CenteredCheckboxDelegate` — vlastní vykreslování checkboxu rozbilo viditelnost (interakce s `QTableView::indicator` stylesheetem). Docházka má zpět default Qt checkbox (vlevo). Barevné podbarvení sloupce **Datum odevzdání** podle stavu Pokus zůstává.
**0.5.4** — Sloupec **Docházka** má teď checkbox **vystředěný** (vlastní `CenteredCheckboxDelegate` — default Qt jej kreslí vlevo). Buňka **Datum odevzdání** přebírá **stejnou barvu jako sloupec Pokus**: zelená (řádný), žlutá (oprava), oranžová (po termínu), červená (neodevzdal). I prázdná buňka u neodevzdaných je červená — vizuální párování usnadní orientaci.
**0.5.3** — Komentář teď konzistentně vyplňuje zbytek šířky **i po přepnutí roku**. Root cause: `resizeColumnsToContents()` se volal v `_set_year_data` a u některých ročníků s delšími komentáři roztáhl ostatní sloupce nad šířku viewportu, čímž vytlačil Stretch komentář. Nyní používáme **pevné defaultní šířky** z `COLUMNS` (uživatel si může roztáhnout ručně), Komentář drží `Stretch` napříč všemi year switchi.
**0.5.2** — Sloupec **Komentář** opět vyplňuje zbytek šířky okna (explicitní `Stretch` resize mode + správné pořadí volání — předtím se nastavoval před `setModel`, takže Qt neměl ještě sloupce). Buňka **Docházky pro repetenta** má teď mírně **světlejší zelenou** `(195, 225, 145)` — vizuálně odlišuje auto-uznanou docházku od ručně potvrzené.
**0.5.1** — Polish dialogu „Nový ročník". Datumy předvyplněny na **dnes** (řádný) a **dnes + 60 dní** (opravný). Validace: opravný termín musí být později než řádný — jinak warning. Default rok je teď **první prázdný** — pokud aktuální rok existuje, ale je bez studentů, použije se on (import proběhne do něj). Roky se studenty jsou nadále blokované.
**0.5.0** — **Import nového ročníku z CSV s automatickým rozpoznáním repetentů**. Dialog „Nový ročník" má teď file picker pro `getStudentiByRoakce` CSV. Po načtení se každý student porovná s předchozími ročníky podle osobního čísla; repetenti mají **přenesené body z minulého roku** (`test1`, `test2`, `projekt` = původní hodnoty **včetně bonusu**, clamped na maximum). Bonus se nepřenáší (reset). Datum odevzdání, pokus, ukončení a override známky se resetují. Komentář a ISTQB CTFL se přenáší. **Generální pravidlo**: repetent má **automaticky uznanou docházku** — gate vždy splněn, v tabulce needitovatelné. Platí napříč celou app (grading + UI + statistiky).
**0.4.5** — Reálný **fix scroll lag**. Tabulka má `setVerticalScrollMode(ScrollPerItem)` (méně paint eventů na macOS trackpad), a `model.data()` má teď **memoizační cache** s klíčem `(row, col, role)`. Při scrollu Qt opakovaně volá `data()` pro každou buňku × ~5 rolí — cache redukuje per-call cost na ~2.6 μs (předtím ~6 μs). Cache je invalidovaná v `set_students` / `emit_row_changed` / `sort` / `set_top_ranks` / `set_repetent_os_cisla`. Pro **checkboxy CTFL / Ukončil / Docházka** přidán stylesheet — bílé čtverečky s tmavým rámečkem, **zelená výplň** při zaškrtnutí.
**0.4.4** — Graf známek zmenšen na fixních **170 × 80 px** (předtím se roztahoval na šířku panelu) a vycentrován. Statistický dock zúžen z 280 na 210 px minima. Přidána **ikona aplikace** v macOS stylu — zaoblený modrý badge s motivem sloupcového grafu A→F + popisek „AP4TS" (1024 × 1024 PNG, generovaná skriptem `tools/generate_icon.py`). Ikona se nastavuje na `QApplication` a `QMainWindow` při startu.
**0.4.3** — Sloupcový graf známek je kompaktnější (cca poloviční výška, tenčí sloupečky), pořadí **A → F** zleva, a počet je teď napsán **těsně nad horní hranou** každého sloupečku.
**0.4.2** — **Plynulý scroll**: tabulka už nepoužívá `ResizeToContents` (přepočítával šířky sloupců při každém scrollu). Nyní `Interactive` + jednorázový `resizeColumnsToContents()` po načtení ročníku; uživatel si může sloupce ručně roztáhnout, Komentář vyplní zbytek. Ve statistickém docku nový **sloupcový graf** rozložení známek (A–F) — výška sloupce podle počtu, číslo nad sloupcem.
**0.4.1** — Polish editovatelnosti. Sloupce **Os. číslo, Příjmení, Jméno, Pokus** jsou nyní needitovatelné (chrání data ze STAGu / odvozený stav). Sloupec **Bonus** je naopak editovatelný — zadáš jen celkový bonus, systém ho automaticky rozdělí do T1/T2/Projektu (priorita: doplnit bránu, pak maximalizace známky). Sloupce **CTFL a Ukončil** zobrazují vedle checkboxu textové „Ano/Ne", aby byl stav vidět i v případě špatně rozlišitelného checkboxu. Datum a checkboxové sloupce **zarovnány na střed**.
**0.4.0** — UI restrukturace. Pravý dock „Detail studenta" odstraněn — vše se edituje inline v tabulce. Pro bonusy přidána toolbar akce **„💎 Bonus…"** (otevře dialog se třemi spinboxy + auto-rozdělit). Nový sloupec **„Ukončil"** (checkbox) — náhrada za checkbox z detail panelu. Symbol repetenta v buňce změněn z `↻` na **„REP"** (čitelnější). Hlavička sloupce ISTQB sjednocena na **„CTFL"**. Známky **A–E** mají nyní gradient zelená → bledě žlutá; **červená je vyhrazena jen pro F**. Sloupce **Pořadí / Repetent / CTFL** přesunuty za **Známku**; první sloupec je **Os. číslo**. Tabulka se po načtení ročníku řadí podle **Příjmení**; uživatel může klikat hlavičky a řadit po libovolném sloupci. Sloupce mají dynamickou šířku podle obsahu, Komentář zabere zbytek.
**0.3.2** — Po startu se vybere nejnovější ročník, který má studenty (přeskočí prázdné). Ukončení studenti zobrazení přes toggle „Zobrazit ukončené" mají všechna pole **šedou barvou** přebíjející ostatní stavové styly — vizuálně okamžitě odlišitelné. Šířka sloupců se nyní přizpůsobuje obsahu (`ResizeToContents`), poslední sloupec **Komentář** zabere zbytek (`Stretch`) — řeší obstříhnutí např. v sloupci Bonus.
**0.3.1** — Stejné stavové barvy aplikovány na sloupec **Projekt** (zelená / žlutá / červená). Sloupec **Bonus** zobrazuje rozdělení v závorce — `celkem (T1/T2/Projekt)`. Nadpisy sekcí v statistickém docku mají bílý text na tmavě modrém banneru — čitelné v light i dark mode. Nové toolbar akce **„♻ Vynulovat hodnocení"** (vynuluje body/bonusy/docházku, zachová studenty) a **„🗑 Smazat ročník"** (úplně odstraní JSON ročníku), obě s konfirmací.
**0.3.0** — Testy v tabulce mají stavové barvy: zelená (≥ 15 čistě), žlutá (≥ 15 s bonusem), červená (nesplněno). Statistika ukazuje kolik studentů „splnilo díky bonusu" jako kontextový údaj v sekci Splnilo. Nový stav studenta **„zakončil studium"** — checkbox v detailu skryje studenta z tabulky, toolbar má toggle „Zobrazit ukončené" pro práci s historií. Stavové sloupce (známka, pokus, docházka, projekt %, testy) mají nyní přednost nad barvou řádku pro repetenty.
**0.2.1** — UI polish: maximalizace okna po startu, datumy ve formátu DD.MM.YYYY, barevné odlišení skupin sloupců (jako v Excelu — identity / testy / projekt / bonus / meta / result / komentář), oprava `Projekt %` (počítá se z čistých bodů projektu bez bonusu), tmavší text na řádcích repetentů, oprava překrývání statistického docku při přepínání ročníků, cache výsledků hodnocení v tabulce kvůli plynulejšímu scrollování.
**0.2.0** — ISTQB CTFL automatická A, top-5 podle Celkem, barevná tabulka, statistický dock, 4-stavé odevzdání, detekce repetentů, dynamická detekce sloupců Excelu a načítání deadlinů.
**0.1.0** — počáteční verze (gating, bonus, JSON persistence, CSV import/export, PySide6 UI).
