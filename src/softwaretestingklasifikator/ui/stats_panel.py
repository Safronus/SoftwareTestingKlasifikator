"""Dock widget se statistikou ročníku — známky, splnilo, odevzdal, repetenti.

Termíny odevzdání jsou editovatelné přímo zde (perzistentní QDateEdit
widgety, které přežijí rebuild statistik). Změny se okamžitě hlásí
parentovi přes signál `deadlinesChanged`.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from softwaretestingklasifikator.config import DATE_FORMAT_QT
from softwaretestingklasifikator.domain.models import (
    POKUS_LABELS,
    POKUS_NEODEVZDAL,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_RADNY,
    YearDeadlines,
)
from softwaretestingklasifikator.domain.stats import GRADE_ORDER, YearStats
from softwaretestingklasifikator.ui.grade_chart import GradeChart
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
    TEST_FAIL_BG,
    TEST_FAIL_FG,
    TEST_PASS_CLEAN_BG,
    TEST_PASS_CLEAN_FG,
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
    """Levý dock se statistikou ročníku.

    Strategie: vnitřní `_inner` widget (počty, graf, repetenti, …) se
    vždy kompletně nahrazuje (re-create) — bez `takeAt`/`deleteLater`
    race se starými prvky. Termíny odevzdání jsou ale **perzistentní**,
    aby je rebuild stats nezničil uprostřed uživatelovy editace."""

    deadlinesChanged = Signal(object)  # YearDeadlines

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._committed_deadlines = YearDeadlines()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Perzistentní editor termínů (přežije set_stats rebuildy).
        self._deadlines_widget = self._build_deadlines_widget()
        outer.addWidget(self._deadlines_widget)
        self._deadlines_widget.hide()

        self._inner: QWidget | None = None
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding,
        )
        self.set_stats(YearStats())

    # ------------------------------------------------------------------
    # Persistent deadline editor
    # ------------------------------------------------------------------
    def _build_deadlines_widget(self) -> QWidget:
        w = QWidget(self)
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 8, 8, 0)
        v.setSpacing(2)
        v.addWidget(_make_section_title("Termíny odevzdání"))

        grid = QGridLayout()
        grid.setSpacing(2)

        grid.addWidget(_make_cell(
            "1. termín", QColor(146, 208, 80), QColor(20, 60, 20), bold=True,
        ), 0, 0)
        self.date_first = QDateEdit()
        self._configure_date_edit(self.date_first)
        grid.addWidget(self.date_first, 0, 1)

        grid.addWidget(_make_cell(
            "Opravný", QColor(246, 178, 107), QColor(90, 50, 10), bold=True,
        ), 1, 0)
        self.date_second = QDateEdit()
        self._configure_date_edit(self.date_second)
        grid.addWidget(self.date_second, 1, 1)

        v.addLayout(grid)
        return w

    def _configure_date_edit(self, de: QDateEdit) -> None:
        de.setDisplayFormat(DATE_FORMAT_QT)
        de.setCalendarPopup(True)
        de.setSpecialValueText("—")
        de.setMinimumDate(QDate(2000, 1, 1))
        # Commit jen po dokončení editace (Enter / focus-out / kalendář).
        # Použití dateChanged by způsobilo rebuild panelu při každém stisku
        # klávesy, což by ukradlo focus uprostřed psaní.
        de.editingFinished.connect(self._on_editing_finished)
        # Kalendářový pop-up vrací nezpracovanou hodnotu přes dateChanged
        # AŽ KDYŽ se popup zavře a focus odejde — to už pokryje editingFinished.

    def _collect_deadlines(self) -> YearDeadlines:
        def from_de(de: QDateEdit) -> date | None:
            if de.date() == de.minimumDate():
                return None
            qd = de.date()
            return date(qd.year(), qd.month(), qd.day())

        return YearDeadlines(
            first=from_de(self.date_first),
            second=from_de(self.date_second),
        )

    def _apply_deadlines_silently(self, dl: YearDeadlines) -> None:
        """Naplnit pickery hodnotami bez vyvolání signálu (sync z parentu)."""
        for de, val in ((self.date_first, dl.first), (self.date_second, dl.second)):
            de.blockSignals(True)
            if val is None:
                de.setDate(de.minimumDate())
            else:
                de.setDate(QDate(val.year, val.month, val.day))
            de.blockSignals(False)

    def _on_editing_finished(self) -> None:
        new = self._collect_deadlines()
        # Validace: pokud jsou nastavené oba, opravný musí být po řádném.
        if (
            new.first is not None
            and new.second is not None
            and new.second <= new.first
        ):
            QMessageBox.warning(
                self,
                "Neplatné termíny",
                "Deadline 2. pokusu (opravný) musí být později než "
                "deadline 1. pokusu.",
            )
            self._apply_deadlines_silently(self._committed_deadlines)
            return
        if new == self._committed_deadlines:
            return
        self._committed_deadlines = new
        self.deadlinesChanged.emit(new)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_stats(self, stats: YearStats, deadlines: YearDeadlines | None = None) -> None:
        # 1) Sync perzistentního editoru termínů.
        if deadlines is None:
            self._deadlines_widget.hide()
            # Nepřepisuj _committed (rok není načtený) — sync ale pickery,
            # aby případný flash zobrazení nezmátl uživatele.
            self._committed_deadlines = YearDeadlines()
            self._apply_deadlines_silently(self._committed_deadlines)
        else:
            self._deadlines_widget.show()
            self._committed_deadlines = deadlines
            self._apply_deadlines_silently(deadlines)

        # 2) Rebuild dynamické části (počty, graf, repetenti, …).
        new_inner = QWidget(self)
        layout = QVBoxLayout(new_inner)
        layout.setContentsMargins(8, 4, 8, 8)
        layout.setSpacing(6)

        # Známky — tabulka + sloupcový graf
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

        chart = GradeChart(new_inner)
        chart.set_counts(stats.grades)
        layout.addWidget(chart, 0, Qt.AlignmentFlag.AlignHCenter)

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

        # Splnění bran testů (každý test zvlášť — díky bonusu v závorce)
        layout.addWidget(_make_section_title("Splnění testů"))
        tests_grid = QGridLayout()
        tests_grid.setSpacing(0)
        rows = (
            ("Test 1 splnilo", stats.test1_splnilo, stats.test1_diky_bonusu, True),
            ("Test 1 nesplnilo", stats.test1_nesplnilo, 0, False),
            ("Test 2 splnilo", stats.test2_splnilo, stats.test2_diky_bonusu, True),
            ("Test 2 nesplnilo", stats.test2_nesplnilo, 0, False),
        )
        for row_idx, (label, count, diky_bonusu, is_pass) in enumerate(rows):
            text = (
                f"{label}  ({diky_bonusu} díky bonusu)"
                if is_pass and diky_bonusu
                else label
            )
            bg = TEST_PASS_CLEAN_BG if is_pass else TEST_FAIL_BG
            fg = TEST_PASS_CLEAN_FG if is_pass else TEST_FAIL_FG
            tests_grid.addWidget(_make_cell(text, bg, fg, bold=True), row_idx, 0)
            tests_grid.addWidget(
                _make_cell(str(count), _COUNT_BG, _COUNT_FG, bold=True, min_width=40),
                row_idx, 1,
            )
        layout.addLayout(tests_grid)

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

        # Swap inner. hide() PŘED removeWidget zajistí, že starý widget
        # neblikne jako floating top-level okno.
        if self._inner is not None:
            self._inner.hide()
            self.layout().removeWidget(self._inner)
            self._inner.deleteLater()
        self.layout().addWidget(new_inner)
        self._inner = new_inner
