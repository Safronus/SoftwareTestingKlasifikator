"""Datové modely studentů a ročníku."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from softwaretestingklasifikator.config import POINTS_DECIMALS

# Stavy odevzdání projektu — drží se v Student.pokus.
POKUS_RADNY = "radny"
POKUS_OPRAVNY = "opravny"
POKUS_PO_TERMINU = "po_terminu"
POKUS_NEODEVZDAL = "neodevzdal"
POKUS_VALUES: tuple[str, ...] = (
    POKUS_RADNY,
    POKUS_OPRAVNY,
    POKUS_PO_TERMINU,
    POKUS_NEODEVZDAL,
)
POKUS_LABELS: dict[str, str] = {
    POKUS_RADNY: "1. pokus",
    POKUS_OPRAVNY: "Oprava",
    POKUS_PO_TERMINU: "Po termínu",
    POKUS_NEODEVZDAL: "Neodevzdal",
}


def _normalize_pokus(value) -> str:
    """Akceptuje int/str/None, vrací jeden ze stringů POKUS_VALUES."""
    if value is None or value == "":
        return POKUS_RADNY
    if isinstance(value, str):
        v = value.strip().lower()
        if v in POKUS_VALUES:
            return v
        # Tolerance pro stará data (1/2) přijatá jako string.
        if v in ("1", "1."):
            return POKUS_RADNY
        if v in ("2", "2."):
            return POKUS_OPRAVNY
        return POKUS_RADNY
    if isinstance(value, int):
        return POKUS_OPRAVNY if value >= 2 else POKUS_RADNY
    return POKUS_RADNY


def _round_points(value: float) -> float:
    return round(float(value), POINTS_DECIMALS)


@dataclass
class BonusBreakdown:
    test1: float = 0.0
    test2: float = 0.0
    projekt: float = 0.0

    def total(self) -> float:
        return _round_points(self.test1 + self.test2 + self.projekt)

    def normalized(self) -> BonusBreakdown:
        return BonusBreakdown(
            test1=_round_points(self.test1),
            test2=_round_points(self.test2),
            projekt=_round_points(self.projekt),
        )


@dataclass
class Student:
    os_cislo: str
    jmeno: str
    prijmeni: str
    titul_pred: str = ""
    titul_za: str = ""
    username: str = ""
    email: str = ""
    vizualni_id: str = ""

    test1: float = 0.0
    test2: float = 0.0
    projekt: float = 0.0
    bonus: BonusBreakdown = field(default_factory=BonusBreakdown)

    dochazka: bool = False
    datum_odevzdani: date | None = None
    pokus: str = POKUS_RADNY  # viz POKUS_VALUES
    ma_istqb_ctfl: bool = False  # certifikát ISTQB CTFL → automaticky A
    komentar: str = ""

    # Volitelná uložená známka (např. při importu historických dat).
    # Pokud None, počítá se z bodů.
    znamka_override: str | None = None

    def display_name(self) -> str:
        parts = [self.titul_pred, self.jmeno, self.prijmeni, self.titul_za]
        return " ".join(p for p in parts if p).strip()

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.datum_odevzdani is not None:
            d["datum_odevzdani"] = self.datum_odevzdani.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Student:
        bonus_data = data.get("bonus") or {}
        datum_str = data.get("datum_odevzdani")
        return cls(
            os_cislo=str(data.get("os_cislo", "")),
            jmeno=str(data.get("jmeno", "")),
            prijmeni=str(data.get("prijmeni", "")),
            titul_pred=str(data.get("titul_pred", "")),
            titul_za=str(data.get("titul_za", "")),
            username=str(data.get("username", "")),
            email=str(data.get("email", "")),
            vizualni_id=str(data.get("vizualni_id", "")),
            test1=_round_points(data.get("test1", 0.0)),
            test2=_round_points(data.get("test2", 0.0)),
            projekt=_round_points(data.get("projekt", 0.0)),
            bonus=BonusBreakdown(
                test1=_round_points(bonus_data.get("test1", 0.0)),
                test2=_round_points(bonus_data.get("test2", 0.0)),
                projekt=_round_points(bonus_data.get("projekt", 0.0)),
            ),
            dochazka=bool(data.get("dochazka", False)),
            datum_odevzdani=date.fromisoformat(datum_str) if datum_str else None,
            pokus=_normalize_pokus(data.get("pokus", POKUS_RADNY)),
            ma_istqb_ctfl=bool(data.get("ma_istqb_ctfl", False)),
            komentar=str(data.get("komentar", "") or ""),
            znamka_override=(data.get("znamka_override") or None),
        )


@dataclass
class YearDeadlines:
    """Termíny odevzdání projektu pro daný akademický rok."""

    first: date | None = None   # řádný termín
    second: date | None = None  # opravný termín

    def to_dict(self) -> dict:
        return {
            "first": self.first.isoformat() if self.first else None,
            "second": self.second.isoformat() if self.second else None,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> YearDeadlines:
        if not data:
            return cls()
        return cls(
            first=date.fromisoformat(data["first"]) if data.get("first") else None,
            second=date.fromisoformat(data["second"]) if data.get("second") else None,
        )


@dataclass
class YearData:
    year: int
    deadlines: YearDeadlines = field(default_factory=YearDeadlines)
    students: list[Student] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "deadlines": self.deadlines.to_dict(),
            "students": [s.to_dict() for s in self.students],
        }

    @classmethod
    def from_dict(cls, data: dict) -> YearData:
        return cls(
            year=int(data["year"]),
            deadlines=YearDeadlines.from_dict(data.get("deadlines")),
            students=[Student.from_dict(s) for s in data.get("students", [])],
        )
