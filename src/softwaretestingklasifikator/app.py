"""Vstupní bod aplikace."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from softwaretestingklasifikator.ui.main_window import MainWindow

_ICON_PATH = Path(__file__).resolve().parent / "resources" / "icon.png"


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
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
