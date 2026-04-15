#!/usr/bin/env python3
"""
Integration tests requiring Blender's bpy (run headless).

  blender --background --python tests/blender_e2e.py

Exit code 0 on success, 1 on assertion failure.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _clear_mesh_objects() -> None:
    import bpy

    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def main() -> int:
    import bpy
    from blender_gpt.apply_actions import apply_actions
    from blender_gpt.context_builder import build_scene_digest

    _clear_mesh_objects()
    ctx = bpy.context

    # --- add ---
    logs_add = apply_actions(
        ctx,
        [
            {
                "op": "create_primitive",
                "primitive": "CUBE",
                "name": "TestCube",
                "location": [1.0, 2.0, 3.0],
            }
        ],
    )
    assert "TestCube" in bpy.data.objects, list(bpy.data.objects.keys())
    assert any("create_primitive" in line for line in logs_add), logs_add

    # --- describe (scene digest includes named object and selection) ---
    bpy.ops.object.select_all(action="DESELECT")
    cube = bpy.data.objects["TestCube"]
    cube.select_set(True)
    ctx.view_layer.objects.active = cube

    digest = build_scene_digest(ctx, max_chars=100_000)
    assert "Scene:" in digest, digest[:500]
    assert "Selection:" in digest
    assert "TestCube" in digest

    # --- remove ---
    logs_del = apply_actions(
        ctx,
        [{"op": "delete_objects", "names": ["TestCube"]}],
    )
    assert "TestCube" not in bpy.data.objects
    assert any("delete" in line.lower() for line in logs_del), logs_del

    print("OK: add, describe (digest), remove — all passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError:
        traceback.print_exc()
        raise SystemExit(1)
