import bpy

from .. import utilities

from . import _functions as functions

class MMT_PT_OrientationPanel(bpy.types.Panel):
    bl_idname = "MMT_PT_Orientation"
    bl_label = "Orientation"
    bl_order = 0
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(obj and obj.type == 'ARMATURE' and hasattr(obj.data, 'mmt'))

    def draw(self, context):
        obj = context.object
        settings = obj.data.mmt.orientation
        column = self.layout.column()
        column.use_property_split = True
        column.use_property_decorate = False
        column.prop(settings, 'max_length')
        column.prop(settings, 'original_shape')
        column.prop(settings, 'oriented_shape')
        column.separator()
        operator = column.operator("mmt.oriented", text=functions.get_oriented_label(obj), icon='GROUP_BONE')
        # only pass on what's genuinely been remembered, otherwise let the operator infer it from the bones...
        if settings.original_identifier:
            operator.max_length = settings.max_length
        if utilities.functions.get_available_shape(settings.original_identifier):
            operator.original_shape = settings.original_shape
        if utilities.functions.get_available_shape(settings.oriented_identifier):
            operator.oriented_shape = settings.oriented_shape
