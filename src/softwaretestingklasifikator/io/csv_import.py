"""Import seznamu studentů ze STAGu (CSV `getStudentiByRoakce`, cp1250)."""

from __future__ import annotations

import csv
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from softwaretestingklasifikator.config import (
    MAX_PROJEKT,
    MAX_TEST1,
    MAX_TEST2,
    POINTS_DECIMALS,
    STAG_CSV_DELIMITER,
    STAG_CSV_ENCODING,
    STAG_CSV_QUOTECHAR,
)
from softwaretestingklasifikator.domain.models import (
    POKUS_RADNY,
    BonusBreakdown,
    Student,
)


def _norm_name(s: str | None) -> str:
    """Normalizace jména/příjmení pro porovnání: lowercase + bez diakritiky."""
    if not s:
        return ""
    ascii_form = (
        unicodedata.normalize("NFD", s)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return ascii_form.strip().lower()

# Sloupce, které z roakce CSV používáme. Ostatní jsou ignorovány.
ROAKCE_COLUMNS = (
    "osCislo", "jmeno", "prijmeni", "stav",
)


def read_roakce_csv(path: Path) -> list[Student]:
    """Načte studenty ze STAG roakce CSV (cp1250, ;).

    Filtruje záznamy, kde `stav` není "S" (studuje) — neaktivní/přerušené studium
    se nedostane do klasifikace.
    """
    students: list[Student] = []
    with open(path, encoding=STAG_CSV_ENCODING, newline="") as f:
        reader = csv.DictReader(
            f,
            delimiter=STAG_CSV_DELIMITER,
            quotechar=STAG_CSV_QUOTECHAR,
        )
        for row in reader:
            os_cislo = (row.get("osCislo") or "").strip()
            if not os_cislo:
                continue
            stav = (row.get("stav") or "").strip().upper()
            if stav and stav != "S":
                # Neaktivní student — přeskočit.
                continue
            students.append(
                Student(
                    os_cislo=os_cislo,
                    jmeno=(row.get("jmeno") or "").strip(),
                    prijmeni=(row.get("prijmeni") or "").strip(),
                )
            )
    return students


@dataclass
class TestScoreRow:
    """Jeden řádek z CSV s body z testů (Moodle / STAG export)."""

    __test__ = False  # vyhne pytestu sběru jako test class

    jmeno: str
    prijmeni: str
    test1: float | None = None  # None = nepsal/-
    test2: float | None = None


@dataclass
class TestScoreImportResult:
    __test__ = False  # vyhne pytestu sběru jako test class
    matched: int = 0
    unmatched: list[tuple[str, str]] = field(default_factory=list)
    updated_test1: int = 0
    updated_test2: int = 0
    improved_test1: int = 0  # max-pravidlo: nová hodnota nahradila vyšší původní
    improved_test2: int = 0
    rows_total: int = 0


def _find_column(fields: list[str], *candidates: str) -> str | None:
    """Najde sloupec, jehož název obsahuje (case-insensitive) některý z kandidátů.

    Tolerantní vůči variacím v hlavičkách (Moodle vs STAG vs vlastní).
    """
    for cand in candidates:
        cand_low = cand.lower()
        for f in fields:
            if cand_low in (f or "").lower():
                return f
    return None


def _parse_score(value) -> float | None:
    """Parsuje string z CSV: prázdné nebo '-'/'—' → None, jinak float (akceptuje ',')."""
    if value is None:
        return None
    v = str(value).strip()
    if v in ("", "-", "—", "–"):
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def read_test_scores_csv(path: Path) -> list[TestScoreRow]:
    """Načte CSV s body z testů.

    Očekává UTF-8 comma-separated formát s hlavičkami typu Moodle/STAG:
    `Křestní jméno, Příjmení, ID, ..., Test: Test č. 1 (...), Test: Test č. 2 (...)`.
    Tolerantní k variacím — sloupce se hledají podle podřetězce.
    """
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames or [])
        jmeno_col = _find_column(fields, "křestní", "jméno", "first")
        prijmeni_col = _find_column(fields, "příjmení", "surname", "last")
        t1_col = _find_column(fields, "Test č. 1", "Test 1", "test1")
        t2_col = _find_column(fields, "Test č. 2", "Test 2", "test2")
        if not jmeno_col or not prijmeni_col:
            raise ValueError(
                "CSV neobsahuje sloupce 'Křestní jméno' a 'Příjmení'. "
                f"Nalezené sloupce: {fields}"
            )
        rows: list[TestScoreRow] = []
        for raw in reader:
            rows.append(TestScoreRow(
                jmeno=(raw.get(jmeno_col) or "").strip(),
                prijmeni=(raw.get(prijmeni_col) or "").strip(),
                test1=_parse_score(raw.get(t1_col)) if t1_col else None,
                test2=_parse_score(raw.get(t2_col)) if t2_col else None,
            ))
    return rows


