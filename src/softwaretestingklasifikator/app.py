"""Vstupní bod aplikace."""

from __future__ import annotations

import contextlib
import locale
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from softwaretestingklasifikator.io.storage import default_data_dir
from softwaretestingklasifikator.ui.main_window import MainWindow

_ICON_PATH = Path(__file__).resolve().parent / "resources" / "icon.png"

# Jméno zámkového souboru ve složce data/. Drží se po celou dobu běhu;
# uvolní se zničením QLockFile objektu (= ukončením procesu).
LOCK_FILENAME = ".app.lock"
# Po této době se zámek po spadlém procesu považuje za starý. QLockFile
# navíc sám ověřuje, jestli PID držitele na TOMTO stroji ještě žije (a starý
# zámek po pádu rovnou odstraní bez ohledu na čas). Časový limit hraje roli
# hlavně u zámku z jiného stroje (např. sdílená složka přes iCloud), kde
# živost PID ověřit nejde.
_STALE_LOCK_MS = 30_000


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


def acquire_lock(data_dir: Path) -> tuple[QLockFile, tuple[int, str, str] | None]:
    """Pokusí se získat zámek jedné instance na složce `data_dir`.

    Vrací `(lock, holder)`:
    - `holder is None` → zámek získán; volající MUSÍ držet `lock` po celou
      dobu běhu (jinak se předčasně uvolní a ochrana zmizí).
    - `holder = (pid, hostname, appname)` → zámek drží jiná (žijící) instance.

    Zámek po spadlém procesu na stejném stroji QLockFile odstraní sám
    (ověří, že PID už neexistuje), takže pád aplikace uživatele nezablokuje.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data_dir / LOCK_FILENAME))
    lock.setStaleLockTime(_STALE_LOCK_MS)
    if lock.tryLock(100):
        return lock, None
    pid, host, appname = lock.getLockInfo()
    return lock, (pid, host, appname)


def force_lock(lock: QLockFile, data_dir: Path) -> bool:
    """Násilně převezme zámek (uživatel potvrdil „Přesto otevřít").

    Nejdřív zkusí standardní odstranění starého zámku, jinak smaže soubor
    napřímo a znovu zamkne. Vrací True při úspěchu.
    """
    if not lock.removeStaleLockFile():
        with contextlib.suppress(OSError):
            (data_dir / LOCK_FILENAME).unlink()
    return lock.tryLock(100)


def _confirm_force_start(holder: tuple[int, str, str]) -> bool:
    """Dialog při běžící jiné instanci. Vrací True = přesto otevřít."""
    pid, host, _appname = holder
    box = QMessageBox()
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Aplikace už běží")
    box.setText("Klasifikátor je zřejmě už spuštěný nad stejnými daty.")
    box.setInformativeText(
        f"Zámek drží proces PID {pid} na „{host}“.\n\n"
        "Spuštění druhé instance může způsobit, že si navzájem přepíšete "
        "změny (poslední uložení vyhraje).\n\n"
        "Pokud jste si jistí, že žádná jiná instance neběží (např. po pádu "
        "nebo na jiném počítači přes sdílenou složku), můžete přesto otevřít."
    )
    quit_btn = box.addButton("Ukončit", QMessageBox.ButtonRole.RejectRole)
    force_btn = box.addButton("Přesto otevřít", QMessageBox.ButtonRole.DestructiveRole)
    box.setDefaultButton(quit_btn)
    box.exec()
    return box.clickedButton() is force_btn


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

    # Single-instance soft-lock nad datovou složkou — brání dvěma instancím
    # editovat stejná data a tiše si přepisovat změny.
    data_dir = default_data_dir()
    lock, holder = acquire_lock(data_dir)
    if holder is not None:
        if not _confirm_force_start(holder):
            return 1
        force_lock(lock, data_dir)
    # Zámek musí přežít celou dobu běhu — drž referenci na app objektu.
    app._instance_lock = lock  # type: ignore[attr-defined]

    window = MainWindow(data_dir=data_dir)
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
