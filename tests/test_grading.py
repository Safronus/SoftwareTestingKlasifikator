"""Testy gating logiky a vyhledávání známky."""

from __future__ import annotations

import pytest

from softwaretestingklasifikator.domain.grading import evaluate, grade_from_celkem
from softwaretestingklasifikator.domain.models import BonusBreakdown, Student


def make_student(test1=0.0, test2=0.0, projekt=0.0, dochazka=True, bonus=None) -> Student:
    return Student(
        os_cislo="X0001", jmeno="Test", prijmeni="Student",
        test1=test1, test2=test2, projekt=projekt,
        dochazka=dochazka, bonus=bonus or BonusBreakdown(),
    )


@pytest.mark.parametrize("celkem, expected", [
    (0, "F"),
    (119.999, "F"),
    (120, "E"),
    (135.999, "E"),
    (136, "D"),
    (151.999, "D"),
    (152, "C"),
    (167.999, "C"),
    (168, "B"),
    (183.999, "B"),
    (184, "A"),
    (200, "A"),
])
def test_grade_from_celkem_bands(celkem, expected):
    assert grade_from_celkem(celkem) == expected


def test_gate_fail_test1_returns_F():
    # Bez bonusu, T1 < 15
    s = make_student(test1=14.999, test2=25, projekt=150)
    r = evaluate(s)
    assert not r.gate.test1_ok
    assert r.znamka == "F"


def test_gate_fail_dochazka_returns_F_even_when_points_max():
    s = make_student(test1=25, test2=25, projekt=150, dochazka=False)
    r = evaluate(s)
    assert r.celkem == 200
    assert not r.gate.dochazka_ok
    assert r.znamka == "F"


def test_bonus_can_unlock_gate():
    s = make_student(test1=14, test2=15, projekt=90,
                     bonus=BonusBreakdown(test1=1.5, test2=0, projekt=0))
    r = evaluate(s)
    assert r.gate.test1_ok
    assert r.znamka != "F"


def test_celkem_includes_total_bonus():
    s = make_student(test1=15, test2=15, projekt=90,
                     bonus=BonusBreakdown(test1=1, test2=2, projekt=3))
    r = evaluate(s)
    assert r.celkem == pytest.approx(15 + 15 + 90 + 6)


def test_three_decimal_precision():
    s = make_student(test1=13.5879, test2=18.0, projekt=149.123)
    r = evaluate(s)
    # rounded to 3 decimals
    assert r.celkem == round(13.5879 + 18.0 + 149.123, 3)


def test_excel_row_example_arabadzhiyan():
    """Příklad z reálného Excelu 2023 → měla by vyjít F (Projekt < 90)."""
    s = make_student(test1=12.4, test2=10.23, projekt=0,
                     bonus=BonusBreakdown())
    r = evaluate(s)
    assert r.znamka == "F"
    assert not r.gate.projekt_ok
    assert not r.gate.test2_ok  # 10.23 < 15
