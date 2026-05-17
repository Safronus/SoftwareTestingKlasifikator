"""Testy transferu hodnocení z minulého ročníku do nového (repetent)."""

from __future__ import annotations

from softwaretestingklasifikator.config import MAX_PROJEKT, MAX_TEST1, MAX_TEST2
from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import (
    POKUS_NEODEVZDAL,
    POKUS_RADNY,
    BonusBreakdown,
    Student,
    YearData,
)
from softwaretestingklasifikator.io.csv_import import transfer_from_previous
from softwaretestingklasifikator.io.storage import (
    find_previous_students_batch,
    save_year,
)


def _make_prev(test1=0.0, test2=0.0, projekt=0.0, bonus=None,
               dochazka=False, komentar="", ma_istqb_ctfl=False,
               pokus=POKUS_RADNY) -> Student:
    return Student(
        os_cislo="A1", jmeno="A", prijmeni="B",
        test1=test1, test2=test2, projekt=projekt,
        bonus=bonus or BonusBreakdown(),
        dochazka=dochazka, komentar=komentar,
        ma_istqb_ctfl=ma_istqb_ctfl, pokus=pokus,
    )


def test_transfer_uznani_testu_s_bonusem():
    # Loni: test1=13 + bonus_test1=2 → letos test1=15 (uznáno)
    prev = _make_prev(test1=13, test2=20, projekt=100,
                      bonus=BonusBreakdown(test1=2, test2=0, projekt=0))
    new = Student(os_cislo="A1", jmeno="A", prijmeni="B")
    transfer_from_previous(new, prev)
    assert new.test1 == 15  # 13 + 2
    assert new.test2 == 20  # nezměněno, bonus byl 0
    assert new.projekt == 100  # nezměněno, bonus byl 0
    assert new.bonus.total() == 0  # bonus se nepřenese


def test_transfer_uznani_projektu_s_bonusem():
    # Loni: projekt=80 + bonus_projekt=15 → letos projekt=95
    prev = _make_prev(test1=20, test2=20, projekt=80,
                      bonus=BonusBreakdown(projekt=15))
    new = Student(os_cislo="A1", jmeno="A", prijmeni="B")
    transfer_from_previous(new, prev)
    assert new.projekt == 95


def test_transfer_clamping_na_maxima():
    # Loni: test1=20 + bonus_test1=20 = 40, ale MAX_TEST1=25 → letos test1=25
    prev = _make_prev(test1=20, test2=24, projekt=140,
                      bonus=BonusBreakdown(test1=20, test2=10, projekt=50))
    new = Student(os_cislo="A1", jmeno="A", prijmeni="B")
    transfer_from_previous(new, prev)
    assert new.test1 == MAX_TEST1
    assert new.test2 == MAX_TEST2
    assert new.projekt == MAX_PROJEKT


def test_transfer_failed_test_zustava_failed():
    # Loni: test1=10 + bonus_test1=0 → letos test1=10 (failed)
    prev = _make_prev(test1=10, test2=10, projekt=20)
    new = Student(os_cislo="A1", jmeno="A", prijmeni="B")
    transfer_from_previous(new, prev)
    assert new.test1 == 10
    assert new.test2 == 10
    assert new.projekt == 20


def test_transfer_resetuje_stav():
    from datetime import date
    prev = _make_prev(test1=20, test2=20, projekt=100, pokus=POKUS_NEODEVZDAL)
    prev.datum_odevzdani = date(2025, 5, 12)
    prev.ukoncil_studium = True
    prev.znamka_override = "A"
    new = Student(os_cislo="A1", jmeno="A", prijmeni="B")
    transfer_from_previous(new, prev)
    assert new.pokus == POKUS_RADNY
    assert new.datum_odevzdani is None
    assert new.ukoncil_studium is False
    assert new.znamka_override is None


def test_transfer_kopiruje_komentar_a_istqb():
    prev = _make_prev(test1=15, test2=15, projekt=90,
                      komentar="Vynikající projekt", ma_istqb_ctfl=True)
    new = Student(os_cislo="A1", jmeno="Eva", prijmeni="N")
    transfer_from_previous(new, prev)
    assert new.komentar == "Vynikající projekt"
    assert new.ma_istqb_ctfl is True


def test_find_previous_students_batch(tmp_path):
    # 2023: A1
    # 2024: A2, A3
    # 2025: A1, A3, A9 — repetenti A1 (z 2023) a A3 (z 2024)
    save_year(tmp_path, YearData(year=2023, students=[
        Student(os_cislo="A1", jmeno="x", prijmeni="x", test1=20),
    ]))
    save_year(tmp_path, YearData(year=2024, students=[
        Student(os_cislo="A2", jmeno="x", prijmeni="x"),
        Student(os_cislo="A3", jmeno="x", prijmeni="x", test1=18),
    ]))
    save_year(tmp_path, YearData(year=2025, students=[
        Student(os_cislo="A1", jmeno="x", prijmeni="x", test1=22),  # novější verze A1
        Student(os_cislo="A3", jmeno="x", prijmeni="x", test1=19),  # novější A3
        Student(os_cislo="A9", jmeno="x", prijmeni="x"),
    ]))

    # Pro nový ročník 2026, hledáme A1, A3, A_NOVY
    result = find_previous_students_batch(
        tmp_path, {"A1", "A3", "A_NOVY"}, current_year=2026,
    )
    assert set(result.keys()) == {"A1", "A3"}  # A_NOVY nenalezen
    assert result["A1"][0] == 2025  # nejnovější výskyt
    assert result["A1"][1].test1 == 22
    assert result["A3"][0] == 2025
    assert result["A3"][1].test1 == 19


