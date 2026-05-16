"""Barevné palety pro UI — známky, stavy, repetenti."""

from __future__ import annotations

from PySide6.QtGui import QColor

from softwaretestingklasifikator.domain.models import (
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
)

# Gradient od zelené (A) přes žlutou (D) k červené (F).
GRADE_BG: dict[str, QColor] = {
    "A": QColor(146, 208, 80),   # zelená
    "B": QColor(196, 220, 92),   # žluto-zelená
    "C": QColor(255, 217, 102),  # zlatá
    "D": QColor(246, 178, 107),  # tmavě žlutá / světle oranžová
    "E": QColor(231, 117, 90),   # červeno-oranžová
    "F": QColor(204, 70, 70),    # červená
}
GRADE_FG: dict[str, QColor] = {
    "A": QColor(20, 60, 20),
    "B": QColor(40, 60, 20),
    "C": QColor(80, 60, 0),
    "D": QColor(90, 50, 10),
    "E": QColor(255, 255, 255),
    "F": QColor(255, 255, 255),
}


# Stavy odevzdání projektu (sloupec "Pokus").
POKUS_BG: dict[str, QColor] = {
    POKUS_RADNY: QColor(146, 208, 80),       # zelená
    POKUS_OPRAVNY: QColor(255, 217, 102),    # žlutá
    POKUS_PO_TERMINU: QColor(246, 178, 107), # oranžová
    POKUS_NEODEVZDAL: QColor(204, 70, 70),   # červená
}
POKUS_FG: dict[str, QColor] = {
    POKUS_RADNY: QColor(20, 60, 20),
    POKUS_OPRAVNY: QColor(80, 60, 0),
    POKUS_PO_TERMINU: QColor(90, 50, 10),
    POKUS_NEODEVZDAL: QColor(255, 255, 255),
}


# Docházka splněno / nesplněno.
DOCHAZKA_OK_BG = QColor(146, 208, 80)
DOCHAZKA_FAIL_BG = QColor(204, 70, 70)


# Pozadí pro řádek repetenta (mírná tónace, čitelný i přes ostatní barvy).
REPETENT_ROW_BG = QColor(255, 220, 180)  # světle lososová


def projekt_percent_bg(percent: float) -> QColor:
    """Gradient na základě procentního výsledku projektu (0..1+).

    0–<0.6  → červená (= pod bránou)
    0.6–<0.8 → žlutá
    0.8–<0.9 → zelenožlutá
    ≥0.9    → zelená
    """
    if percent < 0.6:
        return QColor(231, 117, 90)
    if percent < 0.8:
        return QColor(255, 217, 102)
    if percent < 0.9:
        return QColor(196, 220, 92)
    return QColor(146, 208, 80)
