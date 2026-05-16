"""Jednorázový import historického Excelu `Hodnocení_Projekty_prezenční.xlsx`.

Spuštění:

    python scripts/import_excel.py --xlsx "/cesta/k/Hodnoceni.xlsx" --out data/

Pro každý list (rok) vytvoří `data/<rok>.json`. Skript NIKDY nezapisuje žádná
osobní data do repa — výstupní složka je v `.gitignore` (`data/`).

Předpoklady o tvaru Excelu (ověřeno proti listům 2023/2024/2025):

    A=Jméno  B=Příjmení  C=Test1  D=Test2  E=Projekt  F=Projekt%
    G/H/I = bonus alokace (Test1/Test2/Projekt)   J=bonus_celkem
    K=Celkem  L=Známka  M=Datum odevzdání  N=Pokus  O=Ve stagu?  P=Komentář

Pokud původní rozložení v daném listu jiné, skript hlásí varování a řádek
přeskočí. Docházka v Excelu není; nastavuje se `True` u všech studentů s
nenulovou klasifikací (jinak by se rekonstruovaná známka rozcházela
s tím, co je v Excelu).
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
    BonusBreakdown,
    Student,
    YearData,
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


def _to_pokus(value) -> int:
    if value is None:
        return 1
    s = str(value).strip().rstrip(".")
    try:
        n = int(s)
    except ValueError:
        return 1
    return 2 if n >= 2 else 1


def import_sheet(ws, year: int, verbose: bool = False) -> YearData:
    students: list[Student] = []
    skipped = 0
    mismatches = 0

    for r in range(3, ws.max_row + 1):
        jmeno = ws.cell(r, 1).value
        prijmeni = ws.cell(r, 2).value
        if not jmeno and not prijmeni:
            continue

        excel_known_grade = ws.cell(r, 12).value
        if not excel_known_grade or not str(excel_known_grade).strip():
            # Student bez vyhodnocení v Excelu — nepatří do historie.
            skipped += 1
            continue

        test1 = _to_float(ws.cell(r, 3).value)
        test2 = _to_float(ws.cell(r, 4).value)
        projekt = _to_float(ws.cell(r, 5).value)
        bonus_t1 = _to_float(ws.cell(r, 7).value)
        bonus_t2 = _to_float(ws.cell(r, 8).value)
        bonus_pj = _to_float(ws.cell(r, 9).value)
        datum = _to_date(ws.cell(r, 13).value)
        pokus = _to_pokus(ws.cell(r, 14).value)
        komentar = ws.cell(r, 16).value or ""

        # Heuristika docházky: pokud má v Excelu jinou než F známku, předpokládáme
        # splněnou docházku (jinak bychom rekonstruovanou známku rozhodili).
        dochazka = bool(excel_known_grade) and str(excel_known_grade).strip() != "F"

        student = Student(
            os_cislo="",  # v Excelu chybí
            jmeno=str(jmeno or "").strip(),
            prijmeni=str(prijmeni or "").strip(),
            test1=test1,
            test2=test2,
            projekt=projekt,
            bonus=BonusBreakdown(test1=bonus_t1, test2=bonus_t2, projekt=bonus_pj),
            dochazka=dochazka,
            datum_odevzdani=datum,
            pokus=pokus,
            komentar=str(komentar).strip() if komentar else "",
        )

        # Pojistka konzistence: ulož i Excel-grade jako override, kdyby naše logika
        # vrátila něco jiného (např. když Excel měl jiný gating pro daný rok).
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

    return YearData(year=year, students=students)


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
        # Krátký souhrn rozložení známek pro kontrolu
        dist: dict[str, int] = {}
        for s in data.students:
            g = s.znamka_override or evaluate(s).znamka
            dist[g] = dist.get(g, 0) + 1
        print(f"  rozložení známek: {json.dumps(dist, ensure_ascii=False, sort_keys=True)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
