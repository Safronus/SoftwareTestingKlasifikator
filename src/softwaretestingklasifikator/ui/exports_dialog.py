"""Dialog pro správu historických exportů STAG CSV.

Zobrazuje seznam všech exportů z `data/exports/<rok>/`, umožňuje filtrovat
podle ročníku, otevřít konkrétní export ve Finderu a mazat soubory.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from softwaretestingklasifikator.io.exports import (
    ExportInfo,
    delete_export,
    list_exports,
)

_ROLE_INFO = Qt.ItemDataRole.UserRole


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} kB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


class ExportsDialog(QDialog):
    """Modal dialog: tabulka exportů + akce (otevřít, smazat)."""

    def __init__(self, data_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self._data_dir = data_dir
        self.setWindowTitle("Exportované CSV")
        self.resize(700, 460)

        layout = QVBoxLayout(self)

        # --- Filter ----------------------------------------------------
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Ročník:"))
        self.year_combo = QComboBox()
        self.year_combo.addItem("Všechny", None)
        filter_row.addWidget(self.year_combo)
        filter_row.addStretch(1)
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: gray;")
        filter_row.addWidget(self.info_label)
        layout.addLayout(filter_row)

        # --- Table -----------------------------------------------------
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels([
            "Ročník", "Datum a čas exportu", "Velikost", "Soubor",
        ])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(lambda *_: self._open_selected())
        layout.addWidget(self.tree, 1)

        # --- Akce ------------------------------------------------------
        btn_row = QHBoxLayout()
        self.btn_open = QPushButton("Otevřít ve Finderu")
        self.btn_open.clicked.connect(self._open_selected)
        btn_row.addWidget(self.btn_open)

        self.btn_open_folder = QPushButton("Otevřít složku exportů")
        self.btn_open_folder.clicked.connect(self._open_root_folder)
        btn_row.addWidget(self.btn_open_folder)

        self.btn_delete = QPushButton("🗑 Smazat vybrané")
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.btn_delete)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # --- Close -----------------------------------------------------
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.year_combo.currentIndexChanged.connect(self._refresh_table)
        self._populate_years()
        self._refresh_table()

    # ---- internal --------------------------------------------------
    def _populate_years(self) -> None:
        years = sorted(
            {e.year for e in list_exports(self._data_dir)},
            reverse=True,
        )
        for y in years:
            self.year_combo.addItem(str(y), y)

    def _refresh_table(self) -> None:
        year = self.year_combo.currentData()
        self.tree.clear()
        exports = list_exports(self._data_dir, year=year)
        total_bytes = 0
        for info in exports:
            item = QTreeWidgetItem([
                str(info.year),
                info.timestamp.strftime("%d.%m.%Y %H:%M:%S"),
                _format_size(info.size),
                info.path.name,
            ])
            item.setData(0, _ROLE_INFO, info)
            self.tree.addTopLevelItem(item)
            total_bytes += info.size
        self.info_label.setText(
            f"Celkem {len(exports)} export(ů) · {_format_size(total_bytes)}"
        )
        self._update_buttons()
        self.tree.itemSelectionChanged.connect(self._update_buttons)

    def _update_buttons(self) -> None:
        selected = self._selected_infos()
        self.btn_open.setEnabled(len(selected) == 1)
        self.btn_delete.setEnabled(len(selected) >= 1)

    def _selected_infos(self) -> list[ExportInfo]:
        infos: list[ExportInfo] = []
        for item in self.tree.selectedItems():
            data = item.data(0, _ROLE_INFO)
            if isinstance(data, ExportInfo):
                infos.append(data)
        return infos

    def _open_selected(self) -> None:
        selected = self._selected_infos()
        if not selected:
            return
        info = selected[0]
        # Otevři rodičovskou složku (Finder na macOS).
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(info.path.parent)))

    def _open_root_folder(self) -> None:
        from softwaretestingklasifikator.io.exports import default_exports_dir
        folder = default_exports_dir(self._data_dir)
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _delete_selected(self) -> None:
        selected = self._selected_infos()
        if not selected:
            return
        if len(selected) == 1:
            ts = selected[0].timestamp.strftime("%d.%m.%Y %H:%M:%S")
            msg = (
                f'Opravdu smazat export\n„{selected[0].path.name}" '
                f'({ts}, ročník {selected[0].year})?'
            )
        else:
            msg = f"Opravdu smazat {len(selected)} vybraných exportů?"
        confirm = QMessageBox.warning(
            self, "Smazat exporty", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        errors: list[str] = []
        for info in selected:
            try:
                delete_export(info)
            except OSError as exc:
                errors.append(f"{info.path.name}: {exc}")
        if errors:
            QMessageBox.warning(
                self, "Smazání s chybami",
                "Některé exporty se nepodařilo smazat:\n" + "\n".join(errors),
            )
        self._refresh_table()
