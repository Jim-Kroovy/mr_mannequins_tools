import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _interface as interface

def register():
    register_class(operators.MMT_OT_Template)
    register_class(interface.MMT_MT_Templates)
    bpy.types.VIEW3D_MT_add.append(interface.add_templates_menu)

def unregister():
    bpy.types.VIEW3D_MT_add.remove(interface.add_templates_menu)
    unregister_class(interface.MMT_MT_Templates)
    unregister_class(operators.MMT_OT_Template)
