"""EN 15978 whole-building life-cycle carbon model.

Pure functions over a small in-memory factor database (data/*.json, seeded from the Lithuanian
Building Data Bank (PDB / SGC IS) prototype calculator). Given a building definition and a list of
material quantities, computes tCO2e per life-cycle module (A1-A3 … D2) and the RESULTS roll-up.

No external services, no macros — the whole model is inspectable Python. That is the point:
an open alternative to a closed .xlsm prototype.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

MATERIALS: list[dict] = json.loads((DATA / "materials.json").read_text())
BUILDING_TYPES: list[dict] = json.loads((DATA / "building_types.json").read_text())
DEFAULTS: dict = json.loads((DATA / "defaults.json").read_text())

MAT_BY_NAME = {m["name"]: m for m in MATERIALS}
BTYPE_BY_NAME = {b["name"]: b for b in BUILDING_TYPES}

# EN 15978 module labels used in the results roll-up.
MODULES = [
    ("A1-A3", "Product stage — raw materials, transport, manufacturing"),
    ("A4", "Transport to construction site"),
    ("A5", "Construction-site emissions (wastage + site energy)"),
    ("B4", "Replacement over the assessment period"),
    ("B6", "Operational energy use"),
    ("B7", "Operational water use"),
    ("C1", "Deconstruction / demolition"),
    ("C2", "Waste transport"),
    ("C3", "Waste processing for reuse / recycling"),
    ("C4", "Final disposal"),
    ("D1", "Reuse, recycling & recovery (benefits/loads beyond boundary)"),
]


@dataclass
class MaterialLine:
    name: str
    quantity: float           # in the material's own unit (m³ / m² / pcs)
    replacements: int = 0     # B4: number of replacements over the assessment period

    @property
    def factor(self) -> dict:
        return MAT_BY_NAME[self.name]

    @property
    def mass_kg(self) -> float:
        return self.quantity * self.factor["mass_per_unit"]


@dataclass
class Building:
    building_type: str
    gross_floor_area: float
    year_completion: int = 2023
    assessment_period: int = 50
    materials: list[MaterialLine] = field(default_factory=list)

    @property
    def btype(self) -> dict:
        return BTYPE_BY_NAME[self.building_type]


def _t(kg: float) -> float:
    """kg CO2e → tonnes CO2e."""
    return kg / 1000.0


def assess(b: Building) -> dict:
    """Return {module: tCO2e}, plus totals and per-material A1-A3 detail."""
    d = DEFAULTS
    area = b.gross_floor_area
    years = b.assessment_period

    a1a3 = a1a3_fossil = a1a3_bio = 0.0
    a4 = a5 = b4 = c2 = c3 = c4 = d1 = 0.0
    detail = []

    for line in b.materials:
        f = line.factor
        mass = line.mass_kg
        gwp = f.get("gwp_total") or 0.0
        gwp_f = f.get("gwp_fossil") or gwp
        gwp_b = f.get("gwp_biogenic") or 0.0
        a1a3_line = _t(mass * gwp)
        a1a3 += a1a3_line
        a1a3_fossil += _t(mass * gwp_f)
        a1a3_bio += _t(mass * gwp_b)

        # A4 transport to site: mass(t) × distance(km) × EF(kgCO2e/tkm) = kgCO2e → tCO2e
        a4 += _t((mass / 1000.0) * d["a4_distance_km"] * d["a4_ef_tkm"])
        # A5 construction: wastage share of A1-A3
        a5 += a1a3_line * (f.get("wastage_pct") or 0.0) / 100.0
        # B4 replacement: each replacement re-incurs the product-stage emission
        b4 += a1a3_line * line.replacements
        # C2 waste transport: mass(t) × distance(km) × EF(kgCO2e/tkm) = kgCO2e → tCO2e
        c2 += _t((mass / 1000.0) * d["c2_waste_distance_km"] * d["c2_ef_tkm"])
        # C3 processing for reuse/recycling
        c3 += _t(mass * d["c3_reuse_share"] * d["c3_ef"])
        # C4 final disposal
        c4 += _t(mass * d["c4_disposal_share"] * d["c4_ef"])
        # D1 benefits beyond boundary: substitution credit (negative)
        d1 += _t(mass * d["d1_reuse_share"] * d["d1_substitution"] * -gwp)

        detail.append({"name": line.name, "mass_t": round(mass / 1000.0, 2),
                       "a1a3_t": round(a1a3_line, 2)})

    # A5 also carries construction-site energy per m²
    a5 += _t(area * d["a5_site_energy_kg_m2"])

    bt = b.btype
    # B6 operational energy over the assessment period
    b6 = _t(area * bt["energy_kwh_m2"] * d["grid_electricity_ef"] * years)
    # B7 operational water
    b7 = _t(area * bt["water_m3_m2"] * bt["water_ef"] * years)
    # C1 demolition (area-based intensity)
    c1 = _t(area * bt["demolition_kg_m2"])

    modules = {
        "A1-A3": a1a3, "A4": a4, "A5": a5, "B4": b4, "B6": b6, "B7": b7,
        "C1": c1, "C2": c2, "C3": c3, "C4": c4, "D1": d1,
    }
    modules = {k: round(v, 2) for k, v in modules.items()}

    embodied = sum(modules[m] for m in ("A1-A3", "A4", "A5", "B4", "C1", "C2", "C3", "C4"))
    operational = modules["B6"] + modules["B7"]
    total_excl_d = embodied + operational
    total_incl_d = total_excl_d + modules["D1"]

    return {
        "modules": modules,
        "detail": sorted(detail, key=lambda x: -x["a1a3_t"]),
        "a1a3_split": {"fossil": round(a1a3_fossil, 2), "biogenic": round(a1a3_bio, 2)},
        "totals": {
            "embodied": round(embodied, 2),
            "operational": round(operational, 2),
            "total_excl_d": round(total_excl_d, 2),
            "total_incl_d": round(total_incl_d, 2),
            "per_m2": round(total_excl_d * 1000 / b.gross_floor_area, 1) if b.gross_floor_area else 0,
            "per_m2_year": round(total_excl_d * 1000 / (b.gross_floor_area * b.assessment_period), 1)
            if b.gross_floor_area and b.assessment_period else 0,
        },
    }
