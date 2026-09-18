import bpy
import bmesh
import math

from mathutils import Matrix

from .. import utilities

def remove_debug_shapes():
    # scope the search to the debug collection rather than all scene objects...
    debug_collection = bpy.data.collections.get("Debug")
    if not debug_collection:
        return
    for obj in [o for o in debug_collection.objects if o.get("Debug Type") == "Weight Shape"]:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    try:
        bpy.app.handlers.depsgraph_update_post.remove(debug_shape_cleanup)
    except ValueError:
        pass

def debug_shape_cleanup(scene, depsgraph):
    prefs = utilities.functions.get_addon_preferences(bpy.context)
    # skip the depsgraph update caused by the operator itself...
    if prefs.debug_skip[0]:
        prefs.debug_skip[0] = False
        return
    # the next update is from user interaction after the redo panel closed...
    remove_debug_shapes()

def add_debug_cube(name, location, scale, rotation, taper=0.0):
    # remove any existing debug cube with this name...
    existing = bpy.data.objects.get(name)
    if existing:
        data = existing.data
        bpy.data.objects.remove(existing, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    # scale the +Y face vertices toward center based on taper (tail end)...
    if taper > 0.0:
        for v in bm.verts:
            if v.co.y > 0.99:
                v.co.x *= (1.0 - taper)
                v.co.z *= (1.0 - taper)
    cube_mesh = bpy.data.meshes.new(name)
    bm.to_mesh(cube_mesh)
    bm.free()
    # get or create the debug collection and link it to the scene root if new...
    debug_collection = bpy.data.collections.get("Debug")
    if not debug_collection:
        debug_collection = bpy.data.collections.new("Debug")
        bpy.context.scene.collection.children.link(debug_collection)
    # create and link the object into the debug collection...
    obj = bpy.data.objects.new(name, cube_mesh)
    debug_collection.objects.link(obj)
    obj.display_type = 'WIRE'
    obj.location = location
    obj.scale = scale
    obj.rotation_euler = rotation.to_euler()
    # flag the object for cleanup by the depsgraph handler...
    obj["Debug Type"] = "Weight Shape"

def add_debug_cylinder(name, location, scale, rotation, cap_ends=True, taper=False):
    # remove any existing debug cylinder with this name...
    existing = bpy.data.objects.get(name)
    if existing:
        data = existing.data
        bpy.data.objects.remove(existing, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    # create cylinder geometry directly so no mode switch is needed...
    bm = bmesh.new()
    # taper makes a cone with base at -Y (head) and tip at +Y (tail) after rotation...
    bmesh.ops.create_cone(bm, cap_ends=cap_ends, cap_tris=False, segments=16, radius1=1.0, radius2=1.0 - taper, depth=2.0)
    # rotate depth axis from Z to Y to match bone primary axis...
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, 'X'), verts=bm.verts)
    cylinder_mesh = bpy.data.meshes.new(name)
    bm.to_mesh(cylinder_mesh)
    bm.free()
    # get or create the debug collection and link it to the scene root if new...
    debug_collection = bpy.data.collections.get("Debug")
    if not debug_collection:
        debug_collection = bpy.data.collections.new("Debug")
        bpy.context.scene.collection.children.link(debug_collection)
    # create and link the object into the debug collection...
    obj = bpy.data.objects.new(name, cylinder_mesh)
    debug_collection.objects.link(obj)
    obj.display_type = 'WIRE'
    obj.location = location
    obj.scale = scale
    obj.rotation_euler = rotation.to_euler()
    # flag the object for cleanup by the depsgraph handler...
    obj["Debug Type"] = "Weight Shape"

def add_debug_sphere(name, location, scale, rotation, hemisphere=None):
    # remove any existing debug sphere with this name...
    existing = bpy.data.objects.get(name)
    if existing:
        data = existing.data
        bpy.data.objects.remove(existing, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    # create sphere geometry directly so no mode switch is needed...
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    # rotate poles from Z to Y to match bone primary axis...
    bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(-90), 3, 'X'), verts=bm.verts)
    # optionally cut to a hemisphere by deleting the unwanted half...
    if hemisphere == 'TOP':
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y < -0.0001], context='VERTS')
    elif hemisphere == 'BOT':
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.y > 0.0001], context='VERTS')
    sphere_mesh = bpy.data.meshes.new(name)
    bm.to_mesh(sphere_mesh)
    bm.free()
    # get or create the debug collection and link it to the scene root if new...
    debug_collection = bpy.data.collections.get("Debug")
    if not debug_collection:
        debug_collection = bpy.data.collections.new("Debug")
        bpy.context.scene.collection.children.link(debug_collection)
    # create and link the object into the debug collection...
    obj = bpy.data.objects.new(name, sphere_mesh)
    debug_collection.objects.link(obj)
    obj.display_type = 'WIRE'
    obj.location = location
    obj.scale = scale
    obj.rotation_euler = rotation.to_euler()
    # flag the object for cleanup by the depsgraph handler...
    obj["Debug Type"] = "Weight Shape"
