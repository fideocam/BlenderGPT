import bpy


class BlenderGPTAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    base_url: bpy.props.StringProperty(
        name="Ollama base URL",
        default="http://127.0.0.1:11434",
        description="Base URL for Ollama (no trailing slash)",
    )
    model: bpy.props.StringProperty(
        name="Model",
        default="llama3.2:latest",
        description="Ollama model name (must match ollama list, e.g. llama3.2:latest)",
    )
    num_ctx: bpy.props.IntProperty(
        name="Context length (num_ctx)",
        default=0,
        min=0,
        max=262144,
        description=(
            "Passed to Ollama as options.num_ctx. 0 = Ollama chooses at runtime (VRAM-based). "
            "Use Sync context from model to match a 128k/256k model."
        ),
    )
    max_context_chars: bpy.props.IntProperty(
        name="Max scene context (chars)",
        default=48_000,
        min=2000,
        max=500_000,
        description=(
            "Truncate serialized scene digest beyond this size. "
            "Sync from model sets this from num_ctx (~3.5 chars/token, minus prompt reserve)."
        ),
    )
    context_hint: bpy.props.StringProperty(
        name="Context hint",
        default="Use Sync context from model after setting the model name.",
        options={"HIDDEN"},
    )
    request_timeout: bpy.props.IntProperty(
        name="Request timeout (seconds)",
        default=600,
        min=30,
        max=3600,
        description="Max wait for Ollama /api/chat (first run may load the model)",
    )
    auto_wake_ollama: bpy.props.BoolProperty(
        name="Auto-start Ollama",
        default=True,
        description="If Ollama is not running, try to open the Ollama app (macOS) or ollama serve",
    )
    preload_model: bpy.props.BoolProperty(
        name="Preload model on ask",
        default=False,
        description="Extra /api/generate warm-up before chat (doubles load time; usually not needed)",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "base_url")
        layout.prop(self, "model")
        layout.prop(self, "num_ctx")
        layout.prop(self, "max_context_chars")
        layout.prop(self, "request_timeout")
        layout.prop(self, "auto_wake_ollama")
        layout.prop(self, "preload_model")
        if self.context_hint:
            col = layout.column(align=True)
            col.scale_y = 0.8
            for line in self.context_hint.split("\n")[:4]:
                col.label(text=line, icon="INFO")
        layout.separator()
        row = layout.row(align=True)
        row.operator("blender_gpt.sync_context", text="Sync context from model", icon="FILE_REFRESH")
        row.operator("blender_gpt.ping", text="Test connection", icon="CHECKMARK")


def register():
    bpy.utils.register_class(BlenderGPTAddonPreferences)


def unregister():
    bpy.utils.unregister_class(BlenderGPTAddonPreferences)
