import bpy

from bpy.utils import (register_class, unregister_class)
from bpy.props import (PointerProperty)

from . import _functions as functions
from . import _operators as operators
from . import _properties as properties
from . import _interface as interface

def register():
    # per bone translation retargeting mode...
    register_class(properties.MMT_PG_RetargetingMapping)
    register_class(properties.MMT_PG_RetargetingBone)
    bpy.types.PoseBone.mmt = PointerProperty(type=properties.MMT_PG_RetargetingBone)
    register_class(operators.MMT_OT_RetargetingAddMapping)
    register_class(operators.MMT_OT_RetargetingRemoveMapping)
    register_class(interface.MMT_PT_RetargetingItem)
    register_class(interface.MMT_PT_RetargetingBone)
    # set the retarget pose, apply it, or retarget actions, all in the pose apply menu... (set and apply share an operator so apply can reuse the last target)
    register_class(operators.MMT_OT_RetargetingPose)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_pose_operator)
    register_class(operators.MMT_OT_RetargetingActions)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_action_operator)
    # keyframe cleaning...
    register_class(operators.MMT_OT_RetargetingKeyframes)
    bpy.types.DOPESHEET_MT_key.append(operators.add_fcurve_operator)

def unregister():
    # keyframe cleaning...
    bpy.types.DOPESHEET_MT_key.remove(operators.add_fcurve_operator)
    unregister_class(operators.MMT_OT_RetargetingKeyframes)
    # remove retarget pose/apply/action operators...
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_action_operator)
    unregister_class(operators.MMT_OT_RetargetingActions)
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_pose_operator)
    unregister_class(operators.MMT_OT_RetargetingPose)
    # per bone translation retargeting mode...
    unregister_class(interface.MMT_PT_RetargetingBone)
    unregister_class(interface.MMT_PT_RetargetingItem)
    unregister_class(operators.MMT_OT_RetargetingRemoveMapping)
    unregister_class(operators.MMT_OT_RetargetingAddMapping)
    del bpy.types.PoseBone.mmt
    unregister_class(properties.MMT_PG_RetargetingBone)
    unregister_class(properties.MMT_PG_RetargetingMapping)
    # armature compatibility...
