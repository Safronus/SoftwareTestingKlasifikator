"""Vstupní bod aplikace."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from softwaretestingklasifikator.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SoftwareTestingKlasifikator")
    app.setOrganizationName("UTB-FAI")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
