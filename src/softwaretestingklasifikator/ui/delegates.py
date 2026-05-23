"""Custom item delegates pro QTableView."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
)

from softwaretestingklasifikator.config import POINTS_DECIMALS
from softwaretestingklasifikator.domain.models import POKUS_LABELS, POKUS_VALUES


class PointsDelegate(QStyledItemDelegate):
    """Editor pro bodové sloupce — QDoubleSpinBox s `POINTS_DECIMALS`
    desetinami (default Qt by ořezával na 2)."""

    def __init__(self, maximum: float, parent=None) -> None:
        super().__init__(parent)
        self._maximum = maximum

    def createEditor(self, parent, option, index):  # type: ignore[override]
        spin = QDoubleSpinBox(parent)
        spin.setDecimals(POINTS_DECIMALS)
        spin.setRange(0.0, self._maximum)
        spin.setSingleStep(10 ** (-POINTS_DECIMALS))  # 0.001 při decimals=3
        spin.setAccelerated(True)
        return spin

    def setEditorData(self, editor: QDoubleSpinBox, index) -> None:  # type: ignore[override]
        try:
            editor.setValue(float(index.data(Qt.ItemDataRole.EditRole) or 0))
        except (TypeError, ValueError):
            editor.setValue(0.0)

    def setModelData(self, editor: QDoubleSpinBox, model, index) -> None:  # type: ignore[override]
        editor.interpretText()
        model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)


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
    """Vykreslí checkbox v buňce na střed (default Qt ho dává vlevo).

    Strategie: necháme buňku vykreslit přes standardní `CE_ItemViewItem`
    (drží pozadí/BackgroundRole, selection, focus), ale s vypnutým
    `HasCheckIndicator` — pak overlayneme indicator přes
    `PE_IndicatorItemViewItemCheck` do středu rectu. Klik kdekoli v buňce
    toggle-uje hodnotu (UX patří k centrovanému checkboxu)."""

    def paint(self, painter, option, index):  # type: ignore[override]
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if check_state is None:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        # Vypneme default indicator (vlevo) — překreslíme ho ručně do středu.
        opt.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()

        # 1) Pozadí + selection + focus (z BackgroundRole apod.).
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        # 2) Centrovaný checkbox indicator přes PE_IndicatorItemViewItemCheck —
        # používá stejný native styl jako default, jen jiný rect.
        check_opt = QStyleOptionButton()
        indicator_size = style.pixelMetric(
            QStyle.PixelMetric.PM_IndicatorWidth, opt, widget,
        )
        x = opt.rect.center().x() - indicator_size // 2 + 1
        y = opt.rect.center().y() - indicator_size // 2 + 1
        check_opt.rect = QRect(x, y, indicator_size, indicator_size)
        check_opt.state = QStyle.StateFlag.State_Enabled
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            # Repetent — checkbox je read-only (automaticky uznáno).
            check_opt.state = QStyle.StateFlag.State_ReadOnly
        cs = Qt.CheckState(check_state)
        if cs == Qt.CheckState.Checked:
            check_opt.state |= QStyle.StateFlag.State_On
        elif cs == Qt.CheckState.PartiallyChecked:
            check_opt.state |= QStyle.StateFlag.State_NoChange
        else:
            check_opt.state |= QStyle.StateFlag.State_Off
        style.drawPrimitive(
            QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,
            check_opt, painter, widget,
        )

    def editorEvent(self, event, model, option, index):  # type: ignore[override]
        # Default editorEvent jen kliky uvnitř (left-aligned) checkbox rectu.
        # Centrovaný checkbox má jiný rect, tak interpretujeme klik kdekoli
        # v buňce — UX, kterou uživatel u centrovaného checkboxu čeká.
        if not (index.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return False
        check_state = index.data(Qt.ItemDataRole.CheckStateRole)
        if check_state is None:
            return False

        if event.type() in (
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseButtonDblClick,
        ):
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            if not option.rect.contains(event.position().toPoint()):
                return False
        elif event.type() == QEvent.Type.KeyPress:
            if event.key() not in (Qt.Key.Key_Space, Qt.Key.Key_Select):
                return False
        else:
            return False

        cs = Qt.CheckState(check_state)
        new_state = (
            Qt.CheckState.Unchecked
            if cs == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        return model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
