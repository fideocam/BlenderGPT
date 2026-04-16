#!/usr/bin/env python3
"""
Export every non-placeholder shape from Archimate_blank.pptx using Microsoft PowerPoint
(save as picture → PDF), then convert to EMF with Inkscape. Four connection-target
markers (left, right, top, bottom) are injected into the intermediate SVG so each
EMF carries the same visual anchor guides as the hand-built stencil set.

Requires: macOS, Microsoft PowerPoint, Inkscape on PATH.

PowerPoint writes to ~/Library/Containers/com.microsoft.Powerpoint/Data/ when using a
short filename (see Microsoft sandbox rules).
"""
from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from connection_anchors import connection_anchor_fragment


def localname(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def sp_tree_children(root: ET.Element) -> list[ET.Element]:
    for sp in root.iter():
        if localname(sp.tag) == "spTree":
            return list(sp)
    raise ValueError("spTree not found")


def drawable_elements(tree_children: list[ET.Element]) -> list[ET.Element]:
    out: list[ET.Element] = []
    for ch in tree_children:
        if localname(ch.tag) in ("nvGrpSpPr", "grpSpPr"):
            continue
        out.append(ch)
    return out


def _has_placeholder(el: ET.Element) -> bool:
    for e in el.iter():
        if localname(e.tag) == "ph":
            return True
    return False


def _parse_viewbox_wh(svg_text: str) -> tuple[float, float]:
    m = re.search(r'viewBox\s*=\s*"([^"]+)"', svg_text)
    if not m:
        raise ValueError("viewBox not found in SVG")
    parts = [p for p in re.split(r"[\s,]+", m.group(1).strip()) if p]
    vals = [float(p) for p in parts]
    if len(vals) == 4:
        return vals[2], vals[3]
    if len(vals) == 2:
        return vals[0], vals[1]
    raise ValueError(f"Unexpected viewBox values: {vals}")


def pdf_to_emf_with_connection_anchors(pdf_path: Path, emf_path: Path) -> int:
    """PDF → SVG (Inkscape), inject four side anchors, SVG → EMF."""
    tmp_svg = pdf_path.with_suffix(".anchors.svg")
    r1 = subprocess.run(
        ["inkscape", str(pdf_path), "--export-type=svg", "-o", str(tmp_svg)],
        capture_output=True,
        text=True,
    )
    if r1.returncode != 0:
        print(r1.stderr or r1.stdout, file=sys.stderr)
        return r1.returncode
    try:
        svg = tmp_svg.read_text(encoding="utf-8")
        if 'id="connection-anchors"' not in svg:
            vw, vh = _parse_viewbox_wh(svg)
            frag = connection_anchor_fragment(vw, vh)
            if "</svg>" not in svg:
                raise ValueError("closing </svg> missing")
            svg = svg.replace("</svg>", frag + "\n</svg>", 1)
            tmp_svg.write_text(svg, encoding="utf-8")
        r2 = subprocess.run(
            [
                "inkscape",
                str(tmp_svg),
                "--export-type=emf",
                f"--export-filename={emf_path}",
            ],
            capture_output=True,
            text=True,
        )
        if r2.returncode != 0:
            print(r2.stderr or r2.stdout, file=sys.stderr)
            return r2.returncode
    finally:
        try:
            tmp_svg.unlink(missing_ok=True)
        except OSError:
            pass
    return 0


def cnvpr_name(el: ET.Element) -> str:
    for e in el.iter():
        if localname(e.tag) == "cNvPr":
            return e.get("name", "") or ""
    return ""


def merged_text(el: ET.Element) -> str:
    parts: list[str] = []
    for e in el.iter():
        if localname(e.tag) == "t" and e.text:
            parts.append(e.text)
    s = html.unescape("".join(parts))
    s = re.sub(r"\s+", " ", s.replace("\u00a0", " ")).strip()
    return s


def slug_label(text: str, fallback: str) -> str:
    base = text if text else fallback
    base = re.sub(r"[^\w\s-]", "", base, flags=re.UNICODE)
    base = re.sub(r"[-\s]+", "_", base).strip("_")
    return (base[:80] if base else "unnamed").lower()


def build_label_for_drawable(el: ET.Element) -> str:
    t = merged_text(el)
    if t:
        return t
    nm = cnvpr_name(el)
    nm = re.sub(r"^Group\s+\d+$", "", nm).strip()
    if nm:
        return nm
    return ""


def _applescript_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def applescript_export(pptx_posix: str, last_slide: int) -> str:
    # Sequential n per slide so filenames match filtered (non-placeholder) drawables.
    lines = [
        'tell application "Microsoft PowerPoint"',
        f'  set fp to POSIX file "{_applescript_str(pptx_posix)}"',
        "  open fp",
        "  delay 3",
        "  set pres to active presentation",
        f"  repeat with snum from 1 to {last_slide}",
        "    set sl to slide snum of pres",
        "    set exportNum to 0",
        "    repeat with i from 1 to count of shapes of sl",
        "      set sh to shape i of sl",
        "      if (shape type of sh) is not shape type place holder then",
        "        set exportNum to exportNum + 1",
        '        set fn to "ea_s" & snum & "_n" & exportNum & ".pdf"',
        "        save as picture sh file name fn picture type save as PDF file",
        "      end if",
        "    end repeat",
        "  end repeat",
        "  close pres saving no",
        "end tell",
    ]
    return "\n".join(lines)


def main() -> int:
    pptx = Path(
        os.environ.get(
            "EA_PPTX",
            "/tmp/EAinPowerpoint/Archimate_blank.pptx",
        )
    ).resolve()
    if not pptx.is_file():
        print(f"Missing PPTX: {pptx}", file=sys.stderr)
        return 1

    out_root = Path(__file__).resolve().parent / "exact_from_powerpoint"
    pdf_stage = out_root / "_pdf_stage"
    emf_dir = out_root / "emf"
    pdf_stage.mkdir(parents=True, exist_ok=True)
    emf_dir.mkdir(parents=True, exist_ok=True)

    container = Path.home() / "Library/Containers/com.microsoft.Powerpoint/Data"
    if not container.is_dir():
        print(f"Expected PowerPoint container: {container}", file=sys.stderr)
        return 1

    # Remove stale exports from prior runs
    for p in container.glob("ea_s*_n*.pdf"):
        try:
            p.unlink()
        except OSError:
            pass

    last_slide = 10
    script = applescript_export(str(pptx), last_slide)
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr or r.stdout, file=sys.stderr)
        return r.returncode

    used: dict[str, int] = {}
    converted = 0

    with zipfile.ZipFile(pptx, "r") as zf:
        for snum in range(1, last_slide + 1):
            data = zf.read(f"ppt/slides/slide{snum}.xml")
            root = ET.fromstring(data)

            drawables = [
                el
                for el in drawable_elements(sp_tree_children(root))
                if not _has_placeholder(el)
            ]
            for i in range(1, len(drawables) + 1):
                src = container / f"ea_s{snum}_n{i}.pdf"
                if not src.is_file():
                    print(f"Missing export: {src.name}", file=sys.stderr)
                    continue
                el = drawables[i - 1]
                raw_label = build_label_for_drawable(el)
                slug = slug_label(raw_label, f"shape_{cnvpr_name(el)}")
                key = f"S{snum:02d}_{slug}"
                used[key] = used.get(key, 0) + 1
                if used[key] > 1:
                    stem = f"{key}_{used[key]}"
                else:
                    stem = key
                dst_pdf = pdf_stage / f"{stem}.pdf"
                shutil.copy2(src, dst_pdf)
                dst_emf = emf_dir / f"{stem}.emf"
                ir = pdf_to_emf_with_connection_anchors(dst_pdf, dst_emf)
                if ir != 0:
                    return ir
                converted += 1

    print(f"Wrote {converted} PDF + EMF pairs under {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
