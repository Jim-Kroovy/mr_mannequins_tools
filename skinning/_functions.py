import bpy
import math

from mathutils import Vector, Euler

from .. import utilities
from . import _debug

def get_weighted_groups(armature, mesh):
    # another simple function to return bone existing and weight valid vertex groups...
    existing = [g for g in mesh.vertex_groups if g.name in armature.data.bones]
    weighted = [g for g in existing if any(vg.group == g.index and vg.weight > 0.0 for v in mesh.data.vertices for vg in v.groups)]
    return existing, weighted

def set_mesh_origin(mesh, location):
    # compute the shift from current origin to new origin in local mesh space...
    rot_scale_inv = mesh.matrix_world.to_3x3().inverted()
    delta_local = rot_scale_inv @ (Vector(location) - mesh.matrix_world.to_translation())
    # offset all vertices and shape key data to maintain world positions...
    shapes = mesh.data.shape_keys.key_blocks if mesh.data.shape_keys else []
    for v in mesh.data.vertices:
        v.co -= delta_local
        for shape in shapes:
            shape.data[v.index].co -= delta_local
    # move the object's world origin to the new location...
    world_mat = mesh.matrix_world.copy()
    world_mat.translation = Vector(location)
    mesh.matrix_world = world_mat
    bpy.context.view_layer.update()

def set_socketed_meshes(selection, suffices=True):
    """attach single weighted meshes to bones (apply rotation for editing)..."""
    # save our current mode... (if there is no contextual object then we must be in object mode)...
    last_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    selected = [o for o in bpy.context.selected_objects] if bpy.context.object else []
    active = bpy.context.view_layer.objects.active
    # make sure nothing is selected...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    # save the 3D cursors current location...
    cursor = bpy.context.scene.cursor.location.copy()
    # bones need to be at rest while we read their head/matrix_local and apply transforms off them...
    armatures = {m.object for mesh in selection if mesh.type == 'MESH' for m in mesh.modifiers if m.type == 'ARMATURE' and m.object}
    for armature in armatures:
        armature.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    try:
        # for each mesh...
        for mesh in [o for o in selection if o.type == 'MESH']:
            # detect the armature from the first valid armature modifier...
            armature = next((m.object for m in mesh.modifiers if m.type == 'ARMATURE' and m.object), None)
            if armature:
                # if there is only one vertex group weighted to the armature...
                _, weighted = get_weighted_groups(armature, mesh)
                if len(weighted) == 1:
                    group = weighted[0]
                    # we can get the bone...
                    bone = armature.data.bones.get(group.name)
                    # select the mesh...
                    mesh.select_set(True)
                    # remove the armature modifiers...
                    for mod in [m for m in mesh.modifiers if m.type == 'ARMATURE']:
                        mesh.modifiers.remove(mod)
                    # remove the vertex group...
                    mesh.vertex_groups.remove(group)
                    # set the meshes origin to the bones head...
                    set_mesh_origin(mesh, bone.head_local)
                    # then set the parenting...
                    mesh.parent = armature
                    mesh.parent_type = 'BONE'
                    mesh.parent_bone = bone.name
                    # remove bone length from location...
                    mesh.location = Vector((0.0, -bone.length, 0.0))
                    # and set rotation to inverse bone space...
                    mesh.rotation_euler = bone.matrix_local.inverted().to_euler()
                    # and apply rotations...
                    utilities.functions.set_mesh_transforms(mesh, False, True, False)
                    # aaaand set the name... (unless it already ends with the bone name)...
                    if suffices and not mesh.name.endswith("_" + bone.name):
                        mesh.name = mesh.name + "_" + bone.name
                    # deselect the mesh for the next iteration...
                    mesh.select_set(False)
    finally:
        for armature in armatures:
            armature.data.pose_position = 'POSE'
        bpy.context.view_layer.update()
    # return the 3D cursor to wherever it was...
    bpy.context.scene.cursor.location = cursor
    # reselect anything we deselected...
    bpy.ops.object.select_all(action='DESELECT')
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = active
    # then return our mode to whatever it was...
    bpy.ops.object.mode_set(mode=last_mode)

