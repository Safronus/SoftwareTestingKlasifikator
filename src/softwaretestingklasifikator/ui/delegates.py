"""Custom item delegates pro QTableView."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate

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
