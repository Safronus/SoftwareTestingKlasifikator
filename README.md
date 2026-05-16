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
- **detekce repetentů** podle osobního čísla z předchozích ročníků (zvýrazněný řádek + ikonka `↻`),
- **top 5** studentů podle Celkem se zlatým / stříbrným / bronzovým odznakem,
- dock se statistikou ročníku: počet známek, splnilo/nesplnilo, rozpad stavů odevzdání, ISTQB, repetenti, deadliny.

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
    ├── student_detail.py      # detail panel pro editaci jednoho studenta
    ├── stats_panel.py         # dock se statistikou ročníku
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

**0.2.0** — ISTQB CTFL automatická A, top-5 podle Celkem, barevná tabulka, statistický dock, 4-stavé odevzdání, detekce repetentů, dynamická detekce sloupců Excelu a načítání deadlinů.
**0.1.0** — počáteční verze (gating, bonus, JSON persistence, CSV import/export, PySide6 UI).
