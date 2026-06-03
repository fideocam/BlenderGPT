import bpy

from .operators import ADDON_ID


def _status_line(g: bpy.types.PropertyGroup) -> str:
    if g.busy:
        return (g.status or "Calling Ollama…").strip()
    return (g.status or "").strip()


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

        layout.separator()
        layout.prop(g, "prompt", text="")

        row = layout.row(align=True)
        if g.busy:
            row.alignment = "RIGHT"
            row.operator("blender_gpt.stop", text="Stop", icon="CANCEL")
        else:
            row.alignment = "RIGHT"
            row.operator("blender_gpt.send", text="Ask BlenderGPT", icon="PLAY")

        status = _status_line(g)
        if status:
            stat_row = row.row(align=True)
            stat_row.enabled = False
            stat_row.label(
                text=status if len(status) <= 140 else status[:137] + "…",
                icon="TIME" if g.busy else "INFO",
            )

        layout.separator()
        layout.label(text="Response:", icon="TEXT")
        if g.response:
            box = layout.box()
            for line in g.response.split("\n")[:40]:
                box.label(text=line)
            if g.response.count("\n") >= 40:
                box.label(text="…")
        else:
            layout.label(text="(reply appears here)", icon="INFO")
        layout.prop(g, "response", text="")

        layout.separator()
        footer = layout.row(align=True)
        footer.operator(
            "blender_gpt.print",
            text="Prepare for Print",
            icon="EXPORT",
        )
        footer.operator(
            "preferences.addon_show", text="Settings", icon="PREFERENCES"
        ).module = ADDON_ID


def register():
    bpy.utils.register_class(VIEW3D_PT_blender_gpt)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_blender_gpt)
