import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _interface as interface
from . import _properties as properties

def register():
    # shared addon preferences...
    register_class(properties.MMT_PG_UtilitiesDefaults)
    register_class(properties.MMT_AP_UtilitiesPreferences)
    # apply meshes...
    register_class(operators.MMT_OT_UtilitiesApply)
    bpy.types.VIEW3D_MT_object_apply.append(operators.add_apply_operator)
    # clean meshes...
    register_class(operators.MMT_OT_UtilitiesClean)
    bpy.types.VIEW3D_MT_object_apply.append(operators.add_clean_operator)
    # invokes an operator as though it was called from the 3D viewport...
    register_class(operators.MMT_OT_UtilitiesInvoke)

def unregister():
    # invokes an operator as though it was called from the 3D viewport...
    unregister_class(operators.MMT_OT_UtilitiesInvoke)
    # clean meshes...
    bpy.types.VIEW3D_MT_object_apply.remove(operators.add_clean_operator)
    unregister_class(operators.MMT_OT_UtilitiesClean)
    # apply meshes...
    bpy.types.VIEW3D_MT_object_apply.remove(operators.add_apply_operator)
    unregister_class(operators.MMT_OT_UtilitiesApply)
    # shared addon preferences...
    unregister_class(properties.MMT_AP_UtilitiesPreferences)
    unregister_class(properties.MMT_PG_UtilitiesDefaults)
