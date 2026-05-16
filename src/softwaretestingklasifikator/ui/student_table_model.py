"""Qt model nad seznamem studentů s počítanými sloupci (Celkem, Známka)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal

from softwaretestingklasifikator.config import (
    MAX_PROJEKT,
    MAX_TEST1,
    MAX_TEST2,
    POINTS_DECIMALS,
)
from softwaretestingklasifikator.domain.grading import evaluate
from softwaretestingklasifikator.domain.models import Student

# (klíč, label, editable)
COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("os_cislo", "Os. číslo", False),
    ("prijmeni", "Příjmení", True),
    ("jmeno", "Jméno", True),
    ("test1", "Test 1", True),
    ("test2", "Test 2", True),
    ("projekt", "Projekt", True),
    ("projekt_pct", "Projekt %", False),
    ("bonus_total", "Bonus", False),
    ("dochazka", "Docházka", True),
    ("datum_odevzdani", "Odevzdání", True),
    ("pokus", "Pokus", True),
    ("celkem", "Celkem", False),
    ("znamka", "Známka", False),
    ("komentar", "Komentář", True),
)


def _r(v: float) -> float:
    return round(float(v), POINTS_DECIMALS)


class StudentTableModel(QAbstractTableModel):
    studentChanged = Signal(int)  # row index

    def __init__(self, students: list[Student] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._students: list[Student] = students or []

    # ---- public API ----
    def students(self) -> list[Student]:
        return self._students

    def set_students(self, students: list[Student]) -> None:
        self.beginResetModel()
        self._students = students
        self.endResetModel()

    def student_at(self, row: int) -> Student | None:
        if 0 <= row < len(self._students):
            return self._students[row]
        return None

    def emit_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._students):
            top = self.index(row, 0)
            bottom = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(top, bottom, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
            self.studentChanged.emit(row)

    def add_student(self, student: Student) -> None:
        row = len(self._students)
        self.beginInsertRows(QModelIndex(), row, row)
        self._students.append(student)
        self.endInsertRows()
        self.studentChanged.emit(row)

    def remove_row(self, row: int) -> None:
        if not (0 <= row < len(self._students)):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self._students.pop(row)
        self.endRemoveRows()

    # ---- Qt API ----
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._students)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: D401
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return COLUMNS[section][1]
        return section + 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        key, _, editable = COLUMNS[index.column()]
        base = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if key == "dochazka":
            base |= Qt.ItemFlag.ItemIsUserCheckable
        elif editable:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        student = self._students[index.row()]
        key, _, _ = COLUMNS[index.column()]
        result = evaluate(student)

        if key == "dochazka" and role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if student.dochazka else Qt.CheckState.Unchecked

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if key == "os_cislo":
                return student.os_cislo
            if key == "jmeno":
                return student.jmeno
            if key == "prijmeni":
                return student.prijmeni
            if key == "test1":
                return _r(student.test1)
            if key == "test2":
                return _r(student.test2)
            if key == "projekt":
                return _r(student.projekt)
            if key == "projekt_pct":
                return f"{result.projekt_percent * 100:.1f} %"
            if key == "bonus_total":
                return _r(student.bonus.total())
            if key == "dochazka":
                # CheckStateRole je výše; tady jen prázdný display.
                return ""
            if key == "datum_odevzdani":
                return student.datum_odevzdani.isoformat() if student.datum_odevzdani else ""
            if key == "pokus":
                return student.pokus
            if key == "celkem":
                return _r(result.celkem)
            if key == "znamka":
                return student.znamka_override or result.znamka
            if key == "komentar":
                return student.komentar

        if role == Qt.ItemDataRole.ToolTipRole:
            if key == "znamka" and not result.gate.all_ok:
                reasons = []
                if not result.gate.test1_ok:
                    reasons.append("Test 1 < 15")
                if not result.gate.test2_ok:
                    reasons.append("Test 2 < 15")
                if not result.gate.projekt_ok:
                    reasons.append("Projekt < 90")
                if not result.gate.dochazka_ok:
                    reasons.append("Docházka nesplněna")
                return "F (brána): " + ", ".join(reasons)
            if key == "celkem":
                return (
                    f"Test 1: {result.test1_total:g} · "
                    f"Test 2: {result.test2_total:g} · "
                    f"Projekt: {result.projekt_total:g}"
                )

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ("test1", "test2", "projekt", "projekt_pct", "bonus_total", "celkem", "pokus"):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if key in ("znamka", "dochazka"):
                return int(Qt.AlignmentFlag.AlignCenter)

        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        student = self._students[index.row()]
        key, _, editable = COLUMNS[index.column()]

        if key == "dochazka" and role == Qt.ItemDataRole.CheckStateRole:
            checked = Qt.CheckState(value) == Qt.CheckState.Checked
            if student.dochazka == checked:
                return False
            student.dochazka = checked
            self.emit_row_changed(index.row())
            return True

        if role != Qt.ItemDataRole.EditRole or not editable:
            return False

        try:
            if key == "jmeno":
                student.jmeno = str(value).strip()
            elif key == "prijmeni":
                student.prijmeni = str(value).strip()
            elif key == "test1":
                student.test1 = max(0.0, min(MAX_TEST1, _r(float(value))))
            elif key == "test2":
                student.test2 = max(0.0, min(MAX_TEST2, _r(float(value))))
            elif key == "projekt":
                student.projekt = max(0.0, min(MAX_PROJEKT, _r(float(value))))
            elif key == "datum_odevzdani":
                s = str(value).strip()
                if not s:
                    student.datum_odevzdani = None
                else:
                    student.datum_odevzdani = date.fromisoformat(s)
            elif key == "pokus":
                p = int(value)
                student.pokus = 2 if p >= 2 else 1
            elif key == "komentar":
                student.komentar = str(value)
            else:
                return False
        except (ValueError, TypeError):
            return False

        self.emit_row_changed(index.row())
        return True
