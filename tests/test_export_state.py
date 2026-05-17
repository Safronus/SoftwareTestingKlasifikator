"""Testy hashe exportovatelného stavu + serializace metadat exportu."""

from __future__ import annotations

from datetime import date, datetime

from softwaretestingklasifikator.domain.export_state import compute_export_hash
from softwaretestingklasifikator.domain.models import (
    POKUS_OPRAVNY,
    POKUS_RADNY,
    Student,
    YearData,
)
from softwaretestingklasifikator.io.storage import load_year, save_year


def _mk_year() -> YearData:
    return YearData(
        year=2026,
        students=[
            Student(
                os_cislo="A00002", jmeno="Bob", prijmeni="Beta",
                test1=15, test2=12, projekt=130,
                dochazka=True,
                datum_odevzdani=date(2026, 5, 10),
                pokus=POKUS_RADNY,
            ),
            Student(
                os_cislo="A00001", jmeno="Alice", prijmeni="Alfa",
                test1=22, test2=20, projekt=180,
                dochazka=True,
                datum_odevzdani=date(2026, 5, 9),
                pokus=POKUS_RADNY,
            ),
        ],
    )


def test_hash_is_deterministic_across_student_order():
    """Stejní studenti v jiném pořadí → stejný hash (sortujeme po os_cislo)."""
    a = _mk_year()
    b = _mk_year()
    b.students.reverse()
    assert compute_export_hash(a) == compute_export_hash(b)


def test_hash_changes_when_grade_relevant_field_changes():
    a = _mk_year()
    h0 = compute_export_hash(a)

    # Změna pokusu — promítá se do CSV → hash musí být jiný.
    a.students[0].pokus = POKUS_OPRAVNY
    assert compute_export_hash(a) != h0

    # Změna data odevzdání — taktéž v CSV.
    a.students[0].pokus = POKUS_RADNY
    a.students[0].datum_odevzdani = date(2026, 5, 11)
    assert compute_export_hash(a) != h0


def test_hash_changes_when_points_change_grade_or_total():
    a = _mk_year()
    h0 = compute_export_hash(a)
    # Měnit body znamená měnit Celkem (a často i známku).
    a.students[0].test1 = 24
    assert compute_export_hash(a) != h0


def test_hash_unchanged_for_irrelevant_field():
    """Komentář se neexportuje, tudíž hash by se neměl měnit."""
    a = _mk_year()
    h0 = compute_export_hash(a)
    a.students[0].komentar = "interní poznámka"
    assert compute_export_hash(a) == h0


def test_export_metadata_roundtrip(tmp_path):
    data = _mk_year()
    data.last_exported_hash = "deadbeef"
    data.last_exported_at = datetime(2026, 5, 16, 14, 30, 0)
    save_year(tmp_path, data)

    loaded = load_year(tmp_path, 2026)
    assert loaded.last_exported_hash == "deadbeef"
    assert loaded.last_exported_at == datetime(2026, 5, 16, 14, 30, 0)


def test_export_metadata_defaults_when_missing(tmp_path):
    """Starší JSON bez polí export-state se musí načíst bez chyby."""
    import json
    (tmp_path / "2025.json").write_text(
        json.dumps({
            "year": 2025,
            "deadlines": {"first": None, "second": None},
            "students": [],
        }),
        encoding="utf-8",
    )
    loaded = load_year(tmp_path, 2025)
    assert loaded.last_exported_hash is None
    assert loaded.last_exported_at is None
