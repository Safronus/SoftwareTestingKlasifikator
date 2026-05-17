"""Testy importu bodů z testů (Moodle/STAG CSV)."""

from __future__ import annotations

from softwaretestingklasifikator.config import MAX_TEST1, MAX_TEST2
from softwaretestingklasifikator.domain.models import Student
from softwaretestingklasifikator.io.csv_import import (
    TestScoreRow,
    _norm_name,
    _parse_score,
    apply_test_scores,
    read_test_scores_csv,
)


def _s(jmeno, prijmeni, test1=0.0, test2=0.0) -> Student:
    return Student(os_cislo=f"X{jmeno[0]}", jmeno=jmeno, prijmeni=prijmeni,
                   test1=test1, test2=test2)


def test_norm_name_strips_diacritics():
    assert _norm_name("Matěj") == "matej"
    assert _norm_name("Bartoš") == "bartos"
    assert _norm_name(" Bača ") == "baca"
    assert _norm_name(None) == ""


def test_parse_score_handles_dash_and_floats():
    assert _parse_score("-") is None
    assert _parse_score("—") is None
    assert _parse_score("") is None
    assert _parse_score(None) is None
    assert _parse_score("13.33") == 13.33
    assert _parse_score("13,5") == 13.5  # čeká i čárku
    assert _parse_score("abc") is None


def test_apply_basic_match_and_set():
    students = [_s("Eva", "Nováková"), _s("Petr", "Svoboda")]
    rows = [
        TestScoreRow(jmeno="Eva", prijmeni="Nováková", test1=20.5, test2=18.0),
        TestScoreRow(jmeno="Petr", prijmeni="Svoboda", test1=15.0, test2=None),
    ]
    r = apply_test_scores(students, rows)
    assert r.matched == 2
    assert r.unmatched == []
    assert r.updated_test1 == 2
    assert r.updated_test2 == 1
    assert students[0].test1 == 20.5
    assert students[0].test2 == 18.0
    assert students[1].test1 == 15.0


def test_apply_max_rule_for_repetent():
    # Repetent už má test1=20 z minulého roku, CSV říká 15 → zachovat 20.
    students = [_s("Eva", "Nováková", test1=20.0, test2=10.0)]
    rows = [TestScoreRow(jmeno="Eva", prijmeni="Nováková", test1=15.0, test2=18.0)]
    r = apply_test_scores(students, rows)
    assert students[0].test1 == 20.0  # CSV horší → zachováno
    assert students[0].test2 == 18.0  # CSV lepší → zaktualizováno
    assert r.improved_test2 == 1  # mělo původně 10, teď 18 (lepší)
    assert r.improved_test1 == 0  # zůstalo 20, žádné improvement


def test_apply_matches_diacritics_insensitive():
    students = [_s("Matěj", "Bača")]
    rows = [TestScoreRow(jmeno="matej", prijmeni="baca", test1=22.0)]
    r = apply_test_scores(students, rows)
    assert r.matched == 1
    assert students[0].test1 == 22.0


def test_apply_unmatched_listed():
    students = [_s("Eva", "Nováková")]
    rows = [
        TestScoreRow(jmeno="Eva", prijmeni="Nováková", test1=20.0),
        TestScoreRow(jmeno="Neznámý", prijmeni="Student", test1=15.0),
    ]
    r = apply_test_scores(students, rows)
    assert r.matched == 1
    assert r.unmatched == [("Neznámý", "Student")]


def test_apply_clamps_to_max():
    students = [_s("Eva", "Nováková")]
    rows = [TestScoreRow(jmeno="Eva", prijmeni="Nováková",
                         test1=30.0, test2=99.0)]
    apply_test_scores(students, rows)
    assert students[0].test1 == MAX_TEST1  # 25
    assert students[0].test2 == MAX_TEST2  # 25


def test_apply_none_score_doesnt_overwrite():
    students = [_s("Eva", "Nováková", test1=15.0, test2=10.0)]
    rows = [TestScoreRow(jmeno="Eva", prijmeni="Nováková",
                         test1=None, test2=None)]
    result = apply_test_scores(students, rows)
    assert students[0].test1 == 15.0  # nezměněno
    assert students[0].test2 == 10.0
    assert result.updated_test1 == 0
    assert result.updated_test2 == 0


def test_read_csv_moodle_format(tmp_path):
    csv_content = (
        '"Křestní jméno",Příjmení,ID,Instituce,Oddělení,"E-mailová adresa",'
        '"Test: Test č. 1 (Skutečná hodnota)","Test: Test č. 2 (Skutečná hodnota)",'
        '"Poslední stáhnutí z kurzu"\n'
        'Matěj,Bača,MB080084,,,m_baca@utb.cz,-,-,1778994740\n'
        'Tadeáš,Baier,tb472401,,,t_baier@utb.cz,13.33,14.56,1778994740\n'
        'Martin,Bartoš,mb478577,,,m_bartos@utb.cz,16.85,15.63,1778994740\n'
    )
    p = tmp_path / "scores.csv"
    p.write_text(csv_content, encoding="utf-8")
    rows = read_test_scores_csv(p)
    assert len(rows) == 3
    assert rows[0].jmeno == "Matěj"
    assert rows[0].prijmeni == "Bača"
    assert rows[0].test1 is None  # "-"
    assert rows[0].test2 is None
    assert rows[1].test1 == 13.33
    assert rows[1].test2 == 14.56
    assert rows[2].test1 == 16.85
    assert rows[2].test2 == 15.63
