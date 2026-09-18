# legacy metadata...
bl_info = {
    "name": "Mr Mannequins Tools",
    "author": "James Goldsworthy (Jim Kroovy)",
    "version": (5, 0, 0),
    "blender": (5, 0, 0),
    "location": "3D Viewport > Pose",
    "description": "Rigging, mesh and export tools for (almost) any character.",
    "category": "Armatures",
}

import bpy

from . import utilities, rigging, retargeting, orientation, shaping, skinning, importing, exporting, templates

def register():
    # load shared addon preferences then domain subpackages in dependency order... (rigging first)...
    utilities.register()
    orientation.register()
    rigging.register()
    retargeting.register()
    shaping.register()
    skinning.register()
    importing.register()
    exporting.register()
    templates.register()
    # a version change means a new install landed over an old one (preferences survive that, unlike a full remove/reinstall), so drop settings that might not match the new schema...
    prefs = utilities.functions.get_addon_preferences(bpy.context)
    version = ".".join(str(n) for n in bl_info["version"])
    if prefs.version != version:
        prefs.import_settings, prefs.export_settings, prefs.version = "", "", version

def unregister():
    # reverse of registration order...
    templates.unregister()
    exporting.unregister()
    importing.unregister()
    skinning.unregister()
    shaping.unregister()
    retargeting.unregister()
    rigging.unregister()
    orientation.unregister()
    utilities.unregister()
