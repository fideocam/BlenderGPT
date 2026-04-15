import bpy

from .operators import ADDON_ID


class VIEW3D_PT_blender_gpt(bpy.types.Panel):
    bl_label = "BlenderGPT"
    bl_idname = "VIEW3D_PT_blender_gpt"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderGPT"

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        wm = context.window_manager
        g = wm.blender_gpt

        prefs = context.preferences.addons.get(ADDON_ID)
        if prefs is None:
            layout.label(text="Enable the add-on in Preferences.", icon="ERROR")
            return

        row = layout.row(align=True)
        row.operator("blender_gpt.ping", text="Test Ollama", icon="CHECKMARK")
        row.operator("preferences.addon_show", text="Settings", icon="PREFERENCES").module = ADDON_ID

        layout.separator()
        layout.prop(g, "prompt", text="")
        row = layout.row(align=True)
        row.operator("blender_gpt.send", text="Ask BlenderGPT", icon="PLAY")
        stop = row.operator("blender_gpt.stop", text="Stop", icon="CANCEL")
        stop.enabled = g.busy

        if g.busy:
            layout.label(text="Working…", icon="TIME")

        if g.status:
            box = layout.box()
            box.label(text="Status:", icon="INFO")
            for line in (g.status[:2000]).split("\n")[:12]:
                box.label(text=line)

        layout.separator()
        layout.label(text="Response:")
        col = layout.column(align=True)
        col.scale_y = 0.9
        col.prop(g, "response", text="")


def register():
    bpy.utils.register_class(VIEW3D_PT_blender_gpt)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_blender_gpt)
