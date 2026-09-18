import bpy

class MMT_PT_Orientation(bpy.types.Panel):
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
        operator = column.operator("mmt.oriented", icon='GROUP_BONE')
        operator.max_length = settings.max_length
        operator.original_shape = settings.original_shape
        operator.oriented_shape = settings.oriented_shape
