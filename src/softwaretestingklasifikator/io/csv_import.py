"""Import seznamu studentů ze STAGu (CSV `getStudentiByRoakce`, cp1250)."""

from __future__ import annotations

import csv
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

# Sloupce, které z roakce CSV používáme. Ostatní jsou ignorovány.
ROAKCE_COLUMNS = (
    "osCislo", "jmeno", "prijmeni", "titulPred", "titulZa",
    "userName", "email", "stav",
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
                    titul_pred=(row.get("titulPred") or "").strip(),
                    titul_za=(row.get("titulZa") or "").strip(),
                    username=(row.get("userName") or "").strip(),
                    email=(row.get("email") or "").strip(),
                )
            )
    return students


def transfer_from_previous(student: Student, previous: Student) -> None:
    """Přenese hodnocení z minulého ročníku do nového studenta (repetent).

    Pravidla:
    - test1, test2, projekt: přenese se `prev_test + prev_bonus_test` (uznáno
      i s bonusem), oříznuto na MAX dané části.
    - bonus se NEPŘENÁŠÍ (reset na 0).
    - docházka, komentář, ISTQB CTFL: kopie.
    - datum_odevzdani, pokus, ukoncil_studium, znamka_override: reset na
      výchozí (nová klasifikace pro nový rok).
    """
    def _r(v: float) -> float:
        return round(float(v), POINTS_DECIMALS)

    student.test1 = min(MAX_TEST1, _r(previous.test1 + previous.bonus.test1))
    student.test2 = min(MAX_TEST2, _r(previous.test2 + previous.bonus.test2))
    student.projekt = min(MAX_PROJEKT, _r(previous.projekt + previous.bonus.projekt))
    student.bonus = BonusBreakdown()
    student.dochazka = previous.dochazka  # repetent dostává auto-True i přes tohle
    student.komentar = previous.komentar
    student.ma_istqb_ctfl = previous.ma_istqb_ctfl
    student.datum_odevzdani = None
    student.pokus = POKUS_RADNY
    student.ukoncil_studium = False
    student.znamka_override = None


def merge_students(existing: list[Student], imported: list[Student]) -> tuple[list[Student], int, int]:
    """Sloučí nově importované studenty do existujícího seznamu podle `os_cislo`.

    Pravidla:
    - Nový os_cislo → přidat.
    - Existující → aktualizovat pouze identifikační údaje (jméno, příjmení, tituly,
      username, email, vizualni_id), body/bonusy/docházku NEPŘEPISOVAT.

    Returns: (merged_list, added_count, updated_count)
    """
    by_os: dict[str, Student] = {s.os_cislo: s for s in existing}
    added = 0
    updated = 0
    for new in imported:
        if new.os_cislo in by_os:
            cur = by_os[new.os_cislo]
            changed = False
            for attr in ("jmeno", "prijmeni", "titul_pred", "titul_za", "username", "email"):
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
