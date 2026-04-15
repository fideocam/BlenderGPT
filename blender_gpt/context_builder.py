"""Build a compact text digest of the scene and current selection for the LLM."""

from __future__ import annotations

import bpy


def _object_lines(obj: bpy.types.Object, depth: int = 0) -> list[str]:
    indent = "  " * depth
    lines = [
        f"{indent}- object: name={obj.name!r} type={obj.type} "
        f"visible={not obj.hide_viewport} hide_render={obj.hide_render}"
    ]
    if obj.type == "MESH" and obj.data:
        mesh = obj.data
        lines.append(
            f"{indent}  mesh: verts={len(mesh.vertices)} faces={len(mesh.polygons)} "
            f"materials={len(mesh.materials)}"
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

    lines.append("")
    lines.append("Selection:")
    sel = list(context.view_layer.objects.selected)
    if not sel:
        lines.append("  (none)")
    else:
        for obj in sel:
            lines.extend(_object_lines(obj, 1))
        if context.view_layer.objects.active:
            a = context.view_layer.objects.active
            lines.append(f"  active_object: {a.name!r}")

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
