import bpy

from bpy.utils import (register_class, unregister_class)
from bpy.props import (PointerProperty)

from . import _functions as functions
from . import _operators as operators
from . import _properties as properties
from . import _interface as interface

def register():
    # per bone translation retargeting mode...
    register_class(properties.MMT_PG_Mapping)
    register_class(properties.MMT_PG_Bone)
    bpy.types.PoseBone.mmt = PointerProperty(type=properties.MMT_PG_Bone)
    register_class(operators.MMT_OT_AddMapping)
    register_class(operators.MMT_OT_RemoveMapping)
    register_class(interface.MMT_PT_RetargetingItem)
    register_class(interface.MMT_PT_RetargetingBone)
    # set the retarget pose, apply it (meshes/rest/actions), or retarget actions from another armature - all in Pose Mode's Apply menu... (set/apply share one operator so apply can reuse sets last target)...
    register_class(operators.MMT_OT_Pose)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_pose_operator)
    register_class(operators.MMT_OT_Actions)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_action_operator)
    # keyframe cleaning...
    register_class(operators.MMT_OT_FCurve)
    bpy.types.DOPESHEET_MT_key.append(operators.add_fcurve_operator)

def unregister():
    # keyframe cleaning...
    bpy.types.DOPESHEET_MT_key.remove(operators.add_fcurve_operator)
    unregister_class(operators.MMT_OT_FCurve)
    # remove retarget pose/apply/action operators...
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_action_operator)
    unregister_class(operators.MMT_OT_Actions)
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_pose_operator)
    unregister_class(operators.MMT_OT_Pose)
    # per bone translation retargeting mode...
    unregister_class(interface.MMT_PT_RetargetingBone)
    unregister_class(interface.MMT_PT_RetargetingItem)
    unregister_class(operators.MMT_OT_RemoveMapping)
    unregister_class(operators.MMT_OT_AddMapping)
    del bpy.types.PoseBone.mmt
    unregister_class(properties.MMT_PG_Bone)
    unregister_class(properties.MMT_PG_Mapping)
    # armature compatibility...
