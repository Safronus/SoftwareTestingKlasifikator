"""Testy importu dat odevzdání projektu (Moodle CSV)."""

from __future__ import annotations

from datetime import date

import pytest

from softwaretestingklasifikator.domain.models import (
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
    Student,
    YearDeadlines,
)
from softwaretestingklasifikator.io.csv_import import (
    ProjectDateRow,
    _derive_pokus_from_date,
    _name_tokens,
    _parse_czech_date,
    apply_project_dates,
    read_project_dates_csv,
)


@pytest.mark.parametrize("text, expected", [
    ("Sobota, 9. května 2026, 20.33", date(2026, 5, 9)),
    ("Pondělí, 11. května 2026, 22.55", date(2026, 5, 11)),
    ("Úterý, 12. května 2026, 16.58", date(2026, 5, 12)),
    ("Pátek, 1. ledna 2027, 8.00", date(2027, 1, 1)),
    ("Středa, 31. prosince 2026, 23.59", date(2026, 12, 31)),
    ("-", None),
    ("—", None),
    ("", None),
    (None, None),
    ("nějaký nesmysl", None),
])
def test_parse_czech_date(text, expected):
    assert _parse_czech_date(text) == expected


def test_name_tokens_handles_multi_word_names():
    """Robustní vůči víceslovým jménům (Theodor Jaroslav Krokavec)."""
    a = _name_tokens("Theodor Jaroslav", "Krokavec")
    b = _name_tokens("Theodor Jaroslav Krokavec")
    assert a == b


def test_name_tokens_diacritics_insensitive():
    a = _name_tokens("Matěj", "Bača")
    b = _name_tokens("matej baca")
    assert a == b


@pytest.mark.parametrize("d, deadlines, expected", [
    (None, YearDeadlines(), POKUS_NEODEVZDAL),
    (date(2026, 5, 10), YearDeadlines(first=date(2026, 5, 14)), POKUS_RADNY),
    (date(2026, 5, 14), YearDeadlines(first=date(2026, 5, 14)), POKUS_RADNY),
    (date(2026, 5, 15), YearDeadlines(first=date(2026, 5, 14),
                                       second=date(2026, 7, 19)), POKUS_OPRAVNY),
    (date(2026, 7, 19), YearDeadlines(first=date(2026, 5, 14),
                                       second=date(2026, 7, 19)), POKUS_OPRAVNY),
    (date(2026, 7, 20), YearDeadlines(first=date(2026, 5, 14),
                                       second=date(2026, 7, 19)), POKUS_PO_TERMINU),
])
def test_derive_pokus_from_date(d, deadlines, expected):
    assert _derive_pokus_from_date(d, deadlines) == expected


def test_apply_sets_date_and_derives_pokus():
    students = [
        Student(os_cislo="A1", jmeno="Eva", prijmeni="Nováková",
                pokus=POKUS_NEODEVZDAL),
        Student(os_cislo="A2", jmeno="Petr", prijmeni="Svoboda",
                pokus=POKUS_NEODEVZDAL),
    ]
    rows = [
        ProjectDateRow(full_name="Eva Nováková", submission_date=date(2026, 5, 10)),
        ProjectDateRow(full_name="Petr Svoboda", submission_date=None),
    ]
    deadlines = YearDeadlines(first=date(2026, 5, 14), second=date(2026, 7, 19))
    r = apply_project_dates(students, rows, deadlines=deadlines)

    assert r.matched == 2
    assert r.set_date == 1
    assert r.set_neodevzdal == 1
    assert r.unmatched == []
    assert students[0].datum_odevzdani == date(2026, 5, 10)
    assert students[0].pokus == POKUS_RADNY
    assert students[1].datum_odevzdani is None
    assert students[1].pokus == POKUS_NEODEVZDAL


def test_apply_match_multi_word_name():
    students = [
        Student(os_cislo="A1", jmeno="Theodor Jaroslav", prijmeni="Krokavec",
                pokus=POKUS_NEODEVZDAL),
    ]
    rows = [
        ProjectDateRow(full_name="Theodor Jaroslav Krokavec",
                       submission_date=date(2026, 5, 10)),
    ]
    r = apply_project_dates(students, rows,
                             deadlines=YearDeadlines(first=date(2026, 5, 14)))
    assert r.matched == 1
    assert students[0].datum_odevzdani == date(2026, 5, 10)


def test_apply_unmatched_tracked():
    students = [Student(os_cislo="A1", jmeno="Eva", prijmeni="Nováková")]
    rows = [
        ProjectDateRow(full_name="Eva Nováková", submission_date=None),
        ProjectDateRow(full_name="Neznámý Student", submission_date=None),
    ]
    r = apply_project_dates(students, rows)
    assert r.matched == 1
    assert r.unmatched == ["Neznámý Student"]


def test_apply_accumulates_multiple_files():
    students = [
        Student(os_cislo="A1", jmeno="Eva", prijmeni="N"),
        Student(os_cislo="A2", jmeno="Petr", prijmeni="S"),
    ]
    rows1 = [ProjectDateRow(full_name="Eva N", submission_date=date(2026, 5, 10))]
    rows2 = [ProjectDateRow(full_name="Petr S", submission_date=None)]
    deadlines = YearDeadlines(first=date(2026, 5, 14))

    result = apply_project_dates(students, rows1, deadlines=deadlines)
    result = apply_project_dates(students, rows2, deadlines=deadlines, result=result)

    assert result.files_processed == 2
    assert result.rows_total == 2
    assert result.matched == 2
    assert result.set_date == 1
    assert result.set_neodevzdal == 1


def test_read_csv_moodle_format(tmp_path):
    csv_content = (
        '﻿Identifikátor,"Celý název","E-mailová adresa",Stav,Známka,'
        '"Maximální známka","Známka může být změněna",'
        '"Poslední změna (odevzdaný úkol)","Online text",'
        '"Poslední změna (hodnocení)","Komentář učitele"\n'
        'Účastník1,"Eva Nováková",eva@x,"Stav",,,Ano,"Sobota, 9. května 2026, 20.33",,,\n'
        'Účastník2,"Petr Svoboda",p@x,"Stav",,,Ano,-,,,\n'
    )
    p = tmp_path / "submissions.csv"
    p.write_text(csv_content, encoding="utf-8")
    rows = read_project_dates_csv(p)
    assert len(rows) == 2
    assert rows[0].full_name == "Eva Nováková"
    assert rows[0].submission_date == date(2026, 5, 9)
    assert rows[1].full_name == "Petr Svoboda"
    assert rows[1].submission_date is None
