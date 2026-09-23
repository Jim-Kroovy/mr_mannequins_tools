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
    # swap weighted meshes onto whichever rigging/oriented armature was selected while weight painting, and back again...
    functions.set_paint_subscribed()
    bpy.app.handlers.load_post.append(functions.set_paint_loaded)

def unregister():
    # swap weighted meshes onto whichever rigging/oriented armature was selected while weight painting, and back again -
    # matched by name rather than by the current function object, since a dev-reload can swap that object out from under
    # a handler thats still sat in blenders own list from before the reload, breaking a plain identity based remove()...
    for handler in list(bpy.app.handlers.load_post):
        if getattr(handler, '__name__', None) == 'set_paint_loaded' and getattr(handler, '__module__', None) == functions.__name__:
            bpy.app.handlers.load_post.remove(handler)
    bpy.msgbus.clear_by_owner(functions.weight_paint_owner)
    # socket/unsocket bone meshes...
    bpy.types.VIEW3D_MT_object_apply.remove(operators.add_socket_operator)
    unregister_class(operators.MMT_OT_Socket)
    # weight meshes...
    bpy.types.VIEW3D_MT_paint_weight.remove(operators.add_weight_operator)
    unregister_class(operators.MMT_OT_Weight)
