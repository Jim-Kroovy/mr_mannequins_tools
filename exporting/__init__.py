import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _properties as properties

def register():
    # export asset properties... (must be registered in dependency order)...
    register_class(properties.MMT_PG_ExportFBX)
    register_class(properties.MMT_PG_Clean)
    register_class(properties.MMT_PG_Meshes)
    register_class(properties.MMT_PG_Action)
    register_class(properties.MMT_PG_Export)
    # compatible FBX export...
    register_class(operators.MMT_OT_Export)
    bpy.types.TOPBAR_MT_file_export.append(operators.add_export_operator)

def unregister():
    # compatible FBX export...
    bpy.types.TOPBAR_MT_file_export.remove(operators.add_export_operator)
    unregister_class(operators.MMT_OT_Export)
    # export asset properties...
    unregister_class(properties.MMT_PG_Export)
    unregister_class(properties.MMT_PG_Action)
    unregister_class(properties.MMT_PG_Meshes)
    unregister_class(properties.MMT_PG_Clean)
    unregister_class(properties.MMT_PG_ExportFBX)
