"""Custom item delegates pro QTableView."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
)

from softwaretestingklasifikator.domain.models import POKUS_LABELS, POKUS_VALUES


class PokusDelegate(QStyledItemDelegate):
    """ComboBox editor pro sloupec „Pokus" — řádný / oprava / po termínu / neodevzdal."""

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for value in POKUS_VALUES:
            combo.addItem(POKUS_LABELS[value], value)
        return combo

    def setEditorData(self, editor: QComboBox, index) -> None:  # type: ignore[override]
        current = index.data(Qt.ItemDataRole.EditRole)
        idx = editor.findData(current)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor: QComboBox, model, index) -> None:  # type: ignore[override]
        model.setData(index, editor.currentData(), Qt.ItemDataRole.EditRole)


class CenteredCheckboxDelegate(QStyledItemDelegate):
    """Vykresluje checkbox vystředěný v buňce.

    Default Qt kreslí checkbox na levém okraji buňky. Pro sloupce typu
    Docházka (text = "") to vypadá nesymetricky. Tento delegát:
    1. vykreslí pozadí + selection rám standardně, ale **bez** built-in
       checkboxu (HasCheckIndicator feature odebrána),
    2. vykreslí PE_IndicatorCheckBox vystředěný v cell rectu.
    Toggle se obsluhuje v `editorEvent` standardním způsobem (model.setData
    CheckStateRole), takže respektuje ItemIsUserCheckable flag.
    """

    def paint(self, painter, option, index) -> None:  # noqa: D401
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Skryj built-in checkbox feature; vykreslíme ho ručně.
        opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        opt.text = ""
        widget = option.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if check_state is None:
            return

        cb_opt = QStyleOptionButton()
        cb_opt.state = QStyle.StateFlag.State_Enabled
        is_checked = check_state in (Qt.CheckState.Checked, int(Qt.CheckState.Checked))
        cb_opt.state |= (
            QStyle.StateFlag.State_On if is_checked else QStyle.StateFlag.State_Off
        )

        # Velikost indikátoru — z aktuálního stylu (respektuje stylesheet width/height).
        indicator_rect = style.subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator, cb_opt, widget
        )
        cb_w = indicator_rect.width() or 18
        cb_h = indicator_rect.height() or 18

        cell = option.rect
        cx = cell.x() + (cell.width() - cb_w) // 2
        cy = cell.y() + (cell.height() - cb_h) // 2
        cb_opt.rect = QRect(cx, cy, cb_w, cb_h)
        style.drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorCheckBox, cb_opt, painter, widget,
        )

    def editorEvent(self, event, model, option, index) -> bool:  # noqa: D401
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return False
        if event.type() == QEvent.Type.MouseButtonRelease:
            current = index.data(Qt.ItemDataRole.CheckStateRole)
            is_checked = current in (Qt.CheckState.Checked, int(Qt.CheckState.Checked))
            new_state = Qt.CheckState.Unchecked if is_checked else Qt.CheckState.Checked
            return model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
        return False
