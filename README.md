# BlenderGPT

Blender add-on in the spirit of **ArchiGPT**: chat with a local **Ollama** model using a **scene digest** and **selection**, then optionally apply **small JSON-defined edits** (primitives, transforms, delete, rename, smooth shading, a subset of modifiers).

## Install

1. Copy the `blender_gpt` folder into Blender’s `scripts/addons` directory, **or** zip the `blender_gpt` folder and use **Edit → Preferences → Add-ons → Install…**.
2. Enable **Interface → BlenderGPT**.
3. In add-on preferences, set **Ollama base URL** (default `http://127.0.0.1:11434`) and **Model** (e.g. `llama3.2`).
4. In the **3D Viewport**, open the sidebar (**N**) → **BlenderGPT** tab.

## Requirements

- Blender **4.0+** (tested against current API patterns).
- [Ollama](https://ollama.com) running locally with your chosen model pulled.

## Usage

- **Test Ollama** checks `/api/tags`.
- Type a prompt, **Ask BlenderGPT**. The add-on sends the system prompt, your text, and a text digest of the scene (truncated by **Max scene context** in preferences).
- If the model ends its reply with a JSON object `{"actions":[...]}`, those actions are validated and applied on the main thread (one undo step).
- **Stop** sets a cancel flag (the HTTP client may not interrupt immediately).

For a **3D-print-oriented task list** and how it maps to JSON actions, see **[process.md](process.md)** in the repository root.

## Capabilities (geometry)

- **Primitives:** cube, sphere, **cylinder**, cone, plane, **torus**, **ico sphere**, **Suzanne** (`MONKEY`), plus optional `scale` / cube `size`.
- **Holes / cuts:** `boolean_difference` (and union/intersect) between two mesh objects; optional `delete_cutter`. Position a cutter with `set_transform` first, or use **`groove_box_cut`** for an axis-aligned slot.
- **Skeletons:** `create_armature` builds a **simple chain of connected bones** along one axis (useful as a rig stub, not a full biped solver).

Complex surfacing (fillets, CNC threads, medical skeletons from scan data, etc.) still needs manual modeling or custom scripts beyond this allowlist.

## Safety

Only the operations implemented in `apply_actions.py` run. Unknown `op` values are skipped. Prefer a dedicated `.blend` when experimenting. Booleans need mostly manifold geometry; expect failures on bad meshes.

## Tests

**Fast (no Blender):** parses JSON action lists and prompt wiring.

```bash
pip install -r requirements-dev.txt
# or: pip install -e ".[dev]"
pytest
```

**Integration (real `bpy`):** requires the `blender` executable on `PATH`.

```bash
blender --background --python tests/blender_e2e.py
# or
pytest tests/test_blender_subprocess.py
```

## License

MIT (aligned with the ArchiGPT / Archi ecosystem).
