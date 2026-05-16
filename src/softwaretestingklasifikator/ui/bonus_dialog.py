"""Dialog pro nastavení bonusových bodů studenta — náhrada za bývalý detail panel.

Obsahuje 3 spinboxy (T1/T2/Projekt), pole pro celkový bonus a tlačítko
auto-rozdělení (priorita: doplnit do brány, pak maximalizovat známku).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from softwaretestingklasifikator.config import (
    MAX_PROJEKT,
    MAX_TEST1,
    MAX_TEST2,
    POINTS_DECIMALS,
)
from softwaretestingklasifikator.domain.bonus import suggest_allocation
from softwaretestingklasifikator.domain.models import BonusBreakdown, Student


class BonusDialog(QDialog):
    def __init__(self, student: Student, parent=None) -> None:
        super().__init__(parent)
        self._student = student
        self.setWindowTitle(f"Bonus — {student.display_name() or student.os_cislo}")
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        info = QLabel(
            f"<b>{student.display_name() or student.os_cislo}</b><br>"
            f"<span style='color:gray;'>"
            f"Test 1: {student.test1:g} · Test 2: {student.test2:g} · "
            f"Projekt: {student.projekt:g}"
            f"</span>"
        )
        layout.addWidget(info)

        form = QFormLayout()
        self.spin_t1 = self._make_spin(0, MAX_TEST1)
        self.spin_t2 = self._make_spin(0, MAX_TEST2)
        self.spin_pj = self._make_spin(0, MAX_PROJEKT)
        self.spin_t1.setValue(student.bonus.test1)
        self.spin_t2.setValue(student.bonus.test2)
        self.spin_pj.setValue(student.bonus.projekt)
        form.addRow("Bonus → Test 1", self.spin_t1)
        form.addRow("Bonus → Test 2", self.spin_t2)
        form.addRow("Bonus → Projekt", self.spin_pj)
        layout.addLayout(form)

        # Auto-rozdělit
        auto_row = QHBoxLayout()
        self.spin_total = self._make_spin(0, MAX_TEST1 + MAX_TEST2 + MAX_PROJEKT)
        self.spin_total.setValue(student.bonus.total())
        self.btn_suggest = QPushButton("Auto-rozdělit")
        self.btn_suggest.setToolTip(
            "Doplní nejprve do brány (T1/T2/Projekt na 15/15/90), "
            "pak maximalizuje známku."
        )
        self.btn_suggest.clicked.connect(self._apply_suggest)
        auto_row.addWidget(QLabel("Celkový bonus k rozdělení:"))
        auto_row.addWidget(self.spin_total)
        auto_row.addWidget(self.btn_suggest)
        layout.addLayout(auto_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Sync total at každé změně dílčí složky.
        for spin in (self.spin_t1, self.spin_t2, self.spin_pj):
            spin.valueChanged.connect(self._sync_total)

    @staticmethod
    def _make_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setDecimals(POINTS_DECIMALS)
        s.setRange(float(minimum), float(maximum))
        s.setSingleStep(1.0)
        s.setAlignment(Qt.AlignmentFlag.AlignRight)
        return s

    def _sync_total(self) -> None:
        total = round(
            self.spin_t1.value() + self.spin_t2.value() + self.spin_pj.value(),
            POINTS_DECIMALS,
        )
        self.spin_total.blockSignals(True)
        try:
            self.spin_total.setValue(total)
        finally:
            self.spin_total.blockSignals(False)

    def _apply_suggest(self) -> None:
        total = self.spin_total.value()
        a = suggest_allocation(
            test1=self._student.test1,
            test2=self._student.test2,
            projekt=self._student.projekt,
            total_bonus=total,
        )
        self.spin_t1.setValue(a.test1)
        self.spin_t2.setValue(a.test2)
        self.spin_pj.setValue(a.projekt)

    def selected_bonus(self) -> BonusBreakdown:
        return BonusBreakdown(
            test1=round(self.spin_t1.value(), POINTS_DECIMALS),
            test2=round(self.spin_t2.value(), POINTS_DECIMALS),
            projekt=round(self.spin_pj.value(), POINTS_DECIMALS),
        )
