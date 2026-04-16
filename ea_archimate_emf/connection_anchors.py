"""
Shared SVG fragment: four connection-target markers (left, right, top, bottom).

Inserted as vector artwork so authors can align connectors to the ring/dot targets.
Inserted pictures in PowerPoint still expose the usual frame glue points on the
bounding box; these targets are explicit visual attachment guides.
"""

from __future__ import annotations


def connection_anchor_fragment(view_w: float, view_h: float, margin: float | None = None) -> str:
    """
    Ring + centre dot at the midpoint of each side of the view box.
    Drawn last in the SVG so targets sit on top of the artwork.
    """
    if margin is None:
        margin = max(4.0, min(view_w, view_h) * 0.055)
    cx = view_w / 2
    cy = view_h / 2
    r_ring = max(3.5, min(view_w, view_h) * 0.035)
    r_dot = r_ring * 0.38
    stroke = "#1565c0"
    sw = 1.35
    fill_dot = "#1565c0"

    def target(px: float, py: float) -> str:
        return (
            f'<g transform="translate({px:.4f},{py:.4f})">'
            f'<circle r="{r_ring:.4f}" fill="none" stroke="{stroke}" stroke-width="{sw}"/>'
            f'<circle r="{r_dot:.4f}" fill="{fill_dot}" stroke="none"/>'
            f"</g>"
        )

    # Midpoints of left, right, top, bottom edges (slightly inset so rings stay inside viewBox)
    left = (margin, cy)
    right = (view_w - margin, cy)
    top = (cx, margin)
    bottom = (cx, view_h - margin)

    parts = [
        '<g id="connection-anchors" class="connection-anchors">',
        "<title>Connection targets: left, right, top, bottom</title>",
        target(*left),
        target(*right),
        target(*top),
        target(*bottom),
        "</g>",
    ]
    return "\n".join(parts)
