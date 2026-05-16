"""Jednorázový import historického Excelu `Hodnocení_Projekty_prezenční.xlsx`.

Spuštění:

    python scripts/import_excel.py --xlsx "/cesta/k/Hodnoceni.xlsx" --out data/

Pro každý list (rok) vytvoří `data/<rok>.json`. Skript NIKDY nezapisuje žádná
osobní data do repa — výstupní složka je v `.gitignore` (`data/`).

Pevně dané sloupce (stejné napříč všemi listy):

    A=Jméno  B=Příjmení  C=Test1  D=Test2  E=Projekt  F=Projekt%
    G/H/I = bonus alokace (Test1/Test2/Projekt)   J=bonus_celkem
    K=Celkem  L=Známka

Variabilní sloupce (rozložení se mezi listy mění — viz 2023 vs. 2024/2025):

    "Datum odevzdání*", "Pokus", "Komentář", os_cislo (typicky W)

Pozice těchto sloupců se hledá dynamicky podle textu hlavičky v řádku 1.

Docházka v Excelu není; nastavuje se `True` u všech studentů s nenulovou
klasifikací (jinak by se rekonstruovaná známka rozcházela s Excelem).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import openpyxl  # type: ignore
except ImportError:  # pragma: no cover
    print("Chybí openpyxl. Nainstaluj: pip install -e \".[dev]\"", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from softwaretestingklasifikator.domain.grading import evaluate  # noqa: E402
from softwaretestingklasifikator.domain.models import (  # noqa: E402
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
    BonusBreakdown,
    Student,
    YearData,
    YearDeadlines,
)
from softwaretestingklasifikator.io.storage import save_year  # noqa: E402


def _to_float(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _to_pokus(value) -> str:
    """Map text v Excelu na string stav. Default: řádný."""
    if value is None:
        return POKUS_RADNY
    s = str(value).strip().lower().rstrip(".")
    if s in ("", "1"):
        return POKUS_RADNY
    if s in ("2", "oprava", "opravny", "opravný", "opravna"):
        return POKUS_OPRAVNY
    if s in ("po terminu", "po termínu", "po termínu.", "po termině"):
        return POKUS_PO_TERMINU
    if s in ("neodevzdal", "neodevzdano", "neodevzdáno", "neodevzdal."):
        return POKUS_NEODEVZDAL
    return POKUS_RADNY


# Klíče vyhledávání hlaviček (case-insensitive, prefix match).
_HEADER_KEYS: dict[str, tuple[str, ...]] = {
    "datum_odevzdani": ("datum odevzd", "datum odevzdání"),
    "pokus": ("pokus",),
    "komentar": ("komentář", "komentar"),
}


def _detect_columns(ws) -> dict[str, int | None]:
    """Najde sloupce podle textu hlavičky (řádek 1) — vrací 1-based indexy.

    Také se pokusí najít sloupec s os. čísly: postupně zkouší obvyklé pozice
    (V, W, X) a vybírá první, jehož hodnoty v prvních datových řádcích vypadají
    jako osobní čísla (formát [A-Z]\\d+).
    """
    found: dict[str, int | None] = {"datum_odevzdani": None, "pokus": None, "komentar": None}
    max_col = min(ws.max_column, 40)
    for c in range(1, max_col + 1):
        h = ws.cell(1, c).value
        if not h:
            continue
        h_norm = str(h).strip().lower()
        for key, prefixes in _HEADER_KEYS.items():
            if found[key] is not None:
                continue
            if any(h_norm.startswith(p) for p in prefixes):
                found[key] = c

    # Detekce sloupce os_cisla — bez hlavičky, hledáme hodnoty typu "A12345".
    import re

    pat = re.compile(r"^[A-Za-z]\d{4,}$")
    os_col: int | None = None
    for c in range(15, min(ws.max_column, 30) + 1):
        hits = 0
        for r in range(3, min(ws.max_row, 30) + 1):
            v = ws.cell(r, c).value
            if isinstance(v, str) and pat.match(v.strip()):
                hits += 1
        if hits >= 3:
            os_col = c
            break
    found["os_cislo"] = os_col
    return found


def _extract_deadlines(ws) -> YearDeadlines:
    """Najde buňku „Deadliny" a vrátí dvě následující data (1. a 2. termín)."""
    for r in range(1, 30):
        for c in range(1, 30):
            v = ws.cell(r, c).value
            if isinstance(v, str) and "deadlin" in v.lower():
                first_val = ws.cell(r + 1, c).value
                second_val = ws.cell(r + 2, c).value
                first = _to_date(first_val)
                second = _to_date(second_val)
                return YearDeadlines(first=first, second=second)
    return YearDeadlines()


