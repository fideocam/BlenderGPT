"""Build a compact text digest of the scene and current selection for the LLM."""

from __future__ import annotations

import bpy
from mathutils import Vector


def world_bbox_stats(obj: bpy.types.Object) -> dict[str, tuple[float, float, float]]:
    """World-space axis-aligned bounds from object bound_box."""
    mw = obj.matrix_world
    corners = [mw @ Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    mn = (min(xs), min(ys), min(zs))
    mx = (max(xs), max(ys), max(zs))
    center = ((mn[0] + mx[0]) * 0.5, (mn[1] + mx[1]) * 0.5, (mn[2] + mx[2]) * 0.5)
    dims = (mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2])
    return {"center": center, "dimensions": dims, "min": mn, "max": mx}


def _object_lines(obj: bpy.types.Object, depth: int = 0) -> list[str]:
    indent = "  " * depth
    loc = obj.location
    lines = [
        f"{indent}- object: name={obj.name!r} type={obj.type} "
        f"visible={not obj.hide_viewport} hide_render={obj.hide_render}"
    ]
    lines.append(
        f"{indent}  transform: location=[{loc.x:.6f},{loc.y:.6f},{loc.z:.6f}] "
        f"rotation_euler=[{obj.rotation_euler.x:.6f},{obj.rotation_euler.y:.6f},{obj.rotation_euler.z:.6f}] "
        f"scale=[{obj.scale.x:.6f},{obj.scale.y:.6f},{obj.scale.z:.6f}]"
    )
    if obj.type == "MESH" and obj.data:
        mesh = obj.data
        lines.append(
            f"{indent}  mesh: verts={len(mesh.vertices)} faces={len(mesh.polygons)} "
            f"materials={len(mesh.materials)}"
        )
        bb = world_bbox_stats(obj)
        c = bb["center"]
        d = bb["dimensions"]
        lines.append(
            f"{indent}  world_bbox_center=[{c[0]:.6f},{c[1]:.6f},{c[2]:.6f}] "
            f"world_dimensions=[{d[0]:.6f},{d[1]:.6f},{d[2]:.6f}]"
        )
    if obj.modifiers:
        names = ", ".join(m.name + ":" + m.type for m in obj.modifiers[:8])
        if len(obj.modifiers) > 8:
            names += ", ..."
        lines.append(f"{indent}  modifiers: {names}")
    if obj.material_slots:
        mats = []
        for slot in obj.material_slots[:6]:
            m = slot.material
            mats.append(m.name if m else "(empty)")
        lines.append(f"{indent}  materials: {', '.join(mats)}")
    if obj.children:
        lines.append(f"{indent}  children:")
        for ch in obj.children:
            lines.extend(_object_lines(ch, depth + 2))
    return lines


def build_scene_digest(context: bpy.types.Context, max_chars: int) -> str:
    scene = context.scene
    lines: list[str] = []
    lines.append(f"Scene: {scene.name}")
    lines.append(f"Frame: {scene.frame_current}  Render engine: {scene.render.engine}")

    world = scene.world
    if world:
        lines.append(f"World: {world.name}")

    lines.append("Collections and root objects:")

    def walk_collections(col: bpy.types.Collection, depth: int = 0) -> None:
        ind = "  " * (1 + depth)
        lines.append(f"{ind}collection: {col.name}")
        for child in col.children:
            walk_collections(child, depth + 1)

    walk_collections(scene.collection)
    for obj in scene.objects:
        if obj.parent is None:
            lines.extend(_object_lines(obj, 1))

    us = scene.unit_settings
    lines.append(
        f"unit_settings: system={us.system} length_unit={us.length_unit} "
        f"scale_length={us.scale_length}"
    )

    lines.append("")
    lines.append(
        "Selection (use for 'selected', 'this', 'it'; active_object for singular edits):"
    )
    lines.append(
        "Use world_bbox_center and world_dimensions from the digest for hole/cut placement. "
        "Do not guess [0,0,0]. Omit center in create_bolt_hole to auto-place at target bbox center."
    )
    sel = list(context.view_layer.objects.selected)
    if not sel:
        lines.append("  selected_objects: (none)")
    else:
        lines.append("  selected_objects: " + ", ".join(obj.name for obj in sel))
        for obj in sel:
            lines.extend(_object_lines(obj, 1))
    active = context.view_layer.objects.active
    if active:
        lines.append(f"  active_object: {active.name!r}")
    elif len(sel) == 1:
        lines.append(f"  active_object: {sel[0].name!r}  (only selection)")

    text = "\n".join(lines)
    if len(text) > max_chars:
        head = max_chars // 2
        tail = max_chars - head - 80
        text = (
            text[:head]
            + "\n\n... [truncated middle] ...\n\n"
            + text[-tail:]
        )
    return text
