"""Hlavní okno aplikace."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtGui import QAction, QIcon
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
from softwaretestingklasifikator.config import (
    DATE_FORMAT_PY,
    MAX_PROJEKT,
    MAX_TEST1,
    MAX_TEST2,
    SUBJECT_CODE,
)
from softwaretestingklasifikator.domain.export_state import compute_export_hash
from softwaretestingklasifikator.domain.grading import derive_pokus_from_date
from softwaretestingklasifikator.domain.models import (
    POKUS_RADNY,
    BonusBreakdown,
    YearData,
    YearDeadlines,
)
from softwaretestingklasifikator.domain.stats import (
    compute_stats,
    previous_years_os_cisla,
    top_n_indices,
)
from softwaretestingklasifikator.domain.time_ago import format_time_ago
from softwaretestingklasifikator.io.csv_export import export_via_template_csv
from softwaretestingklasifikator.io.csv_import import (
    ProjectDateImportResult,
    apply_project_dates,
    apply_test_scores,
    dedup_project_dates,
    merge_students,
    read_project_dates_csv,
    read_roakce_csv,
    read_test_scores_csv,
    transfer_from_previous,
)
from softwaretestingklasifikator.io.exports import list_exports, next_export_path
from softwaretestingklasifikator.io.storage import (
    default_data_dir,
    find_previous_student_by_name,
    find_previous_students_batch,
    list_available_years,
    load_year,
    save_year,
)
from softwaretestingklasifikator.ui.delegates import (
    CenteredCheckboxDelegate,
    PointsDelegate,
    PokusDelegate,
)
from softwaretestingklasifikator.ui.exports_dialog import ExportsDialog
from softwaretestingklasifikator.ui.stats_panel import StatsPanel
from softwaretestingklasifikator.ui.student_table_model import COLUMNS, StudentTableModel
from softwaretestingklasifikator.ui.year_config_dialog import YearConfigDialog


class MainWindow(QMainWindow):
    AUTOSAVE_DELAY_MS = 500

    def __init__(self, data_dir: Path | None = None) -> None:
        super().__init__()
        self.data_dir = data_dir or default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.setWindowTitle(f"{SUBJECT_CODE} Klasifikátor v{__version__}")
        icon_path = Path(__file__).resolve().parent.parent / "resources" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
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

        toolbar.addSeparator()

        self.action_import = QAction("📥 Import studentů (CSV)", self)
        self.action_import.triggered.connect(self._import_roakce)
        toolbar.addAction(self.action_import)

        self.action_import_tests = QAction("📊 Import bodů z testů (CSV)", self)
        self.action_import_tests.setToolTip(
            "Naimportuje body z Testu č. 1 a č. 2 z CSV (Moodle export). "
            "Spáruje studenty podle jména + příjmení. Vždy se zapíše vyšší "
            "z původní a nové hodnoty (repetent, který už má body z minulého "
            "roku, o ně nepřijde)."
        )
        self.action_import_tests.triggered.connect(self._import_test_scores)
        toolbar.addAction(self.action_import_tests)

        self.action_import_dates = QAction("📅 Import dat odevzdání (CSV)", self)
        self.action_import_dates.setToolTip(
            "Naimportuje data odevzdání projektu z jednoho nebo více Moodle CSV. "
            "Spáruje studenty podle celého jména. Studentům bez data se nastaví "
            "stav Neodevzdal."
        )
        self.action_import_dates.triggered.connect(self._import_project_dates)
        toolbar.addAction(self.action_import_dates)

        self.action_export = QAction("📤 Export hodnocení (CSV)", self)
        self.action_export.triggered.connect(self._export_predmet)
        toolbar.addAction(self.action_export)

        self.action_manage_exports = QAction("📁 Exportované CSV…", self)
        self.action_manage_exports.setToolTip(
            "Spravovat historické exporty — seznam, otevřít ve Finderu, smazat."
        )
        self.action_manage_exports.triggered.connect(self._open_exports_manager)
        toolbar.addAction(self.action_manage_exports)

        toolbar.addSeparator()

        self.action_delete_student = QAction("🗑 Odstranit studenta", self)
        self.action_delete_student.triggered.connect(self._delete_selected_student)
        toolbar.addAction(self.action_delete_student)

        self.action_show_finished = QAction("👁 Zobrazit ukončené", self)
        self.action_show_finished.setCheckable(True)
        self.action_show_finished.setChecked(False)
        self.action_show_finished.toggled.connect(self._apply_row_visibility)
        toolbar.addAction(self.action_show_finished)

        self.action_mark_all_dochazka = QAction("✓ Docházka všem", self)
        self.action_mark_all_dochazka.setToolTip(
            "Označit splněnou docházku všem studentům aktuálního ročníku najednou."
        )
        self.action_mark_all_dochazka.triggered.connect(self._mark_all_dochazka)
        toolbar.addAction(self.action_mark_all_dochazka)

        toolbar.addSeparator()

        self.action_reset_year = QAction("♻ Vynulovat hodnocení", self)
        self.action_reset_year.setToolTip(
            "Smaže body, bonusy, docházku a meta u všech studentů v aktuálním "
            "ročníku — seznam studentů zůstane zachován."
        )
        self.action_reset_year.triggered.connect(self._reset_year_grades)
        toolbar.addAction(self.action_reset_year)

        self.action_delete_year = QAction("🗑 Smazat ročník", self)
        self.action_delete_year.setToolTip(
            "Úplně smaže aktuální ročník (JSON soubor i ze seznamu)."
        )
        self.action_delete_year.triggered.connect(self._delete_year)
        toolbar.addAction(self.action_delete_year)

        # --- Central: studentská tabulka -----------------------------
        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        # ScrollPerItem snižuje počet paint eventů na trackpadu (vs. per-pixel
        # smooth scroll, který triggeruje paint na každý pixel).
        self.table.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerItem)
        self.table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerItem)
        # Stylesheet pro checkboxy ve sloupcích Docházka / CTFL / Ukončil,
        # ať jsou viditelné i na světlém pozadí.
        self.table.setStyleSheet(
            """
            QTableView::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #4A5868;
                border-radius: 3px;
                background-color: #FFFFFF;
            }
            QTableView::indicator:checked {
                background-color: #5DC97A;
                border-color: #2D8B40;
            }
            QTableView::indicator:hover {
                border-color: #2D8B40;
            }
            """
        )
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.model = StudentTableModel(parent=self)
        self.table.setModel(self.model)
        # Resize modes lze nastavit až po setModel — předtím nejsou sloupce
        # registrované v headeru.
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        komentar_col = next((i for i, c in enumerate(COLUMNS) if c[0] == "komentar"), None)
        if komentar_col is not None:
            header.setSectionResizeMode(komentar_col, QHeaderView.ResizeMode.Stretch)
        # Sloupec „Chybí" se auto-fituje na obsah — délka stringu se mění
        # podle toho, jestli mají studenti deficit (prázdná buňka vs.
        # „X.XXX / Y.YYY"). Bez ResizeToContents by uživatel musel
        # roztahovat ručně po každé úpravě bonusu.
        chybi_col = next((i for i, c in enumerate(COLUMNS) if c[0] == "chybi"), None)
        if chybi_col is not None:
            header.setSectionResizeMode(chybi_col, QHeaderView.ResizeMode.ResizeToContents)
        # Pevné defaultní šířky z COLUMNS — uživatel si může roztáhnout ručně.
        # Nepoužíváme resizeColumnsToContents, protože po year switch při delších
        # komentářích vytlačí Stretch sloupec mimo viewport.
        for i in range(self.model.columnCount()):
            if i not in (komentar_col, chybi_col):
                self.table.setColumnWidth(i, self.model.column_default_width(i))
        # CTFL: po zaškrtnutí se text rozšíří z „Ne" na bold „Ano" — auto-resize
        # column to contents při každé změně dat, aby se text neořezával.
        self._istqb_col = next(
            (i for i, c in enumerate(COLUMNS) if c[0] == "istqb"), None,
        )
        if self._istqb_col is not None:
            self._resize_istqb_to_contents()
            self.model.studentChanged.connect(
                lambda *_: self._resize_istqb_to_contents()
            )
            self.model.modelReset.connect(self._resize_istqb_to_contents)
        self.model.studentChanged.connect(self._schedule_autosave)
        self.model.studentChanged.connect(lambda *_: self._refresh_stats())
        self.model.studentChanged.connect(lambda *_: self._apply_row_visibility())
        # Indikátor neuložených změn ať reaguje hned — ne až po autosave.
        self.model.studentChanged.connect(lambda *_: self._update_status_for_year())
        self.model.modelReset.connect(self._refresh_stats)
        self.model.modelReset.connect(self._apply_row_visibility)
        self.model.repetentToggledOn.connect(self._on_repetent_marked)
        self.setCentralWidget(self.table)

        # ComboBox delegate pro sloupec „Pokus"
        pokus_col = next((i for i, c in enumerate(COLUMNS) if c[0] == "pokus"), None)
        if pokus_col is not None:
            self.table.setItemDelegateForColumn(pokus_col, PokusDelegate(self.table))
        # Bodové sloupce — QDoubleSpinBox s POINTS_DECIMALS desetinami
        # (default Qt editor by ořezával na 2).
        for col_key, maximum in (
            ("test1", MAX_TEST1),
            ("test2", MAX_TEST2),
            ("projekt", MAX_PROJEKT),
            ("bonus_total", MAX_TEST1 + MAX_TEST2 + MAX_PROJEKT),
        ):
            col_idx = next(
                (i for i, c in enumerate(COLUMNS) if c[0] == col_key), None,
            )
            if col_idx is not None:
                self.table.setItemDelegateForColumn(
                    col_idx, PointsDelegate(maximum, self.table),
                )
        # Centrovaný checkbox pro sloupec „Docházka"
        dochazka_col = next(
            (i for i, c in enumerate(COLUMNS) if c[0] == "dochazka"), None,
        )
        if dochazka_col is not None:
            self.table.setItemDelegateForColumn(
                dochazka_col, CenteredCheckboxDelegate(self.table),
            )

        # --- Left dock: statistika ---------------------------------
        self.stats_panel = StatsPanel()
        self.stats_panel.deadlinesChanged.connect(self._on_deadlines_changed)
        stats_dock = QDockWidget("Statistika ročníku", self)
        stats_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        stats_dock.setWidget(self.stats_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, stats_dock)
        stats_dock.setMinimumWidth(210)

        # --- Status bar --------------------------------------------
        self.setStatusBar(QStatusBar())
        self.status_label = QLabel("")
        self.status_label.setTextFormat(Qt.TextFormat.RichText)
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

        if not years:
            self._set_year_data(None)
            self._update_status("Zatím žádný ročník — vytvoř ho tlačítkem ➕.")
            return

        # Vybereme nejnovější ročník, který má nějaké studenty.
        # Pokud jsou všechny ročníky prázdné, použijeme nejnovější.
        chosen = years[-1]
        for year in reversed(years):
            data = load_year(self.data_dir, year)
            if data.students:
                chosen = year
                break
        idx = self.year_combo.findText(str(chosen))
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        self._load_year(chosen)

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
            self.model.set_deadlines(None)
            self.model.set_students([])
            self.stats_panel.set_stats(compute_stats(YearData(year=0)), deadlines=None)
            for a in (self.action_export, self.action_import, self.action_import_tests,
                      self.action_import_dates,
                      self.action_delete_student, self.action_mark_all_dochazka,
                      self.action_reset_year, self.action_delete_year):
                a.setEnabled(False)
            return
        for a in (self.action_export, self.action_import,
                  self.action_delete_student,
                  self.action_reset_year, self.action_delete_year):
            a.setEnabled(True)
        # Set repetent os_cisla *before* set_students, aby tabulka při prvním
        # renderu měla správné podbarvení řádků.
        repetents = previous_years_os_cisla(self.data_dir, data.year)
        self.model.set_repetent_os_cisla(repetents)
        # Deadliny musí být v modelu před editací — re-derivace pokusu při
        # ruční změně data odevzdání je potřebuje.
        self.model.set_deadlines(data.deadlines)
        self.model.set_students(data.students)
        # Defaultně řadit po Příjmení vzestupně.
        prijmeni_col = next((i for i, c in enumerate(COLUMNS) if c[0] == "prijmeni"), 1)
        self.table.sortByColumn(prijmeni_col, Qt.SortOrder.AscendingOrder)
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

    def _resize_istqb_to_contents(self) -> None:
        """CTFL sloupec: auto-resize podle obsahu, ale s bezpečným floorem.

        Po zaškrtnutí checkboxu se text změní z „Ne" na bold „Ano" (širší)
        — bez resize by se v default 60 px ořezalo."""
        if self._istqb_col is None:
            return
        self.table.resizeColumnToContents(self._istqb_col)
        # Floor — i kdyby ResizeToContents vrátilo nečekaně málo, ať je
        # text vidět bez ellipsis.
        min_w = self.model.column_default_width(self._istqb_col)
        if self.table.columnWidth(self._istqb_col) < min_w:
            self.table.setColumnWidth(self._istqb_col, min_w)

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
        base = f"Ročník {d.year} ({len(d.students)} studentů){suffix}"
        indicator_html = self._export_indicator_html()
        if indicator_html:
            self._update_status(f"{base} &nbsp; {indicator_html}")
        else:
            self._update_status(base)

    def _export_indicator_html(self) -> str:
        """HTML fragment vyjadřující stav exportu vůči poslednímu STAGu.

        Indikátor dává smysl jen u **aktuálního** akademického roku — u
        starších ročníků už stejně nelze STAG upravovat. Bere v potaz i
        ručně smazané archivované exporty (chybí soubor → „nebylo
        exportováno")."""
        d = self._current_year_data
        if d is None or not d.students:
            return ""
        if d.year != date.today().year:
            return ""
        # Pokud byly všechny archivované exporty smazané, persistovaný
        # hash je bezpředmětný — odkazuje na neexistující soubor.
        has_archive = bool(list_exports(self.data_dir, d.year))
        if d.last_exported_hash is None or not has_archive:
            return (
                "<span style='color:#b8860b;'>"
                "⚠ Zatím nebylo exportováno do STAGu</span>"
            )
        current = compute_export_hash(d)
        when = (
            format_time_ago(d.last_exported_at) if d.last_exported_at else ""
        )
        when_suffix = f" ({when})" if when else ""
        if current == d.last_exported_hash:
            return (
                f"<span style='color:#1f8a39;'>"
                f"✓ Synchronizováno se STAGem{when_suffix}</span>"
            )
        return (
            f"<span style='color:#c0392b;'>"
            f"● Neuložené změny od posledního exportu{when_suffix}</span>"
        )

    def _update_status(self, msg: str) -> None:
        self.status_label.setText(msg)

    def _new_year(self) -> None:
        all_years = list_available_years(self.data_dir)
        # Blokující roky = ty, které už mají studenty (do nich nelze).
        # Prázdné existující roky NEjsou blokující — můžeme do nich naimportovat.
        non_empty: set[int] = set()
        for y in all_years:
            if load_year(self.data_dir, y).students:
                non_empty.add(y)

        # Default rok = první kalendářní rok ≥ dnešní, který není blokující.
        # (typicky: dnes je 2026, 2026 existuje prázdný → default 2026)
        default_year = date.today().year
        while default_year in non_empty:
            default_year += 1

        # Pre-fill deadlinů z existujícího prázdného ročníku (pokud jsou).
        existing_deadlines = None
        if default_year in all_years:
            existing_deadlines = load_year(self.data_dir, default_year).deadlines

        dlg = YearConfigDialog(
            self,
            year=default_year,
            deadlines=existing_deadlines,
            blocking_years=non_empty,
        )
        if dlg.exec() != YearConfigDialog.DialogCode.Accepted:
            return
        year = dlg.selected_year()
        deadlines = dlg.selected_deadlines()
        csv_path = dlg.selected_csv_path()

        data = YearData(year=year, deadlines=deadlines, students=[])

        info_msg = ""
        if csv_path is not None:
            try:
                imported = read_roakce_csv(csv_path)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(
                    self, "Chyba importu",
                    f"Načtení CSV selhalo:\n{exc}\n\n"
                    f"Ročník {year} bude vytvořen prázdný.",
                )
                imported = []

            if imported:
                # Najdi nejnovější předchozí výskyty napříč všemi roky.
                os_cisla = {s.os_cislo for s in imported if s.os_cislo}
                prev_map = find_previous_students_batch(self.data_dir, os_cisla, year)

                repetenti_count = 0
                source_years: set[int] = set()
                for s in imported:
                    found = prev_map.get(s.os_cislo)
                    if found is not None:
                        prev_year, prev_student = found
                        transfer_from_previous(s, prev_student)
                        repetenti_count += 1
                        source_years.add(prev_year)

                data.students = imported
                info_msg = (
                    f"Naimportováno {len(imported)} studentů.\n"
                    f"Repetentů (přeneseno z minulých let): {repetenti_count}"
                )
                if source_years:
                    yrs = ", ".join(str(y) for y in sorted(source_years, reverse=True))
                    info_msg += f"\nZdrojové ročníky: {yrs}"

        save_year(self.data_dir, data)
        self._refresh_year_combo()
        idx = self.year_combo.findText(str(year))
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        if info_msg:
            QMessageBox.information(self, "Ročník vytvořen", info_msg)

    def _on_deadlines_changed(self, deadlines: YearDeadlines) -> None:
        """Reakce na inline editaci termínů ve Statistice ročníku.

        Přepočítá `pokus` u všech studentů s datem odevzdání (řádný /
        opravný / po termínu podle nových deadlinů), refreshne tabulku,
        statistiku a status bar a uloží."""
        if self._current_year_data is None:
            return
        self._current_year_data.deadlines = deadlines
        # Sync deadlines do modelu — re-derivace pokusu při inline editaci
        # data odevzdání v tabulce.
        self.model.set_deadlines(deadlines)
        for s in self._current_year_data.students:
            if s.datum_odevzdani is not None:
                s.pokus = derive_pokus_from_date(s.datum_odevzdani, deadlines)
        # set_students (stejná reference) → beginResetModel/endResetModel →
        # invalidace cache → re-render tabulky. Sort indikátor zůstává.
        self.model.set_students(self._current_year_data.students)
        self._save_now()
        self._update_status_for_year()

    def _mark_all_dochazka(self) -> None:
        if self._current_year_data is None:
            return
        students = self._current_year_data.students
        if not students:
            QMessageBox.information(
                self, "Docházka všem",
                "Ročník zatím nemá žádné studenty.",
            )
            return
        missing = sum(1 for s in students if not s.dochazka)
        if missing == 0:
            QMessageBox.information(
                self, "Docházka všem",
                "Všichni studenti už mají docházku splněnou — žádná změna.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Označit docházku všem",
            f"Označit splněnou docházku všem {len(students)} studentům "
            f"aktuálního ročníku?\n\n"
            f"(Aktuálně {missing} studentů docházku nemá.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for s in students:
            s.dochazka = True
        self.model.set_students(students)
        prijmeni_col = next((i for i, c in enumerate(COLUMNS) if c[0] == "prijmeni"), 1)
        self.table.sortByColumn(prijmeni_col, Qt.SortOrder.AscendingOrder)
        self._refresh_stats()
        self._apply_row_visibility()
        self._save_now()
        self._update_status(
            f"Docházka označena jako splněná u {missing} studentů."
        )

    def _reset_year_grades(self) -> None:
        if self._current_year_data is None:
            return
        year = self._current_year_data.year
        count = len(self._current_year_data.students)
        if count == 0:
            QMessageBox.information(self, "Vynulovat hodnocení", f"Ročník {year} nemá žádné studenty.")
            return
        confirm = QMessageBox.warning(
            self,
            "Vynulovat hodnocení",
            f"Opravdu vynulovat hodnocení všech {count} studentů v ročníku {year}?\n\n"
            "Smazána budou: body z testů, body z projektu, bonusy, docházka,\n"
            "datum odevzdání, stav pokusu, ISTQB, ukončení studia, komentář a\n"
            "případná známka-override.\n\n"
            "Seznam studentů (jméno, příjmení, os. číslo) zůstává.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for s in self._current_year_data.students:
            s.test1 = 0.0
            s.test2 = 0.0
            s.projekt = 0.0
            s.bonus = BonusBreakdown()
            s.dochazka = False
            s.datum_odevzdani = None
            s.pokus = POKUS_RADNY
            s.ma_istqb_ctfl = False
            s.ukoncil_studium = False
            s.komentar = ""
            s.znamka_override = None
        self.model.set_students(self._current_year_data.students)
        self._refresh_stats()
        self._apply_row_visibility()
        self._save_now()
        QMessageBox.information(self, "Hotovo", f"Hodnocení {count} studentů ročníku {year} bylo vynulováno.")

    def _delete_year(self) -> None:
        if self._current_year_data is None:
            return
        year = self._current_year_data.year
        count = len(self._current_year_data.students)
        confirm = QMessageBox.critical(
            self,
            "Smazat ročník",
            f"Opravdu úplně smazat ročník {year} ({count} studentů)?\n\n"
            "Smaže se JSON soubor a ročník zmizí z aplikace.\n"
            "TUTO AKCI NELZE VRÁTIT ZPĚT.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        from softwaretestingklasifikator.io.storage import year_file
        path = year_file(self.data_dir, year)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "Chyba", f"Smazání souboru selhalo:\n{exc}")
            return
        self._current_year_data = None
        self._refresh_year_combo()

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

    def _on_repetent_marked(self, row: int) -> None:
        """Reakce na ruční zaškrtnutí „REP" checkboxu — pokus o transfer
        dat z předchozího ročníku podle jména a příjmení."""
        if self._current_year_data is None:
            return
        student = self.model.student_at(row)
        if student is None:
            return
        found = find_previous_student_by_name(
            self.data_dir,
            student.jmeno,
            student.prijmeni,
            self._current_year_data.year,
        )
        name = student.display_name() or student.os_cislo
        if found is None:
            self._update_status(
                f'„{name}" označen jako repetent. V minulých ročnících '
                f'žádný výskyt — body se nepřenášejí.'
            )
            return
        prev_year, prev_student = found
        transfer_from_previous(student, prev_student)
        self.model.emit_row_changed(row)
        self._save_now()
        self._update_status(
            f'„{name}" označen jako repetent. '
            f'Body přeneseny z ročníku {prev_year}.'
        )

    def _import_project_dates(self) -> None:
        if self._current_year_data is None:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import dat odevzdání projektu (jeden nebo více CSV)",
            str(Path.home()),
            "CSV (*.csv);;Všechny soubory (*)",
        )
        if not paths:
            return

        # Nejdřív načti všechny řádky ze všech souborů, pak dedup (best-wins),
        # teprve potom apply. Bez dedup by druhý CSV bez data přepsal první
        # CSV s datem na neodevzdal.
        all_rows: list = []
        files_with_errors: list[tuple[str, str]] = []
        files_processed = 0
        for path_str in paths:
            try:
                rows = read_project_dates_csv(Path(path_str))
            except Exception as exc:  # noqa: BLE001
                files_with_errors.append((Path(path_str).name, str(exc)))
                continue
            files_processed += 1
            all_rows.extend(rows)

        raw_row_count = len(all_rows)
        deduped = dedup_project_dates(all_rows)
        result = ProjectDateImportResult()
        apply_project_dates(
            self._current_year_data.students,
            deduped,
            deadlines=self._current_year_data.deadlines,
            result=result,
        )
        # Přepsat counts hodnotami z multi-file kontextu.
        result.files_processed = files_processed
        result.rows_total = raw_row_count  # včetně duplicit
        result.files_with_errors = files_with_errors

        # Refresh tabulky + persist.
        self.model.set_students(self._current_year_data.students)
        prijmeni_col = next((i for i, c in enumerate(COLUMNS) if c[0] == "prijmeni"), 1)
        self.table.sortByColumn(prijmeni_col, Qt.SortOrder.AscendingOrder)
        self._refresh_stats()
        self._apply_row_visibility()
        self._save_now()

        msg_lines = [
            f"Zpracováno souborů: {result.files_processed}",
            f"Načteno řádků celkem: {result.rows_total} "
            f"(unikátních studentů po dedup: {len(deduped)})",
            f"Spárováno se studenty ročníku: {result.matched}",
            f"  ⤷ s datem odevzdání: {result.set_date}",
            f"  ⤷ označeno jako Neodevzdal: {result.set_neodevzdal}",
        ]
        if result.unmatched:
            msg_lines.append(
                f"\nNenalezeno v ročníku: {len(result.unmatched)}"
            )
            for n in result.unmatched[:10]:
                msg_lines.append(f"  · {n}")
            if len(result.unmatched) > 10:
                msg_lines.append(f"  … a dalších {len(result.unmatched) - 10}")
        if result.files_with_errors:
            msg_lines.append("\nChyby při čtení souborů:")
            for fname, err in result.files_with_errors:
                msg_lines.append(f"  · {fname}: {err}")
        QMessageBox.information(
            self, "Import dat odevzdání", "\n".join(msg_lines)
        )

    def _import_test_scores(self) -> None:
        if self._current_year_data is None:
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import bodů z testů (CSV)",
            str(Path.home()),
            "CSV (*.csv);;Všechny soubory (*)",
        )
        if not path_str:
            return
        try:
            rows = read_test_scores_csv(Path(path_str))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Chyba importu",
                f"Načtení CSV s body z testů selhalo:\n{exc}",
            )
            return

        result = apply_test_scores(self._current_year_data.students, rows)

        # Refresh tabulky (set_students invaliduje cache + sort + repaint).
        self.model.set_students(self._current_year_data.students)
        prijmeni_col = next((i for i, c in enumerate(COLUMNS) if c[0] == "prijmeni"), 1)
        self.table.sortByColumn(prijmeni_col, Qt.SortOrder.AscendingOrder)
        self._refresh_stats()
        self._apply_row_visibility()
        self._save_now()

        msg = (
            f"Načteno {result.rows_total} řádků z CSV.\n"
            f"Spárováno: {result.matched}\n"
            f"Nenalezeno v ročníku: {len(result.unmatched)}\n\n"
            f"Test 1 — aktualizováno: {result.updated_test1}"
        )
        if result.improved_test1:
            msg += f" (z toho {result.improved_test1} přes pravidlo max)"
        msg += f"\nTest 2 — aktualizováno: {result.updated_test2}"
        if result.improved_test2:
            msg += f" (z toho {result.improved_test2} přes pravidlo max)"
        if result.unmatched:
            msg += "\n\nNenalezeni (prvních 10):"
            for j, p in result.unmatched[:10]:
                msg += f"\n  · {j} {p}"
            if len(result.unmatched) > 10:
                msg += f"\n  … a dalších {len(result.unmatched) - 10}"
        QMessageBox.information(self, "Import bodů z testů", msg)

    def _open_exports_manager(self) -> None:
        dlg = ExportsDialog(self.data_dir, self)
        dlg.exec()
        # Mohl smazat archivované exporty — indikátor v status baru
        # se musí re-evaluovat.
        self._update_status_for_year()

    def _export_predmet(self) -> None:
        if self._current_year_data is None:
            return
        year = self._current_year_data.year
        # Předvolba: poslední archivovaný export pro tento ročník
        # (řetězíme verze) — uživatel může přesto vybrat jiné CSV.
        year_exports = list_exports(self.data_dir, year)
        initial_path = (
            str(year_exports[0].path) if year_exports else str(Path.home())
        )
        # Jeden dialog: vyber nosné CSV ze STAGu.
        template_str, _ = QFileDialog.getOpenFileName(
            self,
            "Export hodnocení — vyber nosné CSV ze STAGu (SeznamStudentuNaPredmetu)",
            initial_path,
            "CSV ze STAGu (*.csv);;Všechny soubory (*)",
        )
        if not template_str:
            return

        # Cílovou cestu spočítáme automaticky v data/exports/<rok>/.
        output_path = next_export_path(self.data_dir, year)

        try:
            result = export_via_template_csv(
                Path(template_str),
                output_path,
                self._current_year_data,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self, "Chyba exportu", f"Export selhal:\n{exc}",
            )
            return

        # Zaznamenej hash + čas exportu, ať umíme detekovat neuložené změny.
        self._sync_students_to_year_data()
        self._current_year_data.last_exported_hash = compute_export_hash(
            self._current_year_data
        )
        self._current_year_data.last_exported_at = datetime.now()
        try:
            save_year(self.data_dir, self._current_year_data)
        except OSError as exc:
            QMessageBox.warning(
                self, "Pozor",
                f"CSV bylo uloženo, ale stav exportu se nepodařilo zapsat:\n{exc}",
            )
        self._update_status_for_year()

        msg_lines = [
            f"Uloženo: {output_path}",
            "",
            f"Studentů zapsáno do CSV: {result.updated}",
        ]
        if result.csv_only_unchanged:
            msg_lines.append(
                f"Řádků v CSV mimo aplikaci (ponecháno beze změny): "
                f"{result.csv_only_unchanged}"
            )
        if result.app_only:
            msg_lines.append(
                f"\nStudentů v aplikaci, kteří NEJSOU v CSV "
                f"(přeskočeno): {len(result.app_only)}"
            )
            for s in result.app_only[:15]:
                name = s.display_name() or s.os_cislo
                msg_lines.append(f"  · {name} ({s.os_cislo})")
            if len(result.app_only) > 15:
                msg_lines.append(f"  … a dalších {len(result.app_only) - 15}")

        # Info dialog s tlačítkem „Otevřít ve Finderu".
        box = QMessageBox(self)
        box.setWindowTitle("Export dokončen")
        box.setText("\n".join(msg_lines))
        box.setIcon(QMessageBox.Icon.Information)
        box.addButton(QMessageBox.StandardButton.Ok)
        open_btn = box.addButton(
            "Otevřít ve Finderu", QMessageBox.ButtonRole.ActionRole,
        )
        box.exec()
        if box.clickedButton() is open_btn:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_path.parent)))

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_now()
        super().closeEvent(event)
