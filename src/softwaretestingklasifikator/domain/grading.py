"""Vyhodnocení známky a brány."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from softwaretestingklasifikator.config import (
    GATE_PROJEKT,
    GATE_TEST1,
    GATE_TEST2,
    GRADE_BANDS,
    MAX_PROJEKT,
    POINTS_DECIMALS,
)
from softwaretestingklasifikator.domain.models import (
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
    Student,
    YearDeadlines,
)


def derive_pokus_from_date(
    submission_date: date | None,
    deadlines: YearDeadlines | None,
) -> str:
    """Odvodí pokus podle data odevzdání a deadlinů ročníku.

    None → neodevzdal. <= 1. deadline → radny. <= 2. deadline → opravny.
    Jinak po termínu. Když deadliny nejsou nastavené a datum existuje,
    spadne na řádný pokus (neumíme rozhodnout).
    """
    if submission_date is None:
        return POKUS_NEODEVZDAL
    if deadlines is None:
        return POKUS_RADNY
    if deadlines.first and submission_date <= deadlines.first:
        return POKUS_RADNY
    if deadlines.second and submission_date <= deadlines.second:
        return POKUS_OPRAVNY
    if deadlines.first or deadlines.second:
        return POKUS_PO_TERMINU
    return POKUS_RADNY


def _r(value: float) -> float:
    return round(float(value), POINTS_DECIMALS)


@dataclass(frozen=True)
class GateStatus:
    test1_ok: bool
    test2_ok: bool
    projekt_ok: bool
    odevzdano_ok: bool
    dochazka_ok: bool

    @property
    def all_ok(self) -> bool:
        return (
            self.test1_ok
            and self.test2_ok
            and self.projekt_ok
            and self.odevzdano_ok
            and self.dochazka_ok
        )


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
                "odevzdano_ok": self.gate.odevzdano_ok,
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


def evaluate(student: Student, is_repetent: bool = False) -> GradeResult:
    """Spočítá bránu, celkové body a finální známku.

    `is_repetent`: pokud True, docházka je automaticky uznána (repetent ji už
    splnil v některém předchozím ročníku). Mimo to platí standardní pravidla.
    """
    t1 = _r(student.test1 + student.bonus.test1)
    t2 = _r(student.test2 + student.bonus.test2)
    pj = _r(student.projekt + student.bonus.projekt)
    # Projekt % se počítá z čistých bodů projektu (bez bonusu) — odpovídá
    # praxi v původním Excelu (E/150), aby procento odráželo skutečný
    # výkon na projektu, ne navýšení bonusem.
    pj_pct = _r(student.projekt / MAX_PROJEKT) if MAX_PROJEKT else 0.0
    celkem = _r(student.test1 + student.test2 + student.projekt + student.bonus.total())

    # ISTQB CTFL → automatická A bez ohledu na body i bránu.
    if student.ma_istqb_ctfl:
        gate = GateStatus(
            test1_ok=True, test2_ok=True, projekt_ok=True,
            odevzdano_ok=True, dochazka_ok=True,
        )
        return GradeResult(
            test1_total=t1, test2_total=t2, projekt_total=pj,
            projekt_percent=pj_pct, celkem=celkem,
            gate=gate, znamka="A",
        )

    gate = GateStatus(
        test1_ok=t1 >= GATE_TEST1,
        test2_ok=t2 >= GATE_TEST2,
        projekt_ok=pj >= GATE_PROJEKT,
        odevzdano_ok=student.pokus != POKUS_NEODEVZDAL,
        dochazka_ok=student.dochazka or is_repetent,
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
