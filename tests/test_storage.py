"""Testy JSON persistence ročníku."""

from __future__ import annotations

from datetime import date

from softwaretestingklasifikator.domain.models import (
    POKUS_OPRAVNY,
    POKUS_RADNY,
    BonusBreakdown,
    Student,
    YearData,
    YearDeadlines,
)
from softwaretestingklasifikator.io.storage import (
    list_available_years,
    load_year,
    save_year,
    year_file,
)


def test_save_and_load_roundtrip(tmp_path):
    students = [
        Student(
            os_cislo="A00001", jmeno="Alice", prijmeni="Alfa",
            test1=22.5, test2=18.123, projekt=140,
            bonus=BonusBreakdown(test1=1, test2=2, projekt=3),
            dochazka=True,
            datum_odevzdani=date(2026, 5, 10),
            pokus=POKUS_RADNY,
            komentar="OK",
        ),
        Student(os_cislo="A00002", jmeno="Bob", prijmeni="Beta"),
    ]
    data = YearData(
        year=2026,
        deadlines=YearDeadlines(first=date(2026, 5, 12), second=date(2026, 6, 2)),
        students=students,
    )

    target = save_year(tmp_path, data)
    assert target == year_file(tmp_path, 2026)
    assert target.exists()

    loaded = load_year(tmp_path, 2026)
    assert loaded.year == 2026
    assert loaded.deadlines.first == date(2026, 5, 12)
    assert loaded.deadlines.second == date(2026, 6, 2)
    assert len(loaded.students) == 2
    a = loaded.students[0]
    assert a.os_cislo == "A00001"
    assert a.test2 == 18.123
    assert a.bonus.projekt == 3
    assert a.datum_odevzdani == date(2026, 5, 10)
    assert a.komentar == "OK"
    assert a.pokus == POKUS_RADNY


def test_pokus_int_migration_legacy_json(tmp_path):
    import json
    target = tmp_path / "2025.json"
    target.write_text(json.dumps({
        "year": 2025,
        "deadlines": {"first": None, "second": None},
        "students": [
            {"os_cislo": "A1", "jmeno": "Old", "prijmeni": "Schema", "pokus": 2},
        ],
    }), encoding="utf-8")
    loaded = load_year(tmp_path, 2025)
    assert loaded.students[0].pokus == POKUS_OPRAVNY


def test_load_missing_returns_empty_year(tmp_path):
    data = load_year(tmp_path, 1999)
    assert data.year == 1999
    assert data.students == []


def test_list_available_years(tmp_path):
    save_year(tmp_path, YearData(year=2024))
    save_year(tmp_path, YearData(year=2026))
    save_year(tmp_path, YearData(year=2023))
    assert list_available_years(tmp_path) == [2023, 2024, 2026]
