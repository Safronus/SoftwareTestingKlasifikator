"""Vyhodnocení známky a brány."""

from __future__ import annotations

from dataclasses import dataclass

from softwaretestingklasifikator.config import (
    GATE_PROJEKT,
    GATE_TEST1,
    GATE_TEST2,
    GRADE_BANDS,
    MAX_PROJEKT,
    POINTS_DECIMALS,
)
from softwaretestingklasifikator.domain.models import Student


def _r(value: float) -> float:
    return round(float(value), POINTS_DECIMALS)


@dataclass(frozen=True)
class GateStatus:
    test1_ok: bool
    test2_ok: bool
    projekt_ok: bool
    dochazka_ok: bool

    @property
    def all_ok(self) -> bool:
        return self.test1_ok and self.test2_ok and self.projekt_ok and self.dochazka_ok


@dataclass(frozen=True)
class GradeResult:
    test1_total: float   # test1 + bonus.test1
    test2_total: float   # test2 + bonus.test2
    projekt_total: float # projekt + bonus.projekt
    projekt_percent: float  # (projekt + bonus.projekt) / MAX_PROJEKT, 0..1+
    celkem: float        # všechny body + součet bonusů
    gate: GateStatus
    znamka: str          # finální písmeno

    def to_dict(self) -> dict:
        return {
            "test1_total": self.test1_total,
            "test2_total": self.test2_total,
            "projekt_total": self.projekt_total,
            "projekt_percent": self.projekt_percent,
            "celkem": self.celkem,
            "gate": {
                "test1_ok": self.gate.test1_ok,
                "test2_ok": self.gate.test2_ok,
                "projekt_ok": self.gate.projekt_ok,
                "dochazka_ok": self.gate.dochazka_ok,
            },
            "znamka": self.znamka,
        }


def grade_from_celkem(celkem: float) -> str:
    """Vyhledá písmeno známky podle pásma. Pásmo je [lower, upper)."""
    for lower, upper, letter in GRADE_BANDS:
        if celkem < lower:
            continue
        if upper is None or celkem < upper:
            return letter
    # Nedostupný stav (celkem mimo všechna pásma) — pojistka.
    return GRADE_BANDS[-1][2]


def evaluate(student: Student) -> GradeResult:
    """Spočítá bránu, celkové body a finální známku."""
    t1 = _r(student.test1 + student.bonus.test1)
    t2 = _r(student.test2 + student.bonus.test2)
    pj = _r(student.projekt + student.bonus.projekt)
    pj_pct = _r(pj / MAX_PROJEKT) if MAX_PROJEKT else 0.0
    celkem = _r(student.test1 + student.test2 + student.projekt + student.bonus.total())

    gate = GateStatus(
        test1_ok=t1 >= GATE_TEST1,
        test2_ok=t2 >= GATE_TEST2,
        projekt_ok=pj >= GATE_PROJEKT,
        dochazka_ok=student.dochazka,
    )

    znamka = grade_from_celkem(celkem) if gate.all_ok else "F"
    return GradeResult(
        test1_total=t1,
        test2_total=t2,
        projekt_total=pj,
        projekt_percent=pj_pct,
        celkem=celkem,
        gate=gate,
        znamka=znamka,
    )
