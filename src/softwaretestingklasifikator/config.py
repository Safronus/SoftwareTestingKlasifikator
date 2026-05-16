"""Konstanty klasifikace převzaté z dosavadní praxe (Excel 2023–2025)."""

from __future__ import annotations

# Maximální dosažitelné body z jednotlivých částí
MAX_TEST1: float = 25.0
MAX_TEST2: float = 25.0
MAX_PROJEKT: float = 150.0
MAX_CELKEM: float = MAX_TEST1 + MAX_TEST2 + MAX_PROJEKT  # 200.0

# Prahy "brány" (60 % z každé části)
GATE_TEST1: float = 15.0
GATE_TEST2: float = 15.0
GATE_PROJEKT: float = 90.0

# Pásma známek (lower_inclusive, upper_exclusive, znamka)
# Poslední pásmo je shora otevřené (≥ 184).
GRADE_BANDS: tuple[tuple[float, float | None, str], ...] = (
    (0.0, 120.0, "F"),
    (120.0, 136.0, "E"),
    (136.0, 152.0, "D"),
    (152.0, 168.0, "C"),
    (168.0, 184.0, "B"),
    (184.0, None, "A"),
)

# Body se ukládají s 3 desetinnými místy.
POINTS_DECIMALS: int = 3

# Kódování CSV pro STAG (jak importu, tak exportu).
STAG_CSV_ENCODING: str = "cp1250"
STAG_CSV_DELIMITER: str = ";"
STAG_CSV_QUOTECHAR: str = '"'

# Předmět a katedra (pro export, pevně dáno).
SUBJECT_DEPARTMENT: str = "AUIUI"
SUBJECT_CODE: str = "AP4TS"
