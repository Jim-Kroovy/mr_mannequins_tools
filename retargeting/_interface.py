import bpy

def draw_bone_retargeting(layout, pose_bone):
    layout.use_property_split = True
    layout.prop(pose_bone.mmt, 'rotation')
    layout.prop(pose_bone.mmt, 'translation')
    layout.prop(pose_bone.mmt, 'mirror')
    layout.operator("mmt.set_below", icon='TRIA_DOWN')

class MMT_PT_RetargetingItem(bpy.types.Panel):
    bl_idname = "MMT_PT_RetargetingItem"
    bl_label = "Retargeting"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Item"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(obj and obj.type == 'ARMATURE' and obj.mode == 'POSE' and context.active_pose_bone)

    def draw(self, context):
        draw_bone_retargeting(self.layout, context.active_pose_bone)

class MMT_PT_RetargetingBone(bpy.types.Panel):
    bl_idname = "MMT_PT_RetargetingBone"
    bl_label = "Retargeting"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'bone'

    @classmethod
    def poll(cls, context):
        obj = context.object
        # only in pose mode - the retargeting mode lives on the pose bone, which edit mode has no equivalent of...
        return bool(obj and obj.type == 'ARMATURE' and obj.mode == 'POSE' and context.active_pose_bone)

    def draw(self, context):
        draw_bone_retargeting(self.layout, context.active_pose_bone)
