import bpy

from .operators import resolve_addon_id


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

        addon_id = resolve_addon_id(context)
        prefs = context.preferences.addons.get(addon_id)
        if prefs is None:
            layout.label(text="Enable BlenderGPT in Preferences.", icon="ERROR")
            layout.label(text="Get Extensions or Add-ons, then enable.", icon="INFO")
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
        resp_header = layout.row(align=True)
        resp_header.label(text="Response", icon="TEXT")
        tools = resp_header.row(align=True)
        tools.alignment = "RIGHT"
        has_response = bool((g.response or "").strip())
        tools.enabled = has_response
        tools.operator("blender_gpt.copy_response", text="Copy", icon="DUPLICATE")
        tools.operator("blender_gpt.copy_actions_json", text="Copy JSON", icon="COPYDOWN")
        tools.operator(
            "blender_gpt.open_response_text",
            text="Text Editor",
            icon="TEXT",
        )

        if not has_response:
            layout.label(text="(reply appears here)", icon="INFO")
        else:
            box = layout.box()
            col = box.column(align=True)
            col.enabled = True
            col.prop(g, "response", text="")
            col.label(text="Tip: use Copy / Copy JSON, or open in Text Editor.", icon="INFO")

        layout.separator()
        footer = layout.row(align=True)
        footer.operator(
            "blender_gpt.print",
            text="Prepare for Print",
            icon="EXPORT",
        )
        footer.operator(
            "preferences.addon_show", text="Settings", icon="PREFERENCES"
        ).module = addon_id


def register():
    bpy.utils.register_class(VIEW3D_PT_blender_gpt)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_blender_gpt)
