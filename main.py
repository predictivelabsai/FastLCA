"""FastLCA — open-source whole-building life-cycle carbon calculator (EN 15978).

A single-file FastHTML app: define a building, add materials, and get a live carbon breakdown
by life-cycle module (A1-A3 … D), with an XLSX export. An open, inspectable alternative to the
closed .xlsm prototype used by Lithuania's Building Data Bank (PDB / SGC IS).

    pip install -r requirements.txt
    python main.py         # → http://localhost:5001
"""
from __future__ import annotations

from fasthtml.common import (
    H1, H2, H3, A, Button, Div, Form, Input, Li, Option, P, Response, Script, Select,
    Span, Style, Table, Td, Th, Tr, Titled, Ul, fast_app, serve,
)

from lca.model import BUILDING_TYPES, DEFAULTS, MATERIALS, MODULES, Building, MaterialLine, assess

STYLE = """
:root { --brand:#1d4ed8; }
main.container { max-width: 1000px; }
.lead { color:#475569; }
.card { border:1px solid #e2e8f0; border-radius:10px; padding:14px 16px; margin:10px 0;
        background:var(--card-background-color, #fff); }
.chip { display:inline-block; background:#eff6ff; color:var(--brand); font-weight:700;
        font-size:.72rem; padding:2px 8px; border-radius:20px; letter-spacing:.3px; }
.muted { color:#64748b; font-size:.88rem; }
.stats { grid-template-columns: repeat(4, 1fr); gap:10px; }
.stat { text-align:center; border:1px solid #e2e8f0; border-radius:10px; padding:12px 6px;
        background:linear-gradient(180deg,#f8fafc,#fff); }
.stat-value { font-size:1.7rem; font-weight:800; color:var(--brand); line-height:1.1; }
.stat-unit { font-size:.72rem; color:#64748b; }
.stat-label { font-size:.8rem; margin-top:4px; }
table td, table th { padding:6px 8px; }
@media (prefers-color-scheme: dark) {
  .card { background:#0f172a; border-color:#1e293b; }
  .stat { background:#0f172a; border-color:#1e293b; }
  .chip { background:#1e293b; }
}
"""

app, rt = fast_app(
    hdrs=(Script(src="https://cdn.plot.ly/plotly-2.35.2.min.js"), Style(STYLE)),
    pico=True,
)

# ── in-memory session state (single-user demo) ────────────────────────────────────────
STATE: dict = {
    "building_type": BUILDING_TYPES[0]["name"],
    "gross_floor_area": 2000.0,
    "year_completion": 2023,
    "assessment_period": DEFAULTS["assessment_period_years"],
    "lines": [  # a worked example so the page is never empty
        {"name": "Ready-mix concrete, C30/37", "quantity": 900.0, "replacements": 0},
        {"name": "Reinforcement steel", "quantity": 80.0, "replacements": 0},
        {"name": "Structural steel", "quantity": 40.0, "replacements": 0},
        {"name": "Rock wool", "quantity": 350.0, "replacements": 0},
        {"name": "Window, wood-aluminium, triple-glazed", "quantity": 300.0, "replacements": 1},
    ],
}

MODULE_LABEL = dict(MODULES)


def _building() -> Building:
    return Building(
        building_type=STATE["building_type"],
        gross_floor_area=float(STATE["gross_floor_area"]),
        year_completion=int(STATE["year_completion"]),
        assessment_period=int(STATE["assessment_period"]),
        materials=[MaterialLine(l["name"], float(l["quantity"]), int(l.get("replacements", 0)))
                   for l in STATE["lines"]],
    )


# ── UI fragments ───────────────────────────────────────────────────────────────────────
def building_form():
    return Form(
        Div(
            _labelled("Building type", Select(
                *[Option(b["name"], selected=b["name"] == STATE["building_type"]) for b in BUILDING_TYPES],
                name="building_type")),
            _labelled("Gross floor area (m²)", Input(name="gross_floor_area", type="number",
                     value=STATE["gross_floor_area"], step="1", min="1")),
            _labelled("Year of completion", Input(name="year_completion", type="number",
                     value=STATE["year_completion"], step="1")),
            _labelled("Assessment period (yrs)", Input(name="assessment_period", type="number",
                     value=STATE["assessment_period"], step="1", min="1")),
            cls="grid"),
        hx_post="/set-building", hx_target="#results", hx_swap="outerHTML",
        hx_trigger="change", cls="card")


def add_material_form():
    return Form(
        Div(
            _labelled("Material", Select(*[Option(m["name"]) for m in MATERIALS], name="name")),
            _labelled("Quantity", Input(name="quantity", type="number", value="10", step="0.01", min="0")),
            _labelled("Unit", Input(name="unit", value="", readonly=True, id="unit-hint", placeholder="m³ / m² / pcs")),
            _labelled("Replacements", Input(name="replacements", type="number", value="0", step="1", min="0")),
            cls="grid"),
        Button("+ Add material", type="submit"),
        hx_post="/add-material", hx_target="#app", hx_swap="outerHTML", cls="card")


