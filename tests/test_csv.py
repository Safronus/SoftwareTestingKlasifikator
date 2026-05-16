"""Testy CSV importu (roakce) a exportu (predmet)."""

from __future__ import annotations

import csv

from softwaretestingklasifikator.config import (
    STAG_CSV_DELIMITER,
    STAG_CSV_ENCODING,
    STAG_CSV_QUOTECHAR,
)
from softwaretestingklasifikator.domain.models import Student, YearData
from softwaretestingklasifikator.io.csv_export import PREDMET_COLUMNS, export_to_predmet_csv
from softwaretestingklasifikator.io.csv_import import merge_students, read_roakce_csv

ROAKCE_HEADERS = (
    "osCislo", "jmeno", "prijmeni", "titulPred", "titulZa", "stav",
    "userName", "stprIdno", "nazevSp", "fakultaSp", "kodSp", "formaSp",
    "typSp", "typSpKey", "mistoVyuky", "rocnik", "financovani", "oborKomb",
    "oborIdnos", "email", "maxDobaDatum", "simsP58", "simsP59", "cisloKarty",
    "pohlavi", "rozvrhovyKrouzek", "studijniKruh", "evidovanBankovniUcet",
    "studReferentkaUsername", "studReferentkaUcitidno", "studReferentkaEmail",
    "studReferentkaTelefon", "studReferentkaPrijmeniJmeno",
    "planovaneOdevzdaniVSKPText", "statutPredmetu", "casPrihlaseni",
)


def _write_roakce(path, rows):
    with open(path, "w", encoding=STAG_CSV_ENCODING, newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=list(ROAKCE_HEADERS),
            delimiter=STAG_CSV_DELIMITER, quotechar=STAG_CSV_QUOTECHAR,
            quoting=csv.QUOTE_ALL,
        )
        w.writeheader()
        for row in rows:
            w.writerow({h: row.get(h, "") for h in ROAKCE_HEADERS})


def test_read_roakce_basic(tmp_path):
    p = tmp_path / "in.csv"
    _write_roakce(p, [
        {"osCislo": "A1", "jmeno": "Eva", "prijmeni": "Nováková", "stav": "S", "userName": "e_nov", "email": "e@x"},
        {"osCislo": "A2", "jmeno": "Petr", "prijmeni": "Svoboda", "stav": "S"},
    ])
    out = read_roakce_csv(p)
    assert len(out) == 2
    assert out[0].os_cislo == "A1"
    assert out[0].jmeno == "Eva"
    assert out[0].prijmeni == "Nováková"
    assert out[0].email == "e@x"


def test_read_roakce_skips_inactive(tmp_path):
    p = tmp_path / "in.csv"
    _write_roakce(p, [
        {"osCislo": "A1", "jmeno": "A", "prijmeni": "X", "stav": "S"},
        {"osCislo": "A2", "jmeno": "B", "prijmeni": "Y", "stav": "P"},  # přerušeno
        {"osCislo": "", "jmeno": "C", "prijmeni": "Z", "stav": "S"},  # bez os_cisla
    ])
    out = read_roakce_csv(p)
    assert [s.os_cislo for s in out] == ["A1"]


def test_merge_students_adds_and_updates():
    existing = [Student(os_cislo="A1", jmeno="Old", prijmeni="Name")]
    imported = [
        Student(os_cislo="A1", jmeno="New", prijmeni="Name", email="new@x"),
        Student(os_cislo="A2", jmeno="Other", prijmeni="Person"),
    ]
    merged, added, updated = merge_students(existing, imported)
    assert added == 1
    assert updated == 1
    assert [s.os_cislo for s in merged] == ["A1", "A2"]
    assert merged[0].jmeno == "New"
    assert merged[0].email == "new@x"


def test_merge_does_not_overwrite_points():
    existing = [Student(os_cislo="A1", jmeno="A", prijmeni="X", test1=20, projekt=140)]
    imported = [Student(os_cislo="A1", jmeno="A", prijmeni="X")]
    merged, _, _ = merge_students(existing, imported)
    assert merged[0].test1 == 20
    assert merged[0].projekt == 140


def test_export_predmet_csv_roundtrip(tmp_path):
    students = [
        Student(os_cislo="A1", jmeno="Eva", prijmeni="N", vizualni_id="EN001",
                test1=25, test2=25, projekt=150, dochazka=True),
        Student(os_cislo="A2", jmeno="Petr", prijmeni="S", vizualni_id="PS002",
                test1=14, test2=20, projekt=100, dochazka=True),  # T1 < 15 → F
    ]
    data = YearData(year=2026, students=students)
    out_path = tmp_path / "export.csv"
    count = export_to_predmet_csv(out_path, data)
    assert count == 2

    # Načteme zpět a ověříme strukturu
    with open(out_path, encoding=STAG_CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(f, delimiter=STAG_CSV_DELIMITER, quotechar=STAG_CSV_QUOTECHAR)
        rows = list(reader)
    assert len(rows) == 2
    assert list(reader.fieldnames or []) == list(PREDMET_COLUMNS)
    r1 = rows[0]
    assert r1["os_cislo"] == "A1"
    assert r1["zk_hodnoceni"] == "A"
    assert float(r1["zk_body"]) == 200
    assert rows[1]["zk_hodnoceni"] == "F"
    # STAG year = academic_year - 1
    assert r1["rok"] == "2025"
