import bpy

from bpy.props import (EnumProperty, BoolProperty, FloatProperty, FloatVectorProperty)

from . import _functions as functions
from . import _interface as interface

class MMT_OT_Weight(bpy.types.Operator):
    """Weights vertices around bones using an adjustable shape"""
    bl_idname = "mmt.weight"
    bl_label = "Weight Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    shape: EnumProperty(
        name="Shape", description="What shape of weighting to use.",
        items=[
            ('SPHERE', "Sphere", "Add weight using a sphere", 0),
            ('CYLINDER', "Cylinder", "Add weight using a cylinder", 1),
            ('CAPSULE', "Capsule", "Add weight using a cylinder with rounded ends", 2),
            ('CUBE', "Cube", "Add weight using a box shape", 3),
            ], default='SPHERE')

    mode: EnumProperty(
        name="Mode", description="How to affect values.",
        items=[
            ('REPLACE', "Replace", "Replace existing values", 0),
            ('ADD', "Add", "Add to existing values", 1),
            ('SUBTRACT', "Subtract", "Subtract from existing values", 2),
            ], default='REPLACE')

    offset: FloatVectorProperty(
        name="Offset", description="3D location of the weight shape",
        size=3, default=(0.0, 0.0, 0.0), subtype='TRANSLATION')

    rotate: FloatVectorProperty(
        name="Rotate", description="3D rotation of the weight shape",
        size=3, default=(0.0, 0.0, 0.0), subtype='EULER')

    scale: FloatVectorProperty(
        name="Scale", description="3D scale of the weight shape",
        size=3, default=(1.0, 1.0, 1.0), subtype='XYZ')

    weight: FloatProperty(
        name="Weight", description="Weight to apply to vertices",
        min=0.0, max=1.0, default=0.5)

    origin: FloatProperty(
        name="Origin", description="Origin of the shape along the bone.",
        min=0.0, max=1.0, default=0.5)

    blend: FloatProperty(
        name="Blend", description="Factor to begin blending bone weight from.",
        min=0.0, max=1.0, default=0.5)

    taper: FloatProperty(
        name="Taper", description="Factor to taper the end of the shape.",
        min=0.0, max=1.0, default=0.0)

    invert: BoolProperty(
        name="Invert", description="Invert the weighting",
        default=False)

    remove: BoolProperty(
        name="Remove", description="Remove unaffected values",
        default=False)

    show: BoolProperty(
        name="Show", description="Show the shape as wire frame meshes",
        default=False)

    def draw(self, context):
        interface.draw_weight_settings(self)

    def execute(self, context):
        selection = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
        if self.shape in ['SPHERE', 'CUBE']:
            functions.set_weight_spherical(selection, self.shape, self.mode, self.offset, self.rotate, self.scale, self.weight, self.origin, self.blend, self.taper, self.invert, self.remove, self.show)
        elif self.shape in ['CYLINDER', 'CAPSULE']:
            functions.set_weight_cylindrical(selection, self.shape, self.mode, self.offset, self.rotate, self.scale, self.weight, self.origin, self.blend, self.taper, self.invert, self.remove, self.show)
        return {'FINISHED'}

def add_weight_operator(self, context):
    self.layout.operator(MMT_OT_Weight.bl_idname, icon='WPAINT_HLT')

class MMT_OT_Socket(bpy.types.Operator):
    """Attaches single weighted skeletal meshes to their armature to make them correctly oriented socket meshes, or detaches them back to skeletal meshes"""
    bl_idname = "mmt.socket"
    bl_label = "Socket Meshes"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode", description="Whether to socket or unsocket the selected meshes.",
        items=[('SOCKET', "Socket", ""), ('UNSOCKET', "Unsocket", "")], default='SOCKET')

    suffices: BoolProperty(
        name="Suffices", description="Add or strip the parent bone's name as a suffix on the mesh name.",
        default=False)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'suffices', text="Add Suffices" if self.mode == 'SOCKET' else "Remove Suffices")

    def execute(self, context):
        selection = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
        if self.mode == 'SOCKET':
            functions.set_socketed_meshes(selection, self.suffices)
        else:
            functions.set_unsocketed_meshes(selection, self.suffices)
        return {'FINISHED'}

def add_socket_operator(self, context):
    self.layout.separator()
    op = self.layout.operator(MMT_OT_Socket.bl_idname, text="Socket Meshes", icon='LINKED')
    op.mode, op.suffices = 'SOCKET', False
    op = self.layout.operator(MMT_OT_Socket.bl_idname, text="Unsocket Meshes", icon='UNLINKED')
    op.mode, op.suffices = 'UNSOCKET', False
