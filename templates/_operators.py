import bpy

from bpy.props import (EnumProperty, BoolProperty)

from .. import utilities
from . import _functions as functions

class MMT_OT_Template(bpy.types.Operator):
    """Adds a saved template from the Mr Mannequins template library"""
    bl_idname = "mmt.template"
    bl_label = "Template"
    bl_options = {'REGISTER', 'UNDO'}

    def get_template_items(self, context):
        prefs = utilities.functions.get_addon_preferences(context)
        functions.set_template_items(prefs)
        return prefs.template_items

    template: EnumProperty(
        name="Template", description="The saved template to add.",
        items=get_template_items)

    ignore_armatures: BoolProperty(
        name="Ignore Armatures", description="Don't add the template's armature objects.",
        default=False)

    ignore_meshes: BoolProperty(
        name="Ignore Meshes", description="Don't add the template's mesh objects.",
        default=False)

    ignore_materials: BoolProperty(
        name="Ignore Materials", description="Don't add materials to the template's meshes.",
        default=False)

    ignore_animations: BoolProperty(
        name="Ignore Animations", description="Don't add animation data to the template's armatures.",
        default=False)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.prop(self, 'template')
        col.separator()
        col.prop(self, 'ignore_armatures')
        col.prop(self, 'ignore_meshes')
        col.prop(self, 'ignore_materials')
        col.prop(self, 'ignore_animations')

    def execute(self, context):
        if self.template == 'NONE':
            self.report({'ERROR'}, "No saved templates found.")
            return {'CANCELLED'}
        objects, failure = functions.load_saved_template(
            context, self.template, self.ignore_armatures, self.ignore_meshes,
            self.ignore_materials, self.ignore_animations)
        if failure:
            self.report({'ERROR'}, failure)
            return {'CANCELLED'}
        if not objects:
            self.report({'WARNING'}, "Template added nothing (everything was ignored).")
        return {'FINISHED'}