def set_unsocketed_meshes(selection, suffices=False):
    """convert attached meshes to single weighted meshes (apply rotation and location for editing)..."""
    # save our current mode... (if there is no contextual object then we must be in object mode)...
    last_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    selected = [o for o in bpy.context.selected_objects] if bpy.context.object else []
    active = bpy.context.view_layer.objects.active
    # make sure nothing is selected...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    # for each mesh parented by bone to an armature...
    statics = [o for o in selection if o.type == 'MESH' and o.parent and o.parent.type == 'ARMATURE' and o.parent_type == 'BONE' and o.parent_bone in o.parent.data.bones]
    # bones need to be at rest while we clear their bone-parenting and apply transforms off them...
    armatures = {m.parent for m in statics}
    for armature in armatures:
        armature.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    try:
        for mesh in statics:
            armature = mesh.parent
            # select it...
            mesh.select_set(True)
            # create/get the vertex group by the parent bone name...
            group = mesh.vertex_groups.get(mesh.parent_bone)
            if not group:
                group = mesh.vertex_groups.new(name=mesh.parent_bone)
            # get all of it's indices and assign them to the vertex group...
            indices = [v.index for v in mesh.data.vertices]
            group.add(indices, 1.0, 'REPLACE')
            # add an armature modifier...
            mod = mesh.modifiers.new(name="Armature", type='ARMATURE')
            mod.object = armature
            # save a copy of the current world matrix...
            world_matrix = mesh.matrix_world.copy()
            # clear the parenting...
            mesh.parent, mesh.parent_type, mesh.parent_bone = None, 'OBJECT', ""
            # set the world matrix back and update the view layer...
            mesh.matrix_world = world_matrix
            bpy.context.view_layer.update()
            # and apply their locations and rotations... (ignore scale for now)...
            utilities.functions.set_mesh_transforms(mesh, True, True, False)
            if suffices and mesh.name.endswith("_" + group.name):
                mesh.name = mesh.name[:-len("_" + group.name)]
    finally:
        for armature in armatures:
            armature.data.pose_position = 'POSE'
        bpy.context.view_layer.update()
    # reselect anything we deselected...
    bpy.ops.object.select_all(action='DESELECT')
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = active
    # then return our mode to whatever it was...
    bpy.ops.object.mode_set(mode=last_mode)

def set_weight_spherical(meshes, shape='SPHERE', mode='REPLACE', offset=(0.0, 0.0, 0.0), rotate=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0), weight=0.5, origin=0.5, blend=0.5, taper=0.0, invert=False, remove=False, show=False):
    # remove any previous debug shapes before the new run...
    _debug.remove_debug_shapes()
    for mesh in meshes:
        # find the meshes selected armature...
        armature = None
        for mod in mesh.modifiers:
            if mod.type == 'ARMATURE':
                if mod.object and mod.object.select_get():
                    armature = mod.object
                    break
        if armature:
            bones = [pb.bone for pb in armature.pose.bones if pb.select]
            for bb in bones:
                # if the vertex group doesn't exist, create it...
                group = mesh.vertex_groups.get(bb.name)
                if not group:
                    group = mesh.vertex_groups.new(name=bb.name)
                # compute radii from bone length...
                length, _ = utilities.functions.get_distance_direction(bb.head_local, bb.tail_local)
                inner, outer = (length * 0.5) * blend, length * 0.5
                # so the sphere origin is simply the origin fraction along Y plus the offset...
                shape_origin = Vector((0.0, length * origin, 0.0)) + Vector(offset)
                # build the inverse rotation to apply rotate to the sphere...
                rot_inv = Euler(rotate).to_matrix().inverted()
                sx, sy, sz = scale[0], scale[1], scale[2]
                # precompute the inverse bone matrix to transform verts into bone local space...
                bone_inv = bb.matrix_local.inverted()
                # add a debug sphere per bone showing the inner and outer bounds...
                if show:
                    world_origin = armature.matrix_world @ (bb.matrix_local @ shape_origin)
                    world_rot = armature.matrix_world.to_3x3() @ bb.matrix_local.to_3x3() @ Euler(rotate).to_matrix()
                    if shape == 'CUBE':
                        _debug.add_debug_cube("DEBUG_outer_" + bb.name, world_origin, Vector(scale) * outer, world_rot, taper=taper)
                        _debug.add_debug_cube("DEBUG_inner_" + bb.name, world_origin, Vector(scale) * inner, world_rot, taper=taper)
                    else:
                        _debug.add_debug_sphere("DEBUG_outer_" + bb.name, world_origin, Vector(scale) * outer, world_rot)
                        _debug.add_debug_sphere("DEBUG_inner_" + bb.name, world_origin, Vector(scale) * inner, world_rot)
                # iterate over non-hidden vertices...
                for v in mesh.data.vertices:
                    if v.hide:
                        continue
                    # transform the vertex into bone local space...
                    v_local = bone_inv @ v.co
                    # get delta from sphere origin in bone local space...
                    delta = v_local - shape_origin
                    # rotate delta by inverse rotate to orient the ellipsoid...
                    rot_delta = rot_inv @ delta
                    # divide by scale to get ellipsoid distance...
                    scaled = Vector((
                        rot_delta.x / sx if sx else 0.0,
                        rot_delta.y / sy if sy else 0.0,
                        rot_delta.z / sz if sz else 0.0,
                    ))
                    if shape == 'CUBE':
                        if taper > 0.0:
                            # taper XZ cross-section based on Y position: full at +Y, reduced at -Y...
                            t = (outer - scaled.y) / (2.0 * outer) if outer else 0.0
                            t_blended = max(1.0 - taper * (1.0 - t), 0.0001)
                            distance = max(abs(scaled.x) / t_blended, abs(scaled.z) / t_blended, abs(scaled.y))
                        else:
                            distance = max(abs(scaled.x), abs(scaled.y), abs(scaled.z))
                    else:
                        distance = scaled.length
                    # compute weight from distance...
                    if distance > inner and distance < outer:
                        alpha = utilities.functions.get_mapped_range(distance, inner, outer, 1.0, 0.0, clamp=True, default=1.0)
                    else:
                        alpha = 1.0 if distance <= inner else 0.0
                    factor = 1.0 - alpha if invert else alpha
                    if weight * factor > 0.00001:
                        group.add([v.index], weight * factor, mode)
                    elif remove:
                        group.remove([v.index])
    # register cleanup handler after all work is done...
    if show:
        # skip flag stops depsgraph updates from vertex group changes removing shapes early...
        prefs = utilities.functions.get_addon_preferences(bpy.context)
        prefs.debug_skip[0] = True
        if _debug.debug_shape_cleanup not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(_debug.debug_shape_cleanup)

