#!/usr/bin/env python3
"""
Generate ArchiMate-style stencil SVGs aligned with fideocam/EAinPowerpoint (Archimate_blank.pptx),
then export to .emf via Inkscape CLI.

Each graphic includes four connection-target markers (left, right, top, bottom) as visible
guides for where to attach connectors in PowerPoint.

Run: python3 generate_icons.py
Requires: inkscape on PATH.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from connection_anchors import connection_anchor_fragment

W, H = 200, 120
STROKE = "#2f2f2f"
STROKE_W = 1.8

# Approximate ArchiMate / deck tints
COL = {
    "business": "#fff9c4",
    "application": "#bbdefb",
    "technology": "#c8e6c9",
    "motivation": "#ffe0b2",
    "neutral": "#eceff1",
    "relation": "#ffffff",
}


def svg_wrap(inner: str) -> str:
    anchors = connection_anchor_fragment(W, H)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
        f'<rect width="100%" height="100%" fill="#fafafa"/>'
        f"{inner}"
        f"{anchors}"
        f"</svg>"
    )


def label(txt: str, y: float = 108) -> str:
    esc = (
        txt.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return (
        f'<text x="{W / 2}" y="{y}" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" '
        f'font-size="9" fill="#333">{esc}</text>'
    )


def rnd_rect(x: float, y: float, rw: float, rh: float, fill: str, rx: float = 10) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{rw}" height="{rh}" rx="{rx}" ry="{rx}" '
        f'fill="{fill}" stroke="{STROKE}" stroke-width="{STROKE_W}"/>'
    )


def ellipse(cx: float, cy: float, rx: float, ry: float, fill: str) -> str:
    return (
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
        f'fill="{fill}" stroke="{STROKE}" stroke-width="{STROKE_W}"/>'
    )


def polygon(points: str, fill: str) -> str:
    return f'<polygon points="{points}" fill="{fill}" stroke="{STROKE}" stroke-width="{STROKE_W}"/>'


def line(x1: float, y1: float, x2: float, y2: float, dashed: bool = False) -> str:
    dash = 'stroke-dasharray="6 4"' if dashed else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{STROKE}" '
        f'stroke-width="{STROKE_W}" {dash}/>'
    )


def arrow_head(x: float, y: float, deg: float = 0) -> str:
    # Open arrow
    return (
        f'<g transform="translate({x},{y}) rotate({deg})">'
        f'<path d="M -8 -5 L 0 0 L -8 5" fill="none" stroke="{STROKE}" stroke-width="{STROKE_W}"/>'
        f"</g>"
    )


def icons() -> list[tuple[str, str]]:
    """(filename_stem, svg_inner_body including optional label)."""
    o: list[tuple[str, str]] = []

    # --- Business ---
    o.append(
        (
            "Business_Actor",
            ellipse(100, 52, 38, 22, COL["business"]) + label("Business Actor"),
        )
    )
    o.append(
        (
            "Business_Role",
            rnd_rect(38, 28, 124, 48, COL["business"])
            + label("Business Role"),
        )
    )
    o.append(
        (
            "Business_Service",
            rnd_rect(38, 28, 124, 48, COL["business"], rx=6)
            + label("Business Service"),
        )
    )
    o.append(
        (
            "Business_Process",
            polygon("100,28 162,76 100,100 38,76", COL["business"]) + label("Business Process"),
        )
    )
    o.append(
        (
            "Business_Object",
            rnd_rect(38, 32, 124, 44, COL["business"], rx=4)
            + label("Business Object"),
        )
    )
    o.append(
        (
            "Work_Package",
            rnd_rect(48, 30, 104, 50, COL["business"], rx=4)
            + label("Work Package"),
        )
    )

    # --- Application ---
    o.append(
        (
            "Application_Function",
            rnd_rect(38, 28, 124, 48, COL["application"], rx=14)
            + label("Application Function"),
        )
    )
    o.append(
        (
            "Application_Component",
            rnd_rect(56, 30, 108, 46, COL["application"], rx=3)
            + (
                f'<rect x="44" y="32" width="14" height="12" fill="#90caf9" stroke="{STROKE}" stroke-width="1.2"/>'
                f'<rect x="44" y="48" width="14" height="12" fill="#90caf9" stroke="{STROKE}" stroke-width="1.2"/>'
            )
            + label("Application Component"),
        )
    )

    o.append(
        (
            "Application_Service",
            rnd_rect(38, 28, 124, 48, COL["application"], rx=6) + label("Application Service"),
        )
    )
    o.append(
        (
            "Application_Process",
            polygon("100,28 162,76 100,100 38,76", COL["application"]) + label("Application Process"),
        )
    )
    o.append(
        (
            "Application_Interface",
            ellipse(100, 54, 52, 18, COL["application"]) + label("Application Interface"),
        )
    )
    o.append(
        (
            "Data_Object",
            rnd_rect(52, 34, 96, 40, COL["application"], rx=22) + label("Data Object"),
        )
    )

    # --- Technology ---
    o.append(
        (
            "Technology_Node",
            rnd_rect(40, 26, 120, 52, COL["technology"], rx=4)
            + f'<rect x="52" y="38" width="96" height="28" fill="#a5d6a7" stroke="{STROKE}" stroke-width="1.2" rx="2"/>'
            + label("Node"),
        )
    )
    o.append(
        (
            "Technology_Interface",
            ellipse(100, 54, 52, 18, COL["technology"]) + label("Technology Interface"),
        )
    )
    o.append(
        (
            "Technology",
            rnd_rect(38, 28, 124, 48, COL["technology"], rx=8) + label("Technology"),
        )
    )
    o.append(
        (
            "Location",
            rnd_rect(38, 28, 124, 48, COL["neutral"], rx=6)
            + f'<circle cx="100" cy="52" r="14" fill="none" stroke="{STROKE}" stroke-width="{STROKE_W}"/>'
            + f'<circle cx="100" cy="52" r="4" fill="{STROKE}"/>'
            + label("Location"),
        )
    )

    # --- Motivation / strategic in deck ---
    o.append(
        (
            "Constraint",
            rnd_rect(38, 28, 124, 48, COL["motivation"], rx=2)
            + line(48, 38, 152, 90, dashed=True)
            + label("Constraint"),
        )
    )
    o.append(
        (
            "Requirement",
            rnd_rect(38, 28, 124, 48, COL["motivation"], rx=2) + label("Requirement"),
        )
    )
    o.append(
        (
            "Gap",
            polygon("100,30 160,100 40,100", COL["motivation"]) + label("Gap"),
        )
    )
    o.append(
        (
            "Goal",
            polygon("100,28 155,76 100,100 45,76", COL["motivation"]) + label("Goal"),
        )
    )
    o.append(
        (
            "Representation",
            rnd_rect(48, 30, 104, 50, COL["neutral"], rx=2)
            + f'<path d="M 58 42 L 142 42 M 58 54 L 130 54 M 58 66 L 138 66" stroke="{STROKE}" stroke-width="1.4"/>'
            + label("Representation"),
        )
    )

    # --- Relationships (compact mini-diagrams) ---
    def rel(name: str, mid: str) -> tuple[str, str]:
        body = (
            rnd_rect(10, 40, 36, 36, COL["business"], rx=4)
            + rnd_rect(154, 40, 36, 36, COL["application"], rx=4)
            + mid
            + label(name.replace("_", " "), y=106)
        )
        return (name, body)

    o.append(
        rel(
            "Rel_flow",
            line(46, 58, 154, 58)
            + arrow_head(154, 58, 0),
        )
    )
    o.append(
        rel(
            "Rel_serving",
            line(46, 58, 154, 58)
            + f'<polygon points="154,58 138,50 138,66" fill="{STROKE}"/>',
        )
    )
    o.append(
        rel(
            "Rel_association",
            line(46, 58, 154, 58, dashed=True),
        )
    )
    o.append(
        rel(
            "Rel_access",
            line(46, 58, 154, 58, dashed=False)
            + f'<text x="100" y="52" text-anchor="middle" font-size="14" fill="{STROKE}">A</text>',
        )
    )
    o.append(
        rel(
            "Rel_assignment",
            line(46, 58, 154, 58)
            + f'<polygon points="150,58 138,52 138,64" fill="{STROKE}"/>'
            + f'<line x1="130" y1="58" x2="138" y2="58" stroke="{STROKE}" stroke-width="{STROKE_W}"/>',
        )
    )
    o.append(
        rel(
            "Rel_realization",
            line(46, 58, 154, 58, dashed=True)
            + f'<polygon points="154,58 136,50 136,66" fill="none" stroke="{STROKE}" stroke-width="{STROKE_W}"/>',
        )
    )
    o.append(
        rel(
            "Rel_specialization",
            line(46, 58, 154, 58)
            + f'<polygon points="154,58 138,50 138,66" fill="none" stroke="{STROKE}" stroke-width="{STROKE_W}"/>',
        )
    )
    o.append(
        rel(
            "Rel_aggregation",
            line(46, 58, 120, 58)
            + line(120, 58, 154, 58)
            + f'<circle cx="120" cy="58" r="5" fill="none" stroke="{STROKE}" stroke-width="{STROKE_W}"/>',
        )
    )

    return o


def main() -> int:
    root = Path(__file__).resolve().parent
    svg_dir = root / "svg"
    emf_dir = root / "emf"
    svg_dir.mkdir(exist_ok=True)
    emf_dir.mkdir(exist_ok=True)

    items = icons()
    for stem, inner in items:
        svg_path = svg_dir / f"{stem}.svg"
        svg_path.write_text(svg_wrap(inner), encoding="utf-8")

    # Batch export
    for stem, _ in items:
        svg_path = svg_dir / f"{stem}.svg"
        emf_path = emf_dir / f"{stem}.emf"
        cmd = [
            "inkscape",
            str(svg_path),
            "--export-type=emf",
            f"--export-filename={emf_path}",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr or r.stdout, file=sys.stderr)
            return r.returncode

    print(f"Wrote {len(list(svg_dir.glob('*.svg')))} SVG and EMF files under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
