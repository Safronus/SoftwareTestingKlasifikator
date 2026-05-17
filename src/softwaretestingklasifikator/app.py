"""Vstupní bod aplikace."""

from __future__ import annotations

import locale
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from softwaretestingklasifikator.ui.main_window import MainWindow

_ICON_PATH = Path(__file__).resolve().parent / "resources" / "icon.png"


def _setup_czech_locale() -> None:
    """Nastaví cs_CZ collation pro správné řazení diakritiky.

    Bez tohoto by Č skončilo až za Z (Unicode kód U+010C vs. U+005A).
    Pokud žádná varianta není dostupná, sort spadne na default Unicode
    order (méně ideální, ale funkční).
    """
    for loc in ("cs_CZ.UTF-8", "cs_CZ.utf8", "cs_CZ", "Czech_Czech Republic.1250"):
        try:
            locale.setlocale(locale.LC_COLLATE, loc)
            return
        except locale.Error:
            continue


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    # POZOR: locale musí být nastaveno PO QApplication() — Qt si při startu
    # resetuje globální C locale a strxfrm by pak ignoroval cs_CZ collation.
    _setup_czech_locale()
    app.setApplicationName("SoftwareTestingKlasifikator")
    app.setApplicationDisplayName("AP4TS Klasifikátor")
    app.setOrganizationName("UTB-FAI")
    if _ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))
    window = MainWindow()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
