import bpy

from bpy.utils import (register_class, unregister_class)
from bpy.props import (PointerProperty)

from . import _functions as functions
from . import _operators as operators
from . import _properties as properties
from . import _interface as interface

def register():
    # per bone translation retargeting mode...
    register_class(properties.MMT_PG_Bone)
    bpy.types.PoseBone.mmt = PointerProperty(type=properties.MMT_PG_Bone)
    register_class(operators.MMT_OT_SetBelow)
    register_class(interface.MMT_PT_RetargetingItem)
    register_class(interface.MMT_PT_RetargetingBone)
    # retarget the active armature or actions from another armature in Pose Mode's Apply menu...
    register_class(operators.MMT_OT_Retarget)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_armature_operator)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_actions_operator)
    # keyframe cleaning...
    register_class(operators.MMT_OT_FCurve)
    bpy.types.DOPESHEET_MT_key.append(operators.add_fcurve_operator)

def unregister():
    # keyframe cleaning...
    bpy.types.DOPESHEET_MT_key.remove(operators.add_fcurve_operator)
    unregister_class(operators.MMT_OT_FCurve)
    # remove retarget armature and action operators...
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_actions_operator)
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_armature_operator)
    unregister_class(operators.MMT_OT_Retarget)
    # per bone translation retargeting mode...
    unregister_class(interface.MMT_PT_RetargetingBone)
    unregister_class(interface.MMT_PT_RetargetingItem)
    unregister_class(operators.MMT_OT_SetBelow)
    del bpy.types.PoseBone.mmt
    unregister_class(properties.MMT_PG_Bone)
    # armature compatibility...
