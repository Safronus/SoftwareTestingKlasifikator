"""Qt model nad seznamem studentů s počítanými sloupci (Celkem, Známka)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont

from softwaretestingklasifikator.config import (
    DATE_FORMAT_PY,
    GATE_PROJEKT,
    GATE_TEST1,
    GATE_TEST2,
    MAX_PROJEKT,
    MAX_TEST1,
    MAX_TEST2,
    POINTS_DECIMALS,
)
from softwaretestingklasifikator.domain.bonus import suggest_allocation
from softwaretestingklasifikator.domain.grading import GradeResult, evaluate
from softwaretestingklasifikator.domain.models import (
    POKUS_LABELS,
    POKUS_VALUES,
    Student,
    _normalize_pokus,
)
from softwaretestingklasifikator.ui.theme import (
    DOCHAZKA_FAIL_BG,
    DOCHAZKA_OK_BG,
    DOCHAZKA_REPETENT_OK_BG,
    GRADE_BG,
    GRADE_FG,
    GROUP_BG,
    ISTQB_BG,
    ISTQB_FG,
    POKUS_BG,
    POKUS_FG,
    REPETENT_FG,
    REPETENT_ROW_BG,
    TEST_FAIL_BG,
    TEST_FAIL_FG,
    TEST_PASS_BONUS_BG,
    TEST_PASS_BONUS_FG,
    TEST_PASS_CLEAN_BG,
    TEST_PASS_CLEAN_FG,
    TOP_RANK_BG,
    TOP_RANK_FG,
    UKONCIL_BG,
    UKONCIL_FG,
    projekt_percent_bg,
)


def _test_status_bg(pure: float, total: float, gate: float) -> QColor:
    if pure >= gate:
        return TEST_PASS_CLEAN_BG
    if total >= gate:
        return TEST_PASS_BONUS_BG
    return TEST_FAIL_BG


def _test_status_fg(pure: float, total: float, gate: float) -> QColor:
    if pure >= gate:
        return TEST_PASS_CLEAN_FG
    if total >= gate:
        return TEST_PASS_BONUS_FG
    return TEST_FAIL_FG

# (klíč, label, editable, min_width, skupina)
# První sloupec = osobní číslo. Pořadí / Repetent / CTFL / Ukončil jsou
# umístěny mezi Známkou a Komentářem. Identita (os_cislo, příjmení, jméno)
# a Pokus jsou needitovatelné (přicházejí z importu / odvozují se).
COLUMNS: tuple[tuple[str, str, bool, int, str], ...] = (
    ("os_cislo", "Os. číslo", False, 80, "identity"),
    ("prijmeni", "Příjmení", False, 130, "identity"),
    ("jmeno", "Jméno", False, 110, "identity"),
    ("test1", "Test 1", True, 60, "tests"),
    ("test2", "Test 2", True, 60, "tests"),
    ("projekt", "Projekt", True, 70, "project"),
    ("projekt_pct", "Projekt %", False, 70, "project"),
    ("bonus_total", "Bonus", True, 150, "bonus"),
    ("celkem", "Celkem", False, 70, "result"),
    ("znamka", "Známka", False, 60, "result"),
    ("dochazka", "Docházka", True, 70, "meta"),
    ("datum_odevzdani", "Odevzdání", True, 100, "meta"),
    ("pokus", "Pokus", False, 110, "meta"),
    ("rank", "🏆", False, 36, "badge"),
    ("repetent", "REP", False, 50, "badge"),
    ("istqb", "CTFL", True, 60, "badge"),
    ("ukoncil", "Ukončil", True, 70, "badge"),
    ("komentar", "Komentář", True, 200, "note"),
)


def _r(v: float) -> float:
    return round(float(v), POINTS_DECIMALS)


# Sentinel pro memoize — None je legitimní cached hodnota.
_MISSING = object()


class StudentTableModel(QAbstractTableModel):
    studentChanged = Signal(int)  # row index

    def __init__(self, students: list[Student] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._students: list[Student] = students or []
        self._repetent_os_cisla: set[str] = set()
        self._top_ranks: dict[int, int] = {}
        # Cache GradeResult per row — invaliduje se při set_students /
        # emit_row_changed. Bez ní by se evaluate() volalo pro každou
        # buňku × roli (~5000+ volání na refresh) a scroll znatelně sekal.
        self._eval_cache: dict[int, GradeResult] = {}
        # Memoizace data() — klíč (row, col, int(role)), hodnota je výsledek
        # _compute_data. Při scrollu Qt opakovaně volá data() pro každou
        # viditelnou buňku × ~5 rolí; cache to redukuje na dict lookup.
        self._data_cache: dict[tuple[int, int, int], object] = {}

    def _invalidate_data_cache(self, row: int | None = None) -> None:
        if row is None:
            self._data_cache.clear()
            return
        # Smaže jen entries pro daný řádek.
        keys = [k for k in self._data_cache if k[0] == row]
        for k in keys:
            del self._data_cache[k]

    def _eval(self, row: int, student: Student) -> GradeResult:
        cached = self._eval_cache.get(row)
        if cached is not None:
            return cached
        r = evaluate(student, is_repetent=self.is_repetent(student))
        self._eval_cache[row] = r
        return r

    # ---- public API ----
    def students(self) -> list[Student]:
        return self._students

    def set_students(self, students: list[Student]) -> None:
        self.beginResetModel()
        self._students = students
        self._top_ranks = {}
        self._eval_cache.clear()
        self._invalidate_data_cache()
        self.endResetModel()

    def student_at(self, row: int) -> Student | None:
        if 0 <= row < len(self._students):
            return self._students[row]
        return None

    def set_repetent_os_cisla(self, os_cisla: set[str]) -> None:
        self.beginResetModel()
        self._repetent_os_cisla = set(os_cisla)
        self._eval_cache.clear()
        self._invalidate_data_cache()
        self.endResetModel()

    def repetent_os_cisla(self) -> set[str]:
        return set(self._repetent_os_cisla)

    def is_repetent(self, student: Student) -> bool:
        return bool(student.os_cislo) and student.os_cislo in self._repetent_os_cisla

    def set_top_ranks(self, ranks: dict[int, int]) -> None:
        self._top_ranks = dict(ranks)
        self._invalidate_data_cache()
        if self._students:
            top = self.index(0, 0)
            bottom = self.index(self.rowCount() - 1, self.columnCount() - 1)
            self.dataChanged.emit(top, bottom, [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.BackgroundRole,
            ])

    def emit_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._students):
            self._eval_cache.pop(row, None)
            self._invalidate_data_cache(row)
            top = self.index(row, 0)
            bottom = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(
                top, bottom,
                [
                    Qt.ItemDataRole.DisplayRole,
                    Qt.ItemDataRole.EditRole,
                    Qt.ItemDataRole.BackgroundRole,
                    Qt.ItemDataRole.ForegroundRole,
                ],
            )
            self.studentChanged.emit(row)

    def add_student(self, student: Student) -> None:
        row = len(self._students)
        self.beginInsertRows(QModelIndex(), row, row)
        self._students.append(student)
        self._eval_cache.clear()
        self._invalidate_data_cache()
        self.endInsertRows()
        self.studentChanged.emit(row)

    def remove_row(self, row: int) -> None:
        if not (0 <= row < len(self._students)):
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self._students.pop(row)
        self._eval_cache.clear()
        self._invalidate_data_cache()
        self.endRemoveRows()

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if not (0 <= column < len(COLUMNS)):
            return
        key_attr = COLUMNS[column][0]

        def keyfn(s: Student):
            from datetime import date as _date
            if key_attr == "prijmeni":
                return (s.prijmeni or "").lower()
            if key_attr == "jmeno":
                return (s.jmeno or "").lower()
            if key_attr == "os_cislo":
                return s.os_cislo or ""
            if key_attr == "test1":
                return s.test1
            if key_attr == "test2":
                return s.test2
            if key_attr == "projekt":
                return s.projekt
            if key_attr == "projekt_pct":
                return s.projekt / MAX_PROJEKT if MAX_PROJEKT else 0.0
            if key_attr == "bonus_total":
                return s.bonus.total()
            if key_attr == "dochazka":
                return 1 if s.dochazka else 0
            if key_attr == "datum_odevzdani":
                return s.datum_odevzdani or _date.min
            if key_attr == "pokus":
                return s.pokus
            if key_attr == "celkem":
                return evaluate(s).celkem
            if key_attr == "znamka":
                return s.znamka_override or evaluate(s).znamka
            if key_attr == "istqb":
                return 1 if s.ma_istqb_ctfl else 0
            if key_attr == "ukoncil":
                return 1 if s.ukoncil_studium else 0
            if key_attr == "repetent":
                return 1 if self.is_repetent(s) else 0
            if key_attr == "komentar":
                return (s.komentar or "").lower()
            return ""

        self.beginResetModel()
        self._students.sort(key=keyfn, reverse=(order == Qt.SortOrder.DescendingOrder))
        self._eval_cache.clear()
        self._top_ranks = {}
        self._invalidate_data_cache()
        self.endResetModel()

    # ---- Qt API ----
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._students)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Vertical:
            if role == Qt.ItemDataRole.DisplayRole:
                return section + 1
            return None
        if not (0 <= section < len(COLUMNS)):
            return None
        key = COLUMNS[section][0]
        if role == Qt.ItemDataRole.ToolTipRole:
            tooltips = {
                "rank": "Pořadí v top 5 podle Celkem.",
                "repetent": "Student byl podle os. čísla evidován v některém předchozím roce.",
                "istqb": "Student má certifikát ISTQB CTFL — automatická známka A.",
            }
            if key in tooltips:
                return tooltips[key]
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        return COLUMNS[section][1]

    def column_default_width(self, section: int) -> int:
        return COLUMNS[section][3]

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        key, _, editable, _, _ = COLUMNS[index.column()]
        base = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if key in ("dochazka", "istqb", "ukoncil"):
            # Repetent má docházku automaticky uznanou — needitovatelnou.
            if key == "dochazka" and self.is_repetent(self._students[index.row()]):
                pass
            else:
                base |= Qt.ItemFlag.ItemIsUserCheckable
        elif editable:
            base |= Qt.ItemFlag.ItemIsEditable
        return base

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        # Memoize: každý paint event volá data() pro každou viditelnou buňku
        # × 5 rolí. Bez cache se každé volání proženje plnou logikou
        # _compute_data (větve, instanciace QBrush, lookupy v setech…).
        if not index.isValid():
            return None
        cache_key = (index.row(), index.column(), int(role))
        cached = self._data_cache.get(cache_key, _MISSING)
        if cached is not _MISSING:
            return cached
        value = self._compute_data(index, role)
        self._data_cache[cache_key] = value
        return value

    def _compute_data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        student = self._students[index.row()]
        key, _, _, _, group = COLUMNS[index.column()]
        result = self._eval(index.row(), student)
        grade = student.znamka_override or result.znamka
        repetent = self.is_repetent(student)
        rank = self._top_ranks.get(index.row())

        if key == "dochazka" and role == Qt.ItemDataRole.CheckStateRole:
            # Repetent: automaticky uznaná docházka.
            shown = student.dochazka or repetent
            return Qt.CheckState.Checked if shown else Qt.CheckState.Unchecked
        if key == "istqb" and role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if student.ma_istqb_ctfl else Qt.CheckState.Unchecked
        if key == "ukoncil" and role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if student.ukoncil_studium else Qt.CheckState.Unchecked

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if key == "rank":
                return f"{rank}." if rank else ""
            if key == "repetent":
                return "REP" if repetent else ""
            if key == "istqb":
                # Vizuální indikátor vedle checkboxu, ať je stav vidět
                # i když je checkbox na světlém pozadí špatně vidět.
                return "Ano" if student.ma_istqb_ctfl else "Ne"
            if key == "ukoncil":
                return "Ano" if student.ukoncil_studium else "Ne"
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
                b = student.bonus
                total = _r(b.total())
                if role == Qt.ItemDataRole.EditRole:
                    return total
                if total == 0:
                    return "0"
                return f"{total:g}  ({b.test1:g} / {b.test2:g} / {b.projekt:g})"
            if key == "dochazka":
                return ""
            if key == "datum_odevzdani":
                if not student.datum_odevzdani:
                    return ""
                if role == Qt.ItemDataRole.EditRole:
                    return student.datum_odevzdani.isoformat()
                return student.datum_odevzdani.strftime(DATE_FORMAT_PY)
            if key == "pokus":
                if role == Qt.ItemDataRole.EditRole:
                    return student.pokus
                return POKUS_LABELS.get(student.pokus, student.pokus)
            if key == "celkem":
                return _r(result.celkem)
            if key == "znamka":
                return grade
            if key == "komentar":
                return student.komentar

        if role == Qt.ItemDataRole.BackgroundRole:
            # Ukončené studium: šedá přebíjí všechny ostatní barvy.
            if student.ukoncil_studium:
                return QBrush(UKONCIL_BG)
            # Stavové sloupce mají přednost před vším včetně repetenta.
            if key == "rank" and rank:
                return QBrush(TOP_RANK_BG.get(rank, TOP_RANK_BG[5]))
            if key == "znamka":
                return QBrush(GRADE_BG.get(grade, GRADE_BG["F"]))
            if key == "celkem":
                # Stejná paleta jako Známka — vizuálně spáruje body s grade.
                return QBrush(GRADE_BG.get(grade, GRADE_BG["F"]))
            if key == "dochazka":
                if student.dochazka:
                    return QBrush(DOCHAZKA_OK_BG)
                if repetent:
                    # Auto-uznáno jako repetent — světlejší odstín, ať je vidět
                    # rozdíl od ručně potvrzené docházky.
                    return QBrush(DOCHAZKA_REPETENT_OK_BG)
                return QBrush(DOCHAZKA_FAIL_BG)
            if key == "pokus":
                return QBrush(POKUS_BG.get(student.pokus, POKUS_BG["radny"]))
            if key == "datum_odevzdani":
                # Vizuálně spáruj barvu s sloupcem Pokus — uživatel okamžitě
                # vidí, jestli datum patří k řádnému / opravnému / pozdnímu /
                # neodevzdanému (i prázdná buňka má červené pozadí).
                return QBrush(POKUS_BG.get(student.pokus, POKUS_BG["radny"]))
            if key == "projekt_pct":
                return QBrush(projekt_percent_bg(result.projekt_percent))
            if key == "test1":
                return QBrush(_test_status_bg(student.test1, result.test1_total, GATE_TEST1))
            if key == "test2":
                return QBrush(_test_status_bg(student.test2, result.test2_total, GATE_TEST2))
            if key == "projekt":
                return QBrush(_test_status_bg(student.projekt, result.projekt_total, GATE_PROJEKT))
            if key == "istqb" and student.ma_istqb_ctfl:
                return QBrush(ISTQB_BG)
            # Repetent: jen ne-stavové sloupce dostávají lososové pozadí.
            if repetent:
                return QBrush(REPETENT_ROW_BG)
            # Skupinový tint pro buňky bez vlastní stavové barvy.
            if group in GROUP_BG:
                return QBrush(GROUP_BG[group])

        if role == Qt.ItemDataRole.ForegroundRole:
            # Ukončené studium: šedý text přebíjí všechny ostatní.
            if student.ukoncil_studium:
                return QBrush(UKONCIL_FG)
            # Stavové FG mají přednost.
            if key == "rank" and rank:
                return QBrush(TOP_RANK_FG)
            if key == "znamka":
                return QBrush(GRADE_FG.get(grade, GRADE_FG["F"]))
            if key == "celkem":
                return QBrush(GRADE_FG.get(grade, GRADE_FG["F"]))
            if key == "dochazka":
                return QBrush(Qt.GlobalColor.white)
            if key == "pokus":
                return QBrush(POKUS_FG.get(student.pokus, POKUS_FG["radny"]))
            if key == "datum_odevzdani":
                return QBrush(POKUS_FG.get(student.pokus, POKUS_FG["radny"]))
            if key == "test1":
                return QBrush(_test_status_fg(student.test1, result.test1_total, GATE_TEST1))
            if key == "test2":
                return QBrush(_test_status_fg(student.test2, result.test2_total, GATE_TEST2))
            if key == "projekt":
                return QBrush(_test_status_fg(student.projekt, result.projekt_total, GATE_PROJEKT))
            if key == "istqb" and student.ma_istqb_ctfl:
                return QBrush(ISTQB_FG)
            # Na repetent (lososové) pozadí ne-stavové sloupce dostávají tmavý text.
            if repetent:
                return QBrush(REPETENT_FG)
            # Defaultní tmavý text pro group-tinted buňky.
            return QBrush(QColor(30, 30, 30))

        if role == Qt.ItemDataRole.FontRole and key in ("znamka", "rank", "repetent", "istqb"):
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ToolTipRole:
            if key == "znamka" and not result.gate.all_ok:
                reasons = []
                if not result.gate.test1_ok:
                    reasons.append("Test 1 < 15")
                if not result.gate.test2_ok:
                    reasons.append("Test 2 < 15")
                if not result.gate.projekt_ok:
                    reasons.append("Projekt < 90")
                if not result.gate.odevzdano_ok:
                    reasons.append("Neodevzdal")
                if not result.gate.dochazka_ok:
                    reasons.append("Docházka nesplněna")
                return "F (brána): " + ", ".join(reasons)
            if key == "znamka" and student.ma_istqb_ctfl:
                return "Automatická A díky certifikátu ISTQB CTFL."
            if key == "celkem":
                return (
                    f"Test 1: {result.test1_total:g} · "
                    f"Test 2: {result.test2_total:g} · "
                    f"Projekt: {result.projekt_total:g} ({result.projekt_percent*100:.1f} %)"
                )
            if key in ("test1", "test2"):
                pure = student.test1 if key == "test1" else student.test2
                total = result.test1_total if key == "test1" else result.test2_total
                gate = GATE_TEST1 if key == "test1" else GATE_TEST2
                if pure >= gate:
                    return f"Splněno čistě ({pure:g} ≥ {gate:g})."
                if total >= gate:
                    return f"Splněno s bonusem ({pure:g} + bonus → {total:g} ≥ {gate:g})."
                return f"Nesplněno ({pure:g} + bonus → {total:g} < {gate:g})."
            if key == "projekt":
                pure = student.projekt
                total = result.projekt_total
                if pure >= GATE_PROJEKT:
                    return f"Splněno čistě ({pure:g} ≥ {GATE_PROJEKT:g})."
                if total >= GATE_PROJEKT:
                    return f"Splněno s bonusem ({pure:g} + bonus → {total:g} ≥ {GATE_PROJEKT:g})."
                return f"Nesplněno ({pure:g} + bonus → {total:g} < {GATE_PROJEKT:g})."
            if key == "bonus_total":
                b = student.bonus
                return (
                    f"Bonus celkem: {b.total():g}\n"
                    f"  → Test 1: {b.test1:g}\n"
                    f"  → Test 2: {b.test2:g}\n"
                    f"  → Projekt: {b.projekt:g}"
                )
            if key == "repetent" and repetent:
                return "Repetent — os. číslo bylo evidováno v některém předchozím roce."
            if key == "rank" and rank:
                return f"Pořadí v top 5: {rank}."
            if key == "pokus":
                return POKUS_LABELS.get(student.pokus, student.pokus)
            if key == "istqb":
                return ("Certifikát ISTQB CTFL: ANO — známka automaticky A"
                        if student.ma_istqb_ctfl
                        else "Certifikát ISTQB CTFL: NE")

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ("test1", "test2", "projekt", "projekt_pct", "bonus_total", "celkem"):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if key in (
                "znamka", "dochazka", "pokus", "repetent", "rank",
                "istqb", "ukoncil", "datum_odevzdani",
            ):
                return int(Qt.AlignmentFlag.AlignCenter)

        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False
        student = self._students[index.row()]
        key, _, editable, _, _ = COLUMNS[index.column()]

        if key == "dochazka" and role == Qt.ItemDataRole.CheckStateRole:
            checked = Qt.CheckState(value) == Qt.CheckState.Checked
            if student.dochazka == checked:
                return False
            student.dochazka = checked
            self.emit_row_changed(index.row())
            return True

        if key == "istqb" and role == Qt.ItemDataRole.CheckStateRole:
            checked = Qt.CheckState(value) == Qt.CheckState.Checked
            if student.ma_istqb_ctfl == checked:
                return False
            student.ma_istqb_ctfl = checked
            self.emit_row_changed(index.row())
            return True

        if key == "ukoncil" and role == Qt.ItemDataRole.CheckStateRole:
            checked = Qt.CheckState(value) == Qt.CheckState.Checked
            if student.ukoncil_studium == checked:
                return False
            student.ukoncil_studium = checked
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
            elif key == "bonus_total":
                total = max(0.0, _r(float(value)))
                # Uživatel zadává jen celkový bonus, systém ho automaticky
                # rozdělí: nejdřív doplnit do brány T1/T2/Projekt, pak zbytek
                # tak, aby maximalizoval známku (suggest_allocation).
                student.bonus = suggest_allocation(
                    test1=student.test1,
                    test2=student.test2,
                    projekt=student.projekt,
                    total_bonus=total,
                )
            elif key == "datum_odevzdani":
                s = str(value).strip()
                if not s:
                    student.datum_odevzdani = None
                else:
                    # Akceptuj DD.MM.YYYY i ISO (YYYY-MM-DD).
                    try:
                        student.datum_odevzdani = date.fromisoformat(s)
                    except ValueError:
                        from datetime import datetime
                        student.datum_odevzdani = datetime.strptime(s, DATE_FORMAT_PY).date()
            elif key == "pokus":
                v = str(value).strip()
                if v in POKUS_VALUES:
                    student.pokus = v
                else:
                    student.pokus = _normalize_pokus(value)
            elif key == "komentar":
                student.komentar = str(value)
            else:
                return False
        except (ValueError, TypeError):
            return False

        self.emit_row_changed(index.row())
        return True
