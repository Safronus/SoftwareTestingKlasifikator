"""Souhrnné statistiky ročníku."""

from __future__ import annotations

from dataclasses import dataclass, field

from softwaretestingklasifikator.config import GRADE_BANDS
from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import (
    POKUS_LABELS,
    POKUS_VALUES,
    YearData,
)

GRADE_ORDER: tuple[str, ...] = tuple(letter for _, _, letter in reversed(GRADE_BANDS))


@dataclass
class YearStats:
    grades: dict[str, int] = field(default_factory=lambda: {g: 0 for g in GRADE_ORDER})
    pokus_counts: dict[str, int] = field(default_factory=lambda: {p: 0 for p in POKUS_VALUES})
    dochazka_splneno: int = 0
    dochazka_nesplneno: int = 0
    repetenti: int = 0
    celkem: int = 0

    @property
    def splnilo(self) -> int:
        """Počet studentů, kteří dosáhli jiné známky než F."""
        return self.celkem - self.grades.get("F", 0)

    @property
    def nesplnilo(self) -> int:
        return self.grades.get("F", 0)


def compute_stats(year_data: YearData, repetent_os_cisla: set[str] | None = None) -> YearStats:
    repetent_os_cisla = repetent_os_cisla or set()
    stats = YearStats()
    stats.celkem = len(year_data.students)
    for s in year_data.students:
        result = evaluate(s)
        grade = s.znamka_override or result.znamka
        stats.grades[grade] = stats.grades.get(grade, 0) + 1
        stats.pokus_counts[s.pokus] = stats.pokus_counts.get(s.pokus, 0) + 1
        if s.dochazka:
            stats.dochazka_splneno += 1
        else:
            stats.dochazka_nesplneno += 1
        if s.os_cislo and s.os_cislo in repetent_os_cisla:
            stats.repetenti += 1
    return stats


def previous_years_os_cisla(data_dir, current_year: int) -> set[str]:
    """Vrátí sjednocení os_čísel ze všech ročníků <`current_year`>.

    Použije se pro detekci repetentů v aktuálním roce (= student, jehož
    osobní číslo se vyskytlo v některém předchozím ročníku).
    """
    # Import zde lokálně kvůli závislosti na storage (cyklus jinak nehrozí).
    from softwaretestingklasifikator.io.storage import list_available_years, load_year

    result: set[str] = set()
    for year in list_available_years(data_dir):
        if year >= current_year:
            continue
        try:
            data = load_year(data_dir, year)
        except OSError:
            continue
        for s in data.students:
            if s.os_cislo:
                result.add(s.os_cislo)
    return result


__all__ = [
    "GRADE_ORDER",
    "POKUS_LABELS",
    "YearStats",
    "compute_stats",
    "previous_years_os_cisla",
]
