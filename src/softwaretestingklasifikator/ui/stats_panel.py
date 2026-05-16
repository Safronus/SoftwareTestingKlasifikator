"""Dock widget se statistikou ročníku — známky, splnilo, odevzdal, repetenti."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from softwaretestingklasifikator.domain.models import (
    POKUS_LABELS,
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
)
from softwaretestingklasifikator.domain.stats import GRADE_ORDER, YearStats
from softwaretestingklasifikator.ui.theme import (
    DOCHAZKA_FAIL_BG,
    DOCHAZKA_OK_BG,
    GRADE_BG,
    GRADE_FG,
    POKUS_BG,
    POKUS_FG,
    REPETENT_ROW_BG,
)

_COUNT_BG = QColor(70, 130, 180)
_COUNT_FG = QColor(255, 255, 255)


def _qcolor_to_css(c: QColor) -> str:
    return f"rgb({c.red()}, {c.green()}, {c.blue()})"


def _make_cell(text: str, bg: QColor, fg: QColor, *, bold: bool = False, min_width: int = 0) -> QLabel:
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setMargin(4)
    if min_width:
        lbl.setMinimumWidth(min_width)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(
        f"background-color: {_qcolor_to_css(bg)};"
        f"color: {_qcolor_to_css(fg)};"
        f"font-weight: {weight};"
        f"border: 1px solid rgba(0,0,0,0.15);"
    )
    return lbl


def _make_section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    font = QFont()
    font.setBold(True)
    lbl.setFont(font)
    lbl.setStyleSheet("color: rgba(0,0,0,0.7); padding-top: 8px;")
    return lbl


class StatsPanel(QWidget):
    """Pravý dolní dock se statistikou ročníku."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)
        self.set_stats(YearStats())
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)

    def set_stats(self, stats: YearStats) -> None:
        # Vyčistit
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        # Známky
        self._layout.addWidget(_make_section_title("Počet známek"))
        grade_grid = QGridLayout()
        grade_grid.setSpacing(0)
        for row, letter in enumerate(GRADE_ORDER):
            bg = GRADE_BG.get(letter)
            fg = GRADE_FG.get(letter)
            grade_grid.addWidget(_make_cell(letter, bg, fg, bold=True, min_width=40), row, 0)
            grade_grid.addWidget(
                _make_cell(str(stats.grades.get(letter, 0)), _COUNT_BG, _COUNT_FG, bold=True, min_width=40),
                row, 1,
            )
        self._layout.addLayout(grade_grid)

        # Splnilo / Nesplnilo / Celkem
        self._layout.addWidget(_make_section_title("Splnilo / Nesplnilo"))
        sn_grid = QGridLayout()
        sn_grid.setSpacing(0)
        sn_grid.addWidget(_make_cell("Splnilo", DOCHAZKA_OK_BG, QColor(20, 60, 20), bold=True), 0, 0)
        sn_grid.addWidget(_make_cell(str(stats.splnilo), _COUNT_BG, _COUNT_FG, bold=True, min_width=40), 0, 1)
        sn_grid.addWidget(_make_cell("Nesplnilo", DOCHAZKA_FAIL_BG, QColor(255, 255, 255), bold=True), 1, 0)
        sn_grid.addWidget(_make_cell(str(stats.nesplnilo), _COUNT_BG, _COUNT_FG, bold=True), 1, 1)
        sn_grid.addWidget(_make_cell("Celkem", QColor(220, 220, 220), QColor(40, 40, 40), bold=True), 2, 0)
        sn_grid.addWidget(_make_cell(str(stats.celkem), _COUNT_BG, _COUNT_FG, bold=True), 2, 1)
        self._layout.addLayout(sn_grid)

        # Odevzdal — řádný / oprava / po termínu / neodevzdal (horizontální bar)
        self._layout.addWidget(_make_section_title("Stav odevzdání"))
        odev_row = QHBoxLayout()
        odev_row.setSpacing(0)
        for state in (POKUS_RADNY, POKUS_OPRAVNY, POKUS_PO_TERMINU, POKUS_NEODEVZDAL):
            count = stats.pokus_counts.get(state, 0)
            cell = _make_cell(
                f"{POKUS_LABELS[state]}\n{count}",
                POKUS_BG[state],
                POKUS_FG[state],
                bold=True,
                min_width=70,
            )
            cell.setWordWrap(True)
            odev_row.addWidget(cell)
        self._layout.addLayout(odev_row)

        # Docházka
        self._layout.addWidget(_make_section_title("Docházka"))
        doch_row = QHBoxLayout()
        doch_row.setSpacing(0)
        doch_row.addWidget(_make_cell(
            f"Splněno\n{stats.dochazka_splneno}",
            DOCHAZKA_OK_BG, QColor(20, 60, 20), bold=True, min_width=70,
        ))
        doch_row.addWidget(_make_cell(
            f"Nesplněno\n{stats.dochazka_nesplneno}",
            DOCHAZKA_FAIL_BG, QColor(255, 255, 255), bold=True, min_width=70,
        ))
        self._layout.addLayout(doch_row)

        # Repetenti
        rep_row = QHBoxLayout()
        rep_label = _make_cell("Repetenti", REPETENT_ROW_BG, QColor(80, 40, 0), bold=True, min_width=100)
        rep_count = _make_cell(str(stats.repetenti), _COUNT_BG, _COUNT_FG, bold=True, min_width=50)
        rep_row.addWidget(rep_label)
        rep_row.addWidget(rep_count)
        rep_row.addStretch(1)
        self._layout.addSpacing(8)
        self._layout.addLayout(rep_row)

        # spacer
        spacer = QFrame()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(spacer)
