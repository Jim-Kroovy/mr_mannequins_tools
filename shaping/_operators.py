import bpy

from bpy.props import (EnumProperty, BoolProperty, StringProperty, FloatProperty, IntProperty)

from . import _functions as functions
from . import _interface as interface

class MMT_OT_Mirror(bpy.types.Operator):
    """Mirrors shape keys over the X axis by left/right affix"""
    bl_idname = "mmt.mirror"
    bl_label = "Mirror Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    basis: StringProperty(
        name="Basis", description="The shape key to use as the basis for blended mirroring.",
        default="")

    prefix: StringProperty(
        name="Prefix", description="Only mirror shape keys using this prefix",
        default="")

    active: BoolProperty(
        name="Only Active", description="Only mirror the active shape key.",
        default=True)

    selected: BoolProperty(
        name="Only Selected", description="Only mirror selected vertices.",
        default=False)

    method: EnumProperty(
        name="Method", description="How to mirror the shape key.",
        items=[
            ('BLEND', "Blend", "Clear opposing sides with a blend over the the X axis", 0),
            ('FLIP', "Flip", "Flip the shape key over the X axis without any blending", 1),
            ], default='BLEND')

    blend: FloatProperty(
        name="Blend", description="Central blending distance for mirrored shape keys.",
        min=0.0, default=0.1, subtype="DISTANCE")

    def invoke(self, context, event):
        if context.active_object and context.active_object.data.shape_keys:
            self.basis = context.active_object.data.shape_keys.key_blocks[0].name
        return self.execute(context)

    def draw(self, context):
        interface.draw_mirror_settings(self, context)

    def execute(self, context):
        selection = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
        functions.set_mirrored_shapes(selection, self.basis, self.prefix, self.active, self.selected, self.method, self.blend)
        return {'FINISHED'}

def add_mirror_operator(self, context):
    self.layout.separator()
    row = self.layout.row()
    row.operator(MMT_OT_Mirror.bl_idname, icon='MOD_MIRROR')
    row.enabled = True if context.object and context.object.type == 'MESH' and context.object.data.shape_keys else False

class MMT_OT_Blend(bpy.types.Operator):
    """Blends shape keys by vertex selection"""
    bl_idname = "mmt.blend"
    bl_label = "Blend Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    prefix: StringProperty(
        name="Prefix", description="Only blend shape keys using this prefix",
        default="")

    active: BoolProperty(
        name="Only Active", description="Only blend the active shape key.",
        default=True)

    blend: FloatProperty(
        name="Blend", description="The distance used to blend out selected verts.",
        min=0.0, default=0.1, subtype="DISTANCE")

    into: StringProperty(
        name="Shape", description="The shape key to blend into.",
        default="")

    alpha: FloatProperty(
        name="Alpha", description="Maximum interpolation to the target shape.",
        min=0.0, max=1.0, default=1.0)

    steps: IntProperty(
        name="Smooth", description="Number of smoothing iterations.",
        min=0, max=20, default=0)

    def invoke(self, context, event):
        if context.active_object and context.active_object.data.shape_keys:
            self.into = context.active_object.data.shape_keys.key_blocks[0].name
        return self.execute(context)

    def draw(self, context):
        interface.draw_blend_settings(self, context)

    def execute(self, context):
        selection = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
        if not self.into:
            self.report({'WARNING'}, "No shape key chosen to blend into.")
            return {'FINISHED'}
        functions.set_blended_shapes(selection, self.prefix, self.active, self.blend, self.into, self.alpha, self.steps)
        return {'FINISHED'}

def add_blend_operator(self, context):
    row = self.layout.row()
    row.operator(MMT_OT_Blend.bl_idname, icon='MOD_SMOOTH')
    row.enabled = True if context.object and context.object.type == 'MESH' and context.object.data.shape_keys else False

class MMT_OT_Extract(bpy.types.Operator):
    """Extracts shape keys on the edited mesh into their own separate meshes"""
    bl_idname = "mmt.extract"
    bl_label = "Extract Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    active: BoolProperty(
        name="Only Active", description="Only extract the active shape key.",
        default=True)

    def execute(self, context):
        functions.get_shape_meshes(context.object, active=self.active)
        return {'FINISHED'}

def add_extract_operator(self, context):
    row = self.layout.row()
    row.operator(MMT_OT_Extract.bl_idname, icon='SHAPEKEY_DATA')
    row.enabled = True if context.object and context.object.type == 'MESH' and context.object.data.shape_keys else False
