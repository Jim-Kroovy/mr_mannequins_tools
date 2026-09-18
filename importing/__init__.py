import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _properties as properties

def register():
    # import asset properties... (must be registered in dependency order)...
    register_class(properties.MMT_PG_ImportFBX)
    register_class(properties.MMT_PG_Orientation)
    register_class(properties.MMT_PG_Retargeting)
    register_class(properties.MMT_PG_Cleaning)
    register_class(properties.MMT_PG_Import)
    # compatible FBX import...
    register_class(operators.MMT_OT_Import)
    bpy.types.TOPBAR_MT_file_import.append(operators.add_import_operator)

def unregister():
    # compatible FBX import...
    bpy.types.TOPBAR_MT_file_import.remove(operators.add_import_operator)
    unregister_class(operators.MMT_OT_Import)
    # import asset properties...
    unregister_class(properties.MMT_PG_Import)
    unregister_class(properties.MMT_PG_Cleaning)
    unregister_class(properties.MMT_PG_Retargeting)
    unregister_class(properties.MMT_PG_Orientation)
    unregister_class(properties.MMT_PG_ImportFBX)