def set_weight_cylindrical(meshes, shape='SPHERE', mode='REPLACE', offset=(0.0, 0.0, 0.0), rotate=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0), weight=0.5, origin=0.5, blend=0.5, taper=0.0, invert=False, remove=False, show=False):
    # remove any previous debug shapes before the new run...
    _debug.remove_debug_shapes()
    for mesh in meshes:
        # find the meshes selected armature...
        armature = None
        for mod in mesh.modifiers:
            if mod.type == 'ARMATURE':
                if mod.object and mod.object.select_get():
                    armature = mod.object
                    break
        if armature:
            bones = [pb.bone for pb in armature.pose.bones if pb.select]
            for bb in bones:
                # if the vertex group doesn't exist, create it...
                group = mesh.vertex_groups.get(bb.name)
                if not group:
                    group = mesh.vertex_groups.new(name=bb.name)
                # compute radii and half length from bone length...
                length, _ = utilities.functions.get_distance_direction(bb.head_local, bb.tail_local)
                inner, outer = (length * 0.5) * blend, length * 0.5
                half_length = length * 0.5
                # the cylinder center is along bone Y at the origin fraction plus offset...
                shape_origin = Vector((0.0, length * origin, 0.0)) + Vector(offset)
                # build the inverse rotation so the cylinder axis aligns to Y in rot space...
                rot_inv = Euler(rotate).to_matrix().inverted()
                sx, sy, sz = scale[0], scale[1], scale[2]
                # precompute the inverse bone matrix to transform verts into bone local space...
                bone_inv = bb.matrix_local.inverted()
                # add debug shapes per bone showing the inner and outer bounds...
                if show:
                    world_origin = armature.matrix_world @ (bb.matrix_local @ shape_origin)
                    world_rot = armature.matrix_world.to_3x3() @ bb.matrix_local.to_3x3() @ Euler(rotate).to_matrix()
                    cyl_outer = Vector((sx * outer, sy * half_length, sz * outer))
                    cyl_inner = Vector((sx * inner, sy * half_length, sz * inner))
                    if shape == 'CAPSULE':
                        # open cylinder body tapered by taper...
                        _debug.add_debug_cylinder("DEBUG_outer_" + bb.name + "_body", world_origin, cyl_outer, world_rot, cap_ends=False, taper=taper)
                        _debug.add_debug_cylinder("DEBUG_inner_" + bb.name + "_body", world_origin, cyl_inner, world_rot, cap_ends=False, taper=taper)
                        world_y = world_rot @ Vector((0.0, 1.0, 0.0))
                        cap_offset = world_y * (half_length * sy)
                        bot = 1.0 - taper
                        # top cap (+Y tail) scales down with taper, bottom cap (-Y head) stays full...
                        _debug.add_debug_sphere("DEBUG_outer_" + bb.name + "_top", world_origin + cap_offset, Vector((sx * outer * bot, outer * bot, sz * outer * bot)), world_rot, hemisphere='TOP')
                        _debug.add_debug_sphere("DEBUG_outer_" + bb.name + "_bot", world_origin - cap_offset, Vector((sx * outer, outer, sz * outer)), world_rot, hemisphere='BOT')
                        _debug.add_debug_sphere("DEBUG_inner_" + bb.name + "_top", world_origin + cap_offset, Vector((sx * inner * bot, inner * bot, sz * inner * bot)), world_rot, hemisphere='TOP')
                        _debug.add_debug_sphere("DEBUG_inner_" + bb.name + "_bot", world_origin - cap_offset, Vector((sx * inner, inner, sz * inner)), world_rot, hemisphere='BOT')
                    else:
                        # flat ended cylinder with optional taper on cylinder shape...
                        debug_taper = taper if shape == 'CYLINDER' else 0.0
                        _debug.add_debug_cylinder("DEBUG_outer_" + bb.name, world_origin, cyl_outer, world_rot, cap_ends=True, taper=debug_taper)
                        _debug.add_debug_cylinder("DEBUG_inner_" + bb.name, world_origin, cyl_inner, world_rot, cap_ends=True, taper=debug_taper)
                # iterate over non-hidden vertices...
                for v in mesh.data.vertices:
                    if v.hide:
                        continue
                    # transform vertex to bone local space and get delta from cylinder origin...
                    v_local = bone_inv @ v.co
                    delta = v_local - shape_origin
                    # apply inverse rotation then divide by scale to get scaled space position...
                    rot_delta = rot_inv @ delta
                    xs = rot_delta.x / sx if sx else 0.0
                    ys = rot_delta.y / sy if sy else 0.0
                    zs = rot_delta.z / sz if sz else 0.0
                    # 2D radial distance from the cylinder axis in scaled space...
                    radial = math.sqrt(xs * xs + zs * zs)
                    radial_outer, radial_inner = outer, inner
                    if shape == 'CAPSULE':
                        # beyond the ends use 3D distance from end cap centers, Y not scaled so caps stay spherical...
                        if ys > half_length:
                            # top cap (+Y tail) scales down with taper...
                            radial = math.sqrt(xs * xs + (rot_delta.y - half_length * sy) ** 2 + zs * zs)
                            bot = 1.0 - taper
                            radial_outer = outer * bot
                            radial_inner = inner * bot
                        elif ys < -half_length:
                            # bottom cap (-Y head) stays full size...
                            radial = math.sqrt(xs * xs + (rot_delta.y + half_length * sy) ** 2 + zs * zs)
                        elif taper > 0.0:
                            # tapered cylinder body...
                            t = (half_length - ys) / (half_length * 2) if half_length else 0.0
                            t_blended = 1.0 - taper * (1.0 - t)
                            radial_outer = outer * t_blended
                            radial_inner = inner * t_blended
                    else:
                        # flat ends: vertices outside the axial extent get no weight...
                        if abs(ys) > half_length:
                            if remove:
                                group.remove([v.index])
                            continue
                        # cylinder only: apply taper from full radius at tail to reduced at head...
                        if shape == 'CYLINDER' and taper > 0.0:
                            t = (half_length - ys) / (half_length * 2) if half_length else 0.0
                            t_blended = 1.0 - taper * (1.0 - t)
                            radial_outer = outer * t_blended
                            radial_inner = inner * t_blended
                    # compute weight from radial distance...
                    if radial > radial_inner and radial < radial_outer:
                        alpha = utilities.functions.get_mapped_range(radial, radial_inner, radial_outer, 1.0, 0.0, clamp=True, default=1.0)
                    else:
                        alpha = 1.0 if radial <= radial_inner else 0.0
                    factor = 1.0 - alpha if invert else alpha
                    if weight * factor > 0.00001:
                        group.add([v.index], weight * factor, mode)
                    elif remove:
                        group.remove([v.index])
    if show:
        prefs = utilities.functions.get_addon_preferences(bpy.context)
        prefs.debug_skip[0] = True
        if _debug.debug_shape_cleanup not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(_debug.debug_shape_cleanup)
