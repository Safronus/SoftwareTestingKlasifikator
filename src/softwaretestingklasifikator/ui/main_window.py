"""Hlavní okno aplikace."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTableView,
    QToolBar,
)

from softwaretestingklasifikator import __version__
from softwaretestingklasifikator.config import DATE_FORMAT_PY, SUBJECT_CODE
from softwaretestingklasifikator.domain.models import YearData
from softwaretestingklasifikator.domain.stats import (
    compute_stats,
    previous_years_os_cisla,
    top_n_indices,
)
from softwaretestingklasifikator.io.csv_export import export_to_predmet_csv
from softwaretestingklasifikator.io.csv_import import merge_students, read_roakce_csv
from softwaretestingklasifikator.io.storage import (
    default_data_dir,
    list_available_years,
    load_year,
    save_year,
)
from softwaretestingklasifikator.ui.delegates import PokusDelegate
from softwaretestingklasifikator.ui.stats_panel import StatsPanel
from softwaretestingklasifikator.ui.student_detail import StudentDetailPanel
from softwaretestingklasifikator.ui.student_table_model import COLUMNS, StudentTableModel
from softwaretestingklasifikator.ui.year_config_dialog import YearConfigDialog


class MainWindow(QMainWindow):
    AUTOSAVE_DELAY_MS = 500

    def __init__(self, data_dir: Path | None = None) -> None:
        super().__init__()
        self.data_dir = data_dir or default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.setWindowTitle(f"{SUBJECT_CODE} Klasifikátor v{__version__}")
        self.resize(1500, 800)

        self._current_year_data: YearData | None = None
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._do_autosave)

        self._build_ui()
        self._refresh_year_combo()

    # ------------------------------------------------------------------
    # UI assembly
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        toolbar = QToolBar("Hlavní")
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize() * 0.9)
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel("  Ročník (LS): "))
        self.year_combo = QComboBox()
        self.year_combo.setMinimumWidth(100)
        self.year_combo.currentTextChanged.connect(self._on_year_changed)
        toolbar.addWidget(self.year_combo)

        self.action_new_year = QAction("➕ Nový ročník", self)
        self.action_new_year.triggered.connect(self._new_year)
        toolbar.addAction(self.action_new_year)

        self.action_edit_year = QAction("Termíny…", self)
        self.action_edit_year.triggered.connect(self._edit_year_deadlines)
        toolbar.addAction(self.action_edit_year)

        toolbar.addSeparator()

        self.action_import = QAction("📥 Import studentů (CSV)", self)
        self.action_import.triggered.connect(self._import_roakce)
        toolbar.addAction(self.action_import)

        self.action_export = QAction("📤 Export hodnocení (CSV)", self)
        self.action_export.triggered.connect(self._export_predmet)
        toolbar.addAction(self.action_export)

        toolbar.addSeparator()

        self.action_save = QAction("💾 Uložit", self)
        self.action_save.setShortcut("Ctrl+S")
        self.action_save.triggered.connect(self._save_now)
        toolbar.addAction(self.action_save)

        self.action_delete_student = QAction("🗑 Odstranit studenta", self)
        self.action_delete_student.triggered.connect(self._delete_selected_student)
        toolbar.addAction(self.action_delete_student)

        self.action_show_finished = QAction("👁 Zobrazit ukončené", self)
        self.action_show_finished.setCheckable(True)
        self.action_show_finished.setChecked(False)
        self.action_show_finished.toggled.connect(self._apply_row_visibility)
        toolbar.addAction(self.action_show_finished)

        # --- Central: studentská tabulka -----------------------------
        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.model = StudentTableModel(parent=self)
        self.table.setModel(self.model)
        for i in range(self.model.columnCount()):
            self.table.setColumnWidth(i, self.model.column_default_width(i))
        self.model.studentChanged.connect(self._schedule_autosave)
        self.model.studentChanged.connect(lambda *_: self._refresh_stats())
        self.model.studentChanged.connect(lambda *_: self._apply_row_visibility())
        self.setCentralWidget(self.table)

        # ComboBox delegate pro sloupec „Pokus"
        pokus_col = next((i for i, c in enumerate(COLUMNS) if c[0] == "pokus"), None)
        if pokus_col is not None:
            self.table.setItemDelegateForColumn(pokus_col, PokusDelegate(self.table))

        # --- Right dock: detail -------------------------------------
        self.detail = StudentDetailPanel()
        self.detail.studentEdited.connect(self._on_detail_edited)
        detail_dock = QDockWidget("Detail studenta", self)
        detail_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        detail_dock.setWidget(self.detail)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, detail_dock)
        detail_dock.setMinimumWidth(360)

        # --- Left dock: statistika ---------------------------------
        self.stats_panel = StatsPanel()
        stats_dock = QDockWidget("Statistika ročníku", self)
        stats_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        stats_dock.setWidget(self.stats_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, stats_dock)
        stats_dock.setMinimumWidth(280)

        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # --- Status bar --------------------------------------------
        self.setStatusBar(QStatusBar())
        self.status_label = QLabel("")
        self.statusBar().addPermanentWidget(self.status_label)

    # ------------------------------------------------------------------
    # Year management
    # ------------------------------------------------------------------
    def _refresh_year_combo(self) -> None:
        years = list_available_years(self.data_dir)
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItems([str(y) for y in years])
        self.year_combo.blockSignals(False)

        if years:
            self.year_combo.setCurrentIndex(len(years) - 1)  # nejnovější
            self._load_year(years[-1])
        else:
            self._set_year_data(None)
            self._update_status("Zatím žádný ročník — vytvoř ho tlačítkem ➕.")

    def _on_year_changed(self, year_str: str) -> None:
        if not year_str:
            return
        try:
            year = int(year_str)
        except ValueError:
            return
        self._load_year(year)

    def _load_year(self, year: int) -> None:
        data = load_year(self.data_dir, year)
        self._set_year_data(data)

    def _set_year_data(self, data: YearData | None) -> None:
        self._current_year_data = data
        if data is None:
            self.model.set_repetent_os_cisla(set())
            self.model.set_students([])
            self.detail.set_student(None)
            self.stats_panel.set_stats(compute_stats(YearData(year=0)), deadlines=None)
            self.action_export.setEnabled(False)
            self.action_import.setEnabled(False)
            self.action_edit_year.setEnabled(False)
            self.action_save.setEnabled(False)
            self.action_delete_student.setEnabled(False)
            return
        self.action_export.setEnabled(True)
        self.action_import.setEnabled(True)
        self.action_edit_year.setEnabled(True)
        self.action_save.setEnabled(True)
        self.action_delete_student.setEnabled(True)
        # Set repetent os_cisla *before* set_students, aby tabulka při prvním
        # renderu měla správné podbarvení řádků.
        repetents = previous_years_os_cisla(self.data_dir, data.year)
        self.model.set_repetent_os_cisla(repetents)
        self.model.set_students(data.students)
        self.detail.set_student(None)
        self._refresh_stats()
        self._apply_row_visibility()
        self._update_status_for_year()

    def _refresh_stats(self) -> None:
        if self._current_year_data is None:
            return
        repetents = self.model.repetent_os_cisla()
        stats = compute_stats(self._current_year_data, repetents)
        self.stats_panel.set_stats(stats, deadlines=self._current_year_data.deadlines)
        # Top 5 počítáme jen z aktivních (ne-ukončených) studentů.
        active_indices = [
            i for i, s in enumerate(self.model.students()) if not s.ukoncil_studium
        ]
        active = [self.model.students()[i] for i in active_indices]
        active_ranks = top_n_indices(active, n=5)
        # remap zpět na původní indexy
        ranks = {active_indices[k]: v for k, v in active_ranks.items()}
        self.model.set_top_ranks(ranks)

    def _apply_row_visibility(self) -> None:
        """Skryje studenty s `ukoncil_studium=True`, pokud není zapnutý toggle."""
        if self._current_year_data is None:
            return
        show_finished = self.action_show_finished.isChecked()
        for row, student in enumerate(self.model.students()):
            self.table.setRowHidden(row, student.ukoncil_studium and not show_finished)

    def _update_status_for_year(self) -> None:
        d = self._current_year_data
        if d is None:
            return
        dl = d.deadlines
        dl_text = []
        if dl.first:
            dl_text.append(f"1. pokus do {dl.first.strftime(DATE_FORMAT_PY)}")
        if dl.second:
            dl_text.append(f"2. pokus do {dl.second.strftime(DATE_FORMAT_PY)}")
        suffix = " · " + " · ".join(dl_text) if dl_text else ""
        self._update_status(f"Ročník {d.year} ({len(d.students)} studentů){suffix}")

    def _update_status(self, msg: str) -> None:
        self.status_label.setText(msg)

    def _new_year(self) -> None:
        existing = set(list_available_years(self.data_dir))
        dlg = YearConfigDialog(self, year=max(existing) + 1 if existing else date.today().year,
                               existing_years=existing)
        if dlg.exec() != YearConfigDialog.DialogCode.Accepted:
            return
        year = dlg.selected_year()
        deadlines = dlg.selected_deadlines()
        data = YearData(year=year, deadlines=deadlines, students=[])
        save_year(self.data_dir, data)
        self._refresh_year_combo()
        idx = self.year_combo.findText(str(year))
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)

    def _edit_year_deadlines(self) -> None:
        if self._current_year_data is None:
            return
        dlg = YearConfigDialog(
            self,
            year=self._current_year_data.year,
            deadlines=self._current_year_data.deadlines,
            edit_only_deadlines=True,
        )
        if dlg.exec() != YearConfigDialog.DialogCode.Accepted:
            return
        self._current_year_data.deadlines = dlg.selected_deadlines()
        self._save_now()
        self._update_status_for_year()

    # ------------------------------------------------------------------
    # Selection / detail editing
    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail.set_student(None)
            return
        student = self.model.student_at(rows[0].row())
        self.detail.set_student(student)

    def _on_detail_edited(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.model.emit_row_changed(rows[0].row())
        self._schedule_autosave()

    def _delete_selected_student(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        student = self.model.student_at(row)
        if student is None:
            return
        name = student.display_name() or student.os_cislo
        confirm = QMessageBox.question(
            self,
            "Odstranit studenta",
            f'Opravdu odstranit „{name}" z ročníku?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.model.remove_row(row)
        self._sync_students_to_year_data()
        self._save_now()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _sync_students_to_year_data(self) -> None:
        if self._current_year_data is None:
            return
        self._current_year_data.students = self.model.students()

    def _schedule_autosave(self, _row: int | QModelIndex | None = None) -> None:
        self._autosave_timer.start(self.AUTOSAVE_DELAY_MS)

    def _do_autosave(self) -> None:
        if self._current_year_data is None:
            return
        self._sync_students_to_year_data()
        try:
            save_year(self.data_dir, self._current_year_data)
            self._update_status_for_year()
        except OSError as exc:
            QMessageBox.critical(self, "Chyba uložení", str(exc))

    def _save_now(self) -> None:
        self._autosave_timer.stop()
        self._do_autosave()

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------
    def _import_roakce(self) -> None:
        if self._current_year_data is None:
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import studentů (getStudentiByRoakce CSV)",
            str(Path.home()),
            "CSV ze STAGu (*.csv);;Všechny soubory (*)",
        )
        if not path_str:
            return
        try:
            imported = read_roakce_csv(Path(path_str))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Chyba importu", f"Soubor se nepodařilo načíst:\n{exc}")
            return
        merged, added, updated = merge_students(self._current_year_data.students, imported)
        self._current_year_data.students = merged
        self.model.set_students(merged)
        self._save_now()
        QMessageBox.information(
            self,
            "Import dokončen",
            f"Načteno {len(imported)} řádků.\nPřidáno: {added}\nAktualizováno: {updated}",
        )

    def _export_predmet(self) -> None:
        if self._current_year_data is None:
            return
        default_name = f"hodnoceni_{self._current_year_data.year}.csv"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export hodnocení (SeznamStudentuNaPredmetu CSV)",
            str(Path.home() / default_name),
            "CSV pro STAG (*.csv);;Všechny soubory (*)",
        )
        if not path_str:
            return
        try:
            count = export_to_predmet_csv(Path(path_str), self._current_year_data)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Chyba exportu", f"Export selhal:\n{exc}")
            return
        QMessageBox.information(self, "Export dokončen", f"Zapsáno {count} řádků do:\n{path_str}")

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_now()
        super().closeEvent(event)
