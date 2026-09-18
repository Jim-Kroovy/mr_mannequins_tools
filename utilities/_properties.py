import bpy

from bpy.props import (StringProperty, BoolVectorProperty, CollectionProperty, IntProperty)

class MMT_PG_Defaults(bpy.types.PropertyGroup):
    # name holds the rigging type identifier (eg. "OPPOSABLE"), json its last used naming/colors/shapes...
    json: StringProperty(default="")

class MMT_AP_Preferences(bpy.types.AddonPreferences):
    # this files own package is always "<root>.utilities" - stripping the trailing segment gives the addons real registered name, whether installed as a legacy addon ("mr_mannequins_tools") or as an extension ("bl_ext.<repo>.mr_mannequins_tools")...
    bl_idname = __package__.rsplit('.', 1)[0]
    # custom shape items from file paths...
    shape_items = []
    # color items from theme palettes...
    color_items = []
    # saved template items from the templates library folder...
    template_items = []
    # armature items for the retarget operator's target-armature picker...
    target_items = []
    # currently unused bone type enum...
    bone_items = [
        ('NONE', "None", "No type", 0),
        ('ROOT', "Root", "A parent shared generally by targets", 1),
        ('FLOOR', "Floor", "A floor vector that cannot be passed through", 2),
        ('ORIGIN', "Origin", "A parent shared by various bones", 3),
        ('ENDING', "Ending", "A bone at the end of a chain", 4),
        ('TARGET', "Target", "A target for other bones", 5),
        ('PARENT', "Parent", "A parent of target and motor bones", 6),
        ('POLE', "Pole", "A pole vector for chains", 7),
        ('VECTOR', "Vector", "A chain vector for chains", 8),
        ('FORWARD', "Forward", "A bone for FK control", 9),
        ('INVERSE', "Inverse", "A bone in an IK chain", 10),
        ('STRETCH', "Stretch", "A bone in an IK chain that stretches", 11),
        ('ROTATOR', "Rotator", "A bone to drive rotation of other bones", 12),
        ('LOCATOR', "Locator", "A bone to drive location of other bones", 13),
        ('SCALER', "Scaler", "A bone to drive scale of other bones", 14),
        ('CONTROL', "Control", "A bone to control transform channels of other bones", 15),
        ]

    # skip flag for the debug shape cleanup depsgraph handler...
    debug_skip: BoolVectorProperty(size=1, default=(False,))

    # last used naming/colors/shapes settings per rigging type, keyed by type identifier...
    defaults: CollectionProperty(type=MMT_PG_Defaults)

    # last used import/export settings, serialized to json so the whole property tree doesn't need duplicating here...
    import_settings: StringProperty(default="")

    export_settings: StringProperty(default="")

    # copied rigging modules (type/settings pairs), serialized to json for the copy/paste rigging operators...
    rigging_clipboard: StringProperty(default="")

    # the addon version these preferences were last saved under, so register() can detect a version change and drop stale settings...
    version: StringProperty(default="")


class MMT_PG_Armature(bpy.types.PropertyGroup):

    module: IntProperty(name="Active Module")