def materials_table():
    if not STATE["lines"]:
        return P("No materials yet — add one above.", cls="muted")
    rows = [Tr(Th("Material"), Th("Qty"), Th("Unit"), Th("Mass (t)"), Th("A1-A3 (tCO₂e)"),
               Th("Repl."), Th(""))]
    b = _building()
    for i, (line, ml) in enumerate(zip(STATE["lines"], b.materials)):
        f = ml.factor
        a1a3 = round(ml.mass_kg * (f.get("gwp_total") or 0) / 1000, 2)
        rows.append(Tr(
            Td(line["name"]), Td(f'{line["quantity"]:g}'), Td(f["unit"]),
            Td(f'{ml.mass_kg/1000:.2f}'), Td(f'{a1a3:.2f}'), Td(str(line.get("replacements", 0))),
            Td(Button("✕", hx_post=f"/del-material/{i}", hx_target="#app", hx_swap="outerHTML",
                      cls="secondary outline", style="padding:2px 10px"))))
    return Table(*rows)


def results_panel():
    r = assess(_building())
    m = r["modules"]
    t = r["totals"]
    total = t["total_excl_d"] or 1

    bars = [Tr(Th("Module"), Th("Stage"), Th("tCO₂e"), Th("Share"))]
    for code, _desc in MODULES:
        v = m[code]
        pct = "" if code == "D1" else f'{v/total*100:.1f}%'
        bars.append(Tr(Td(Span(code, cls="chip")), Td(MODULE_LABEL[code]),
                       Td(f'{v:,.1f}', style="text-align:right"),
                       Td(pct, style="text-align:right;color:#64748b")))

    cards = Div(
        _stat("Total (excl. D)", f'{t["total_excl_d"]:,.0f}', "tCO₂e"),
        _stat("Embodied (A+C)", f'{t["embodied"]:,.0f}', "tCO₂e"),
        _stat("Operational (B6+B7)", f'{t["operational"]:,.0f}', "tCO₂e"),
        _stat("Intensity", f'{t["per_m2"]:,.0f}', "kgCO₂e/m²"),
        cls="grid stats")

    plot_data = {"codes": [c for c, _ in MODULES], "vals": [m[c] for c, _ in MODULES]}
    plot = Script(f"""
      var d=[{{x:{plot_data['codes']!r},y:{plot_data['vals']!r},type:'bar',
              marker:{{color:'#1d4ed8'}}}}];
      Plotly.newPlot('chart', d, {{margin:{{t:10,r:10,b:40,l:50}},
        yaxis:{{title:'tCO₂e'}}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)'}},
        {{displayModeBar:false, responsive:true}});
    """.replace("'", '"'))

    return Div(
        H2("Results — carbon footprint by LCA module"),
        cards,
        Div(id="chart", style="height:320px"),
        plot,
        Table(*bars),
        P(Span(f'Total incl. module D (with reuse/recycling benefits): ', cls="muted"),
          Span(f'{t["total_incl_d"]:,.0f} tCO₂e', style="font-weight:700")),
        A("⬇ Export to XLSX", href="/export.xlsx", role="button", cls="contrast"),
        id="results", cls="card")


def app_body():
    return Div(
        Div(building_form(), add_material_form(), cls="grid"),
        H3("Materials (bill of quantities)"),
        materials_table(),
        results_panel(),
        id="app")


# ── helpers ──────────────────────────────────────────────────────────────────────────
def _labelled(label, ctrl):
    from fasthtml.common import Label
    return Label(label, ctrl)


def _stat(label, value, unit):
    return Div(Div(value, cls="stat-value"), Div(f"{unit}", cls="stat-unit"),
               Div(label, cls="stat-label"), cls="stat")


# ── routes ───────────────────────────────────────────────────────────────────────────
@rt("/")
def index():
    return Titled(
        "FastLCA — building life-cycle carbon",
        Div(P(Span("EN 15978", cls="chip"), " open-source whole-building life-cycle carbon "
              "assessment · an inspectable alternative to a closed .xlsm prototype.", cls="lead")),
        app_body(),
        P(A("What is LCA & how the model works →", href="https://github.com/predictivelabsai/FastHTML-LCA"),
          cls="muted"),
    )


@rt("/set-building")
def set_building(building_type: str, gross_floor_area: float, year_completion: int,
                 assessment_period: int):
    STATE.update(building_type=building_type, gross_floor_area=gross_floor_area,
                 year_completion=year_completion, assessment_period=assessment_period)
    return results_panel()


@rt("/add-material")
def add_material(name: str, quantity: float, replacements: int = 0):
    STATE["lines"].append({"name": name, "quantity": quantity, "replacements": replacements})
    return app_body()


@rt("/del-material/{idx}")
def del_material(idx: int):
    if 0 <= idx < len(STATE["lines"]):
        STATE["lines"].pop(idx)
    return app_body()


@rt("/export.xlsx")
def export_xlsx():
    from lca.export import to_xlsx
    data = to_xlsx(_building())
    return Response(
        data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="fastlca-assessment.xlsx"'})


if __name__ == "__main__":
    serve(port=5001)