def import_sheet(ws, year: int, verbose: bool = False) -> YearData:
    students: list[Student] = []
    skipped = 0
    mismatches = 0

    cols = _detect_columns(ws)
    if verbose:
        readable = {k: openpyxl.utils.get_column_letter(v) if v else None for k, v in cols.items()}
        print(f"  Detekované sloupce: {readable}")

    for r in range(3, ws.max_row + 1):
        jmeno = ws.cell(r, 1).value
        prijmeni = ws.cell(r, 2).value
        if not jmeno and not prijmeni:
            continue

        excel_known_grade = ws.cell(r, 12).value
        if not excel_known_grade or not str(excel_known_grade).strip():
            skipped += 1
            continue

        test1 = _to_float(ws.cell(r, 3).value)
        test2 = _to_float(ws.cell(r, 4).value)
        projekt = _to_float(ws.cell(r, 5).value)
        bonus_t1 = _to_float(ws.cell(r, 7).value)
        bonus_t2 = _to_float(ws.cell(r, 8).value)
        bonus_pj = _to_float(ws.cell(r, 9).value)

        datum = _to_date(ws.cell(r, cols["datum_odevzdani"]).value) if cols["datum_odevzdani"] else None
        pokus = _to_pokus(ws.cell(r, cols["pokus"]).value) if cols["pokus"] else 1
        komentar_raw = ws.cell(r, cols["komentar"]).value if cols["komentar"] else ""
        komentar = str(komentar_raw).strip() if komentar_raw else ""
        os_cislo_raw = ws.cell(r, cols["os_cislo"]).value if cols["os_cislo"] else ""
        os_cislo = str(os_cislo_raw).strip() if os_cislo_raw else ""

        dochazka = bool(excel_known_grade) and str(excel_known_grade).strip() != "F"

        student = Student(
            os_cislo=os_cislo,
            jmeno=str(jmeno or "").strip(),
            prijmeni=str(prijmeni or "").strip(),
            test1=test1,
            test2=test2,
            projekt=projekt,
            bonus=BonusBreakdown(test1=bonus_t1, test2=bonus_t2, projekt=bonus_pj),
            dochazka=dochazka,
            datum_odevzdani=datum,
            pokus=pokus,
            komentar=komentar,
        )

        # Pojistka konzistence
        result = evaluate(student)
        if excel_known_grade and str(excel_known_grade).strip() != result.znamka:
            student.znamka_override = str(excel_known_grade).strip()
            mismatches += 1
            if verbose:
                print(
                    f"  ! r{r} {student.display_name()}: Excel={excel_known_grade!r} "
                    f"vs. recomputed={result.znamka!r} (Celkem={result.celkem:g})"
                )

        students.append(student)

    if verbose:
        print(f"  {len(students)} studentů, {skipped} přeskočeno, {mismatches} grade overrides")

    deadlines = _extract_deadlines(ws)
    if verbose:
        print(f"  Deadliny: 1.={deadlines.first}, 2.={deadlines.second}")
    return YearData(year=year, deadlines=deadlines, students=students)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Import historického Excelu do data/<rok>.json")
    p.add_argument("--xlsx", required=True, type=Path, help="Cesta k zdrojovému .xlsx")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "data", help="Cílová složka (default: data/)")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args(argv)

    if not args.xlsx.exists():
        print(f"Soubor nenalezen: {args.xlsx}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(args.xlsx, data_only=True)

    for sheet_name in wb.sheetnames:
        try:
            year = int(sheet_name)
        except ValueError:
            print(f"Přeskakuji list {sheet_name!r} (není rok)")
            continue
        print(f"Zpracovávám list {year}…")
        ws = wb[sheet_name]
        data = import_sheet(ws, year, verbose=args.verbose)
        target = save_year(args.out, data)
        print(f"  → {target} ({len(data.students)} studentů)")
        with_os = sum(1 for s in data.students if s.os_cislo)
        print(f"  {with_os} z {len(data.students)} studentů má vyplněno os. číslo")
        dist: dict[str, int] = {}
        for s in data.students:
            g = s.znamka_override or evaluate(s).znamka
            dist[g] = dist.get(g, 0) + 1
        print(f"  rozložení známek: {json.dumps(dist, ensure_ascii=False, sort_keys=True)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
