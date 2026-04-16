# 3D printing workflow in Blender (and how BlenderGPT maps to it)

This document lists **typical tasks** a modeler does when preparing meshes for **FDM / resin / SLS** printing, and how they map to **BlenderGPT JSON actions**. It complements the live system prompt the model sees in the add-on.

BlenderGPT only runs **explicit, allowlisted operations**. Anything marked **manual** still needs you, Blender’s UI, or a slicer (PrusaSlicer, Cura, Bambu Studio, Lychee, etc.).

---

## 1. Start from real dimensions

| Task | Why | BlenderGPT |
|------|-----|------------|
| Use **metric millimetres** in the file | Matches slicer expectations and hardware | `set_print_units` |
| Model at **true size** (e.g. M3 hole = 3.2 mm clearance) | Avoids rescaling surprises | `create_primitive` + `scale` / `set_transform` |
| **Apply scale** before export | STL stores mesh data; unapplied scale can confuse size | `apply_scale` |

**Manual:** Calipers, engineering drawings, tolerance tables (e.g. press-fit vs loose).

---

## 2. Build solid geometry

| Task | Why | BlenderGPT |
|------|-----|------------|
| Primitives (box, cylinder, torus, …) | Fast mechanical parts | `create_primitive` |
| **Holes** (through or blind) | Fasteners, vents, weight reduction | `boolean_difference` (cutter = cylinder/cube), optional `delete_cutter` |
| **Grooves / slots** | Cable clips, keyways | `groove_box_cut` or boolean + thin `create_primitive` |
| Combine parts | One watertight body for export | `boolean_union` or `join_meshes` |
| Symmetric parts | Less modelling | `add_modifier` with `MIRROR` (see §6) |
| Linear repeats | Hole patterns, ribs | `add_modifier` with `ARRAY` |

**Manual:** Organic sculpting, complex fillets, surfacing from CAD STEP (often import + cleanup).

---

## 3. Printability (mesh hygiene)

| Task | Why | BlenderGPT |
|------|-----|------------|
| **Merge by distance** | Removes duplicate verts from booleans / imports → helps watertightness | `merge_by_distance` |
| **Consistent normals** | Some slicers behave badly on inverted normals | `normals_make_consistent` |
| **Origin on geometry** | Predictable pivot for rotation on the bed | `origin_to_geometry` |
| **Shell / wall thickness** | Thin walls break; uniform offset | `add_modifier` `SOLIDIFY` with `thickness` |
| Chamfers / light fillets | Reduce stress risers (mechanical) | `add_modifier` `BEVEL` with `width` / `segments` |

**Manual:** Full “manifold audit” (Blender 3D-Print Toolbox or Meshmixer), non-planar holes, minimum feature size for your printer.

---

## 4. Orientation and build plate

| Task | Why | BlenderGPT |
|------|-----|------------|
| Lay model on **Z = 0** (bed plane) | Many slicers assume part sits on bed | `place_on_build_plate` |
| Rotate for fewer overhangs | Less support plastic | `set_transform` (`rotation_euler`) |

**Manual:** Slicer auto-orient, support painting, brim/raft/skirt (slicer-only).

---

## 5. Assemblies and variants

| Task | Why | BlenderGPT |
|------|-----|------------|
| Duplicate a part | Spares, arrays of clips | `duplicate_object` |
| Merge meshes into one object | Single STL | `join_meshes` |

**Manual:** Multi-body STL with named solids (slicer-dependent), articulations.

---

## 6. Modifier shortcuts (JSON)

Use `add_modifier` with extra fields where noted:

| Goal | `modifier_type` | Extra fields |
|------|-----------------|--------------|
| Wall thickness | `SOLIDIFY` | `thickness` (float, scene units) |
| Edge soften | `BEVEL` | `width`, `segments` (optional) |
| Linear array | `ARRAY` | `count`, `relative_offset_displace` e.g. `[1,0,0]` |
| Mirror half | `MIRROR` | `use_axis` via `mirror_axis` string `X` / `Y` / `Z` (implemented) |

---

## 7. Export

| Task | Why | BlenderGPT |
|------|-----|------------|
| **Export STL** (binary preferred) | Universal slicer input | `export_stl` (absolute `filepath`) |

**Rules:** Export **one watertight mesh** per job when possible. If you have several meshes, **`join_meshes`** first or export one `name`.

**Manual:** 3MF/STEP for multi-material or dimension-critical handoff; repair in slicer or Netfabb.

---

## 8. Slicer and printer (always manual)

- Layer height, infill, supports, temperatures, brim, elephant foot compensation  
- Machine limits: min hole diameter, bridging, overhang angle  
- Resin: drain holes, orientation for islands  

BlenderGPT does **not** drive the slicer.

---

## 9. Example action sequences (high level)

**Printed bracket with two bolt holes**

1. `set_print_units`  
2. `create_primitive` CUBE + `scale` for plate  
3. `create_primitive` CYLINDER + `set_transform` for hole A  
4. `boolean_difference` target=plate cutter=cylA `delete_cutter` true  
5. Duplicate hole tool: `duplicate_object` + `set_transform` for hole B, boolean again  
6. `merge_by_distance` on plate  
7. `normals_make_consistent` on plate  
8. `place_on_build_plate` on plate  
9. `apply_scale` on plate  
10. `export_stl` name=plate filepath=`/Users/you/exports/bracket.stl`  

(Exact names must match objects in the scene digest.)

---

## 10. Limits (honest)

- No automatic **support generation** or **slicer profiles**.  
- Booleans can fail on **non-manifold** or **degenerate** geometry.  
- **Clearance** (0.2 mm offset for press-fit) is your design rule—use slightly larger boolean cutters or `set_transform` / `scale` on cutters.  
- **Medical / regulatory** “skeleton” anatomy is not inferred from text; `create_armature` only builds a simple bone chain for rigging stubs.

---

## Quick reference — op names

| Op | Role |
|----|------|
| `set_print_units` | Metric + mm-style unit preset |
| `create_primitive` | Add mesh solids |
| `set_transform` | Move / rotate / scale |
| `boolean_*` | Union / difference / intersect |
| `groove_box_cut` | Slot / groove boolean helper |
| `merge_by_distance` | Weld close vertices |
| `normals_make_consistent` | Fix normals |
| `origin_to_geometry` | Origin to mesh |
| `place_on_build_plate` | Sit lowest point on Z=0 |
| `apply_scale` | Apply scale transform |
| `join_meshes` | Join objects into one |
| `duplicate_object` | Copy object |
| `add_modifier` | SOLIDIFY, BEVEL, ARRAY, MIRROR, … |
| `export_stl` | Write STL to disk |
| `delete_objects` | Remove helpers |
