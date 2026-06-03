"""Parse assistant output and apply a constrained set of bpy scene edits (main thread only)."""

from __future__ import annotations

import json
import math
import os
from json import JSONDecoder
from typing import Any

import bmesh
import uuid

import bpy

from .context_builder import world_bbox_stats


def extract_actions_json(assistant_text: str) -> list[dict[str, Any]]:
    """
    Find the last JSON object in the message that contains an \"actions\" array.
    """
    text = assistant_text.strip()
    markers = ('{"actions"', "{'actions'")
    idx = -1
    for m in markers:
        j = text.rfind(m)
        idx = max(idx, j)
    if idx == -1:
        return []
    snippet = text[idx:]
    try:
        obj, _end = JSONDecoder().raw_decode(snippet)
    except json.JSONDecodeError:
        return []

    actions = obj.get("actions")
    if not isinstance(actions, list):
        return []
    out: list[dict[str, Any]] = []
    for item in actions:
        if isinstance(item, dict) and isinstance(item.get("op"), str):
            out.append(item)
    return out


def _find_object(name: str) -> bpy.types.Object | None:
    return bpy.data.objects.get(name)


def apply_actions(context: bpy.types.Context, actions: list[dict[str, Any]]) -> list[str]:
    """
    Apply actions in order. Returns human-readable log lines.
    Must run on the main thread with a valid context.
    """
    logs: list[str] = []
    if not actions:
        return logs

    bpy.ops.ed.undo_push(message="BlenderGPT apply")

    for raw in actions:
        op = raw.get("op")
        try:
            if op == "create_primitive":
                _apply_create_primitive(context, raw, logs)
            elif op == "delete_objects":
                _apply_delete(context, raw, logs)
            elif op == "set_transform":
                _apply_set_transform(raw, logs)
            elif op == "rename_object":
                _apply_rename(raw, logs)
            elif op == "shade_smooth":
                _apply_shade(raw, logs, smooth=True)
            elif op == "shade_flat":
                _apply_shade(raw, logs, smooth=False)
            elif op == "add_modifier":
                _apply_add_modifier(raw, logs)
            elif op == "boolean_difference":
                _apply_boolean(context, raw, logs, "DIFFERENCE")
            elif op == "boolean_union":
                _apply_boolean(context, raw, logs, "UNION")
            elif op == "boolean_intersect":
                _apply_boolean(context, raw, logs, "INTERSECT")
            elif op == "groove_box_cut":
                _apply_groove_box_cut(context, raw, logs)
            elif op == "create_armature":
                _apply_create_armature(context, raw, logs)
            elif op == "set_print_units":
                _apply_set_print_units(context, logs)
            elif op == "apply_scale":
                _apply_apply_scale(context, raw, logs)
            elif op == "export_stl":
                _apply_export_stl(context, raw, logs)
            elif op == "join_meshes":
                _apply_join_meshes(context, raw, logs)
            elif op == "duplicate_object":
                _apply_duplicate_object(context, raw, logs)
            elif op == "merge_by_distance":
                _apply_merge_by_distance(context, raw, logs)
            elif op == "normals_make_consistent":
                _apply_normals_make_consistent(context, raw, logs)
            elif op == "origin_to_geometry":
                _apply_origin_to_geometry(context, raw, logs)
            elif op == "place_on_build_plate":
                _apply_place_on_build_plate(context, raw, logs)
            elif op == "create_bolt_hole":
                _apply_create_bolt_hole(context, raw, logs)
            elif op == "create_nut_trap":
                _apply_create_nut_trap(context, raw, logs)
            elif op == "create_insert_pocket":
                _apply_create_insert_pocket(context, raw, logs)
            elif op == "create_standoff":
                _apply_create_standoff(context, raw, logs)
            elif op == "check_manufacturability":
                _apply_check_manufacturability(raw, logs)
            else:
                logs.append(f"skip unknown op: {op!r}")
        except Exception as e:
            logs.append(f"error on {op!r}: {e}")

    return logs


