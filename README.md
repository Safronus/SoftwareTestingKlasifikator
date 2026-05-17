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
