# Manufacturability Function Features

## Purpose

The manufacturability function evaluates whether generated or edited geometry is suitable for 3D printing before export. It provides measurable pass/fail checks, reports risks, and can optionally propose or apply fixes.

This is a **geometric verification layer** on top of BlenderGPT action execution.

## Goals

- Reduce failed prints caused by invalid or fragile geometry.
- Provide consistent, profile-driven checks (FDM, resin, etc.).
- Produce a machine-readable report for auditability.
- Support automatic remediation for common issues.

## Core Features

### 1) Topology Validity Checks

- Detect non-manifold edges.
- Detect open boundaries (non-watertight meshes).
- Detect zero-area / degenerate faces.
- Detect inverted or inconsistent normals.

### 2) Geometry Integrity Checks

- Detect self-intersections.
- Detect tiny disconnected islands.
- Detect knife-edge geometry and thin spikes.

### 3) Process-Aware Printability Checks

- Minimum wall thickness verification.
- Minimum feature size verification.
- Overhang risk estimation against configured threshold.
- Build volume fit check for target printer dimensions.
- Build plate contact and floating geometry detection.

### 4) Units and Scale Safety

- Verify scene/object units for print workflows.
- Verify dimensions after transforms.
- Verify scale is applied before export.

### 5) Profile-Driven Thresholds

The function should support configurable profiles, for example:

- `FDM_0_4_NOZZLE`
- `FDM_0_6_NOZZLE`
- `RESIN_STANDARD`

Each profile defines thresholds such as:

- `min_wall_mm`
- `min_feature_mm`
- `max_overhang_deg`
- `max_build_volume_mm` (x, y, z)
- optional clearance defaults

### 6) Structured Reporting

Return a report with:

- object-level status (`PASS`, `WARN`, `FAIL`)
- check-level metrics and thresholds
- violation locations (when available)
- suggested remediation actions

Example report fields:

- `object_name`
- `profile`
- `checks[]` with `{name, status, measured, threshold, message}`
- `summary`

### 7) Remediation Support

Optional auto-fix mode for safe corrective actions:

- `merge_by_distance`
- `normals_make_consistent`
- `place_on_build_plate`
- `apply_scale`

For high-risk issues (e.g., wall thickness, major self-intersections), report and request confirmation instead of blind fixing.

## LLM vs Deterministic Checks: Where Each Adds Value

Existing tools — Blender's 3D Print Toolbox, Meshmixer, PrusaSlicer, Netfabb — run fully deterministic checks. They measure geometry precisely and give exact numbers. BlenderGPT does not replace them; it occupies a different and complementary role.

### What deterministic tools do well

| Check | How | Confidence |
|-------|-----|------------|
| Non-manifold edges | Exact edge topology query | Exact |
| Wall thickness | Ray-cast or distance field | Near-exact |
| Self-intersections | BVH tree overlap test | Exact |
| Build volume fit | Bounding box arithmetic | Exact |
| Overhang angle per face | Dot product vs build direction | Exact |
| Watertightness | Boundary edge count == 0 | Exact |

These are single-answer binary questions. They run in milliseconds with no ambiguity.

### Where an LLM adds value that deterministic tools cannot

**1. Intent inference and dialogue**

Deterministic tools report a violation; they cannot ask why. An LLM can ask:

> "This wall is 0.8 mm. Your FDM profile requires 1.2 mm. Did you intend this as a flexible hinge or a structural wall? I can thicken it if structural."

That disambiguation is impossible without natural language understanding.

**2. Design intent vs check result**

A mesh analyser sees a thin feature and flags it. The LLM can recognise from context that it is intentional (a snap clip, a gasket lip) and explain trade-offs instead of blocking.

**3. Multi-constraint reasoning**

A part may have 12 warnings from a deterministic tool. A human designer needs to know which warnings are critical, which are cosmetic, and in what order to fix them. An LLM can reason across all warnings together, prioritise, and propose a coherent fix sequence rather than a flat error list.

**4. Design-for-manufacturing suggestions that go beyond geometry**

Deterministic tools verify geometry as-is. An LLM can suggest:

- "Add a chamfer here to reduce support requirement"
- "Split this into two parts with an assembly joint to avoid overhangs"
- "This hole diameter is 2.0 mm — FDM typically needs 2.2 mm minimum for a clean bore at 0.4 mm nozzle"

These are design-level interventions, not geometric measurements.

**5. Contextual tolerance advice**

An LLM trained on manufacturing knowledge can contextualise tolerances:

> "You requested a press fit between these two cylinders. Current gap is 0.05 mm, which is below typical FDM variance (~0.2 mm). I will adjust the cutter to 0.25 mm clearance."

A threshold checker can only compare against a fixed number with no understanding of the assembly context.

**6. Natural-language repair instructions**

When a fix cannot be automated, a deterministic tool returns an error code. An LLM can produce step-by-step repair instructions in plain language that a non-expert can follow inside Blender.

**7. Process selection guidance**

> "This part has 0.5 mm features and a 30 mm overhanging arm. FDM at 0.4 mm nozzle is risky here. Resin or a split-print approach would be more reliable."

No threshold checker has this judgement about process trade-offs.

### Combined architecture (recommended)

The most robust approach uses both layers together:

1. **Deterministic layer** — runs fast, produces exact measurements for all checks. Always runs first.
2. **LLM layer** — receives the deterministic report as context, interprets it, prioritises issues, suggests design changes, and explains trade-offs in natural language.

```
User prompt → model actions → deterministic check → structured report
                                                            ↓
                                              LLM interprets + proposes fixes
                                                            ↓
                                              User confirms → remediation actions
```

The deterministic checks provide **ground truth**; the LLM provides **judgement and guidance**.

### Summary table

| Capability | Deterministic | LLM |
|------------|:---:|:---:|
| Exact measurements | ✓ | — |
| Pass/fail per rule | ✓ | — |
| Fast, repeatable | ✓ | — |
| Intent inference | — | ✓ |
| Priority reasoning across warnings | — | ✓ |
| Design-for-manufacturing suggestions | — | ✓ |
| Contextual tolerance advice | — | ✓ |
| Process selection guidance | — | ✓ |
| Plain-language repair steps | — | ✓ |
| Multi-constraint trade-off explanation | — | ✓ |

---

## Integration with BlenderGPT

## Recommended Flow

1. Execute model-generated edit actions.
2. Run manufacturability checks on target mesh objects.
3. If `FAIL`:
   - block export by default
   - return actionable issues and suggested fixes
4. If `WARN`:
   - allow continuation with warning summary
5. If `PASS`:
   - proceed to export workflow

## Suggested New Ops

- `check_manufacturability`
- `auto_fix_manufacturability` (optional, guarded)

## UI Ideas

- Add a "Check Printability" button in BlenderGPT panel.
- Show compact status (`PASS/WARN/FAIL`) with expandable details.
- Offer "Apply safe fixes" for warnings.

## Limitations

- This is geometric verification, not a full slicer simulation.
- Final print success still depends on machine calibration, material, orientation, supports, and slicer settings.
- Checks should be treated as strong preflight validation, not absolute guarantee.

## MVP Scope (Recommended)

Implement these first for immediate value:

1. Manifold/watertight check
2. Min wall thickness check
3. Overhang risk check
4. Build volume fit
5. Basic report output

Then expand with self-intersection detection, bed stability scoring, and guided auto-fixes.
