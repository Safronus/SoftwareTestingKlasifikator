"""Hash exportovatelného stavu ročníku — pro detekci „neuložených změn"
od posledního STAG exportu.

Princip: hashujeme jen ta pole, která se reálně promítnou do STAG CSV
(`zk_datum`, `zk_pokus`, `zk_hodnoceni`, `zk_body`) plus os. číslo
(student identity). Změny v komentářích, bonusu rozdělení apod. samy o
sobě hash nemění, ale skrz vliv na Celkem nebo známku se promítnou.
"""

from __future__ import annotations

import hashlib

from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import YearData


def compute_export_hash(year_data: YearData) -> str:
    """Vrátí SHA-256 hex digest exportovatelného stavu ročníku.

    Hash závisí pouze na fields, které se zapisují do STAG CSV. Stabilní
    a deterministický (sorted iterace, fixed separators).
    """
    h = hashlib.sha256()
    # Stabilní pořadí napříč běhy.
    students = sorted(year_data.students, key=lambda s: s.os_cislo or "")
    for s in students:
        result = evaluate(s)
        grade = s.znamka_override or result.znamka
        datum = s.datum_odevzdani.isoformat() if s.datum_odevzdani else ""
        # Klíčové pole oddělené | (nesmí se objevit v hodnotě).
        record = f"{s.os_cislo}|{datum}|{s.pokus}|{grade}|{result.celkem:.3f}"
        h.update(record.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()
