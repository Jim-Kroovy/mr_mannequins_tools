import bpy

from bpy.props import EnumProperty, FloatProperty, StringProperty

from .. import utilities

def get_original_shape(self):
    # stored by identifier so adding/removing shape files can't remap it onto another shape...
    return next((i[4] for i in utilities.functions.get_shape_items(self, bpy.context) if i[0] == self.original_identifier), 0)

def set_original_shape(self, value):
    self.original_identifier = next((i[0] for i in utilities.functions.get_shape_items(self, bpy.context) if i[4] == value), 'NONE')

def get_oriented_shape(self):
    return next((i[4] for i in utilities.functions.get_shape_items(self, bpy.context) if i[0] == self.oriented_identifier), 0)

def set_oriented_shape(self, value):
    self.oriented_identifier = next((i[0] for i in utilities.functions.get_shape_items(self, bpy.context) if i[4] == value), 'NONE')

class MMT_PG_OrientationSettings(bpy.types.PropertyGroup):

    max_length: FloatProperty(
        name="Max Length", description="Clamp oriented armature bones down to this length if they would otherwise be longer. 0 to disable.",
        default=0.1, min=0.0
        )

    # empty until the operator has actually run... ("NONE" is a deliberate choice)...
    original_identifier: StringProperty(default="", options={'HIDDEN'})

    oriented_identifier: StringProperty(default="", options={'HIDDEN'})

    original_shape: EnumProperty(
        name="Original Shape", description="Custom shape for the original armatures bones.",
        items=utilities.functions.get_shape_items, get=get_original_shape, set=set_original_shape)

    oriented_shape: EnumProperty(
        name="Oriented Shape", description="Custom shape for the oriented armatures bones.",
        items=utilities.functions.get_shape_items, get=get_oriented_shape, set=set_oriented_shape)
