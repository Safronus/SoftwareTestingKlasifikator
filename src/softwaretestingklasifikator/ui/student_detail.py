"""Detail panel pro editaci jednoho studenta — primárně bonus alokace."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from softwaretestingklasifikator.config import (
    GATE_PROJEKT,
    GATE_TEST1,
    GATE_TEST2,
    MAX_PROJEKT,
    MAX_TEST1,
    MAX_TEST2,
    POINTS_DECIMALS,
)
from softwaretestingklasifikator.domain.bonus import suggest_allocation
from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import (
    POKUS_LABELS,
    POKUS_VALUES,
    BonusBreakdown,
    Student,
)


class StudentDetailPanel(QWidget):
    """Pravý dock panel: úprava bodů, bonusové alokace, komentář."""

    studentEdited = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._student: Student | None = None
        self._suspend_signals = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.title_label = QLabel("Vyber studenta v tabulce")
        font = self.title_label.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        self.id_label = QLabel("")
        self.id_label.setStyleSheet("color: gray;")
        layout.addWidget(self.id_label)

        # --- Body --------------------------------------------------------
        points_box = QGroupBox("Body z částí")
        pf = QFormLayout(points_box)
        self.spin_test1 = self._make_spin(0, MAX_TEST1)
        self.spin_test2 = self._make_spin(0, MAX_TEST2)
        self.spin_projekt = self._make_spin(0, MAX_PROJEKT)
        pf.addRow(f"Test č. 1 (max {MAX_TEST1:g}, brána {GATE_TEST1:g})", self.spin_test1)
        pf.addRow(f"Test č. 2 (max {MAX_TEST2:g}, brána {GATE_TEST2:g})", self.spin_test2)
        pf.addRow(f"Projekt (max {MAX_PROJEKT:g}, brána {GATE_PROJEKT:g})", self.spin_projekt)
        layout.addWidget(points_box)

        # --- Bonus -------------------------------------------------------
        bonus_box = QGroupBox("Bonusové body")
        bf = QFormLayout(bonus_box)
        self.spin_bonus_t1 = self._make_spin(0, MAX_TEST1)
        self.spin_bonus_t2 = self._make_spin(0, MAX_TEST2)
        self.spin_bonus_pj = self._make_spin(0, MAX_PROJEKT)
        bf.addRow("→ Test č. 1", self.spin_bonus_t1)
        bf.addRow("→ Test č. 2", self.spin_bonus_t2)
        bf.addRow("→ Projekt", self.spin_bonus_pj)

        suggest_row = QHBoxLayout()
        self.spin_total_bonus = self._make_spin(0, MAX_TEST1 + MAX_TEST2 + MAX_PROJEKT)
        self.btn_suggest = QPushButton("Auto-rozdělit")
        self.btn_suggest.setToolTip(
            "Navrhne rozdělení: nejdřív doplnit do brány, "
            "pak maximalizovat známku přeskočením prahů pásem."
        )
        suggest_row.addWidget(QLabel("Celkový bonus k rozdělení:"))
        suggest_row.addWidget(self.spin_total_bonus)
        suggest_row.addWidget(self.btn_suggest)
        bf.addRow(suggest_row)
        layout.addWidget(bonus_box)

        # --- Ostatní -----------------------------------------------------
        meta_box = QGroupBox("Hodnocení a meta")
        mf = QFormLayout(meta_box)
        from PySide6.QtWidgets import QCheckBox, QDateEdit

        self.chk_dochazka = QCheckBox("Splněno")
        self.date_odevzdani = QDateEdit()
        self.date_odevzdani.setDisplayFormat("yyyy-MM-dd")
        self.date_odevzdani.setCalendarPopup(True)
        self.date_odevzdani.setSpecialValueText("—")
        from PySide6.QtCore import QDate

        self.date_odevzdani.setMinimumDate(QDate(2000, 1, 1))
        self.combo_pokus = QComboBox()
        for v in POKUS_VALUES:
            self.combo_pokus.addItem(POKUS_LABELS[v], v)
        self.txt_komentar = QTextEdit()
        self.txt_komentar.setPlaceholderText("Volitelná poznámka")
        self.txt_komentar.setFixedHeight(70)

        mf.addRow("Docházka", self.chk_dochazka)
        mf.addRow("Datum odevzdání", self.date_odevzdani)
        mf.addRow("Stav odevzdání", self.combo_pokus)
        mf.addRow("Komentář", self.txt_komentar)
        layout.addWidget(meta_box)

        # --- Souhrn ------------------------------------------------------
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("padding: 8px; background: rgba(127,127,127,0.08);")
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.summary_label)

        layout.addStretch(1)

        # Signals
        self.spin_test1.valueChanged.connect(self._on_value_change)
        self.spin_test2.valueChanged.connect(self._on_value_change)
        self.spin_projekt.valueChanged.connect(self._on_value_change)
        self.spin_bonus_t1.valueChanged.connect(self._on_value_change)
        self.spin_bonus_t2.valueChanged.connect(self._on_value_change)
        self.spin_bonus_pj.valueChanged.connect(self._on_value_change)
        self.chk_dochazka.toggled.connect(self._on_value_change)
        self.date_odevzdani.dateChanged.connect(self._on_value_change)
        self.combo_pokus.currentIndexChanged.connect(self._on_value_change)
        self.txt_komentar.textChanged.connect(self._on_value_change)
        self.btn_suggest.clicked.connect(self._apply_suggest)

        self.set_student(None)

    # ---- helpers -------------------------------------------------------
    @staticmethod
    def _make_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setDecimals(POINTS_DECIMALS)
        s.setRange(float(minimum), float(maximum))
        s.setSingleStep(1.0)
        s.setAlignment(Qt.AlignmentFlag.AlignRight)
        return s

    # ---- public API ----------------------------------------------------
    def current_student(self) -> Student | None:
        return self._student

    def set_student(self, student: Student | None) -> None:
        self._student = student
        self._suspend_signals = True
        try:
            if student is None:
                self.title_label.setText("Vyber studenta v tabulce")
                self.id_label.setText("")
                for w in (self.spin_test1, self.spin_test2, self.spin_projekt,
                          self.spin_bonus_t1, self.spin_bonus_t2, self.spin_bonus_pj,
                          self.spin_total_bonus):
                    w.setEnabled(False)
                    w.setValue(0)
                for w in (self.chk_dochazka, self.date_odevzdani,
                          self.combo_pokus, self.txt_komentar, self.btn_suggest):
                    w.setEnabled(False)
                self.chk_dochazka.setChecked(False)
                self.txt_komentar.clear()
                self.summary_label.clear()
                return

            for w in (self.spin_test1, self.spin_test2, self.spin_projekt,
                      self.spin_bonus_t1, self.spin_bonus_t2, self.spin_bonus_pj,
                      self.spin_total_bonus,
                      self.chk_dochazka, self.date_odevzdani, self.combo_pokus,
                      self.txt_komentar, self.btn_suggest):
                w.setEnabled(True)

            self.title_label.setText(student.display_name() or f"({student.os_cislo})")
            self.id_label.setText(f"Os. č.: {student.os_cislo}    Username: {student.username}    Email: {student.email}")

            self.spin_test1.setValue(student.test1)
            self.spin_test2.setValue(student.test2)
            self.spin_projekt.setValue(student.projekt)
            self.spin_bonus_t1.setValue(student.bonus.test1)
            self.spin_bonus_t2.setValue(student.bonus.test2)
            self.spin_bonus_pj.setValue(student.bonus.projekt)
            self.spin_total_bonus.setValue(student.bonus.total())
            self.chk_dochazka.setChecked(student.dochazka)

            from PySide6.QtCore import QDate

            if student.datum_odevzdani:
                d = student.datum_odevzdani
                self.date_odevzdani.setDate(QDate(d.year, d.month, d.day))
            else:
                self.date_odevzdani.setDate(self.date_odevzdani.minimumDate())

            pokus_idx = self.combo_pokus.findData(student.pokus)
            self.combo_pokus.setCurrentIndex(pokus_idx if pokus_idx >= 0 else 0)
            self.txt_komentar.setPlainText(student.komentar)
        finally:
            self._suspend_signals = False
        self._refresh_summary()

    # ---- internal ------------------------------------------------------
    def _on_value_change(self) -> None:
        if self._suspend_signals or self._student is None:
            return
        s = self._student
        s.test1 = round(self.spin_test1.value(), POINTS_DECIMALS)
        s.test2 = round(self.spin_test2.value(), POINTS_DECIMALS)
        s.projekt = round(self.spin_projekt.value(), POINTS_DECIMALS)
        s.bonus = BonusBreakdown(
            test1=round(self.spin_bonus_t1.value(), POINTS_DECIMALS),
            test2=round(self.spin_bonus_t2.value(), POINTS_DECIMALS),
            projekt=round(self.spin_bonus_pj.value(), POINTS_DECIMALS),
        )
        s.dochazka = self.chk_dochazka.isChecked()
        d = self.date_odevzdani.date()
        if d == self.date_odevzdani.minimumDate():
            s.datum_odevzdani = None
        else:
            from datetime import date as _date

            s.datum_odevzdani = _date(d.year(), d.month(), d.day())
        s.pokus = self.combo_pokus.currentData() or "radny"
        s.komentar = self.txt_komentar.toPlainText()

        # Synchronizace pole "Celkový bonus" — odráží součet.
        self._suspend_signals = True
        try:
            self.spin_total_bonus.setValue(s.bonus.total())
        finally:
            self._suspend_signals = False

        self._refresh_summary()
        self.studentEdited.emit()

    def _apply_suggest(self) -> None:
        if self._student is None:
            return
        s = self._student
        total = self.spin_total_bonus.value()
        allocation = suggest_allocation(
            test1=s.test1, test2=s.test2, projekt=s.projekt, total_bonus=total,
        )
        self._suspend_signals = True
        try:
            self.spin_bonus_t1.setValue(allocation.test1)
            self.spin_bonus_t2.setValue(allocation.test2)
            self.spin_bonus_pj.setValue(allocation.projekt)
        finally:
            self._suspend_signals = False
        self._on_value_change()

    def _refresh_summary(self) -> None:
        if self._student is None:
            return
        result = evaluate(self._student)
        gate_parts = []
        gate_parts.append(("Test 1", result.test1_total, GATE_TEST1, result.gate.test1_ok, ""))
        gate_parts.append(("Test 2", result.test2_total, GATE_TEST2, result.gate.test2_ok, ""))
        gate_parts.append((
            "Projekt", result.projekt_total, GATE_PROJEKT, result.gate.projekt_ok,
            f" ({result.projekt_percent * 100:.1f} %)",
        ))
        rows = []
        for name, total, gate, ok, suffix in gate_parts:
            badge = "✓" if ok else "✗"
            rows.append(f"<b>{name}:</b> {total:g} / brána {gate:g}{suffix} {badge}")
        doch_badge = "✓" if result.gate.dochazka_ok else "✗"
        rows.append(f"<b>Docházka:</b> {'splněno' if self._student.dochazka else 'nesplněno'} {doch_badge}")
        odev_badge = "✓" if result.gate.odevzdano_ok else "✗"
        rows.append(f"<b>Stav odevzdání:</b> {POKUS_LABELS.get(self._student.pokus, self._student.pokus)} {odev_badge}")
        grade_color = {
            "A": "#3D8B40", "B": "#5E9933", "C": "#A38A00",
            "D": "#A66726", "E": "#A1422C", "F": "#A0282A",
        }.get(result.znamka, "#666")
        rows.append(
            f"<b>Celkem:</b> {result.celkem:g}    "
            f"<b>Známka:</b> <span style='font-size:14pt; font-weight:bold; color:{grade_color};'>{result.znamka}</span>"
        )
        self.summary_label.setText("<br>".join(rows))
