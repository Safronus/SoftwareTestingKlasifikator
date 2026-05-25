"""Testy auto-alokace bonusu."""

from __future__ import annotations

import pytest

from softwaretestingklasifikator.domain.bonus import suggest_allocation
from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import Student


def test_bonus_zero_returns_zero():
    a = suggest_allocation(test1=10, test2=15, projekt=90, total_bonus=0)
    assert a.total() == 0


def test_bonus_fills_gate_first_test1():
    # Chybí 5 do brány T1 (10→15), zbytek máme 0
    a = suggest_allocation(test1=10, test2=20, projekt=100, total_bonus=5)
    assert a.test1 == 5
    assert a.test2 == 0
    assert a.projekt == 0


def test_bonus_fills_multiple_gates():
    # T1 chybí 5, T2 chybí 3, projekt chybí 10 → 18 celkem
    a = suggest_allocation(test1=10, test2=12, projekt=80, total_bonus=18)
    assert a.test1 == 5
    assert a.test2 == 3
    assert a.projekt == 10


def test_bonus_insufficient_prefers_closer_to_gate():
    # T1 chybí 5 (10→15), T2 chybí 3 (12→15) → T2 je blíž bráně.
    # Bonus 6: prvně doplnit T2 (3 → splněno), zbylé 3 do T1 (částečně).
    # Cíl: aspoň jeden test projde bránou.
    a = suggest_allocation(test1=10, test2=12, projekt=80, total_bonus=6)
    assert a.test2 == 3
    assert a.test1 == 3
    assert a.projekt == 0


def test_bonus_prefers_test_with_more_points():
    # Konkrétní příklad ze zadání: T1=10, T2=13.8 → T2 je blíž bráně 15.
    # Bonus 1.2: musí jít celý do T2 (splní bránu), ne do T1.
    a = suggest_allocation(test1=10, test2=13.8, projekt=100, total_bonus=1.2)
    assert a.test2 == pytest.approx(1.2)
    assert a.test1 == 0
    assert a.projekt == 0


def test_bonus_extra_goes_toward_grade_threshold():
    # Brána splněna, celkem = 25+25+100 = 150, máme bonus 10 →
    # nejbližší práh nad 150 je 152 (C) — 2 by stačily, ale alokujeme >= 2
    # do projektu (preferovaná část), zbytek 8 do dalších prahů kdyby existovaly.
    a = suggest_allocation(test1=25, test2=25, projekt=100, total_bonus=10)
    s = Student(os_cislo="x", jmeno="x", prijmeni="x",
                test1=25, test2=25, projekt=100, bonus=a, dochazka=True)
    r = evaluate(s)
    # Cíl: dostat se alespoň do C (≥152) — bonus 10 stačí na přeskok 168 (B).
    # Implementace dostane Celkem 160, což je C. To je víc než původní D (150).
    assert r.celkem == pytest.approx(160, abs=0.01)
    assert r.znamka == "C"


def test_bonus_does_not_exceed_part_cap():
    a = suggest_allocation(test1=24, test2=24, projekt=149, total_bonus=10)
    assert a.test1 <= 1
    assert a.test2 <= 1
    assert a.projekt <= 1
    assert a.total() <= 3  # nelze přidat víc, kapacita 1+1+1


def test_bonus_total_never_exceeds_input():
    a = suggest_allocation(test1=10, test2=10, projekt=50, total_bonus=20)
    assert a.total() <= 20
