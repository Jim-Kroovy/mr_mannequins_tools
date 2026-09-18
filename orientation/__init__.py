from . import _functions as functions
from . import _operators as operators
from . import _properties as properties
from bpy.utils import register_class, unregister_class
import bpy

def register():
    register_class(properties.MMT_PG_Orientation)
    register_class(operators.MMT_OT_Oriented)
    register_class(operators.MMT_OT_Orient)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_oriented_operator)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_orient_operator)

def unregister():
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_orient_operator)
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_oriented_operator)
    unregister_class(operators.MMT_OT_Orient)
    unregister_class(operators.MMT_OT_Oriented)
    unregister_class(properties.MMT_PG_Orientation)
