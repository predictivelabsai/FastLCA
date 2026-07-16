# FastLCA — User Guide

FastLCA computes a building's **whole-life carbon footprint** (EN 15978) from a bill of quantities.

## 1. Define the building

At the top-left, set:

- **Building type** — drives operational defaults (energy, water, demolition intensity).
- **Gross floor area (m²)** — used for operational and demolition modules and for intensity metrics.
- **Year of completion** and **assessment period** (default 50 years) — the study period for the
  operational modules (B6/B7).

The results recompute the moment you change any field.

## 2. Add materials (the bill of quantities)

At the top-right, pick a material, enter a **quantity in its own unit** (m³, m² or pcs), and
optionally the number of **mid-life replacements** (module B4). Click **+ Add material**. Each line
appears in the *Materials* table with its computed mass and product-stage (A1-A3) carbon; use **✕**
to remove a line.

Material carbon factors (GWP total/fossil/biogenic, kgCO₂e/kg), densities and wastage percentages
come from `data/materials.json` — seeded from the Lithuanian Building Data Bank (PDB / SGC IS)
prototype. Edit that file to add materials or plug in project-specific EPD values.

## 3. Read the results

- **Stat cards** — total carbon (excl. module D), embodied vs. operational split, and intensity
  per m².
- **Bar chart** — carbon by EN 15978 module (A1-A3 … D1).
- **Breakdown table** — tonnes CO₂e and share of total per module, plus the total *including*
  module D (reuse/recycling benefits, shown as a credit).

## 4. Export

**⬇ Export to XLSX** downloads a spreadsheet with a RESULTS sheet (per-module totals + shares +
intensities) and a MATERIALS sheet (mass and A1-A3 per line) — the format the SGC IS tender itself
requires for list exports.

## Modules covered

| Module | Meaning | Driver |
|--------|---------|--------|
| A1-A3 | Product stage | materials × GWP |
| A4 | Transport to site | mass × distance × EF |
| A5 | Construction site | wastage + site energy |
| B4 | Replacement | product-stage × replacements |
| B6 | Operational energy | area × kWh/m² × grid EF × years |
| B7 | Operational water | area × m³/m² × EF × years |
| C1 | Demolition | area × intensity |
| C2 | Waste transport | mass × distance × EF |
| C3 | Waste processing | mass × reuse share × EF |
| C4 | Final disposal | mass × disposal share × EF |
| D1 | Benefits beyond boundary | substitution credit (negative) |

> Factors other than the material GWP values are transparent, editable defaults for demonstration.
> For a certified assessment, replace them with national-methodology and project EPD values in
> `data/*.json` — no code change required.
