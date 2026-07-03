"""Testy UI delegátů (potvrzení „Ukončil studium", tooltip komentáře).

Běží headless přes pytest-qt `qapp` fixture — nevytváří viditelné okno.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QMessageBox, QStyleOptionViewItem

from softwaretestingklasifikator.domain.models import Student
from softwaretestingklasifikator.ui import delegates as D
from softwaretestingklasifikator.ui.student_table_model import COLUMNS, StudentTableModel


def _col(key: str) -> int:
    return next(i for i, c in enumerate(COLUMNS) if c[0] == key)


def _space_event() -> QKeyEvent:
    # Space nad checkable buňkou = toggle (nezávislé na pozici myši/rectu).
    return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)


def _model_one(**kwargs) -> StudentTableModel:
    return StudentTableModel([Student(os_cislo="F1", jmeno="Jan", prijmeni="Novak", **kwargs)])


def test_ukoncil_confirm_cancel_keeps_unchecked(qapp, monkeypatch):
    monkeypatch.setattr(
        D.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    m = _model_one()
    idx = m.index(0, _col("ukoncil"))
    handled = D.ConfirmCheckDelegate("t", "q").editorEvent(
        _space_event(), m, QStyleOptionViewItem(), idx,
    )
    assert handled is True  # událost spolknuta
    assert m.students()[0].ukoncil_studium is False  # ale nic nepřepnuto


def test_ukoncil_confirm_yes_checks(qapp, monkeypatch):
    monkeypatch.setattr(
        D.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    m = _model_one()
    idx = m.index(0, _col("ukoncil"))
    D.ConfirmCheckDelegate("t", "q").editorEvent(
        _space_event(), m, QStyleOptionViewItem(), idx,
    )
    assert m.students()[0].ukoncil_studium is True


def test_ukoncil_uncheck_skips_dialog(qapp, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("Dialog se nemá zobrazit při odškrtnutí.")

    monkeypatch.setattr(D.QMessageBox, "question", staticmethod(_boom))
    m = _model_one(ukoncil_studium=True)
    idx = m.index(0, _col("ukoncil"))
    D.ConfirmCheckDelegate("t", "q").editorEvent(
        _space_event(), m, QStyleOptionViewItem(), idx,
    )
    assert m.students()[0].ukoncil_studium is False  # odškrtnuto bez ptaní


def test_komentar_tooltip_returns_full_text(qapp):
    m = _model_one(komentar="V logu vidím jen 3 funkční testy — to je málo.")
    idx = m.index(0, _col("komentar"))
    assert (
        m.data(idx, Qt.ItemDataRole.ToolTipRole)
        == "V logu vidím jen 3 funkční testy — to je málo."
    )


def test_komentar_tooltip_empty_is_none(qapp):
    m = _model_one()
    idx = m.index(0, _col("komentar"))
    assert m.data(idx, Qt.ItemDataRole.ToolTipRole) is None
