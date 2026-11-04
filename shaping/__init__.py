import bpy

from bpy.utils import (register_class, unregister_class)

from . import _functions as functions
from . import _operators as operators
from . import _interface as interface

def register():
    # mirror meshes...
    register_class(operators.MMT_OT_ShapingMirror)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(operators.add_mirror_operator)
    # blend meshes...
    register_class(operators.MMT_OT_ShapingBlend)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(operators.add_blend_operator)
    # extract meshes...
    register_class(operators.MMT_OT_ShapingExtract)
    bpy.types.VIEW3D_MT_edit_mesh_vertices.append(operators.add_extract_operator)

def unregister():
    # extract meshes...
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(operators.add_extract_operator)
    unregister_class(operators.MMT_OT_ShapingExtract)
    # mirror meshes...
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(operators.add_mirror_operator)
    unregister_class(operators.MMT_OT_ShapingMirror)
    # blend meshes...
    bpy.types.VIEW3D_MT_edit_mesh_vertices.remove(operators.add_blend_operator)
    unregister_class(operators.MMT_OT_ShapingBlend)
