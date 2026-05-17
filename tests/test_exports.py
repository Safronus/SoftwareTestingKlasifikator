"""Testy storage vrstvy pro historické exporty."""

from __future__ import annotations

from datetime import datetime

from softwaretestingklasifikator.io.exports import (
    _parse_export_filename,
    default_exports_dir,
    delete_export,
    exports_dir_for_year,
    list_exports,
    next_export_path,
)


def test_default_exports_dir(tmp_path):
    assert default_exports_dir(tmp_path) == tmp_path / "exports"


def test_exports_dir_for_year(tmp_path):
    assert exports_dir_for_year(tmp_path, 2026) == tmp_path / "exports" / "2026"


def test_next_export_path_creates_dir_and_filename(tmp_path):
    now = datetime(2026, 5, 17, 14, 30, 45)
    p = next_export_path(tmp_path, 2026, now=now)
    assert p == tmp_path / "exports" / "2026" / "2026-05-17_14-30-45.csv"
    assert p.parent.exists()


def test_next_export_path_collision_adds_suffix(tmp_path):
    now = datetime(2026, 5, 17, 14, 30, 45)
    first = next_export_path(tmp_path, 2026, now=now)
    first.write_text("first")
    second = next_export_path(tmp_path, 2026, now=now)
    assert second.name == "2026-05-17_14-30-45_2.csv"
    second.write_text("second")
    third = next_export_path(tmp_path, 2026, now=now)
    assert third.name == "2026-05-17_14-30-45_3.csv"


def test_parse_export_filename_valid():
    assert _parse_export_filename("2026-05-17_14-30-45.csv") == datetime(
        2026, 5, 17, 14, 30, 45,
    )


def test_parse_export_filename_with_suffix():
    assert _parse_export_filename("2026-05-17_14-30-45_2.csv") == datetime(
        2026, 5, 17, 14, 30, 45,
    )


def test_parse_export_filename_invalid():
    assert _parse_export_filename("foo.csv") is None
    assert _parse_export_filename("2026-13-99_99-99-99.csv") is None  # invalid date
    assert _parse_export_filename("export.csv") is None


def test_list_exports_empty_when_no_dir(tmp_path):
    assert list_exports(tmp_path) == []


def test_list_exports_all_years(tmp_path):
    # Vytvoříme exporty napříč 3 lety.
    for year, ts in [
        (2024, datetime(2024, 5, 12, 10, 0, 0)),
        (2025, datetime(2025, 5, 14, 11, 0, 0)),
        (2026, datetime(2026, 5, 17, 12, 0, 0)),
        (2026, datetime(2026, 5, 18, 13, 0, 0)),
    ]:
        p = next_export_path(tmp_path, year, now=ts)
        p.write_text("csv data")
    exports = list_exports(tmp_path)
    assert len(exports) == 4
    # Nejnovější první (sort dle (year, timestamp) desc)
    assert exports[0].year == 2026
    assert exports[0].timestamp == datetime(2026, 5, 18, 13, 0, 0)
    assert exports[-1].year == 2024


def test_list_exports_filter_by_year(tmp_path):
    for year, ts in [
        (2025, datetime(2025, 5, 14, 11, 0, 0)),
        (2026, datetime(2026, 5, 17, 12, 0, 0)),
        (2026, datetime(2026, 5, 18, 13, 0, 0)),
    ]:
        next_export_path(tmp_path, year, now=ts).write_text("x")
    only_2026 = list_exports(tmp_path, year=2026)
    assert len(only_2026) == 2
    assert all(e.year == 2026 for e in only_2026)


def test_list_exports_ignores_unrecognized_files(tmp_path):
    """Cizí soubory ve složce (uživatel je tam zkopíroval) se přeskočí."""
    p = next_export_path(tmp_path, 2026, now=datetime(2026, 5, 17, 12, 0, 0))
    p.write_text("legit")
    junk = exports_dir_for_year(tmp_path, 2026) / "random.csv"
    junk.write_text("junk")
    not_csv = exports_dir_for_year(tmp_path, 2026) / "notes.txt"
    not_csv.write_text("note")
    exports = list_exports(tmp_path)
    assert len(exports) == 1
    assert exports[0].path == p


def test_delete_export_removes_file(tmp_path):
    p = next_export_path(tmp_path, 2026, now=datetime(2026, 5, 17, 12, 0, 0))
    p.write_text("x")
    [info] = list_exports(tmp_path)
    delete_export(info)
    assert not p.exists()
    assert list_exports(tmp_path) == []


def test_delete_export_noop_if_already_gone(tmp_path):
    """Mazání už neexistujícího souboru by nemělo selhat."""
    p = next_export_path(tmp_path, 2026, now=datetime(2026, 5, 17, 12, 0, 0))
    p.write_text("x")
    [info] = list_exports(tmp_path)
    delete_export(info)
    delete_export(info)  # druhé volání — no-op
