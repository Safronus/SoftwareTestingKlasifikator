"""Export hodnocení ve formátu STAG (`SeznamStudentuNaPredmetu`, cp1250).

Hlavní funkce — `export_via_template_csv` — načte existující STAG CSV
(`nosný` template) a do něj zapíše čtyři sloupce z aktuálního ročníku
v aplikaci: `zk_datum`, `zk_pokus`, `zk_hodnoceni`, `zk_body`. Ostatní
sloupce se zachovají beze změny (včetně diakritiky, pořadí, kódování
cp1250 a kompletního quotingu).

Studenti se mezi aplikací a CSV spárují podle `os_cislo`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from softwaretestingklasifikator.config import (
    STAG_CSV_DELIMITER,
    STAG_CSV_ENCODING,
    STAG_CSV_QUOTECHAR,
)
from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import (
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
    Student,
    YearData,
    YearDeadlines,
)

# Mapování stavu Pokusu studenta na STAG `zk_pokus`:
# - řádný i neodevzdal → 1. pokus
# - oprava i po termínu → 2. pokus
_POKUS_TO_ZK_POKUS: dict[str, str] = {
    POKUS_RADNY: "1",
    POKUS_NEODEVZDAL: "1",
    POKUS_OPRAVNY: "2",
    POKUS_PO_TERMINU: "2",
}


@dataclass
class ExportResult:
    updated: int = 0                          # studenti zapsáni do CSV
    app_only: list[Student] = field(default_factory=list)  # v app, ne v CSV
    csv_only_unchanged: int = 0               # v CSV, ne v app — řádky zůstaly


def _deadline_for_today(deadlines: YearDeadlines | None, today: date) -> date | None:
    """Pro neodevzdal-studenty bez data: vybere deadline podle aktuálního data.

    - Pokud `today >= deadlines.second` → použij druhý (opravný) deadline.
    - Jinak → první (řádný) deadline.
    - Pokud jen jeden je nastavený → použij ho.
    - Pokud žádný → None (CSV value se nezmění).
    """
    if deadlines is None:
        return None
    first, second = deadlines.first, deadlines.second
    if second and today >= second:
        return second
    if first:
        return first
    return second


def _format_body(celkem: float) -> str:
    """Zformátuje celkové body s desetinnou tečkou, bez koncových nul."""
    return f"{celkem:.3f}".rstrip("0").rstrip(".") or "0"


def _update_row(
    row: dict[str, str],
    student: Student,
    deadlines: YearDeadlines | None,
    today: date,
) -> None:
    """In-place update čtyř sloupců dle student + deadlinů. Ostatní pole netknout."""
    result = evaluate(student)
    znamka = student.znamka_override or result.znamka

    # zk_datum — app value je source of truth; pro neodevzdal bez data fallback
    # na deadline podle today (viz _deadline_for_today).
    if student.datum_odevzdani is not None:
        row["zk_datum"] = student.datum_odevzdani.strftime("%d.%m.%Y")
    else:
        d = _deadline_for_today(deadlines, today)
        if d is not None:
            row["zk_datum"] = d.strftime("%d.%m.%Y")
        # Pokud žádný deadline, ponechej původní hodnotu (typicky '').

    # zk_pokus — vždy odvozeno z student.pokus, CSV value se ignoruje.
    row["zk_pokus"] = _POKUS_TO_ZK_POKUS.get(student.pokus, "1")

    # zk_hodnoceni — vždy přepsáno aktuální známkou.
    row["zk_hodnoceni"] = znamka

    # zk_body — vždy přepsáno aktuálním Celkem (desetinná tečka).
    row["zk_body"] = _format_body(result.celkem)


def export_via_template_csv(
    template_path: Path,
    output_path: Path,
    year_data: YearData,
    *,
    today: date | None = None,
) -> ExportResult:
    """Načte template CSV a do něj zapíše hodnocení z `year_data`.

    Modifikuje sloupce `zk_datum`, `zk_pokus`, `zk_hodnoceni`, `zk_body`
    u studentů, kteří mají os. číslo shodné s řádkem CSV. Ostatní sloupce
    i ostatní řádky (= studenti v CSV mimo aplikaci) zůstávají netknuté.

    Kódování (`cp1250`), oddělovač (`;`) a quoting (`"` na všech polích)
    jsou zachovány.
    """
    today = today or date.today()

    # Načti template — zachovej původní pořadí sloupců (DictReader to dělá).
    with open(template_path, encoding=STAG_CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(
            f,
            delimiter=STAG_CSV_DELIMITER,
            quotechar=STAG_CSV_QUOTECHAR,
        )
        fieldnames = list(reader.fieldnames or [])
        csv_rows: list[dict[str, str]] = [
            {k: (v if v is not None else "") for k, v in row.items()}
            for row in reader
        ]

    students_by_os: dict[str, Student] = {
        s.os_cislo: s for s in year_data.students if s.os_cislo
    }
    csv_os_cisla: set[str] = {
        (r.get("os_cislo") or "").strip()
        for r in csv_rows
        if (r.get("os_cislo") or "").strip()
    }

    result = ExportResult()
    matched_os: set[str] = set()
    for row in csv_rows:
        os_c = (row.get("os_cislo") or "").strip()
        if not os_c:
            continue
        student = students_by_os.get(os_c)
        if student is None:
            # CSV-only student — řádek zůstane beze změny.
            continue
        _update_row(row, student, year_data.deadlines, today)
        matched_os.add(os_c)

    result.updated = len(matched_os)
    result.app_only = [
        s for os_c, s in students_by_os.items() if os_c not in matched_os
    ]
    result.csv_only_unchanged = len(csv_os_cisla - matched_os)

    # Zapiš zpět — stejné kódování, oddělovač, quoting (QUOTE_ALL).
    with open(output_path, "w", encoding=STAG_CSV_ENCODING, newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter=STAG_CSV_DELIMITER,
            quotechar=STAG_CSV_QUOTECHAR,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    return result
