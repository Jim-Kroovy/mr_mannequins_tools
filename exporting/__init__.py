import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _properties as properties

def register():
    # export asset properties... (must be registered in dependency order)...
    register_class(properties.MMT_PG_ExportingFBX)
    register_class(properties.MMT_PG_ExportingCleanup)
    register_class(properties.MMT_PG_ExportingMeshes)
    register_class(properties.MMT_PG_ExportingAction)
    register_class(properties.MMT_PG_ExportingSettings)
    # compatible FBX export...
    register_class(operators.MMT_OT_ExportingFBX)
    bpy.types.TOPBAR_MT_file_export.append(operators.add_export_operator)

def unregister():
    # compatible FBX export...
    bpy.types.TOPBAR_MT_file_export.remove(operators.add_export_operator)
    unregister_class(operators.MMT_OT_ExportingFBX)
    # export asset properties...
    unregister_class(properties.MMT_PG_ExportingSettings)
    unregister_class(properties.MMT_PG_ExportingAction)
    unregister_class(properties.MMT_PG_ExportingMeshes)
    unregister_class(properties.MMT_PG_ExportingCleanup)
    unregister_class(properties.MMT_PG_ExportingFBX)
