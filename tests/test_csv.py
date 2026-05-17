"""Testy CSV importu (roakce) a exportu (predmet)."""

from __future__ import annotations

import csv

from softwaretestingklasifikator.config import (
    STAG_CSV_DELIMITER,
    STAG_CSV_ENCODING,
    STAG_CSV_QUOTECHAR,
)
from softwaretestingklasifikator.domain.models import Student
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
        {"osCislo": "A1", "jmeno": "Eva", "prijmeni": "Nováková", "stav": "S"},
        {"osCislo": "A2", "jmeno": "Petr", "prijmeni": "Svoboda", "stav": "S"},
    ])
    out = read_roakce_csv(p)
    assert len(out) == 2
    assert out[0].os_cislo == "A1"
    assert out[0].jmeno == "Eva"
    assert out[0].prijmeni == "Nováková"
    assert out[1].os_cislo == "A2"


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
        Student(os_cislo="A1", jmeno="New", prijmeni="Surname"),
        Student(os_cislo="A2", jmeno="Other", prijmeni="Person"),
    ]
    merged, added, updated = merge_students(existing, imported)
    assert added == 1
    assert updated == 1
    assert [s.os_cislo for s in merged] == ["A1", "A2"]
    assert merged[0].jmeno == "New"
    assert merged[0].prijmeni == "Surname"


def test_merge_does_not_overwrite_points():
    existing = [Student(os_cislo="A1", jmeno="A", prijmeni="X", test1=20, projekt=140)]
    imported = [Student(os_cislo="A1", jmeno="A", prijmeni="X")]
    merged, _, _ = merge_students(existing, imported)
    assert merged[0].test1 == 20
    assert merged[0].projekt == 140


