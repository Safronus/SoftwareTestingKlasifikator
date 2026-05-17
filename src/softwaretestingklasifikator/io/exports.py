"""Storage layer pro historické exporty STAG CSV.

Soubory se ukládají do `data/exports/<rok>/<timestamp>.csv`.
Celá složka `data/` je v `.gitignore`, takže exporty se nedostanou na GitHub.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Název souboru = ISO-like timestamp; sortovatelný a self-describing.
_FILENAME_FMT = "%Y-%m-%d_%H-%M-%S.csv"
_FILENAME_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})\.csv$"
)


@dataclass(frozen=True)
class ExportInfo:
    """Metadata o jednom uloženém exportu."""

    path: Path
    year: int           # akademický rok (z cesty data/exports/<year>/)
    timestamp: datetime  # parsed z názvu souboru
    size: int           # velikost v bajtech


def default_exports_dir(data_dir: Path) -> Path:
    return data_dir / "exports"


def exports_dir_for_year(data_dir: Path, year: int) -> Path:
    return default_exports_dir(data_dir) / str(year)


def next_export_path(
    data_dir: Path,
    year: int,
    *,
    now: datetime | None = None,
) -> Path:
    """Vrátí cestu pro nový export — `data/exports/<rok>/<timestamp>.csv`.

    Pokud soubor se stejným timestampem už existuje (export ve stejné vteřině),
    přidá suffix `_2`, `_3`, …
    """
    now = now or datetime.now()
    year_dir = exports_dir_for_year(data_dir, year)
    year_dir.mkdir(parents=True, exist_ok=True)
    base = now.strftime(_FILENAME_FMT)
    candidate = year_dir / base
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = 2
    while True:
        candidate = year_dir / f"{stem}_{suffix}.csv"
        if not candidate.exists():
            return candidate
        suffix += 1


def _parse_export_filename(name: str) -> datetime | None:
    """Z názvu souboru `YYYY-MM-DD_HH-MM-SS.csv` vrátí datetime.

    Vrací None, pokud název neodpovídá očekávanému vzoru — takový soubor je
    cizí (uživatel ho tam možná zkopíroval) a app ho ignoruje.
    """
    m = _FILENAME_RE.match(name)
    if not m:
        # Tolerantně: zkus i variantu se suffixem `_N.csv` (kolize timestampu).
        m_suffix = re.match(
            r"^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})_\d+\.csv$",
            name,
        )
        if not m_suffix:
            return None
        m = m_suffix
    try:
        return datetime(
            year=int(m.group(1)),
            month=int(m.group(2)),
            day=int(m.group(3)),
            hour=int(m.group(4)),
            minute=int(m.group(5)),
            second=int(m.group(6)),
        )
    except ValueError:
        return None


def list_exports(
    data_dir: Path,
    year: int | None = None,
) -> list[ExportInfo]:
    """Seznam exportů. Pokud `year` zadán, jen pro něj; jinak napříč všemi."""
    base = default_exports_dir(data_dir)
    if not base.exists():
        return []
    exports: list[ExportInfo] = []
    year_dirs: list[Path]
    if year is not None:
        d = base / str(year)
        year_dirs = [d] if d.exists() else []
    else:
        year_dirs = [p for p in base.iterdir() if p.is_dir() and p.name.isdigit()]
    for y_dir in year_dirs:
        try:
            y = int(y_dir.name)
        except ValueError:
            continue
        for p in y_dir.iterdir():
            if not p.is_file() or p.suffix != ".csv":
                continue
            ts = _parse_export_filename(p.name)
            if ts is None:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            exports.append(ExportInfo(path=p, year=y, timestamp=ts, size=size))
    # Default sort: nejnovější první.
    exports.sort(key=lambda e: (e.year, e.timestamp), reverse=True)
    return exports


def delete_export(info: ExportInfo) -> None:
    """Smaže soubor. No-op pokud už neexistuje."""
    try:
        info.path.unlink(missing_ok=True)
    except OSError as exc:
        raise OSError(f"Smazání exportu selhalo: {exc}") from exc
