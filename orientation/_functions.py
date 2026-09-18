import bpy

import math

from mathutils import Vector

from .. import utilities

from .. import skinning

from .. import rigging

from .. import retargeting


def get_bone_chained(bone):
    # if this bone has a parent it could be part of a chain...
    if bone.parent:
        # a symmetric pair bone (eg. the thighs) is always a branch, never a chain continuation...
        if utilities.functions.get_primary_child(bone.parent.children) != bone:
            return False
        # get the distance and direction from the parent to the bone...
        distance, direction = utilities.functions.get_distance_direction(bone.parent.head, bone.head)
        # if there is some distance between them...
        if distance >= 0.0001:
            # get the bones axes...
            bone_axes = rigging.functions.get_bone_axes(bone, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
            # iterate through the parents axes...
            parent_axes = rigging.functions.get_bone_axes(bone.parent, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
            for axis, vector in parent_axes.items():
                # check if the parents axis is pointing towards the bones head... (tight threshold)...
                parent_angle = vector.angle(direction)
                if parent_angle <= math.radians(5):
                    # then if the bones same axis is pointing in the same direction... (loose threshold)...
                    child_angle = bone_axes[axis].angle(vector)
                    if child_angle <= math.radians(45):
                        # this is very likely a chain bone...
                        return True
    return False

def set_bone_parent(armature, hierarchy, name):
    # get the bone and it's parent in the hierarchy armature... (if any)...
    hierarchy_bb = hierarchy.data.bones.get(name)
    armature_eb = armature.data.edit_bones.get(name)
    parent_eb = None
    # while we haven't found a parent bone...
    while hierarchy_bb:
        # if the hierarchy bones parent exists in the armature...
        name = hierarchy_bb.parent.name if hierarchy_bb.parent else ""
        if armature.data.edit_bones.get(name):
            # set it and end the loop...
            parent_eb = armature.data.edit_bones.get(name)
            break
        # else we didn't find a parent so get the next one to check...
        hierarchy_bb = hierarchy_bb.parent
    # then set the parent to the one we found... (if any)...
    armature_eb.parent = parent_eb

def set_bone_orientation(armature, name, orient=None, hierarchy=None):
    # get the edit bone to orient (automatic space uses the paired hierarchy)...
    armature_eb = armature.data.edit_bones.get(name)
    # explicit spaces only ever look at the bone being oriented, never a paired hierarchy armature...
    if orient is not None and orient.space != 'AUTO':
        # use the bones own current local axes for local space...
        if orient.space == 'LOCAL':
            axes = rigging.functions.get_bone_axes(armature_eb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
        # the target bones axes for target space... (check validity before calling this)...
        elif orient.space == 'TARGET':
            target_eb = armature.data.edit_bones.get(orient.target)
            axes = rigging.functions.get_bone_axes(target_eb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
        # and the armatures cardinal axes for armature space...
        elif orient.space == 'ARMATURE':
            axes = {
                '+X' : Vector((1.0, 0.0, 0.0)), '-X' : Vector((-1.0, 0.0, 0.0)),
                '+Y' : Vector((0.0, 1.0, 0.0)), '-Y' : Vector((0.0, -1.0, 0.0)),
                '+Z' : Vector((0.0, 0.0, 1.0)), '-Z' : Vector((0.0, 0.0, -1.0)),
                }
        # set the tail position from the tail direction...
        armature_eb.tail = armature_eb.head + (axes[orient.primary] * armature_eb.length)
        # and align roll to the roll direction...
        armature_eb.align_roll(axes[orient.secondary])
        return
    # automatic orientation needs a hierarchy armature with a matching bone to detect it from...
    hierarchy_eb = hierarchy.data.edit_bones.get(name) if hierarchy else None
    if not hierarchy_eb:
        return
    # check whether this bone is part of a chain...
    is_chained = get_bone_chained(hierarchy_eb)
    # get all of the hierarchy bones cardinal direction vectors...
    axes = rigging.functions.get_bone_axes(hierarchy_eb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
    # and the Y axis can just fallback to armature forward...
    y_axis = Vector((0.0, 1.0, 0.0))
    # if the hierarchy edit bone has children...
    if hierarchy_eb.children:
        # aim at the primary child (excluding symmetric pairs, eg. the thighs), same as the retarget pose logic...
        primary = utilities.functions.get_primary_child(hierarchy_eb.children)
        aim = [primary] if primary else hierarchy_eb.children
        direction = utilities.functions.get_edit_direction(hierarchy_eb, aim)
        if direction:
            y_axis = utilities.functions.get_closest_vector(direction, axes.values())
        # however if this is a chain bone...
        if is_chained:
            # and none of it's children are also detected as chain bones... (then we found a chain end)...
            if not any(get_bone_chained(eb) for eb in hierarchy_eb.children):
                # so derive the Y axis from whichever of the hierarchy bone axes is closest to the parent...
                _, direction = utilities.functions.get_distance_direction(hierarchy_eb.parent.head, hierarchy_eb.head)
                y_axis = utilities.functions.get_closest_vector(direction, axes.values())
    # else if the hierarchy edit bone has a parent...
    elif hierarchy_eb.parent:
        # derive the Y axis from whichever of the hierarchy bone axes is closest to the parent... (inversely)...
        _, direction = utilities.functions.get_distance_direction(hierarchy_eb.head, hierarchy_eb.parent.head)
        y_axis = utilities.functions.get_closest_vector(direction * -1, axes.values())
    # set the new tail location from the Y axis...
    tail = armature_eb.head + (y_axis * hierarchy_eb.length)
    armature_eb.tail = tail
    # and set get the shortest possible aligned roll...
    directions = rigging.functions.get_roll_axes(hierarchy_eb, armature_eb.head, tail)
    armature_eb.roll = rigging.functions.get_shortest_roll(armature_eb, directions.values())
    # if the armature bone has a parent and is detected as part of a chain...
    if armature_eb.parent and is_chained:
        # it's roll should be aligned to it's parent...
        z_axis = utilities.functions.get_closest_vector(armature_eb.parent.z_axis, axes.values())
        armature_eb.align_roll(z_axis)

def add_oriented_bone(oriented, original, name, max_length=None):
    original_eb = original.data.edit_bones.get(name)
    head, tail, roll = original_eb.head, original_eb.tail, original_eb.roll
    # create the bone if it doesn't already exist in the oriented armature...
    oriented_eb = oriented.data.edit_bones.new(name)
    # then set the oriented bones head tail and roll...
    oriented_eb.head, oriented_eb.tail, oriented_eb.roll = head, tail, roll
    # update the oriented armature...
    oriented.update_from_editmode()
    # set parenting from the original hierarchy...
    set_bone_parent(oriented, original, name)
    # update the oriented armature...
    oriented.update_from_editmode()
    # set the bones tail position and roll from the original hierarchy...
    set_bone_orientation(oriented, name, hierarchy=original)
    # update the oriented armature...
    oriented.update_from_editmode()
    # optionally clamp the bones length back down to a sensible maximum, keeping it's direction...
    if max_length is not None and oriented_eb.length > max_length:
        direction = (oriented_eb.tail - oriented_eb.head).normalized()
        oriented_eb.tail = oriented_eb.head + (direction * max_length)
    # add the parent constraints to the originals bones...
    rigging.functions.add_parent_constraints(original, oriented, name, name)
    return oriented_eb

def set_shaped_bones(original, oriented, names, original_shape=None, oriented_shape=None):
    # assigns custom shapes by name onto both armatures at once, original scaled down since it's an overlay...
    shape = utilities.functions.get_shape_mesh(original_shape) if original_shape and original_shape != 'NONE' else None
    for name in names:
        pose_bone = original.pose.bones.get(name)
        if pose_bone:
            pose_bone.custom_shape = shape
            pose_bone.custom_shape_scale_xyz = Vector((0.4, 0.4, 0.4))
    shape = utilities.functions.get_shape_mesh(oriented_shape) if oriented_shape and oriented_shape != 'NONE' else None
    for name in names:
        pose_bone = oriented.pose.bones.get(name)
        if pose_bone:
            pose_bone.custom_shape = shape

def add_oriented_armature(original, max_length=None, original_shape='BALL_FULL', oriented_shape=None, use_actions=False):
    # the bone orientation math below is all in local edit-bone space, but clear the originals own object transform anyway (just in case), restoring it onto the new oriented armature once we're done...
    oriented = None
    stored_transform = utilities.functions.get_stored_transform(original)
    utilities.functions.set_cleared_transform(original)
    bpy.context.view_layer.update()
    try:
        # convert the originals sockets to skeletal meshes (include hidden meshes)...
        weighted, attached = utilities.functions.get_armature_meshes(original, bpy.context.scene.objects)
        # unhide everything we're about to touch, so it can be selected/entered/duplicated...
        hidden = utilities.functions.get_hidden_objects({original, *weighted, *attached})
        utilities.functions.set_objects_unhidden(hidden)
        skinning.functions.set_unsocketed_meshes(attached)
        meshes = weighted + attached
        # save our current mode... (if there is no contextual object then we must be in object mode)...
        last_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
        # get all the collections the original is in...
        collections = [coll for coll in original.users_collection]
        # suffix both generated armature names (strip any existing original suffix first)...
        name = original.name[:-len("_Original")] if original.name.endswith("_Original") else original.name
        oriented_name = name + "_Oriented"
        # rename the existing original in place...
        original.name, original.data.name = name + "_Original", name + "_Original"
        # add the oriented armature alongside it with its explicit suffix...
        data = bpy.data.armatures.new(oriented_name)
        oriented = bpy.data.objects.new(oriented_name, data)
        # and link it to the scene... (same collection as original)...
        for collection in collections:
            collection.objects.link(oriented)
        # match world transforms before copying bones in local space...
        oriented.matrix_world = original.matrix_world
        # parent the original armature to the oriented one, preserving the world transform we just matched...
        original.parent = oriented
        original.matrix_parent_inverse = oriented.matrix_world.inverted()
        # viewport display settings, consistent across the oriented and original...
        for armature in (oriented, original):
            armature.show_in_front, armature.data.relation_line_position = True, 'HEAD'
        # the original reads as a wireframe overlay...
        original.display_type = 'WIRE'
        # ensure selection then enter edit mode... (this can be invoked from pose mode)...
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        oriented.select_set(True)
        original.select_set(True)
        bpy.context.view_layer.objects.active = original
        bpy.ops.object.mode_set(mode='EDIT')
        # then iterate on the bones we want to add...
        names = [pb.name for pb in original.pose.bones]
        for name in names:
            # add a matching bone on the oriented armature for it, attempting to orient and constrain it...
            add_oriented_bone(oriented, original, name, max_length)
        # return our mode to whatever it was...
        bpy.ops.object.mode_set(mode=last_mode)
        # give the oriented and original armatures their compatibility flags...
        oriented['Armature Type'], original['Armature Type'] = "Oriented", "Original"
        set_shaped_bones(original, oriented, names, original_shape, oriented_shape)
        # carry each bones retargeting settings over from the original it was created from...
        for name in names:
            retargeting.functions.set_copied_retargeting(original, oriented, name)
        # ensure the meshes are deformed by the (renamed) original and follow it's new parent...
        for mesh in meshes:
            for mod in mesh.modifiers:
                if mod.type == 'ARMATURE':
                    mod.object = original
            mesh.parent = original.parent
        # rehide anything that wasn't visible to begin with...
        for obj in hidden:
            obj.hide_set(True)
        if use_actions:
            # get the tracks and actions of the original armature and retarget them...
            tracks, actions = utilities.functions.get_copied_nla(original)
            retargets = []
            for action in actions:
                retarget = retargeting.functions.set_retargeted_action(bpy.context, action, original, oriented)
                retargets.append(retarget)
            # rename the retargeted actions and get rid of the old ones...
            for i, action in enumerate(actions):
                if action:
                    name = action.name
                    bpy.data.actions.remove(action)
                    if retargets[i]:
                        retargets[i].name = name
            # then rebuild the nla for the oriented armature with the retargeted actions...
            utilities.functions.set_copied_nla(oriented, tracks, retargets)
    finally:
        # restore onto whichever ended up as the hierarchy's new top (oriented once it exists, otherwise original itself)...
        utilities.functions.set_restored_transform(oriented if oriented else original, stored_transform)
        bpy.context.view_layer.update()
    # and return the oriented and original armatures...
    return oriented, original

def clear_parent_constraints(original):
    # drop direct drivers before the original armature becomes passive... (like existing rigging modules)...
    names = ("Parent Transform", "Isolate Location", "Isolate Rotation", "Isolate Scale")
    for pose_bone in original.pose.bones:
        for name in names:
            con = pose_bone.constraints.get(name)
            if con:
                pose_bone.constraints.remove(con)

def set_rigging_reparented(rig, oriented):
    # move the existing rig above the oriented/original pair... (preserve both world transforms)...
    rig_world = rig.matrix_world.copy()
    oriented_world = oriented.matrix_world.copy()
    rig.parent = None
    rig.matrix_world = rig_world
    oriented.parent = rig
    oriented.matrix_world = oriented_world
    # the oriented armature needs its own parent transform constraints by name...
    names = {pb.name for pb in oriented.pose.bones} & {pb.name for pb in rig.pose.bones}
    for name in names:
        rigging.functions.add_parent_constraints(oriented, rig, name, name)


