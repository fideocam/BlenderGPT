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
        default="llama3.2",
        description="Ollama model name",
    )
    num_ctx: bpy.props.IntProperty(
        name="Context length",
        default=8192,
        min=512,
        max=131072,
        description="Optional num_ctx for /api/chat; 0 uses Ollama default",
    )
    max_context_chars: bpy.props.IntProperty(
        name="Max scene context (chars)",
        default=120_000,
        min=2000,
        max=500_000,
        description="Truncate serialized scene digest beyond this size",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "base_url")
        layout.prop(self, "model")
        layout.prop(self, "num_ctx")
        layout.prop(self, "max_context_chars")


def register():
    bpy.utils.register_class(BlenderGPTAddonPreferences)


def unregister():
    bpy.utils.unregister_class(BlenderGPTAddonPreferences)
