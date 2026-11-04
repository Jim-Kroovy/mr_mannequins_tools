import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _interface as interface


def _restore_paint_swaps():
    # extension install unregisters with bpy.data restricted... (only this cleanup waits, handlers and rna still go now)
    if not hasattr(bpy.data, 'objects'):
        return 0.1
    swaps = functions.get_paint_swaps()
    if swaps:
        functions.set_paint_left(swaps)
    return None

def register():
    # weight meshes...
    register_class(operators.MMT_OT_SkinningWeight)
    bpy.types.VIEW3D_MT_paint_weight.append(operators.add_weight_operator)
    # socket/unsocket bone meshes...
    register_class(operators.MMT_OT_SkinningSocket)
    bpy.types.VIEW3D_MT_object_apply.append(operators.add_socket_operator)
    # swap weighted meshes onto whichever trio armature was active while painting and back... (matched by name, a dev reload can swap the function object)
    for handler in list(bpy.app.handlers.depsgraph_update_post):
        if getattr(handler, '__name__', None) == 'update_paint_mode' and getattr(handler, '__module__', None) == functions.__name__:
            bpy.app.handlers.depsgraph_update_post.remove(handler)
    bpy.app.handlers.depsgraph_update_post.append(functions.update_paint_mode)
    for handler in list(bpy.app.handlers.load_post):
        if getattr(handler, '__name__', None) == 'set_paint_loaded' and getattr(handler, '__module__', None) == functions.__name__:
            bpy.app.handlers.load_post.remove(handler)
    bpy.app.handlers.load_post.append(functions.set_paint_loaded)

def unregister():
    # swap weighted meshes onto whichever rigging/oriented/original armature was active while weight painting, and back again...
    for handler in list(bpy.app.handlers.depsgraph_update_post):
        if getattr(handler, '__name__', None) == 'update_paint_mode' and getattr(handler, '__module__', None) == functions.__name__:
            bpy.app.handlers.depsgraph_update_post.remove(handler)
    for handler in list(bpy.app.handlers.load_post):
        if getattr(handler, '__name__', None) == 'set_paint_loaded' and getattr(handler, '__module__', None) == functions.__name__:
            bpy.app.handlers.load_post.remove(handler)
    # handlers are gone now, so it's safe to restore any session left active (eg. disabling the addon mid weight paint) without the handler firing back in behind us...
    functions.weight_paint_busy = False
    if hasattr(bpy.data, 'objects'):
        _restore_paint_swaps()
    elif not bpy.app.timers.is_registered(_restore_paint_swaps):
        bpy.app.timers.register(_restore_paint_swaps, first_interval=0.0)
    functions.tracked_armature = None
    # socket/unsocket bone meshes...
    bpy.types.VIEW3D_MT_object_apply.remove(operators.add_socket_operator)
    unregister_class(operators.MMT_OT_SkinningSocket)
    # weight meshes...
    bpy.types.VIEW3D_MT_paint_weight.remove(operators.add_weight_operator)
    unregister_class(operators.MMT_OT_SkinningWeight)