def apply_test_scores(
    students: list[Student],
    rows: list[TestScoreRow],
) -> TestScoreImportResult:
    """Zapíše body z CSV do existujících studentů ročníku.

    Párování: podle (jméno, příjmení), normalizováno (lowercase + bez diakritiky).
    Pravidlo: vždy `max(existing, csv)` — repetent může mít už lepší body z minulého
    roku, ty zůstanou. Body se clampují na MAX_TEST1 / MAX_TEST2.
    """
    by_name: dict[tuple[str, str], Student] = {}
    for s in students:
        key = (_norm_name(s.jmeno), _norm_name(s.prijmeni))
        # První výskyt vyhrává — duplicitní jména jsou edge case.
        if key not in by_name:
            by_name[key] = s

    result = TestScoreImportResult(rows_total=len(rows))
    for r in rows:
        key = (_norm_name(r.jmeno), _norm_name(r.prijmeni))
        student = by_name.get(key)
        if student is None:
            result.unmatched.append((r.jmeno, r.prijmeni))
            continue
        result.matched += 1
        if r.test1 is not None:
            candidate = min(MAX_TEST1, round(r.test1, POINTS_DECIMALS))
            new_t1 = max(student.test1, candidate)
            if new_t1 != student.test1:
                if student.test1 > 0:
                    result.improved_test1 += 1
                student.test1 = new_t1
                result.updated_test1 += 1
        if r.test2 is not None:
            candidate = min(MAX_TEST2, round(r.test2, POINTS_DECIMALS))
            new_t2 = max(student.test2, candidate)
            if new_t2 != student.test2:
                if student.test2 > 0:
                    result.improved_test2 += 1
                student.test2 = new_t2
                result.updated_test2 += 1
    return result


def transfer_from_previous(student: Student, previous: Student) -> None:
    """Přenese hodnocení z minulého ročníku do nového studenta (repetent).

    Použito při dvou scénářích:
    1. CSV import nového ročníku — student má zatím defaultní hodnoty.
    2. Ručním označení jako REP — student už může mít zadaná data.

    Pravidla (chrání před přepsáním ručně zadaných dat):
    - body (test1, test2, projekt): vždy **max(aktuální, prev_test + prev_bonus)**,
      oříznuto na MAX. Když student už má vyšší body, zůstávají.
    - bonus se NEPŘENÁŠÍ (bonus z minulého roku se „zúčtuje" do testů přes max výše).
    - komentář, docházka, ISTQB CTFL: kopie z `prev` jen pokud aktuální je
      prázdný/default (nepřepíše ručně zadaná data; ale ISTQB lze jen „povýšit",
      nikdy ho neztratit).
    - datum_odevzdani, pokus, ukoncil_studium, znamka_override: vždy reset
      na výchozí (jde o nový rok — tyto stavy z loňska nemají smysl).
    """
    def _r(v: float) -> float:
        return round(float(v), POINTS_DECIMALS)

    # Max-pravidlo pro body: chrání aktuální výsledky, pokud jsou lepší.
    candidate_t1 = min(MAX_TEST1, _r(previous.test1 + previous.bonus.test1))
    candidate_t2 = min(MAX_TEST2, _r(previous.test2 + previous.bonus.test2))
    candidate_pj = min(MAX_PROJEKT, _r(previous.projekt + previous.bonus.projekt))
    student.test1 = max(student.test1, candidate_t1)
    student.test2 = max(student.test2, candidate_t2)
    student.projekt = max(student.projekt, candidate_pj)
    student.bonus = BonusBreakdown()

    # Pole, která chceme zachovat pokud už uživatel něco zadal.
    if not student.komentar:
        student.komentar = previous.komentar
    # ISTQB: zachovat True (nikdy ho nedegradovat), případně povýšit z minula.
    if previous.ma_istqb_ctfl and not student.ma_istqb_ctfl:
        student.ma_istqb_ctfl = True
    # Docházka: u repetenta je stejně auto-True; kopii dělej jen pokud aktuální
    # je False (neudělá to viditelný rozdíl, ale zachová původní hodnotu pokud
    # ji uživatel cíleně nastavil na True).
    if not student.dochazka:
        student.dochazka = previous.dochazka

    # Stavy spjaté s aktuálním rokem — vždy reset.
    student.datum_odevzdani = None
    student.pokus = POKUS_RADNY
    student.ukoncil_studium = False
    student.znamka_override = None


def merge_students(existing: list[Student], imported: list[Student]) -> tuple[list[Student], int, int]:
    """Sloučí nově importované studenty do existujícího seznamu podle `os_cislo`.

    Pravidla:
    - Nový os_cislo → přidat.
    - Existující → aktualizovat pouze identifikační údaje (jméno, příjmení,
      tituly), body/bonusy/docházku NEPŘEPISOVAT.

    Returns: (merged_list, added_count, updated_count)
    """
    by_os: dict[str, Student] = {s.os_cislo: s for s in existing}
    added = 0
    updated = 0
    for new in imported:
        if new.os_cislo in by_os:
            cur = by_os[new.os_cislo]
            changed = False
            for attr in ("jmeno", "prijmeni"):
                new_val = getattr(new, attr)
                if new_val and getattr(cur, attr) != new_val:
                    setattr(cur, attr, new_val)
                    changed = True
            if changed:
                updated += 1
        else:
            by_os[new.os_cislo] = new
            added += 1
    # Zachovat pořadí: existující v původním pořadí, pak noví.
    merged: list[Student] = []
    seen: set[str] = set()
    for s in existing:
        merged.append(by_os[s.os_cislo])
        seen.add(s.os_cislo)
    for new in imported:
        if new.os_cislo not in seen:
            merged.append(by_os[new.os_cislo])
            seen.add(new.os_cislo)
    return merged, added, updated
