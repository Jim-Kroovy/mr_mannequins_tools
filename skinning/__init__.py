import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _interface as interface

def register():
    # weight meshes...
    register_class(operators.MMT_OT_Weight)
    bpy.types.VIEW3D_MT_paint_weight.append(operators.add_weight_operator)
    # socket/unsocket bone meshes...
    register_class(operators.MMT_OT_Socket)
    bpy.types.VIEW3D_MT_object_apply.append(operators.add_socket_operator)

def unregister():
    # socket/unsocket bone meshes...
    bpy.types.VIEW3D_MT_object_apply.remove(operators.add_socket_operator)
    unregister_class(operators.MMT_OT_Socket)
    # weight meshes...
    bpy.types.VIEW3D_MT_paint_weight.remove(operators.add_weight_operator)
    unregister_class(operators.MMT_OT_Weight)
