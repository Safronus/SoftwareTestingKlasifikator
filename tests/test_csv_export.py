"""Testy template-based STAG exportu."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from softwaretestingklasifikator.config import (
    STAG_CSV_DELIMITER,
    STAG_CSV_ENCODING,
    STAG_CSV_QUOTECHAR,
)
from softwaretestingklasifikator.domain.models import (
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
    Student,
    YearData,
    YearDeadlines,
)
from softwaretestingklasifikator.io.csv_export import (
    _deadline_for_today,
    _format_body,
    export_via_template_csv,
)

# Sloupce, jak je STAG generuje.
STAG_FIELDS = [
    "katedra", "zkratka", "rok", "semestr",
    "os_cislo", "jmeno", "prijmeni", "titul",
    "vizualni_id", "licence_isic", "nesplnene_prerekvizity",
    "zk_typ_hodnoceni", "zk_datum", "zk_pokus",
    "zk_hodnoceni", "zk_body",
    "zk_ucit_idno", "zk_jazyk", "zk_ucit_jmeno",
]


def _write_template(path: Path, rows: list[dict[str, str]]) -> None:
    """Helper: vytvoří template CSV ve formátu STAGu (cp1250, ;, QUOTE_ALL)."""
    with open(path, "w", encoding=STAG_CSV_ENCODING, newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=STAG_FIELDS,
            delimiter=STAG_CSV_DELIMITER,
            quotechar=STAG_CSV_QUOTECHAR,
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        for row in rows:
            full_row = {f: row.get(f, "") for f in STAG_FIELDS}
            writer.writerow(full_row)


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, encoding=STAG_CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(
            f, delimiter=STAG_CSV_DELIMITER, quotechar=STAG_CSV_QUOTECHAR,
        )
        return list(reader.fieldnames or []), list(reader)


def _template_row(os_cislo: str, jmeno: str, prijmeni: str, **extras) -> dict:
    return {
        "katedra": "AUIUI", "zkratka": "AP4TS", "rok": "2025", "semestr": "LS",
        "os_cislo": os_cislo, "jmeno": jmeno, "prijmeni": prijmeni,
        "zk_typ_hodnoceni": "A|B|C|D|E|F|FX",
        "zk_pokus": "0",
        **extras,
    }


# --- _deadline_for_today --------------------------------------------------

@pytest.mark.parametrize("today, expected", [
    (date(2026, 5, 1), date(2026, 5, 14)),   # před 1. → 1.
    (date(2026, 5, 14), date(2026, 5, 14)),  # přesně 1. → 1.
    (date(2026, 5, 20), date(2026, 5, 14)),  # mezi → 1.
    (date(2026, 7, 18), date(2026, 5, 14)),  # den před 2. → 1.
    (date(2026, 7, 19), date(2026, 7, 19)),  # přesně 2. → 2.
    (date(2026, 8, 1), date(2026, 7, 19)),   # po 2. → 2.
])
def test_deadline_for_today(today, expected):
    deadlines = YearDeadlines(first=date(2026, 5, 14), second=date(2026, 7, 19))
    assert _deadline_for_today(deadlines, today) == expected


def test_deadline_for_today_none_when_no_deadlines():
    assert _deadline_for_today(YearDeadlines(), date(2026, 5, 1)) is None
    assert _deadline_for_today(None, date(2026, 5, 1)) is None


def test_deadline_for_today_fallback_when_only_one_set():
    only_first = YearDeadlines(first=date(2026, 5, 14))
    only_second = YearDeadlines(second=date(2026, 7, 19))
    assert _deadline_for_today(only_first, date(2026, 5, 1)) == date(2026, 5, 14)
    assert _deadline_for_today(only_first, date(2026, 8, 1)) == date(2026, 5, 14)
    assert _deadline_for_today(only_second, date(2026, 5, 1)) == date(2026, 7, 19)


# --- _format_body ---------------------------------------------------------

@pytest.mark.parametrize("celkem, expected", [
    (0.0, "0"),
    (100.0, "100"),
    (150.5, "150.5"),
    (150.123, "150.123"),
    (150.123456, "150.123"),  # zaokrouhleno na 3 dec
])
def test_format_body_uses_dot(celkem, expected):
    assert _format_body(celkem) == expected


# --- export_via_template_csv ---------------------------------------------

def test_export_updates_only_four_columns(tmp_path):
    """Export updatuje jen zk_datum, zk_pokus, zk_hodnoceni, zk_body."""
    template = tmp_path / "template.csv"
    _write_template(template, [
        _template_row(
            "A1", "Eva", "Nováková",
            titul="Bc.", vizualni_id="EN001",
            zk_ucit_idno="123", zk_ucit_jmeno="Tester",
        ),
    ])
    students = [Student(
        os_cislo="A1", jmeno="Eva", prijmeni="Nováková",
        test1=25, test2=25, projekt=150, dochazka=True,
        pokus=POKUS_RADNY,
        datum_odevzdani=date(2026, 5, 10),
    )]
    data = YearData(year=2026, students=students,
                    deadlines=YearDeadlines(first=date(2026, 5, 14)))

    out = tmp_path / "out.csv"
    result = export_via_template_csv(template, out, data, today=date(2026, 5, 12))
    assert result.updated == 1

    fields, rows = _read_csv(out)
    assert fields == STAG_FIELDS  # pořadí zachováno
    r = rows[0]
    # Změněné sloupce
    assert r["zk_datum"] == "10.05.2026"
    assert r["zk_pokus"] == "1"
    assert r["zk_hodnoceni"] == "A"
    assert r["zk_body"] == "200"
    # NEzměněné — zachovají hodnoty z template
    assert r["titul"] == "Bc."
    assert r["vizualni_id"] == "EN001"
    assert r["zk_ucit_idno"] == "123"
    assert r["zk_ucit_jmeno"] == "Tester"
    assert r["katedra"] == "AUIUI"
    assert r["zk_typ_hodnoceni"] == "A|B|C|D|E|F|FX"


def test_export_preserves_cp1250_diacritics(tmp_path):
    """Diakritika v ne-měněných polích zůstává nedotčená v cp1250."""
    template = tmp_path / "t.csv"
    _write_template(template, [
        _template_row("A1", "Matěj", "Bača"),
    ])
    students = [Student(os_cislo="A1", jmeno="Matěj", prijmeni="Bača",
                        test1=20, test2=20, projekt=120)]
    data = YearData(year=2026, students=students)

    out = tmp_path / "out.csv"
    export_via_template_csv(template, out, data, today=date(2026, 1, 1))

    # Načti zpět v cp1250 — pokud encoding selhal, čeština se rozbije.
    fields, rows = _read_csv(out)
    assert rows[0]["jmeno"] == "Matěj"
    assert rows[0]["prijmeni"] == "Bača"


def test_export_neodevzdal_uses_first_deadline(tmp_path):
    """Pro neodevzdal-studenta bez data se použije 1. deadline."""
    template = tmp_path / "t.csv"
    _write_template(template, [_template_row("A1", "Eva", "N")])
    students = [Student(
        os_cislo="A1", jmeno="Eva", prijmeni="N",
        pokus=POKUS_NEODEVZDAL,  # neodevzdal
        datum_odevzdani=None,
    )]
    data = YearData(year=2026, students=students,
                    deadlines=YearDeadlines(
                        first=date(2026, 5, 14), second=date(2026, 7, 19),
                    ))

    out = tmp_path / "out.csv"
    # Dnes před 2. deadlinem → použij 1. deadline.
    export_via_template_csv(template, out, data, today=date(2026, 5, 1))
    _, rows = _read_csv(out)
    assert rows[0]["zk_datum"] == "14.05.2026"  # 1. deadline


def test_export_neodevzdal_uses_second_deadline_after(tmp_path):
    """Po 2. deadlinu se použije 2. deadline pro neodevzdal."""
    template = tmp_path / "t.csv"
    _write_template(template, [_template_row("A1", "Eva", "N")])
    students = [Student(
        os_cislo="A1", jmeno="Eva", prijmeni="N",
        pokus=POKUS_NEODEVZDAL,
        datum_odevzdani=None,
    )]
    data = YearData(year=2026, students=students,
                    deadlines=YearDeadlines(
                        first=date(2026, 5, 14), second=date(2026, 7, 19),
                    ))

    out = tmp_path / "out.csv"
    export_via_template_csv(template, out, data, today=date(2026, 7, 25))
    _, rows = _read_csv(out)
    assert rows[0]["zk_datum"] == "19.07.2026"  # 2. deadline


@pytest.mark.parametrize("student_pokus, expected", [
    (POKUS_RADNY, "1"),
    (POKUS_NEODEVZDAL, "1"),
    (POKUS_OPRAVNY, "2"),
    (POKUS_PO_TERMINU, "2"),
])
def test_export_zk_pokus_mapping(tmp_path, student_pokus, expected):
    template = tmp_path / "t.csv"
    _write_template(template, [_template_row("A1", "Eva", "N")])
    students = [Student(os_cislo="A1", jmeno="Eva", prijmeni="N",
                        test1=20, test2=20, projekt=120, dochazka=True,
                        pokus=student_pokus,
                        datum_odevzdani=date(2026, 5, 1))]
    data = YearData(year=2026, students=students)
    out = tmp_path / "out.csv"
    export_via_template_csv(template, out, data, today=date(2026, 5, 1))
    _, rows = _read_csv(out)
    assert rows[0]["zk_pokus"] == expected


def test_export_zk_body_uses_dot_separator(tmp_path):
    template = tmp_path / "t.csv"
    _write_template(template, [_template_row("A1", "Eva", "N")])
    students = [Student(
        os_cislo="A1", jmeno="Eva", prijmeni="N",
        test1=23.45, test2=22.5, projekt=130.123,
        dochazka=True,
    )]
    data = YearData(year=2026, students=students)
    out = tmp_path / "out.csv"
    export_via_template_csv(template, out, data, today=date(2026, 5, 1))
    _, rows = _read_csv(out)
    # 23.45 + 22.5 + 130.123 = 176.073
    assert rows[0]["zk_body"] == "176.073"
    assert "," not in rows[0]["zk_body"]


def test_export_csv_only_row_left_unchanged(tmp_path):
    """Řádek v CSV, který nemá protějšek v app, zůstává netknutý."""
    template = tmp_path / "t.csv"
    _write_template(template, [
        _template_row("A1", "V", "App",
                      zk_datum="01.01.2020", zk_pokus="3",
                      zk_hodnoceni="X", zk_body="999"),
        _template_row("A2", "Není", "V App"),  # tento ne v app
    ])
    students = [Student(os_cislo="A1", jmeno="V", prijmeni="App",
                        test1=20, test2=20, projekt=120, dochazka=True,
                        datum_odevzdani=date(2026, 5, 10))]
    data = YearData(year=2026, students=students)

    out = tmp_path / "out.csv"
    result = export_via_template_csv(template, out, data, today=date(2026, 5, 1))
    assert result.updated == 1
    assert result.csv_only_unchanged == 1

    _, rows = _read_csv(out)
    # Řádek A1 přepsán novými hodnotami.
    assert rows[0]["zk_datum"] == "10.05.2026"
    assert rows[0]["zk_pokus"] == "1"
    # Řádek A2 zůstal beze změny.
    assert rows[1]["zk_datum"] == ""
    assert rows[1]["zk_pokus"] == "0"
    assert rows[1]["zk_hodnoceni"] == ""
    assert rows[1]["zk_body"] == ""


def test_export_app_only_listed_in_result(tmp_path):
    """Student v aplikaci, ale ne v CSV — zapíše se do app_only seznamu."""
    template = tmp_path / "t.csv"
    _write_template(template, [_template_row("A1", "Eva", "N")])
    students = [
        Student(os_cislo="A1", jmeno="Eva", prijmeni="N", test1=20),
        Student(os_cislo="A99", jmeno="Není", prijmeni="V CSV", test1=15),
    ]
    data = YearData(year=2026, students=students)
    out = tmp_path / "out.csv"
    result = export_via_template_csv(template, out, data, today=date(2026, 5, 1))
    assert result.updated == 1
    assert len(result.app_only) == 1
    assert result.app_only[0].os_cislo == "A99"


def test_export_uses_app_date_over_csv_date(tmp_path):
    """Když app má datum, vždy přepíše datum v CSV (i kdyby CSV mělo novější)."""
    template = tmp_path / "t.csv"
    _write_template(template, [
        _template_row("A1", "Eva", "N", zk_datum="20.06.2026"),  # novější v CSV
    ])
    students = [Student(
        os_cislo="A1", jmeno="Eva", prijmeni="N",
        test1=20, test2=20, projekt=120, dochazka=True,
        datum_odevzdani=date(2026, 5, 10),  # starší v app
    )]
    data = YearData(year=2026, students=students)
    out = tmp_path / "out.csv"
    export_via_template_csv(template, out, data, today=date(2026, 5, 1))
    _, rows = _read_csv(out)
    # App je source of truth — i přes novější datum v CSV se zapíše app value.
    assert rows[0]["zk_datum"] == "10.05.2026"
