"""Souhrnné statistiky ročníku."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from softwaretestingklasifikator.config import GRADE_BANDS
from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import (
    POKUS_LABELS,
    POKUS_VALUES,
    BonusBreakdown,
    Student,
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
    istqb: int = 0
    ukoncilo: int = 0
    splnilo_diky_bonusu: int = 0
    celkem: int = 0

    @property
    def splnilo(self) -> int:
        """Počet studentů, kteří dosáhli jiné známky než F."""
        return self.celkem - self.grades.get("F", 0)

    @property
    def nesplnilo(self) -> int:
        return self.grades.get("F", 0)


def compute_stats(
    year_data: YearData,
    repetent_os_cisla: set[str] | None = None,
    *,
    exclude_finished: bool = True,
) -> YearStats:
    """Spočítá statistiky ročníku.

    `exclude_finished=True`: počítá jen aktivní studenty (s `ukoncil_studium=False`).
    Počet ukončených je vždy v poli `ukoncilo` zvlášť.
    """
    repetent_os_cisla = repetent_os_cisla or set()
    stats = YearStats()
    stats.ukoncilo = sum(1 for s in year_data.students if s.ukoncil_studium)
    active = [
        s for s in year_data.students
        if not (exclude_finished and s.ukoncil_studium)
    ]
    stats.celkem = len(active)
    for s in active:
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
        if s.ma_istqb_ctfl:
            stats.istqb += 1
        # Splnilo díky bonusu = teď není F, ale bez bonusu by F bylo.
        if grade != "F" and not s.ma_istqb_ctfl and s.bonus.total() > 0:
            without_bonus = replace(s, bonus=BonusBreakdown())
            if evaluate(without_bonus).znamka == "F":
                stats.splnilo_diky_bonusu += 1
    return stats


def top_n_indices(students: list[Student], n: int = 5) -> dict[int, int]:
    """Vrátí mapping `row_index -> pořadí (1..n)` pro N studentů s nejvyšším Celkem.

    Připouští shodu — v takovém případě dostanou stejné pořadí. Cílem je vizuálně
    ukázat „top N" studenty v tabulce. ISTQB CTFL studenti se počítají jako A,
    ale jejich Celkem může být cokoliv — řadíme přesně podle vypočteného Celkem.
    """
    if not students:
        return {}
    scored: list[tuple[float, int]] = []
    for i, s in enumerate(students):
        result = evaluate(s)
        scored.append((result.celkem, i))
    scored.sort(key=lambda x: x[0], reverse=True)
    ranking: dict[int, int] = {}
    rank = 0
    last_score: float | None = None
    for celkem, idx in scored:
        if last_score is None or celkem != last_score:
            rank += 1
            last_score = celkem
        if rank > n:
            break
        ranking[idx] = rank
    return ranking


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
    "top_n_indices",
]
