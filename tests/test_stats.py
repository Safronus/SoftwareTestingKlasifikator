"""Testy domain.stats (top N, repetenti, statistiky)."""

from __future__ import annotations

from softwaretestingklasifikator.domain.models import (
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_RADNY,
    Student,
    YearData,
)
from softwaretestingklasifikator.domain.stats import (
    compute_stats,
    previous_years_os_cisla,
    top_n_indices,
)
from softwaretestingklasifikator.io.storage import save_year


def _s(os_cislo: str, **kwargs) -> Student:
    base = {"jmeno": "x", "prijmeni": "x", "dochazka": True, "pokus": POKUS_RADNY}
    base.update(kwargs)
    return Student(os_cislo=os_cislo, **base)


def test_top_n_returns_top_5_by_celkem():
    students = [
        _s("A1", test1=25, test2=25, projekt=150),   # 200
        _s("A2", test1=25, test2=25, projekt=140),   # 190
        _s("A3", test1=20, test2=25, projekt=120),   # 165
        _s("A4", test1=25, test2=25, projekt=100),   # 150
        _s("A5", test1=20, test2=20, projekt=120),   # 160
        _s("A6", test1=15, test2=15, projekt=90),    # 120
        _s("A7", test1=10, test2=10, projekt=10),    # 30 — out
    ]
    ranks = top_n_indices(students, n=5)
    # Pořadí podle Celkem desc: A1=200, A2=190, A3=165, A5=160, A4=150
    assert ranks[0] == 1  # A1
    assert ranks[1] == 2  # A2
    assert ranks[2] == 3  # A3
    assert ranks[4] == 4  # A5
    assert ranks[3] == 5  # A4
    assert 6 not in ranks  # A7 mimo
    assert 5 not in ranks  # A6 mimo (6. místo)


def test_top_n_handles_ties():
    students = [_s(f"A{i}", test1=25, test2=25, projekt=150) for i in range(3)]
    ranks = top_n_indices(students, n=5)
    # tři studenti se stejným skóre — všichni mají rank 1
    assert all(r == 1 for r in ranks.values())
    assert len(ranks) == 3


def test_compute_stats_counts_istqb():
    students = [
        _s("A1", test1=25, test2=25, projekt=150, ma_istqb_ctfl=True),
        _s("A2", test1=25, test2=25, projekt=150),
        _s("A3", test1=0, test2=0, projekt=0, dochazka=False),
    ]
    stats = compute_stats(YearData(year=2026, students=students))
    assert stats.istqb == 1
    assert stats.grades["A"] == 2  # ISTQB + normální A
    assert stats.grades["F"] == 1


def test_compute_stats_grades_and_pokus():
    students = [
        _s("A1", test1=25, test2=25, projekt=150),
        _s("A2", test1=20, test2=20, projekt=100, pokus=POKUS_OPRAVNY),
        _s("A3", test1=0, test2=0, projekt=0, pokus=POKUS_NEODEVZDAL),
        _s("A4", test1=14, test2=20, projekt=140),  # T1 < 15 → F
    ]
    stats = compute_stats(YearData(year=2026, students=students))
    assert stats.celkem == 4
    assert stats.grades["A"] == 1
    assert stats.grades["F"] == 2  # A3 (neodevzdal) + A4 (T1<15)
    assert stats.pokus_counts[POKUS_RADNY] == 2  # A1, A4
    assert stats.pokus_counts[POKUS_OPRAVNY] == 1
    assert stats.pokus_counts[POKUS_NEODEVZDAL] == 1


def test_previous_years_os_cisla(tmp_path):
    save_year(tmp_path, YearData(year=2023, students=[_s("A1"), _s("A2")]))
    save_year(tmp_path, YearData(year=2024, students=[_s("A3")]))
    save_year(tmp_path, YearData(year=2025, students=[_s("A1"), _s("A3"), _s("A9")]))

    prev_for_2025 = previous_years_os_cisla(tmp_path, 2025)
    assert prev_for_2025 == {"A1", "A2", "A3"}

    prev_for_2023 = previous_years_os_cisla(tmp_path, 2023)
    assert prev_for_2023 == set()


def test_compute_stats_counts_repetenti():
    students = [_s("A1"), _s("A2"), _s("A3")]
    stats = compute_stats(YearData(year=2026, students=students),
                         repetent_os_cisla={"A1", "A3"})
    assert stats.repetenti == 2