def test_find_previous_skipne_current_a_future(tmp_path):
    save_year(tmp_path, YearData(year=2024, students=[
        Student(os_cislo="A1", jmeno="x", prijmeni="x", test1=20),
    ]))
    save_year(tmp_path, YearData(year=2026, students=[
        Student(os_cislo="A1", jmeno="x", prijmeni="x", test1=23),
    ]))
    # Pro current_year=2025 hledáme A1 — najde 2024, ne 2026.
    result = find_previous_students_batch(tmp_path, {"A1"}, current_year=2025)
    assert result["A1"][0] == 2024


def test_repetent_ma_uznanou_dochazku_v_evaluate():
    # Student bez splněné docházky, ale je repetent → docházka uznána
    s = Student(os_cislo="A1", jmeno="x", prijmeni="x",
                test1=20, test2=20, projekt=120, dochazka=False)
    r_normal = evaluate(s, is_repetent=False)
    assert not r_normal.gate.dochazka_ok
    assert r_normal.znamka == "F"

    r_rep = evaluate(s, is_repetent=True)
    assert r_rep.gate.dochazka_ok
    assert r_rep.znamka != "F"  # gate splněn


def test_find_previous_student_by_name(tmp_path):
    from softwaretestingklasifikator.io.storage import (
        find_previous_student_by_name,
        save_year,
    )
    save_year(tmp_path, YearData(year=2024, students=[
        Student(os_cislo="A1", jmeno="Matěj", prijmeni="Bača", test1=18),
        Student(os_cislo="A2", jmeno="Eva", prijmeni="Nováková", test1=22),
    ]))
    save_year(tmp_path, YearData(year=2025, students=[
        Student(os_cislo="A1", jmeno="Matěj", prijmeni="Bača", test1=20),
    ]))
    # Standard match — najde 2025 (nejnovější).
    found = find_previous_student_by_name(tmp_path, "Matěj", "Bača", 2026)
    assert found is not None
    assert found[0] == 2025
    assert found[1].test1 == 20

    # Case + diacritics insensitive.
    found2 = find_previous_student_by_name(tmp_path, "matej", "baca", 2026)
    assert found2 is not None
    assert found2[0] == 2025

    # Student jen v 2024.
    eva = find_previous_student_by_name(tmp_path, "Eva", "Nováková", 2026)
    assert eva is not None
    assert eva[0] == 2024

    # Neexistující.
    none = find_previous_student_by_name(tmp_path, "Nikdo", "Neznámý", 2026)
    assert none is None


def test_repetent_override_in_is_repetent():
    """Manuální override přebíjí auto-detekci."""
    from softwaretestingklasifikator.ui.student_table_model import StudentTableModel
    students = [
        Student(os_cislo="A1", jmeno="x", prijmeni="x"),  # auto-repetent
        Student(os_cislo="A2", jmeno="y", prijmeni="y"),  # ne-repetent
        Student(os_cislo="A3", jmeno="z", prijmeni="z",
                repetent_override=True),  # manuál True
        Student(os_cislo="A1b", jmeno="w", prijmeni="w",
                repetent_override=False),  # zruseno
    ]
    model = StudentTableModel(students=students)
    model._repetent_os_cisla = {"A1", "A1b"}  # A1 a A1b jsou auto

    assert model.is_repetent(students[0]) is True   # auto (override=None)
    assert model.is_repetent(students[1]) is False  # neauto, override=None
    assert model.is_repetent(students[2]) is True   # override=True
    assert model.is_repetent(students[3]) is False  # override=False přebije auto


def test_repetent_override_serializace(tmp_path):
    from softwaretestingklasifikator.io.storage import load_year, save_year
    s = Student(os_cislo="A1", jmeno="x", prijmeni="x", repetent_override=False)
    save_year(tmp_path, YearData(year=2026, students=[s]))
    loaded = load_year(tmp_path, 2026)
    assert loaded.students[0].repetent_override is False

    s2 = Student(os_cislo="A2", jmeno="y", prijmeni="y", repetent_override=True)
    save_year(tmp_path, YearData(year=2027, students=[s2]))
    loaded2 = load_year(tmp_path, 2027)
    assert loaded2.students[0].repetent_override is True

    # Default = None
    s3 = Student(os_cislo="A3", jmeno="z", prijmeni="z")
    save_year(tmp_path, YearData(year=2028, students=[s3]))
    loaded3 = load_year(tmp_path, 2028)
    assert loaded3.students[0].repetent_override is None
