"""Automatický návrh alokace bonusových bodů.

Strategie:
1. Nejprve doplníme do brány (T1→15, T2→15, Projekt→90).
2. Pokud po dopnění brány zbývá bonus, použijeme ho na **maximalizaci známky**:
   alokujeme tak, aby Celkem přeskočilo nejbližší prahy známek (Excel pásma).
   Zbývající bonus přidáme do Projektu (největší hlava, nejmenší riziko překročení maxima).

Pravidla pro overflow: bonus nemůže způsobit, že část přesáhne svůj maximální strop
(test1 ≤ 25, test2 ≤ 25, projekt ≤ 150).
"""

from __future__ import annotations

from softwaretestingklasifikator.config import (
    GATE_PROJEKT,
    GATE_TEST1,
    GATE_TEST2,
    GRADE_BANDS,
    MAX_PROJEKT,
    MAX_TEST1,
    MAX_TEST2,
    POINTS_DECIMALS,
)
from softwaretestingklasifikator.domain.models import BonusBreakdown


def _r(value: float) -> float:
    return round(float(value), POINTS_DECIMALS)


def suggest_allocation(
    test1: float,
    test2: float,
    projekt: float,
    total_bonus: float,
) -> BonusBreakdown:
    """Navrhne rozdělení `total_bonus` mezi 3 části.

    Vstup `test1/test2/projekt` jsou *čisté* body (bez bonusu).
    """
    remaining = max(0.0, _r(total_bonus))

    # Strop kolik bonusu se vejde do jednotlivých částí (kvůli maximu části).
    cap = {
        "test1": max(0.0, _r(MAX_TEST1 - test1)),
        "test2": max(0.0, _r(MAX_TEST2 - test2)),
        "projekt": max(0.0, _r(MAX_PROJEKT - projekt)),
    }
    alloc = {"test1": 0.0, "test2": 0.0, "projekt": 0.0}

    def give(part: str, amount: float) -> float:
        """Přiřadí `amount` (nezáporných) bodů do dané části, vrátí kolik se reálně použilo."""
        amount = max(0.0, _r(amount))
        free = cap[part] - alloc[part]
        give_now = _r(min(amount, free, remaining))
        if give_now > 0:
            alloc[part] = _r(alloc[part] + give_now)
        return give_now

    # 1) Doplnit do brány — priorita: test1, test2, projekt (libovolné pořadí
    #    by stačilo, ale fixní pořadí dělá výstup deterministický).
    need_t1 = max(0.0, _r(GATE_TEST1 - test1))
    need_t2 = max(0.0, _r(GATE_TEST2 - test2))
    need_pj = max(0.0, _r(GATE_PROJEKT - projekt))

    for part, need in (("test1", need_t1), ("test2", need_t2), ("projekt", need_pj)):
        used = give(part, need)
        remaining = _r(remaining - used)
        if remaining <= 0:
            return BonusBreakdown(**alloc)

    # 2) Maximalizace známky — pokud brána splněna, pokoušíme se přeskočit pásma.
    #    Celkem nyní = test1+test2+projekt + součet alokovaného bonusu.
    base_celkem = _r(test1 + test2 + projekt)
    current_celkem = _r(base_celkem + alloc["test1"] + alloc["test2"] + alloc["projekt"])

    # Prahy známek seřazené vzestupně (lower bound nového pásma).
    thresholds = sorted({b[0] for b in GRADE_BANDS if b[0] > 0})

    for thr in thresholds:
        if remaining <= 0:
            break
        if current_celkem >= thr:
            continue
        deficit = _r(thr - current_celkem)
        # Použij bonus přednostně do projektu (má nejvíc kapacity).
        for part in ("projekt", "test1", "test2"):
            used = give(part, deficit)
            deficit = _r(deficit - used)
            remaining = _r(remaining - used)
            current_celkem = _r(current_celkem + used)
            if deficit <= 0:
                break

    # 3) Zbylý bonus přesypeme do projektu (případně přetečením do testů).
    if remaining > 0:
        for part in ("projekt", "test1", "test2"):
            used = give(part, remaining)
            remaining = _r(remaining - used)
            if remaining <= 0:
                break

    return BonusBreakdown(**alloc)
