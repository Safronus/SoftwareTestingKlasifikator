"""Persistence ročníku do `data/<rok>.json` (atomic write)."""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from softwaretestingklasifikator.domain.models import YearData

if TYPE_CHECKING:
    from softwaretestingklasifikator.domain.models import Student


def default_data_dir() -> Path:
    """Defaultní složka pro data — `<repo>/data`.

    Repo cesta se odvozuje z umístění balíčku (tj. funguje i u editable installu
    přes symlink, kde `__file__` ukazuje do `src/`).
    """
    # __file__ = .../src/softwaretestingklasifikator/io/storage.py
    pkg_root = Path(__file__).resolve().parent.parent.parent.parent
    return pkg_root / "data"


def year_file(data_dir: Path, year: int) -> Path:
    return data_dir / f"{year}.json"


def load_year(data_dir: Path, year: int) -> YearData:
    p = year_file(data_dir, year)
    if not p.exists():
        return YearData(year=year)
    with p.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return YearData.from_dict(raw)


def save_year(data_dir: Path, data: YearData) -> Path:
    """Atomic write přes temporary soubor + os.replace."""
    data_dir.mkdir(parents=True, exist_ok=True)
    target = year_file(data_dir, data.year)
    serialized = json.dumps(data.to_dict(), ensure_ascii=False, indent=2)

    fd, tmp_path = tempfile.mkstemp(prefix=f".{data.year}.", suffix=".json.tmp", dir=str(data_dir))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
        os.replace(tmp_path, target)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    return target


_YEAR_FILE_RE = re.compile(r"^(\d{4})\.json$")


def list_available_years(data_dir: Path) -> list[int]:
    if not data_dir.exists():
        return []
    years: list[int] = []
    for p in data_dir.iterdir():
        m = _YEAR_FILE_RE.match(p.name)
        if m:
            years.append(int(m.group(1)))
    return sorted(years)


def find_previous_students_batch(
    data_dir: Path,
    os_cisla: set[str],
    current_year: int,
) -> dict[str, tuple[int, Student]]:
    """Pro každé os. číslo vrátí mapping → (rok, student) jeho nejnovějšího
    předchozího výskytu (rok < current_year).

    Implementace: projde roky sestupně, načte každý jen jednou, pro každý
    rok obslouží všechny ještě nenalezené os. čísla. Vrátí dict os_cislo →
    (year, Student).
    """

    result: dict[str, tuple[int, Student]] = {}
    remaining = set(os_cisla)
    if not remaining:
        return result
    for year in sorted(list_available_years(data_dir), reverse=True):
        if year >= current_year or not remaining:
            continue
        try:
            data = load_year(data_dir, year)
        except OSError:
            continue
        for s in data.students:
            if s.os_cislo in remaining:
                result[s.os_cislo] = (year, s)
                remaining.discard(s.os_cislo)
        if not remaining:
            break
    return result
