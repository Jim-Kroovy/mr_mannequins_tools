from . import _functions as functions
from . import _properties as properties
from . import _operators as operators
from bpy.utils import register_class, unregister_class
import bpy

def register():
    # everything stays in F3 search, split/transfer/redirect also go in the pose mode apply menu once registered...
    register_class(properties.MMT_PG_KeyframingTransferEntry)
    register_class(properties.MMT_PG_KeyframingTransfer)
    register_class(properties.MMT_PG_KeyframingRedirectDirection)
    register_class(properties.MMT_PG_KeyframingRedirectAction)
    register_class(properties.MMT_PG_KeyframingRedirect)
    register_class(properties.MMT_PG_KeyframingLocomotionSwing)
    register_class(properties.MMT_PG_KeyframingLocomotion)
    register_class(properties.MMT_PG_KeyframingLoopingBone)
    register_class(properties.MMT_PG_KeyframingLooping)
    register_class(properties.MMT_PG_KeyframingSplitEntry)
    register_class(properties.MMT_PG_KeyframingSplit)
    register_class(operators.MMT_OT_KeyframingTransfer)
    register_class(operators.MMT_OT_KeyframingRedirect)
    register_class(operators.MMT_OT_KeyframingLocomotion)
    register_class(operators.MMT_OT_KeyframingOscillation)
    register_class(operators.MMT_OT_KeyframingSplit)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_keyframing_operators)

def unregister():
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_keyframing_operators)
    unregister_class(operators.MMT_OT_KeyframingSplit)
    unregister_class(operators.MMT_OT_KeyframingOscillation)
    unregister_class(operators.MMT_OT_KeyframingLocomotion)
    unregister_class(operators.MMT_OT_KeyframingRedirect)
    unregister_class(operators.MMT_OT_KeyframingTransfer)
    unregister_class(properties.MMT_PG_KeyframingSplit)
    unregister_class(properties.MMT_PG_KeyframingSplitEntry)
    unregister_class(properties.MMT_PG_KeyframingLooping)
    unregister_class(properties.MMT_PG_KeyframingLoopingBone)
    unregister_class(properties.MMT_PG_KeyframingLocomotion)
    unregister_class(properties.MMT_PG_KeyframingLocomotionSwing)
    unregister_class(properties.MMT_PG_KeyframingRedirect)
    unregister_class(properties.MMT_PG_KeyframingRedirectAction)
    unregister_class(properties.MMT_PG_KeyframingRedirectDirection)
    unregister_class(properties.MMT_PG_KeyframingTransfer)
    unregister_class(properties.MMT_PG_KeyframingTransferEntry)
