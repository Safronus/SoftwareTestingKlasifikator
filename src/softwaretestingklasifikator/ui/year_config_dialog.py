"""Dialog pro založení / editaci ročníku (rok + deadliny)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from softwaretestingklasifikator.domain.models import YearDeadlines


class YearConfigDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        year: int | None = None,
        deadlines: YearDeadlines | None = None,
        existing_years: set[int] | None = None,
        edit_only_deadlines: bool = False,
    ) -> None:
        super().__init__(parent)
        self._existing_years = existing_years or set()
        self.setWindowTitle("Ročník — nastavení")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.spin_year = QSpinBox()
        self.spin_year.setRange(2020, 2100)
        self.spin_year.setValue(year or date.today().year)
        self.spin_year.setEnabled(not edit_only_deadlines)
        form.addRow("Akademický rok (LS):", self.spin_year)

        self.date_first = QDateEdit()
        self.date_first.setDisplayFormat("yyyy-MM-dd")
        self.date_first.setCalendarPopup(True)
        self.date_first.setSpecialValueText("—")
        self.date_first.setMinimumDate(QDate(2000, 1, 1))

        self.date_second = QDateEdit()
        self.date_second.setDisplayFormat("yyyy-MM-dd")
        self.date_second.setCalendarPopup(True)
        self.date_second.setSpecialValueText("—")
        self.date_second.setMinimumDate(QDate(2000, 1, 1))

        if deadlines:
            if deadlines.first:
                self.date_first.setDate(QDate(deadlines.first.year, deadlines.first.month, deadlines.first.day))
            else:
                self.date_first.setDate(self.date_first.minimumDate())
            if deadlines.second:
                self.date_second.setDate(QDate(deadlines.second.year, deadlines.second.month, deadlines.second.day))
            else:
                self.date_second.setDate(self.date_second.minimumDate())
        else:
            self.date_first.setDate(self.date_first.minimumDate())
            self.date_second.setDate(self.date_second.minimumDate())

        form.addRow("Deadline 1. pokusu:", self.date_first)
        form.addRow("Deadline 2. pokusu:", self.date_second)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if self.spin_year.isEnabled() and self.spin_year.value() in self._existing_years:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Ročník existuje", f"Pro rok {self.spin_year.value()} už soubor existuje.")
            return
        self.accept()

    def selected_year(self) -> int:
        return self.spin_year.value()

    def selected_deadlines(self) -> YearDeadlines:
        def from_de(de: QDateEdit) -> date | None:
            if de.date() == de.minimumDate():
                return None
            d = de.date()
            return date(d.year(), d.month(), d.day())

        return YearDeadlines(first=from_de(self.date_first), second=from_de(self.date_second))
