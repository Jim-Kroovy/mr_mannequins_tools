import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _properties as properties

def register():
    # import asset properties... (must be registered in dependency order)...
    register_class(properties.MMT_PG_ImportingFBX)
    register_class(properties.MMT_PG_ImportingOrientation)
    register_class(properties.MMT_PG_ImportingRetargeting)
    register_class(properties.MMT_PG_ImportingCleanup)
    register_class(properties.MMT_PG_ImportingSettings)
    # compatible FBX import...
    register_class(operators.MMT_OT_ImportingFBX)
    bpy.types.TOPBAR_MT_file_import.append(operators.add_import_operator)

def unregister():
    # compatible FBX import...
    bpy.types.TOPBAR_MT_file_import.remove(operators.add_import_operator)
    unregister_class(operators.MMT_OT_ImportingFBX)
    # import asset properties...
    unregister_class(properties.MMT_PG_ImportingSettings)
    unregister_class(properties.MMT_PG_ImportingCleanup)
    unregister_class(properties.MMT_PG_ImportingRetargeting)
    unregister_class(properties.MMT_PG_ImportingOrientation)
    unregister_class(properties.MMT_PG_ImportingFBX)
