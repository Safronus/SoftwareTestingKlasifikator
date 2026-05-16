# SoftwareTestingKlasifikator

Desktopová aplikace (PySide6) pro klasifikaci studentů předmětu **AP4TS — Testování software** na UTB FAI.

Podporuje:

- import seznamu zapsaných studentů ze STAGu (CSV `getStudentiByRoakce`, kódování Windows-1250),
- evidenci bodů z **Testu č. 1** a **Testu č. 2** (každý 0–25, brána 60 % = 15 b., 3 desetinná místa),
- evidenci bodů z **Projektu** (0–150, brána 60 % = 90 b.),
- **bonusové body** s automatickým návrhem alokace (přednost doplnění do brány, zbytek na maximalizaci známky),
- evidenci **docházky** (splněno / nesplněno),
- výpočet **finální známky A–F** podle pásem převzatých z dosavadní praxe,
- evidenci **data odevzdání projektu**, **pokusu** (1./2.) a volného **komentáře**,
- export hodnocení ve formátu STAG (CSV `SeznamStudentuNaPredmetu`, Windows-1250) s vyplněnými `zk_hodnoceni` a `zk_body`.

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
- mít splněnou docházku.

## Instalace (macOS, iCloud-friendly)

Repo leží v iCloud-synchronizované složce; **venv proto patří mimo iCloud** (jinak iCloud rozbije symlinky a binární soubory). Postup je stejný jako u dalších projektů:

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

## Datová bezpečnost

Aplikace ukládá data studentů do složky `data/` v repu (`data/<rok>.json`). **Tato složka je v `.gitignore`** — žádná osobní data se nikdy nedostanou na GitHub. Veřejný je pouze zdrojový kód.

Pro jednorázový import historických let z přiloženého Excelu existuje skript `scripts/import_excel.py`. Vstupní `.xlsx` rovněž patří do `data/` (rovněž gitignored).

## Testy

```bash
source .venv/bin/activate
pytest
```

Testy používají pouze syntetická data, žádné reálné studenty.
