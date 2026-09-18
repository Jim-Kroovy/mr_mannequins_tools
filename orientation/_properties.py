import bpy

from bpy.props import EnumProperty, FloatProperty

from .. import utilities


class MMT_PG_Orientation(bpy.types.PropertyGroup):

    max_length: FloatProperty(
        name="Max Length", description="Clamp oriented armature bones down to this length if they would otherwise be longer. 0 to disable.",
        default=0.1, min=0.0
        )

    original_shape: EnumProperty(
        name="Original Shape", description="Custom shape for the original armatures bones.",
        items=utilities.functions.get_shape_items)

    oriented_shape: EnumProperty(
        name="Oriented Shape", description="Custom shape for the oriented armatures bones.",
        items=utilities.functions.get_shape_items)
