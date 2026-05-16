"""Dock widget se statistikou ročníku — známky, splnilo, odevzdal, repetenti."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from softwaretestingklasifikator.config import DATE_FORMAT_PY
from softwaretestingklasifikator.domain.models import (
    POKUS_LABELS,
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
    YearDeadlines,
)
from softwaretestingklasifikator.domain.stats import GRADE_ORDER, YearStats
from softwaretestingklasifikator.ui.theme import (
    DOCHAZKA_FAIL_BG,
    DOCHAZKA_OK_BG,
    GRADE_BG,
    GRADE_FG,
    ISTQB_BG,
    ISTQB_FG,
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
    # Bílý text na tmavě modrém banneru — čitelné v light i dark mode docku.
    lbl.setStyleSheet(
        "background-color: rgb(60, 90, 130);"
        "color: white;"
        "padding: 5px 8px;"
        "margin-top: 6px;"
        "border-radius: 2px;"
    )
    return lbl


class StatsPanel(QWidget):
    """Pravý dolní dock se statistikou ročníku.

    Strategie: vnitřní `_inner` widget je vždy kompletně nahrazen
    (re-create) — bez `takeAt`/`deleteLater` race se starými prvky.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner: QWidget | None = None
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        self.set_stats(YearStats())

    def set_stats(self, stats: YearStats, deadlines: YearDeadlines | None = None) -> None:
        # Nahradíme celý vnitřní widget — žádné race s deleteLater.
        new_inner = QWidget(self)
        layout = QVBoxLayout(new_inner)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Deadliny (nahoře)
        if deadlines is not None and (deadlines.first or deadlines.second):
            layout.addWidget(_make_section_title("Termíny odevzdání"))
            dl_grid = QGridLayout()
            dl_grid.setSpacing(0)
            dl_grid.addWidget(_make_cell(
                "1. termín", QColor(146, 208, 80), QColor(20, 60, 20), bold=True), 0, 0)
            dl_grid.addWidget(_make_cell(
                deadlines.first.strftime(DATE_FORMAT_PY) if deadlines.first else "—",
                QColor(245, 245, 245), QColor(40, 40, 40), bold=False), 0, 1)
            dl_grid.addWidget(_make_cell(
                "Opravný", QColor(246, 178, 107), QColor(90, 50, 10), bold=True), 1, 0)
            dl_grid.addWidget(_make_cell(
                deadlines.second.strftime(DATE_FORMAT_PY) if deadlines.second else "—",
                QColor(245, 245, 245), QColor(40, 40, 40), bold=False), 1, 1)
            layout.addLayout(dl_grid)

        # Známky
        layout.addWidget(_make_section_title("Počet známek"))
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
        layout.addLayout(grade_grid)

        # Splnilo / Nesplnilo / Celkem
        layout.addWidget(_make_section_title("Splnilo / Nesplnilo"))
        sn_grid = QGridLayout()
        sn_grid.setSpacing(0)
        splnilo_text = (
            f"Splnilo  ({stats.splnilo_diky_bonusu} díky bonusu)"
            if stats.splnilo_diky_bonusu else "Splnilo"
        )
        sn_grid.addWidget(_make_cell(splnilo_text, DOCHAZKA_OK_BG, QColor(20, 60, 20), bold=True), 0, 0)
        sn_grid.addWidget(_make_cell(str(stats.splnilo), _COUNT_BG, _COUNT_FG, bold=True, min_width=40), 0, 1)
        sn_grid.addWidget(_make_cell("Nesplnilo", DOCHAZKA_FAIL_BG, QColor(255, 255, 255), bold=True), 1, 0)
        sn_grid.addWidget(_make_cell(str(stats.nesplnilo), _COUNT_BG, _COUNT_FG, bold=True), 1, 1)
        sn_grid.addWidget(_make_cell("Celkem", QColor(220, 220, 220), QColor(40, 40, 40), bold=True), 2, 0)
        sn_grid.addWidget(_make_cell(str(stats.celkem), _COUNT_BG, _COUNT_FG, bold=True), 2, 1)
        layout.addLayout(sn_grid)

        # Stav odevzdání
        layout.addWidget(_make_section_title("Stav odevzdání"))
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
        layout.addLayout(odev_row)

        # Docházka
        layout.addWidget(_make_section_title("Docházka"))
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
        layout.addLayout(doch_row)

        # ISTQB CTFL + Repetenti + Ukončilo studium
        layout.addWidget(_make_section_title("ISTQB / Repetenti / Ukončení"))
        extra = QGridLayout()
        extra.setSpacing(0)
        extra.addWidget(_make_cell("ISTQB CTFL", ISTQB_BG, ISTQB_FG, bold=True, min_width=130), 0, 0)
        extra.addWidget(_make_cell(str(stats.istqb), _COUNT_BG, _COUNT_FG, bold=True, min_width=50), 0, 1)
        extra.addWidget(_make_cell("Repetenti", REPETENT_ROW_BG, QColor(80, 40, 0), bold=True, min_width=130), 1, 0)
        extra.addWidget(_make_cell(str(stats.repetenti), _COUNT_BG, _COUNT_FG, bold=True, min_width=50), 1, 1)
        extra.addWidget(_make_cell("Ukončilo studium", QColor(220, 220, 220), QColor(60, 60, 60), bold=True, min_width=130), 2, 0)
        extra.addWidget(_make_cell(str(stats.ukoncilo), _COUNT_BG, _COUNT_FG, bold=True, min_width=50), 2, 1)
        layout.addLayout(extra)

        layout.addStretch(1)

        # Swap inner widget atomically.
        if self._inner is not None:
            self.layout().removeWidget(self._inner)
            self._inner.setParent(None)
            self._inner.deleteLater()
        self.layout().addWidget(new_inner)
        self._inner = new_inner
