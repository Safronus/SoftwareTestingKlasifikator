"""Dialog pro založení / editaci ročníku (rok + deadliny + volitelný CSV import)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from softwaretestingklasifikator.config import DATE_FORMAT_QT
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
        self._csv_path: Path | None = None
        self._edit_only_deadlines = edit_only_deadlines
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
        self.date_first.setDisplayFormat(DATE_FORMAT_QT)
        self.date_first.setCalendarPopup(True)
        self.date_first.setSpecialValueText("—")
        self.date_first.setMinimumDate(QDate(2000, 1, 1))

        self.date_second = QDateEdit()
        self.date_second.setDisplayFormat(DATE_FORMAT_QT)
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

        # CSV picker — jen při zakládání nového ročníku.
        if not edit_only_deadlines:
            csv_row = QHBoxLayout()
            self.csv_edit = QLineEdit()
            self.csv_edit.setPlaceholderText("Volitelný — getStudentiByRoakce CSV")
            self.csv_edit.setReadOnly(True)
            btn_browse = QPushButton("Procházet…")
            btn_browse.clicked.connect(self._browse_csv)
            btn_clear = QPushButton("Vymazat")
            btn_clear.clicked.connect(self._clear_csv)
            csv_row.addWidget(self.csv_edit, 1)
            csv_row.addWidget(btn_browse)
            csv_row.addWidget(btn_clear)
            form.addRow("Import studentů:", csv_row)

            hint = QLabel(
                "Studenti se naimportují z CSV. Pokud jejich os. číslo "
                "figuruje v některém předchozím ročníku, budou označení "
                "jako <b>repetenti</b> a převezmou body z minulého roku "
                "(bez bonusu)."
            )
            hint.setWordWrap(True)
            hint.setStyleSheet("color: rgba(127,127,127,0.9); font-size: 11px;")
            layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyber CSV se studenty (getStudentiByRoakce)",
            str(Path.home()),
            "CSV ze STAGu (*.csv);;Všechny soubory (*)",
        )
        if path:
            self._csv_path = Path(path)
            self.csv_edit.setText(path)

    def _clear_csv(self) -> None:
        self._csv_path = None
        self.csv_edit.clear()

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

    def selected_csv_path(self) -> Path | None:
        return self._csv_path