def _vec3(val: Any, default=(0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if isinstance(val, (list, tuple)) and len(val) >= 3:
        return (float(val[0]), float(val[1]), float(val[2]))
    return default


def _apply_create_primitive(
    context: bpy.types.Context,
    raw: dict[str, Any],
    logs: list[str],
) -> None:
    prim = str(raw.get("primitive", "CUBE")).upper()
    name = raw.get("name")
    loc = _vec3(raw.get("location"), (0.0, 0.0, 0.0))
    size = raw.get("size")

    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    prev_sel = list(view_layer.objects.selected)

    try:
        if prim == "CUBE":
            bpy.ops.mesh.primitive_cube_add(location=loc)
        elif prim == "SPHERE":
            bpy.ops.mesh.primitive_uv_sphere_add(location=loc)
        elif prim == "CYLINDER":
            bpy.ops.mesh.primitive_cylinder_add(location=loc)
        elif prim == "CONE":
            bpy.ops.mesh.primitive_cone_add(location=loc)
        elif prim == "PLANE":
            bpy.ops.mesh.primitive_plane_add(location=loc)
        elif prim == "TORUS":
            bpy.ops.mesh.primitive_torus_add(location=loc)
        elif prim == "ICO_SPHERE":
            bpy.ops.mesh.primitive_ico_sphere_add(location=loc)
        elif prim in ("MONKEY", "SUZANNE"):
            bpy.ops.mesh.primitive_monkey_add(location=loc)
        else:
            logs.append(f"create_primitive: unknown primitive {prim!r}")
            return

        obj = context.view_layer.objects.active
        if obj is None:
            logs.append("create_primitive: no active object after add")
            return
        if isinstance(name, str) and name.strip():
            obj.name = name.strip()[:63]
        if isinstance(size, (int, float)) and size > 0 and prim == "CUBE":
            s = float(size)
            obj.scale = (s, s, s)
        if "scale" in raw:
            sx, sy, sz = _vec3(raw.get("scale"), (1.0, 1.0, 1.0))
            obj.scale = (sx, sy, sz)
        logs.append(f"create_primitive: {prim} -> {obj.name!r}")
    finally:
        for o in view_layer.objects.selected:
            o.select_set(False)
        for o in prev_sel:
            if o.name in view_layer.objects:
                o.select_set(True)
        if prev_active and prev_active.name in view_layer.objects:
            view_layer.objects.active = prev_active


def _apply_delete(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    names = raw.get("names")
    if not isinstance(names, list):
        return
    view_layer = context.view_layer
    for n in names:
        if not isinstance(n, str):
            continue
        obj = bpy.data.objects.get(n)
        if not obj:
            logs.append(f"delete: missing {n!r}")
            continue
        view_layer.objects.active = obj
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.ops.object.delete(use_global=False)
        logs.append(f"delete: {n!r}")


def _apply_set_transform(raw: dict[str, Any], logs: list[str]) -> None:
    name = raw.get("name")
    if not isinstance(name, str):
        return
    obj = _find_object(name)
    if not obj:
        logs.append(f"set_transform: missing {name!r}")
        return
    if "location" in raw:
        obj.location = _vec3(raw.get("location"), obj.location)
    if "rotation_euler" in raw:
        rx, ry, rz = _vec3(raw.get("rotation_euler"), obj.rotation_euler)
        obj.rotation_euler = (rx, ry, rz)
    if "scale" in raw:
        obj.scale = _vec3(raw.get("scale"), obj.scale)
    logs.append(f"set_transform: {name!r}")


def _apply_rename(raw: dict[str, Any], logs: list[str]) -> None:
    a = raw.get("from_name")
    b = raw.get("to_name")
    if not isinstance(a, str) or not isinstance(b, str):
        return
    obj = _find_object(a)
    if not obj:
        logs.append(f"rename: missing {a!r}")
        return
    obj.name = b.strip()[:63]
    logs.append(f"rename: {a!r} -> {b!r}")


def _apply_shade(raw: dict[str, Any], logs: list[str], smooth: bool) -> None:
    name = raw.get("name")
    if not isinstance(name, str):
        return
    obj = _find_object(name)
    if not obj or obj.type != "MESH":
        logs.append(f"shade: missing or non-mesh {name!r}")
        return
    mesh = obj.data
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    mesh.update()
    logs.append(f"{'shade_smooth' if smooth else 'shade_flat'}: {name!r}")


def _apply_add_modifier(raw: dict[str, Any], logs: list[str]) -> None:
    name = raw.get("name")
    mod_type = raw.get("modifier_type")
    if not isinstance(name, str) or not isinstance(mod_type, str):
        return
    obj = _find_object(name)
    if not obj or obj.type != "MESH":
        logs.append(f"add_modifier: missing or non-mesh {name!r}")
        return
    mod_name = raw.get("modifier_name") or mod_type
    if not isinstance(mod_name, str):
        mod_name = mod_type
    mod = obj.modifiers.new(name=mod_name[:63], type=mod_type)
    if mod_type == "SUBSURF" and hasattr(mod, "levels"):
        levels = raw.get("levels")
        if isinstance(levels, int):
            mod.levels = max(0, min(6, levels))
    elif mod_type == "SOLIDIFY" and hasattr(mod, "thickness"):
        mod.thickness = float(raw.get("thickness", 0.001))
        if hasattr(mod, "offset"):
            mod.offset = float(raw.get("solidify_offset", 0.0))
    elif mod_type == "BEVEL":
        if hasattr(mod, "width"):
            mod.width = float(raw.get("width", 0.0005))
        if hasattr(mod, "segments") and raw.get("segments") is not None:
            mod.segments = max(1, int(raw.get("segments", 1)))
    elif mod_type == "ARRAY":
        if hasattr(mod, "count"):
            mod.count = max(1, int(raw.get("count", 2)))
        if hasattr(mod, "use_relative_offset"):
            mod.use_relative_offset = True
        ro = raw.get("relative_offset_displace")
        if hasattr(mod, "relative_offset_displace") and isinstance(ro, (list, tuple)) and len(ro) >= 3:
            mod.relative_offset_displace = (float(ro[0]), float(ro[1]), float(ro[2]))
    elif mod_type == "MIRROR":
        ax = str(raw.get("mirror_axis", "X")).upper()
        if hasattr(mod, "use_axis_x"):
            mod.use_axis_x = ax == "X"
            mod.use_axis_y = ax == "Y"
            mod.use_axis_z = ax == "Z"
        elif hasattr(mod, "use_axis"):
            try:
                mod.use_axis = (ax == "X", ax == "Y", ax == "Z")
            except TypeError:
                mod.use_axis[0] = ax == "X"
                mod.use_axis[1] = ax == "Y"
                mod.use_axis[2] = ax == "Z"
    logs.append(f"add_modifier: {name!r} {mod_type!r}")


def _apply_boolean(
    context: bpy.types.Context,
    raw: dict[str, Any],
    logs: list[str],
    operation: str,
) -> None:
    target_name = raw.get("target")
    cutter_name = raw.get("cutter")
    if not isinstance(target_name, str) or not isinstance(cutter_name, str):
        return
    target = _find_object(target_name)
    cutter = _find_object(cutter_name)
    if not target or target.type != "MESH":
        logs.append(f"boolean: missing or non-mesh target {target_name!r}")
        return
    if not cutter or cutter.type != "MESH":
        logs.append(f"boolean: missing or non-mesh cutter {cutter_name!r}")
        return

    apply_mod = raw.get("apply", True)
    if not isinstance(apply_mod, bool):
        apply_mod = bool(apply_mod)

    delete_cutter = raw.get("delete_cutter", False)
    if not isinstance(delete_cutter, bool):
        delete_cutter = bool(delete_cutter)

    solver = str(raw.get("solver", "EXACT")).upper()
    if solver not in ("EXACT", "FAST"):
        solver = "EXACT"

    mod_name = "BGPT_" + uuid.uuid4().hex[:10]
    mod = target.modifiers.new(name=mod_name, type="BOOLEAN")
    mod.operation = operation
    mod.object = cutter
    if hasattr(mod, "solver"):
        mod.solver = solver

    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    prev_sel = list(view_layer.objects.selected)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        target.select_set(True)
        view_layer.objects.active = target
        if apply_mod:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        if delete_cutter and cutter.name in bpy.data.objects:
            view_layer.objects.active = cutter
            bpy.ops.object.select_all(action="DESELECT")
            cutter.select_set(True)
            bpy.ops.object.delete(use_global=False)
        logs.append(f"boolean_{operation.lower()}: {target_name!r} <- {cutter_name!r}")
    finally:
        for o in view_layer.objects.selected:
            o.select_set(False)
        for o in prev_sel:
            if o.name in view_layer.objects:
                o.select_set(True)
        if prev_active and prev_active.name in view_layer.objects:
            view_layer.objects.active = prev_active


def _apply_groove_box_cut(
    context: bpy.types.Context,
    raw: dict[str, Any],
    logs: list[str],
) -> None:
    """
    Axis-aligned box cutter + boolean difference. Handy for grooves/slots.
    groove_axis: X|Y|Z — long axis of the groove; depth is the third axis (into cut).
    """
    target_name = raw.get("target")
    if not isinstance(target_name, str):
        return
    center = _vec3(raw.get("center") or raw.get("location"), (0.0, 0.0, 0.0))
    length = float(raw.get("length", 1.0))
    width = float(raw.get("width", 0.05))
    depth = float(raw.get("depth", 0.1))
    ax = str(raw.get("groove_axis", "X")).upper()
    if ax == "X":
        sx, sy, sz = length / 2.0, width / 2.0, depth / 2.0
    elif ax == "Y":
        sx, sy, sz = width / 2.0, length / 2.0, depth / 2.0
    else:
        sx, sy, sz = width / 2.0, depth / 2.0, length / 2.0

    cutter_name = raw.get("cutter_name")
    if not isinstance(cutter_name, str) or not cutter_name.strip():
        cutter_name = "GrooveCutter"

    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    prev_sel = list(view_layer.objects.selected)
    try:
        bpy.ops.mesh.primitive_cube_add(location=center)
        cut = view_layer.objects.active
        if cut is None:
            logs.append("groove_box_cut: no cutter after cube add")
            return
        cut.name = cutter_name.strip()[:63]
        cut.scale = (max(sx, 1e-4), max(sy, 1e-4), max(sz, 1e-4))
        _apply_boolean(
            context,
            {
                "target": target_name,
                "cutter": cut.name,
                "apply": raw.get("apply", True),
                "delete_cutter": raw.get("delete_cutter", True),
                "solver": raw.get("solver", "EXACT"),
            },
            logs,
            "DIFFERENCE",
        )
    finally:
        for o in view_layer.objects.selected:
            o.select_set(False)
        for o in prev_sel:
            if o.name in view_layer.objects:
                o.select_set(True)
        if prev_active and prev_active.name in view_layer.objects:
            view_layer.objects.active = prev_active


def _apply_create_armature(
    context: bpy.types.Context,
    raw: dict[str, Any],
    logs: list[str],
) -> None:
    """Connected edit-bone chain (simple skeleton) along one axis in armature space."""
    from mathutils import Vector

    loc = _vec3(raw.get("location"), (0.0, 0.0, 0.0))
    name = raw.get("name")
    axis = str(raw.get("axis", "Y")).upper()
    dir_map = {
        "X": Vector((1.0, 0.0, 0.0)),
        "Y": Vector((0.0, 1.0, 0.0)),
        "Z": Vector((0.0, 0.0, 1.0)),
        "-X": Vector((-1.0, 0.0, 0.0)),
        "-Y": Vector((0.0, -1.0, 0.0)),
        "-Z": Vector((0.0, 0.0, -1.0)),
    }
    direction = dir_map.get(axis, Vector((0.0, 1.0, 0.0))).normalized()

    bc = raw.get("bone_count")
    if bc is None:
        bc = raw.get("segments")
    if isinstance(bc, float):
        bc = int(bc)
    if isinstance(bc, str) and bc.isdigit():
        bc = int(bc)
    if not isinstance(bc, int):
        bc = 3
    bone_count = max(1, min(128, bc))

    seg_len = raw.get("segment_length", 0.25)
    try:
        seg_len = float(seg_len)
    except (TypeError, ValueError):
        seg_len = 0.25
    seg_len = max(1e-4, seg_len)

    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    prev_sel = list(view_layer.objects.selected)
    try:
        bpy.ops.object.armature_add(location=loc)
        obj = view_layer.objects.active
        if obj is None or obj.type != "ARMATURE":
            logs.append("create_armature: armature_add failed")
            return
        if isinstance(name, str) and name.strip():
            obj.name = name.strip()[:63]

        bpy.ops.object.mode_set(mode="EDIT")
        arm = obj.data
        if not arm.edit_bones:
            bpy.ops.object.mode_set(mode="OBJECT")
            logs.append("create_armature: no edit bones")
            return

        parent = arm.edit_bones[0]
        parent.name = "Bone_0"
        parent.head = Vector((0.0, 0.0, 0.0))
        parent.tail = direction * seg_len

        for i in range(1, bone_count):
            child = arm.edit_bones.new(f"Bone_{i}")
            child.head = parent.tail.copy()
            child.tail = parent.tail + direction * seg_len
            child.parent = parent
            child.use_connect = True
            parent = child

        bpy.ops.object.mode_set(mode="OBJECT")
        logs.append(f"create_armature: {obj.name!r} bones={bone_count} axis={axis!r}")
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        for o in view_layer.objects.selected:
            o.select_set(False)
        for o in prev_sel:
            if o.name in view_layer.objects:
                o.select_set(True)
        if prev_active and prev_active.name in view_layer.objects:
            view_layer.objects.active = prev_active


def _with_active_object(
    context: bpy.types.Context,
    obj: bpy.types.Object,
    callback: Any,
) -> None:
    """Select only `obj`, set active, run `callback()` (no args), restore selection."""
    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    prev_sel = list(view_layer.objects.selected)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        view_layer.objects.active = obj
        callback()
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for o in prev_sel:
            if o.name in view_layer.objects:
                o.select_set(True)
        if prev_active and prev_active.name in view_layer.objects:
            view_layer.objects.active = prev_active


def _try_stl_export(filepath: str) -> None:
    fp = os.path.abspath(os.path.expanduser(filepath))
    parent = os.path.dirname(fp)
    if parent:
        os.makedirs(parent, exist_ok=True)
    stl_op = getattr(bpy.ops.wm, "stl_export", None)
    if stl_op is not None:
        stl_op(filepath=fp, check_existing=False, use_selection=True)
        return
    bpy.ops.export_mesh.stl(filepath=fp, check_existing=False, use_selection=True)


def _apply_set_print_units(context: bpy.types.Context, logs: list[str]) -> None:
    us = context.scene.unit_settings
    us.system = "METRIC"
    us.length_unit = "MILLIMETERS"
    us.scale_length = 0.001
    logs.append("set_print_units: metric, length millimetres, unit scale 0.001 (verify grid)")


def _apply_apply_scale(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    names = raw.get("names")
    if names is None and isinstance(raw.get("name"), str):
        names = [raw["name"]]
    if not isinstance(names, list) or not names:
        return
    for n in names:
        if not isinstance(n, str):
            continue
        obj = _find_object(n)
        if not obj:
            logs.append(f"apply_scale: missing {n!r}")
            continue

        def apply_one() -> None:
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        _with_active_object(context, obj, apply_one)
        logs.append(f"apply_scale: {n!r}")


def _apply_export_stl(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    fp = raw.get("filepath")
    if not isinstance(fp, str) or not fp.strip():
        logs.append("export_stl: missing filepath")
        return
    names = raw.get("names")
    if names is None and isinstance(raw.get("name"), str):
        names = [raw["name"]]
    if not isinstance(names, list) or len(names) != 1:
        logs.append("export_stl: provide exactly one mesh (name or single-element names)")
        return
    n = names[0]
    if not isinstance(n, str):
        return
    obj = _find_object(n)
    if not obj or obj.type != "MESH":
        logs.append(f"export_stl: missing or non-mesh {n!r}")
        return

    def do_export() -> None:
        _try_stl_export(fp.strip())

    _with_active_object(context, obj, do_export)
    logs.append(f"export_stl: {n!r} -> {os.path.abspath(os.path.expanduser(fp.strip()))}")


def _apply_join_meshes(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    names = raw.get("names")
    if not isinstance(names, list) or len(names) < 2:
        logs.append("join_meshes: need names list with at least 2 meshes")
        return
    objs: list[bpy.types.Object] = []
    for n in names:
        if not isinstance(n, str):
            continue
        o = _find_object(n)
        if o and o.type == "MESH":
            objs.append(o)
    if len(objs) < 2:
        logs.append("join_meshes: could not resolve two mesh objects")
        return

    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    prev_sel = list(view_layer.objects.selected)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        base = objs[0]
        base.select_set(True)
        view_layer.objects.active = base
        for o in objs[1:]:
            o.select_set(True)
        bpy.ops.object.join()
        logs.append(f"join_meshes: merged into {base.name!r} ({len(objs)} meshes)")
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for o in prev_sel:
            if o.name in view_layer.objects:
                o.select_set(True)
        if prev_active and prev_active.name in view_layer.objects:
            view_layer.objects.active = prev_active


def _apply_duplicate_object(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    name = raw.get("name")
    if not isinstance(name, str):
        return
    obj = _find_object(name)
    if not obj:
        logs.append(f"duplicate_object: missing {name!r}")
        return
    linked = raw.get("linked", False)
    if not isinstance(linked, bool):
        linked = bool(linked)
    view_layer = context.view_layer
    prev_active = view_layer.objects.active
    prev_sel = list(view_layer.objects.selected)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        view_layer.objects.active = obj
        bpy.ops.object.duplicate(linked=linked)
        dup = view_layer.objects.active
        nn = raw.get("new_name")
        if dup and isinstance(nn, str) and nn.strip():
            dup.name = nn.strip()[:63]
        logs.append(f"duplicate_object: {name!r} -> {dup.name if dup else '?'}")
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for o in prev_sel:
            if o.name in view_layer.objects:
                o.select_set(True)
        if prev_active and prev_active.name in view_layer.objects:
            view_layer.objects.active = prev_active


def _apply_merge_by_distance(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    name = raw.get("name")
    if not isinstance(name, str):
        return
    obj = _find_object(name)
    if not obj or obj.type != "MESH":
        logs.append(f"merge_by_distance: missing or non-mesh {name!r}")
        return
    try:
        threshold = float(raw.get("threshold", 0.0001))
    except (TypeError, ValueError):
        threshold = 0.0001
    threshold = max(1e-8, threshold)

    def edit_merge() -> None:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.merge_by_distance(threshold=threshold)
        bpy.ops.object.mode_set(mode="OBJECT")

    _with_active_object(context, obj, edit_merge)
    logs.append(f"merge_by_distance: {name!r} threshold={threshold}")


def _apply_normals_make_consistent(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    name = raw.get("name")
    if not isinstance(name, str):
        return
    obj = _find_object(name)
    if not obj or obj.type != "MESH":
        logs.append(f"normals_make_consistent: missing or non-mesh {name!r}")
        return
    inside = raw.get("inside", False)
    if not isinstance(inside, bool):
        inside = bool(inside)

    def edit_normals() -> None:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="VERT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=inside)
        bpy.ops.object.mode_set(mode="OBJECT")

    _with_active_object(context, obj, edit_normals)
    logs.append(f"normals_make_consistent: {name!r}")


def _apply_origin_to_geometry(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    name = raw.get("name")
    if not isinstance(name, str):
        return
    obj = _find_object(name)
    if not obj:
        logs.append(f"origin_to_geometry: missing {name!r}")
        return

    def origin_set() -> None:
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")

    _with_active_object(context, obj, origin_set)
    logs.append(f"origin_to_geometry: {name!r}")


def _apply_place_on_build_plate(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    from mathutils import Vector

    name = raw.get("name")
    if not isinstance(name, str):
        return
    obj = _find_object(name)
    if not obj or obj.type != "MESH":
        logs.append(f"place_on_build_plate: missing or non-mesh {name!r}")
        return
    mw = obj.matrix_world
    zs = [(mw @ Vector(corner)).z for corner in obj.bound_box]
    min_z = min(zs)
    obj.location.z -= min_z
    logs.append(f"place_on_build_plate: {name!r} dz={-min_z:.6f}")


_BOLT_CLEARANCE_MM = {
    "M2": 2.4,
    "M2.5": 2.9,
    "M3": 3.4,
    "M4": 4.5,
    "M5": 5.5,
    "M6": 6.6,
}
_NUT_AF_MM = {"M3": 5.5, "M4": 7.0, "M5": 8.0, "M6": 10.0}
_INSERT_OD_MM = {"M3": 4.6, "M4": 5.6, "M5": 6.8}
_INSERT_DEPTH_MM = {"M3": 4.5, "M4": 6.0, "M5": 7.0}


def _mm_to_scene(mm: float, context: bpy.types.Context) -> float:
    us = context.scene.unit_settings
    scale = float(getattr(us, "scale_length", 1.0) or 1.0)
    return (mm / 1000.0) / scale


def _axis_to_rot(axis: str) -> tuple[float, float, float]:
    ax = axis.upper()
    if ax == "X":
        return (0.0, 1.5707963267948966, 0.0)
    if ax == "Y":
        return (-1.5707963267948966, 0.0, 0.0)
    return (0.0, 0.0, 0.0)


def _create_cylinder(
    context: bpy.types.Context,
    *,
    radius: float,
    depth: float,
    center: tuple[float, float, float],
    axis: str,
    name: str,
) -> bpy.types.Object | None:
    rot = _axis_to_rot(axis)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=max(radius, 1e-5),
        depth=max(depth, 1e-5),
        location=center,
        rotation=rot,
    )
    obj = context.view_layer.objects.active
    if obj:
        obj.name = name[:63]
    return obj


def _create_hex_prism(
    context: bpy.types.Context,
    *,
    across_flats: float,
    depth: float,
    center: tuple[float, float, float],
    axis: str,
    name: str,
) -> bpy.types.Object | None:
    # For a regular hexagon: across-flats = sqrt(3) * circumradius.
    from math import sqrt

    circumradius = max(across_flats / sqrt(3.0), 1e-5)
    rot = _axis_to_rot(axis)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=6,
        radius=circumradius,
        depth=max(depth, 1e-5),
        location=center,
        rotation=rot,
    )
    obj = context.view_layer.objects.active
    if obj:
        obj.name = name[:63]
    return obj


def _axis_index(axis: str) -> int:
    return {"X": 0, "Y": 1, "Z": 2}.get(axis.upper(), 2)


def _through_depth_along_axis(target: bpy.types.Object, axis: str, margin: float = 1.25) -> float:
    bb = world_bbox_stats(target)
    mn, mx = bb["min"], bb["max"]
    idx = _axis_index(axis)
    span = mx[idx] - mn[idx]
    return max(span * margin, 1e-4)


def _resolve_cut_center(
    raw: dict[str, Any],
    target: bpy.types.Object,
) -> tuple[tuple[float, float, float], str]:
    """
    Resolve cutter center. Default: world bbox center (not object origin).
    center_mode: bbox_center (default) | origin | explicit (requires center in raw)
    """
    bb = world_bbox_stats(target)
    bbox_center = bb["center"]
    mode = str(raw.get("center_mode", "bbox_center")).lower()
    if mode == "origin":
        loc = target.location
        return (loc.x, loc.y, loc.z), "origin"

    if "center" in raw or "location" in raw:
        center = _vec3(raw.get("center") or raw.get("location"), target.location)
        dims = bb["dimensions"]
        max_dim = max(dims) if dims else 1.0
        dist = math.dist(center, bbox_center)
        if dist > max_dim * 1.5:
            return bbox_center, "bbox_center_snapped"
        return center, "explicit"

    return bbox_center, "bbox_center"


def _resolve_hole_diameter_scene(context: bpy.types.Context, raw: dict[str, Any]) -> float:
    if isinstance(raw.get("diameter"), (int, float)):
        return float(raw["diameter"])
    standard = str(raw.get("standard", "M3")).upper()
    mm = _BOLT_CLEARANCE_MM.get(standard, _BOLT_CLEARANCE_MM["M3"])
    extra_mm = float(raw.get("clearance_mm", 0.0) or 0.0)
    return _mm_to_scene(mm + extra_mm, context)


def _apply_create_bolt_hole(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    target_name = raw.get("target")
    if not isinstance(target_name, str):
        logs.append("create_bolt_hole: missing target")
        return
    target = _find_object(target_name)
    if not target or target.type != "MESH":
        logs.append(f"create_bolt_hole: missing or non-mesh {target_name!r}")
        return

    center, center_src = _resolve_cut_center(raw, target)
    axis = str(raw.get("axis", "Z")).upper()
    diameter = _resolve_hole_diameter_scene(context, raw)
    radius = max(0.5 * diameter, 1e-5)
    if bool(raw.get("through", True if "depth" not in raw else False)):
        depth = _through_depth_along_axis(target, axis)
    else:
        depth = float(raw.get("depth", _through_depth_along_axis(target, axis)))

    cutter_name = str(raw.get("cutter_name") or f"{target.name}_bolt_hole")
    cut = _create_cylinder(
        context,
        radius=radius,
        depth=depth,
        center=center,
        axis=axis,
        name=cutter_name,
    )
    if cut is None:
        logs.append("create_bolt_hole: failed to create cutter")
        return
    _apply_boolean(
        context,
        {
            "target": target.name,
            "cutter": cut.name,
            "apply": raw.get("apply", True),
            "delete_cutter": raw.get("delete_cutter", True),
            "solver": raw.get("solver", "EXACT"),
        },
        logs,
        "DIFFERENCE",
    )
    logs.append(
        f"create_bolt_hole: {target.name!r} dia={diameter:.6f} "
        f"center={center_src} through_depth={depth:.6f} axis={axis}"
    )


def _apply_create_nut_trap(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    target_name = raw.get("target")
    if not isinstance(target_name, str):
        logs.append("create_nut_trap: missing target")
        return
    target = _find_object(target_name)
    if not target or target.type != "MESH":
        logs.append(f"create_nut_trap: missing or non-mesh {target_name!r}")
        return

    standard = str(raw.get("standard", "M3")).upper()
    af_mm = float(raw.get("across_flats_mm", _NUT_AF_MM.get(standard, 5.5)))
    af_mm += float(raw.get("clearance_mm", 0.2) or 0.0)
    across_flats = _mm_to_scene(af_mm, context)
    depth = float(raw.get("depth", _mm_to_scene(2.5, context)))
    center, center_src = _resolve_cut_center(raw, target)
    axis = str(raw.get("axis", "Z")).upper()
    cutter_name = str(raw.get("cutter_name") or f"{target.name}_nut_trap")
    cut = _create_hex_prism(
        context,
        across_flats=across_flats,
        depth=depth,
        center=center,
        axis=axis,
        name=cutter_name,
    )
    if cut is None:
        logs.append("create_nut_trap: failed to create cutter")
        return
    _apply_boolean(
        context,
        {
            "target": target.name,
            "cutter": cut.name,
            "apply": raw.get("apply", True),
            "delete_cutter": raw.get("delete_cutter", True),
            "solver": raw.get("solver", "EXACT"),
        },
        logs,
        "DIFFERENCE",
    )
    logs.append(f"create_nut_trap: {target.name!r} standard={standard} center={center_src}")


def _apply_create_insert_pocket(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    target_name = raw.get("target")
    if not isinstance(target_name, str):
        logs.append("create_insert_pocket: missing target")
        return
    target = _find_object(target_name)
    if not target or target.type != "MESH":
        logs.append(f"create_insert_pocket: missing or non-mesh {target_name!r}")
        return

    standard = str(raw.get("standard", "M3")).upper()
    od_mm = float(raw.get("outer_diameter_mm", _INSERT_OD_MM.get(standard, 4.6)))
    depth_mm = float(raw.get("depth_mm", _INSERT_DEPTH_MM.get(standard, 4.5)))
    od_mm += float(raw.get("clearance_mm", 0.15) or 0.0)
    radius = 0.5 * _mm_to_scene(od_mm, context)
    depth = _mm_to_scene(depth_mm, context)
    center, center_src = _resolve_cut_center(raw, target)
    axis = str(raw.get("axis", "Z")).upper()
    cutter_name = str(raw.get("cutter_name") or f"{target.name}_insert_pocket")
    cut = _create_cylinder(
        context,
        radius=radius,
        depth=depth,
        center=center,
        axis=axis,
        name=cutter_name,
    )
    if cut is None:
        logs.append("create_insert_pocket: failed to create cutter")
        return
    _apply_boolean(
        context,
        {
            "target": target.name,
            "cutter": cut.name,
            "apply": raw.get("apply", True),
            "delete_cutter": raw.get("delete_cutter", True),
            "solver": raw.get("solver", "EXACT"),
        },
        logs,
        "DIFFERENCE",
    )
    logs.append(f"create_insert_pocket: {target.name!r} standard={standard} center={center_src}")


def _apply_create_standoff(context: bpy.types.Context, raw: dict[str, Any], logs: list[str]) -> None:
    loc = _vec3(raw.get("center") or raw.get("location"), (0.0, 0.0, 0.0))
    axis = str(raw.get("axis", "Z")).upper()
    outer_d = float(raw.get("outer_diameter", _mm_to_scene(8.0, context)))
    height = float(raw.get("height", _mm_to_scene(10.0, context)))
    name = str(raw.get("name") or "Standoff")
    body = _create_cylinder(
        context,
        radius=max(outer_d * 0.5, 1e-5),
        depth=height,
        center=loc,
        axis=axis,
        name=name,
    )
    if body is None:
        logs.append("create_standoff: failed to create body")
        return
    hole_d = float(raw.get("hole_diameter", _mm_to_scene(3.4, context)))
    hole = _create_cylinder(
        context,
        radius=max(hole_d * 0.5, 1e-5),
        depth=height * 1.2,
        center=loc,
        axis=axis,
        name=f"{name}_hole",
    )
    if hole is None:
        logs.append("create_standoff: failed to create hole cutter")
        return
    _apply_boolean(
        context,
        {
            "target": body.name,
            "cutter": hole.name,
            "apply": True,
            "delete_cutter": True,
            "solver": "EXACT",
        },
        logs,
        "DIFFERENCE",
    )
    target_name = raw.get("target")
    if isinstance(target_name, str):
        target = _find_object(target_name)
        if target and target.type == "MESH":
            _apply_boolean(
                context,
                {
                    "target": target.name,
                    "cutter": body.name,
                    "apply": raw.get("apply_union", True),
                    "delete_cutter": bool(raw.get("delete_standoff", True)),
                    "solver": raw.get("solver", "EXACT"),
                },
                logs,
                "UNION",
            )
            logs.append(f"create_standoff: union into {target.name!r}")
            return
    logs.append(f"create_standoff: created {body.name!r}")


def _apply_check_manufacturability(raw: dict[str, Any], logs: list[str]) -> None:
    names = raw.get("names")
    if names is None and isinstance(raw.get("name"), str):
        names = [raw["name"]]
    if not isinstance(names, list) or not names:
        logs.append("check_manufacturability: provide name or names")
        return
    for n in names:
        if not isinstance(n, str):
            continue
        obj = _find_object(n)
        if not obj or obj.type != "MESH":
            logs.append(f"check_manufacturability: missing or non-mesh {n!r}")
            continue
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.normal_update()
            non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
            boundary = sum(1 for e in bm.edges if e.is_boundary)
            degenerate = sum(1 for f in bm.faces if f.calc_area() <= 1e-12)
            status = "PASS"
            if non_manifold > 0 or boundary > 0:
                status = "FAIL"
            elif degenerate > 0:
                status = "WARN"
            logs.append(
                f"check_manufacturability: {n!r} {status} "
                f"(non_manifold={non_manifold}, boundary={boundary}, degenerate={degenerate})"
            )
        finally:
            bm.free()
