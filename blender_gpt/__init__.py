"""
BlenderGPT — Ollama-backed assistant with scene context and safe JSON-driven edits.
Install: copy the `blender_gpt` folder into Blender's addons directory, or zip it and use Preferences → Add-ons → Install.
"""

import bpy

from . import preferences, operators, ui

bl_info = {
    "name": "BlenderGPT",
    "author": "Raino Annala",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > BlenderGPT",
    "description": "Chat with a local Ollama model using scene and selection context; optional structured scene edits",
    "category": "Interface",
}


def register():
    preferences.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    preferences.unregister()
