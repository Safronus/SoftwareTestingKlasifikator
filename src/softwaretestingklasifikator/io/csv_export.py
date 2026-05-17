"""Export hodnocení ve formátu STAG (`SeznamStudentuNaPredmetu`, cp1250)."""

from __future__ import annotations

import csv
from pathlib import Path

from softwaretestingklasifikator.config import (
    STAG_CSV_DELIMITER,
    STAG_CSV_ENCODING,
    STAG_CSV_QUOTECHAR,
    SUBJECT_CODE,
    SUBJECT_DEPARTMENT,
)
from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import YearData

# Sloupce, ve kterých se export drží — odpovídají STAG predmět CSV.
PREDMET_COLUMNS = (
    "katedra", "zkratka", "rok", "semestr",
    "os_cislo", "jmeno", "prijmeni", "titul",
    "vizualni_id", "licence_isic", "nesplnene_prerekvizity",
    "zk_typ_hodnoceni", "zk_datum", "zk_pokus",
    "zk_hodnoceni", "zk_body",
    "zk_ucit_idno", "zk_jazyk", "zk_ucit_jmeno",
)


def _stag_year(academic_year: int) -> str:
    """STAG vede letní semestr pod ročníkem akademického roku - 1.

    Tj. AP4TS běží v LS 2025/2026 → STAG rok = 2025.
    """
    return str(academic_year - 1)


def export_to_predmet_csv(
    path: Path,
    year_data: YearData,
    *,
    semestr: str = "LS",
    ucit_idno: str = "",
    ucit_jmeno: str = "",
) -> int:
    """Zapíše hodnocení do CSV. Vrací počet zapsaných řádků."""
    rows: list[dict[str, str]] = []
    stag_year = _stag_year(year_data.year)

    for student in year_data.students:
        result = evaluate(student)
        znamka = student.znamka_override or result.znamka
        zk_datum = student.datum_odevzdani.strftime("%d.%m.%Y") if student.datum_odevzdani else ""
        rows.append({
            "katedra": SUBJECT_DEPARTMENT,
            "zkratka": SUBJECT_CODE,
            "rok": stag_year,
            "semestr": semestr,
            "os_cislo": student.os_cislo,
            "jmeno": student.jmeno,
            "prijmeni": student.prijmeni,
            "titul": "",
            "vizualni_id": "",
            "licence_isic": "",
            "nesplnene_prerekvizity": "",
            "zk_typ_hodnoceni": "A|B|C|D|E|F|FX",
            "zk_datum": zk_datum,
            "zk_pokus": str(student.pokus or 1),
            "zk_hodnoceni": znamka,
            "zk_body": f"{result.celkem:.3f}".rstrip("0").rstrip(".") or "0",
            "zk_ucit_idno": ucit_idno,
            "zk_jazyk": "",
            "zk_ucit_jmeno": ucit_jmeno,
        })

    with open(path, "w", encoding=STAG_CSV_ENCODING, newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(PREDMET_COLUMNS),
            delimiter=STAG_CSV_DELIMITER,
            quotechar=STAG_CSV_QUOTECHAR,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
