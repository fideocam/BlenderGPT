#!/usr/bin/env python3
"""
Canonical ArchiMate 3.x relationship connectors as SVG → EMF (Inkscape).

Relationship *geometry* follows the usual ArchiMate textbook / tool conventions
(solid / dashed / dotted lines, diamond, filled and open arrowheads, etc.). The
Open Group ArchiMate specification does not fix pixel line weights; strokes here
are deliberately **thick** for legibility on slides.

Run: python3 generate_archimate_relations.py
Requires: inkscape on PATH.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

W, H = 280, 72
STROKE = "#1a1a1a"
SW = 6.75
SW_DASH = 6.75
DOT = "0 6"


def svg_doc(body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
        f'<rect width="100%" height="100%" fill="#ffffff"/>'
        f"{body}</svg>"
    )


def relations() -> list[tuple[str, str]]:
    """(stem, inner SVG including defs if needed)."""
    cy = H / 2
    x0, x1 = 56.0, W - 24.0

    defs = """
  <defs>
    <marker id="arrowFilled" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L10,5 L0,10 z" fill="#1a1a1a" stroke="none"/>
    </marker>
    <marker id="arrowOpen" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L12,6 L0,12" fill="none" stroke="#1a1a1a" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
    </marker>
    <marker id="arrowHollow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L12,6 L0,12 z" fill="none" stroke="#1a1a1a" stroke-width="5" stroke-linejoin="round"/>
    </marker>
  </defs>
"""

    # Composition: filled diamond at start
    comp_diamond = (
        f'<path d="M {x0 - 26:.1f} {cy:.1f} L {x0 - 13:.1f} {cy - 10:.1f} L {x0:.1f} {cy:.1f} '
        f'L {x0 - 13:.1f} {cy + 10:.1f} Z" fill="{STROKE}" stroke="none"/>'
        f'<line x1="{x0:.1f}" y1="{cy:.1f}" x2="{x1:.1f}" y2="{cy:.1f}" stroke="{STROKE}" stroke-width="{SW}"/>'
    )

    # Aggregation: hollow diamond
    agg_diamond = (
        f'<path d="M {x0 - 26:.1f} {cy:.1f} L {x0 - 13:.1f} {cy - 10:.1f} L {x0:.1f} {cy:.1f} '
        f'L {x0 - 13:.1f} {cy + 10:.1f} Z" fill="none" stroke="{STROKE}" stroke-width="{SW}"/>'
        f'<line x1="{x0:.1f}" y1="{cy:.1f}" x2="{x1:.1f}" y2="{cy:.1f}" stroke="{STROKE}" stroke-width="{SW}"/>'
    )

    def line(
        dash: str | None,
        marker_end: str | None,
        marker_start: str | None = None,
        x_start: float = 36.0,
    ) -> str:
        dashattr = f'stroke-dasharray="{dash}"' if dash else ""
        me = f'marker-end="url(#{marker_end})"' if marker_end else ""
        ms = f'marker-start="url(#{marker_start})"' if marker_start else ""
        return (
            f'<line x1="{x_start}" y1="{cy}" x2="{x1}" y2="{cy}" stroke="{STROKE}" '
            f'stroke-width="{SW_DASH if dash else SW}" {dashattr} {me} {ms}/>'
        )

    items: list[tuple[str, str]] = []

    items.append(("Archimate_Rel_Composition", defs + comp_diamond))
    items.append(("Archimate_Rel_Aggregation", defs + agg_diamond))
    items.append(("Archimate_Rel_Assignment", defs + line(None, "arrowFilled", x_start=40)))
    items.append(("Archimate_Rel_Realization", defs + line("8 6", "arrowHollow", x_start=40)))
    items.append(("Archimate_Rel_Association", defs + line(DOT, None, x_start=40)))
    items.append(("Archimate_Rel_Association_Directed", defs + line(DOT, "arrowOpen", x_start=40)))
    items.append(("Archimate_Rel_Serving", defs + line(None, "arrowFilled", x_start=40)))
    items.append(("Archimate_Rel_Access", defs + line(DOT, "arrowOpen", x_start=40)))
    items.append(("Archimate_Rel_Influence", defs + line("10 6", "arrowOpen", x_start=40)))
    # Same arrowhead style as serving; thicker stroke is a common way to tell them apart in legends.
    trig = (
        defs
        + f'<line x1="40" y1="{cy}" x2="{x1}" y2="{cy}" stroke="{STROKE}" stroke-width="8.5" '
        + 'marker-end="url(#arrowFilled)"/>'
    )
    items.append(("Archimate_Rel_Triggering", trig))
    items.append(("Archimate_Rel_Flow", defs + line(None, "arrowOpen", x_start=40)))

    # Specialization (generalization): hollow triangle at source (left), line to right
    spec = (
        defs
        + f'<path d="M 38 {cy - 14:.1f} L 38 {cy + 14:.1f} L 62 {cy:.1f} Z" fill="none" stroke="{STROKE}" stroke-width="{SW}" stroke-linejoin="round"/>'
        + f'<line x1="62" y1="{cy:.1f}" x2="{x1:.1f}" y2="{cy:.1f}" stroke="{STROKE}" stroke-width="{SW}"/>'
    )
    items.append(("Archimate_Rel_Specialization", spec))

    # Optional: junction (small filled circle on relationship — not an arrow, but useful in PPT)
    junction = (
        defs
        + f'<circle cx="{W / 2:.1f}" cy="{cy:.1f}" r="8" fill="{STROKE}"/>'
    )
    items.append(("Archimate_Rel_Junction", junction))

    return items


def main() -> int:
    root = Path(__file__).resolve().parent / "archimate_relations_emf"
    svg_dir = root / "svg"
    emf_dir = root / "emf"
    svg_dir.mkdir(parents=True, exist_ok=True)
    emf_dir.mkdir(parents=True, exist_ok=True)

    rels = relations()
    for stem, inner in rels:
        (svg_dir / f"{stem}.svg").write_text(svg_doc(inner), encoding="utf-8")

    for stem, _ in rels:
        svg_path = svg_dir / f"{stem}.svg"
        emf_path = emf_dir / f"{stem}.emf"
        r = subprocess.run(
            ["inkscape", str(svg_path), "--export-type=emf", f"--export-filename={emf_path}"],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            print(r.stderr or r.stdout, file=sys.stderr)
            return r.returncode

    print(f"Wrote {len(rels)} relation SVG/EMF under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
