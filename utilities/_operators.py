import bpy

from bpy.props import (BoolProperty, StringProperty)

from . import _functions as functions
from . import _interface as interface

class MMT_OT_Apply(bpy.types.Operator):
    """Applies modifiers and transforms on meshes while preserving shape keys"""
    bl_idname = "mmt.apply"
    bl_label = "Apply Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    original: BoolProperty(
        name="Keep Original", description="Keep original meshes.",
        default=True)

    modifiers: BoolProperty(
        name="Modifiers", description="Apply viewport active modifiers while preserving shape keys.",
        default=True)

    parent: BoolProperty(
        name="Parent", description="Clear parent keeping world position.",
        default=False)

    location: BoolProperty(
        name="Location", description="Apply location transform.",
        default=False)

    rotation: BoolProperty(
        name="Rotation", description="Apply rotation transform.",
        default=False)

    scale: BoolProperty(
        name="Scale", description="Apply scale transform.",
        default=False)

    def draw(self, context):
        interface.draw_apply_settings(self)

    def execute(self, context):
        selection = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
        functions.set_applied_meshes(selection, self.original, self.modifiers, self.parent, self.location, self.rotation, self.scale)
        return {'FINISHED'}

def add_apply_operator(self, context):
    self.layout.separator()
    self.layout.operator(MMT_OT_Apply.bl_idname, icon='CHECKMARK')

class MMT_OT_Clean(bpy.types.Operator):
    """Cleans shape keys, vertex groups and materials by prefix."""
    bl_idname = "mmt.clean"
    bl_label = "Clean Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    prefix: StringProperty(
        name="Clean Prefix", description="The prefix used to clean shape keys, vertex groups and materials",
        default="DEL_")

    shapes: BoolProperty(
        name="Clean Shapes", description="Remove shape keys with the clean prefix.",
        default=False)

    groups: BoolProperty(
        name="Clean Groups", description="Remove vertex groups with the clean prefix.",
        default=False)

    materials: BoolProperty(
        name="Clean Materials", description="Remove materials with the clean prefix.",
        default=False)

    def draw(self, context):
        interface.draw_clean_settings(self)

    def execute(self, context):
        selection = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
        functions.set_cleaned_meshes(selection, self.prefix, self.shapes, self.groups, self.materials)
        return {'FINISHED'}

def add_clean_operator(self, context):
    self.layout.operator(MMT_OT_Clean.bl_idname, icon='TRASH')

class MMT_OT_Invoke(bpy.types.Operator):
    """Opens a menu as though called from the 3D viewport, so operators run from it show their redo panel there instead of wherever it was actually opened from."""
    bl_idname = "mmt.invoke"
    bl_label = ""
    bl_options = {'INTERNAL'}

    menu: StringProperty()

    def execute(self, context):
        # wm.call_menu nested inside an operators execute() crashes Blender outright in background mode...
        if bpy.app.background:
            self.report({'WARNING'}, "Not available in background mode")
            return {'CANCELLED'}
        for area in context.window.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        override = {'window' : context.window, 'screen' : context.screen, 'area' : area, 'region' : region}
                        with context.temp_override(**override):
                            bpy.ops.wm.call_menu(name=self.menu)
                        return {'FINISHED'}
        self.report({'WARNING'}, "No 3D Viewport found")
        return {'CANCELLED'}
