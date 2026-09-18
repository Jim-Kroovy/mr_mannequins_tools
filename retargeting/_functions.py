import bpy
import math
import re
import contextlib

from mathutils import Vector, Quaternion, Matrix, Euler

from .. import utilities
from .. import skinning
from .. import rigging

def set_target_items(preferences, original):
    # cache the armature picker items (none first to avoid an accidental selection)...
    armatures = sorted((o for o in bpy.data.objects if o.type == 'ARMATURE' and o != original), key=lambda o: o.name)
    items = [('NONE', "None", "", 'NONE', 0)] + [(o.name, o.name, "", 'ARMATURE_DATA', i + 1) for i, o in enumerate(armatures)]
    preferences.target_items = items

def set_copied_retargeting(source, target, name):
    # copies a bones retargeting settings by name - used both when oriented/rigging armatures create a bone from wherever it
    # was made from, and to carry edits back down through the hierarchy - a plain name match is enough for either...
    source_pb, target_pb = source.pose.bones.get(name), target.pose.bones.get(name)
    if not (source_pb and target_pb):
        return
    target_pb.mmt.updating = True
    target_pb.mmt.rotation = source_pb.mmt.rotation
    target_pb.mmt.translation = source_pb.mmt.translation
    target_pb.mmt.mirror = source_pb.mmt.mirror
    target_pb.mmt.updating = False

def update_bone_retargeting(self, context):
    if self.updating:
        return
    armature = self.id_data
    if not (isinstance(armature, bpy.types.Object) and armature.type == 'ARMATURE'):
        return
    pose_bone = next((pb for pb in armature.pose.bones if pb.mmt == self), None)
    if not pose_bone:
        return
    self.updating = True
    try:
        # push this bones retargeting settings onto its mirrored left/right counterpart, if it has one and wants them...
        if self.mirror:
            mirrored_name, _ = utilities.functions.get_mirrored_name(pose_bone.name)
            counterpart = armature.pose.bones.get(mirrored_name) if mirrored_name else None
            if counterpart:
                counterpart.mmt.updating = True
                counterpart.mmt.rotation = self.rotation
                counterpart.mmt.translation = self.translation
                counterpart.mmt.mirror = self.mirror
                counterpart.mmt.updating = False
        # and carry edits made on an oriented or rigging bone back down through the hierarchy...
        rig, oriented, original = utilities.functions.get_armature_hierarchy(armature)
        if armature == rig and oriented:
            set_copied_retargeting(armature, oriented, pose_bone.name)
        if armature in (rig, oriented) and original:
            set_copied_retargeting(armature, original, pose_bone.name)
    finally:
        self.updating = False

def get_descendant_bones(pose_bone):
    # every pose bone beneath this one in the hierarchy, recursively...
    descendants = []
    for child in pose_bone.children:
        descendants.append(child)
        descendants.extend(get_descendant_bones(child))
    return descendants

def get_ordered_names(armature, names):
    # walk the hierarchy from the roots down, so parents always get posed before their children...
    ordered = []
    def walk_pose_hierarchy(pose_bones):
        for pose_bone in pose_bones:
            if pose_bone.name in names:
                ordered.append(pose_bone.name)
            walk_pose_hierarchy(pose_bone.children)
    walk_pose_hierarchy([pb for pb in armature.pose.bones if pb.parent is None])
    return ordered

def get_forward_names(origin, orient, rig, target):
    # maps the raw armatures own bone names onto their equivalent name on target (itself, or the rig), following the live Parent Transform constraint chain - so a rigging modules forward prefix, or a shared bones own unrelated name, both still resolve correctly. respects the hierarchy by anchoring on the oriented armature when there is one (its own names already match original 1:1, and it's only a single hop from the rig), only falling back to walking the original armature directly if there's no oriented armature to anchor on...
    forward = {}
    anchor = orient or origin
    if not anchor:
        return forward
    for pose_bone in anchor.pose.bones:
        name = pose_bone.name
        if target == anchor:
            forward[name] = name
            continue
        rig_name = name
        if target == rig:
            con = pose_bone.constraints.get("Parent Transform")
            if con and con.target == rig:
                rig_name = con.subtarget
            forward[name] = rig_name
        else:
            forward[name] = name
    return forward

def get_joint_direction(armature, from_pb, to_pbs):
    # aim towards the mapped childrens center (none if degenerate)...
    start = armature.matrix_world @ from_pb.head
    center = Vector((0.0, 0.0, 0.0))
    for to_pb in to_pbs:
        center += armature.matrix_world @ to_pb.head
    center /= len(to_pbs)
    direction = center - start
    return direction.normalized() if direction.length > 1e-5 else None

def set_bone_retargeted(source, target, name, names):
    source_pb, target_pb = source.pose.bones[name], target.pose.bones[name]
    # the source bone hasn't been touched yet, so its current matrix is still hanging naturally off its already posed parent...
    source_matrix = source.matrix_world.to_3x3() @ source_pb.matrix.to_3x3()
    source_children = [c for c in source_pb.children if c.name in names]
    target_direction = source_direction = None
    if source_children:
        primary = utilities.functions.get_primary_child(source_children)
        aim_children = [primary] if primary else source_children
        target_children = [target.pose.bones[c.name] for c in aim_children]
        # align the nearest bone axes towards the primary child (or their average)...
        target_direction = get_joint_direction(target, target_pb, target_children)
        source_direction = get_joint_direction(source, source_pb, aim_children)
        if target_direction and source_direction:
            source_axes = rigging.functions.get_bone_axes(source_pb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
            target_axes = rigging.functions.get_bone_axes(target_pb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
            source_axes = [(source.matrix_world.to_3x3() @ axis).normalized() for axis in source_axes.values()]
            target_axes = [(target.matrix_world.to_3x3() @ axis).normalized() for axis in target_axes.values()]
            source_direction = utilities.functions.get_closest_vector(source_direction, source_axes)
            target_direction = utilities.functions.get_closest_vector(target_direction, target_axes)
    if not (target_direction and source_direction) and source_pb.parent and target_pb.parent:
        # fall back to each bones inverted closest parent axis (rolls differ)...
        source_to_parent = source_pb.parent.head - source_pb.head
        target_to_parent = target_pb.parent.head - target_pb.head
        if source_to_parent.length > 1e-5 and target_to_parent.length > 1e-5:
            source_axes = rigging.functions.get_bone_axes(source_pb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
            target_axes = rigging.functions.get_bone_axes(target_pb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
            source_closest = utilities.functions.get_closest_vector(source_to_parent.normalized() * -1, source_axes.values())
            target_closest = utilities.functions.get_closest_vector(target_to_parent.normalized() * -1, target_axes.values())
            source_direction = (source.matrix_world.to_3x3() @ source_closest).normalized()
            target_direction = (target.matrix_world.to_3x3() @ target_closest).normalized()
    if target_direction and source_direction:
        swing = source_direction.rotation_difference(target_direction)
        target_world = (swing.to_matrix() @ source_matrix).to_quaternion()
        # bring the target back out of the source armatures own object rotation...
        target = source.matrix_world.to_3x3().to_quaternion().inverted() @ target_world
        # and convert it into the source bones local pose space, relative to its already posed parent...
        parent_pb = source_pb.parent
        if parent_pb:
            parent_pose = parent_pb.matrix.to_quaternion()
            rest_relative = (parent_pb.bone.matrix_local.inverted() @ source_pb.bone.matrix_local).to_quaternion()
        else:
            parent_pose = Quaternion()
            rest_relative = source_pb.bone.matrix_local.to_quaternion()
        basis_rotation = (parent_pose @ rest_relative).inverted() @ target
    else:
        # nothing usable to aim towards, so just hang naturally off the now correctly posed parent...
        basis_rotation = Quaternion()
    # optionally stretch the bone to match the target bones length instead of keeping its own...
    y_scale = 1.0
    # proportional bone lengths can be enabled here when maintain_proportions is disabled...
    source_pb.matrix_basis = Matrix.LocRotScale(Vector((0.0, 0.0, 0.0)), basis_rotation, Vector((1.0, y_scale, 1.0)))
    bpy.context.view_layer.update()
    return source_pb

def set_anchored_bones(armature, meshes):
    # unweighted bones coincident with a weighted one (eg. stock ik_hand_l) float otherwise, so treat them as it's children...
    weighted = utilities.functions.get_weighted_names(meshes)
    for cluster in utilities.functions.get_coincident_clusters(armature):
        anchors = [n for n in cluster if n in weighted]
        followers = [n for n in cluster if n not in weighted]
        if len(anchors) == 1 and followers:
            anchor_pb = armature.pose.bones[anchors[0]]
            anchor_rest = anchor_pb.bone.matrix_local
            for name in followers:
                follower_pb = armature.pose.bones[name]
                follower_pb.matrix = anchor_pb.matrix @ anchor_rest.inverted() @ follower_pb.bone.matrix_local

def set_retargeted_rigging(original, target, max_length, only_selected=False):
    from ..orientation import _functions as orientation_functions
    # check for an oriented tag before retargeting (rebuild existing rigs from cached settings)...
    had_oriented = original.get('Armature Type') is not None
    # resolve the original armature that owns the meshes (fall back to the input)...
    rig, oriented, resolved = utilities.functions.get_armature_hierarchy(original)
    working_source = resolved if resolved else original
    cached = []
    if rig:
        # snapshot every built modules type and settings before its bones go stale under the new pose...
        for item in rig.data.mmt.rigging:
            if item.module:
                cached.append((item.rigging, utilities.functions.get_serialized_settings(item.settings)))
    # remove constraints driving the original before rebuilding its rigs...
    orientation_functions.clear_parent_constraints(working_source)
    if rig:
        data = rig.data
        bpy.data.objects.remove(rig, do_unlink=True)
        if data.users == 0:
            bpy.data.armatures.remove(data)
    # remove the old oriented armature (only if separate from the input)...
    if oriented and oriented != working_source:
        data = oriented.data
        bpy.data.objects.remove(oriented, do_unlink=True)
        if data.users == 0:
            bpy.data.armatures.remove(data)
    # reset selection (the active armature may have been deleted)...
    bpy.context.view_layer.objects.active = working_source
    working_source.select_set(True)
    working = set_retargeted_meshes(working_source, target, max_length, only_selected=only_selected)
    # rebuild the oriented armature only if one existed...
    new_oriented = None
    if had_oriented:
        new_oriented, working = orientation_functions.add_oriented_armature(working, max_length)
        if cached:
            new_rig = rigging.functions.add_rigging_armature(new_oriented)
            for module_rigging, settings_data in cached:
                item = new_rig.data.mmt.rigging.add()
                new_rig.data.mmt.module = len(new_rig.data.mmt.rigging) - 1
                rigging.functions.set_module_restored(bpy.context, item, module_rigging, settings_data)
    return new_oriented, working

@contextlib.contextmanager
def get_graph_override(context):
    # borrow a safe area for the graph editor (changing topbar or statusbar can crash blender)...
    candidates = [a for a in context.window.screen.areas if a.type not in {'TOPBAR', 'STATUSBAR', 'PREFERENCES', 'FILE_BROWSER'}]
    area = next((a for a in candidates if a.type in {'GRAPH_EDITOR', 'DOPESHEET_EDITOR'}), candidates[0] if candidates else None)
    if not area:
        yield None
        return
    original_type = area.type
    if original_type not in {'GRAPH_EDITOR', 'DOPESHEET_EDITOR'}:
        area.type = 'GRAPH_EDITOR'
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    try:
        with context.temp_override(area=area, region=region):
            yield area
    finally:
        if original_type not in {'GRAPH_EDITOR', 'DOPESHEET_EDITOR'}:
            area.type = original_type

def set_decimated_fcurves(context, margin):
    # skip decimates extra undo snapshot (the operator already adds one)...
    original_undo = context.preferences.edit.use_global_undo
    context.preferences.edit.use_global_undo = False
    try:
        bpy.ops.graph.decimate(mode='ERROR', remove_error_margin=margin)
    finally:
        context.preferences.edit.use_global_undo = original_undo

def get_channel_group(fcurve):
    # groups by the owning bone/property path (eg pose.bones["Name"]), so every curve on the same bone thins together...
    match = re.match(r'(.*\])\.', fcurve.data_path)
    return match.group(1) if match else fcurve.data_path

def get_local_deviations(fcurve):
    points = [(p.co.x, p.co.y) for p in fcurve.keyframe_points]
    count = len(points)
    scored = []
    for index, (frame, value) in enumerate(points):
        if index == 0 or index == count - 1:
            scored.append((frame, math.inf))
            continue
        prev_frame, prev_value = points[index - 1]
        next_frame, next_value = points[index + 1]
        span = next_frame - prev_frame
        expected = prev_value + (next_value - prev_value) * ((frame - prev_frame) / span) if span > 0 else prev_value
        scored.append((frame, abs(value - expected)))
    return scored

def get_synced_frames(fcurves, min_spacing):
    entries = []
    for fcurve in fcurves:
        entries.extend(get_local_deviations(fcurve))
    if not entries:
        return []
    entries.sort(key=lambda e: e[0])
    kept = [entries[0]]
    for frame, score in entries[1:]:
        last_frame, last_score = kept[-1]
        if frame - last_frame < min_spacing:
            if score > last_score:
                kept[-1] = (frame, score)
        else:
            kept.append((frame, score))
    return [frame for frame, _ in kept]

def set_synced_channels(fcurves, min_spacing):
    frames = get_synced_frames(fcurves, min_spacing)
    if not frames:
        return
    frame_set = set(frames)
    for fcurve in fcurves:
        existing = {p.co.x for p in fcurve.keyframe_points}
        for frame in frames:
            if frame not in existing:
                fcurve.keyframe_points.insert(frame, fcurve.evaluate(frame), keyframe_type='KEYFRAME')
        for index in reversed(range(len(fcurve.keyframe_points))):
            if fcurve.keyframe_points[index].co.x not in frame_set:
                fcurve.keyframe_points.remove(fcurve.keyframe_points[index], fast=True)
        fcurve.update()

def set_thinned_fcurves(context, min_spacing):
    fcurves = context.selected_editable_fcurves or context.editable_fcurves
    groups = {}
    for fcurve in fcurves:
        groups.setdefault(get_channel_group(fcurve), []).append(fcurve)
    for group in groups.values():
        set_synced_channels(group, min_spacing)

def set_cleaned_action(context, armature, action, decimate, margin, spacing):
    if not armature.animation_data:
        armature.animation_data_create()
    original_action = armature.animation_data.action
    original_active_object = context.view_layer.objects.active
    original_selection = [pb.select for pb in armature.pose.bones]
    original_active_bone = armature.data.bones.active
    context.view_layer.objects.active = armature
    armature.animation_data.action = action
    for pb in armature.pose.bones:
        pb.select = True
    if armature.pose.bones:
        armature.data.bones.active = armature.pose.bones[0].bone
    for fcurve in utilities.functions.get_action_fcurves(action):
        fcurve.select = True
        fcurve.hide = False
    with get_graph_override(context) as area:
        if area:
            if decimate:
                set_decimated_fcurves(context, margin)
            if spacing > 0:
                set_thinned_fcurves(context, spacing)
    for pb, selected in zip(armature.pose.bones, original_selection):
        pb.select = selected
    armature.data.bones.active = original_active_bone
    armature.animation_data.action = original_action
    context.view_layer.objects.active = original_active_object

def get_module_names(rig, module, prefix_names):
    # get module bones by prefix (skip prefixes this module does not define)...
    collection = rig.data.collections_all.get(module.module)
    if not collection:
        return []
    prefices = module.settings.prefices
    prefixes = tuple(prefices[name].affix for name in prefix_names if name in prefices and prefices[name].affix)
    return [b.name for b in collection.bones if b.name.startswith(prefixes)] if prefixes else []

def set_bone_keyed(bone, frame):
    bone.keyframe_insert('location', frame=frame)
    path = 'rotation_euler'
    if bone.rotation_mode == 'QUATERNION':
        path = 'rotation_quaternion'
    elif bone.rotation_mode == 'AXIS_ANGLE':
        path = 'rotation_axis_angle'
    bone.keyframe_insert(path, frame=frame)

def get_bone_channels(action):
    # group curves by bone, property and array index... (so we can evaluate without scene updates)
    channels, bones = {'location', 'rotation_quaternion', 'rotation_euler', 'scale'}, {}
    for fc in utilities.functions.get_action_fcurves(action):
        if '"' in fc.data_path:
            name = fc.data_path.partition('"')[2].split('"')[0]
            prop = fc.data_path.rpartition('.')[2]
            if prop in channels:
                bones.setdefault(name, {}).setdefault(prop, {})[fc.array_index] = fc
    return bones

def get_evaluated_basis(pose_bone, channels, frame):
    # get the bones basis from action curves at this frame... (no scene updates)
    props = channels.get(pose_bone.name, {})
    location = Vector((0.0, 0.0, 0.0))
    for index, fc in props.get('location', {}).items():
        location[index] = fc.evaluate(frame)
    scale = Vector((1.0, 1.0, 1.0))
    for index, fc in props.get('scale', {}).items():
        scale[index] = fc.evaluate(frame)
    if 'rotation_quaternion' in props:
        values = [1.0, 0.0, 0.0, 0.0]
        for index, fc in props['rotation_quaternion'].items():
            values[index] = fc.evaluate(frame)
        rotation = Quaternion(values)
    elif 'rotation_euler' in props:
        values = [0.0, 0.0, 0.0]
        for index, fc in props['rotation_euler'].items():
            values[index] = fc.evaluate(frame)
        order = pose_bone.rotation_mode if pose_bone.rotation_mode in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'} else 'XYZ'
        rotation = Euler(values, order).to_quaternion()
    else:
        rotation = Quaternion()
    return Matrix.LocRotScale(location, rotation, scale)

def get_evaluated_matrix(pose_bone, channels, frame, cache):
    # armature-space matrix from fcurves, recursing through real parents and resolving live "Root Transform" child of bones with no keys of their own...
    if pose_bone.name in cache:
        return cache[pose_bone.name]
    basis = get_evaluated_basis(pose_bone, channels, frame)
    if pose_bone.parent:
        parent_matrix = get_evaluated_matrix(pose_bone.parent, channels, frame, cache)
        matrix = parent_matrix @ pose_bone.parent.bone.matrix_local.inverted() @ pose_bone.bone.matrix_local @ basis
    else:
        matrix = pose_bone.bone.matrix_local @ basis
    root = pose_bone.constraints.get("Root Transform")
    if root and root.influence > 0.0:
        root_pb = root.target.pose.bones.get(root.subtarget)
        root_matrix = get_evaluated_matrix(root_pb, channels, frame, cache)
        constrained = (root_matrix @ root.inverse_matrix) @ matrix
        translation = matrix.translation.lerp(constrained.translation, root.influence)
        rotation = matrix.to_quaternion().slerp(constrained.to_quaternion(), root.influence)
        matrix = Matrix.LocRotScale(translation, rotation, Vector((1.0, 1.0, 1.0)))
    cache[pose_bone.name] = matrix
    return matrix

def get_evaluated_matrices(forwards, channels, frame, cache):
    return [get_evaluated_matrix(pb, channels, frame, cache) for pb in forwards]

def get_bone_translation(bone):
    # a bones rest translation relative to its own parent, undoing the parents own armature-space rest first...
    if bone.parent:
        return (bone.parent.matrix_local.inverted() @ bone.matrix_local).to_translation()
    return bone.matrix_local.to_translation()

def get_bone_rotations(source, target, name, adjusted, forward=None, reverse=None):
    # get fixed transport and correction rotations (preserve the adjusted retarget base pose), plus both bones own rest translations for the per-bone translation retargeting modes...
    forward, reverse = forward or {}, reverse or {}
    from_bone, to_bone = source.data.bones.get(name), target.data.bones.get(forward.get(name, name))
    if not (from_bone and to_bone):
        return None
    source_rest = from_bone.matrix_local.to_quaternion()
    true_rest = to_bone.matrix_local.to_quaternion()
    true_parent = to_bone.parent.matrix_local.to_quaternion() if to_bone.parent else Quaternion()
    # the parent may itself be a forward-prefixed (or shared) bone, so map it back onto adjusted's own raw naming...
    parent_name = reverse.get(to_bone.parent.name, to_bone.parent.name) if to_bone.parent else None
    adjusted_parent = adjusted[parent_name] if parent_name in adjusted else Quaternion()
    transport = true_rest.inverted() @ true_parent @ adjusted_parent.inverted() @ source_rest
    correction = source_rest.inverted() @ adjusted[name]
    return transport, correction, get_bone_translation(from_bone), get_bone_translation(to_bone)

def get_retargeted_rotation(mode, swing, correction, animated):
    # the swing and correction are always solved regardless of mode, since translation retargeting leans on swing too...
    if mode == 'SKELETON':
        # always use the targets own rest pose rotation, ignoring the animation entirely...
        return Quaternion()
    if mode == 'ANIMATION':
        # the rotation straight from the animation, unmodified...
        return animated
    # 'RELATIVE' (and any unrecognised mode) - apply the retarget as a fixed rotational difference from the source rest pose...
    return swing @ animated @ correction

def get_retargeted_translation(mode, swing, source_translation, target_translation, animated):
    # mirrors Unreals own per-bone translation retargeting modes - bring both the animated and the source rest translation into the targets own local axes first, using the same swing rotation already solved for this bones rotation retargeting...
    animated = swing @ animated
    source_translation = swing @ source_translation
    if mode == 'SKELETON':
        # always use the targets own rest translation, ignoring the animation entirely...
        return target_translation
    length = source_translation.length
    if mode == 'SCALED':
        # keep the animated translation, rescaled by the ratio between the source and target rest lengths...
        return animated * (target_translation.length / length) if length > 1e-5 else target_translation
    if mode == 'RELATIVE':
        # apply the retarget as an additive difference between the two rest poses...
        return animated + (target_translation - source_translation)
    if mode == 'ORIENT':
        # same as scaled, but bones sitting at their rest translation (not really being animated) snap cleanly onto the targets own rest translation instead...
        if length < 1e-5 or (animated - source_translation).length < 1e-5:
            return target_translation
        return animated * (target_translation.length / length)
    # 'ANIMATION' (and any unrecognised mode) - the animation drives translation directly, unmodified beyond the orientation fix up...
    return animated

def get_retarget_rotations(source, target, names, ordered, forward=None):
    # create two clean skeleton copies (live poses and constraints cannot affect the retarget base)...
    copies, armatures, rotations = [], [], {}
    for armature in (source, target):
        data = armature.data.copy()
        armatures.append(data)
        data.pose_position = 'POSE'
        obj = bpy.data.objects.new(armature.name + "_Rest", data)
        copies.append(obj)
        bpy.context.scene.collection.objects.link(obj)
        obj.matrix_world = armature.matrix_world.copy()
    if forward:
        # sources own bones may carry a forward prefix (or be unrelated shared bone names) - rename them back to the shared raw names on this throwaway copy so it lines up with names/ordered...
        for raw_name, mapped_name in forward.items():
            if mapped_name != raw_name:
                bone = copies[0].data.bones.get(mapped_name)
                if bone:
                    bone.name = raw_name
    bpy.context.view_layer.update()
    # pose all the bones in order... (updating before calculating children)
    for name in ordered:
        pb = set_bone_retargeted(copies[0], copies[1], name, names)
        rotations[pb.name] = pb.matrix.to_quaternion()
    # clean up the two rest pose armature...
    for obj in copies:
        bpy.data.objects.remove(obj, do_unlink=True)
    for data in armatures:
        if not data.users:
            bpy.data.armatures.remove(data)
    return rotations

def get_root_children(rig, roots):
    # walk outward through child of chains from the root bones, until a pass finds nothing new...
    children = set(roots)
    growing = True
    while growing:
        chained = {pb.name for pb in rig.pose.bones for con in pb.constraints if con.type == 'CHILD_OF' and con.target == rig and con.subtarget in children}
        growing = not chained <= children
        children.update(chained)
    return children

def set_constraints_muted(rig, shared, children, value):
    for name in shared:
        pb = rig.pose.bones[name]
        for con in pb.constraints:
            if not (con.type == 'CHILD_OF' and con.target == rig and con.subtarget in children):
                con.mute = value

def get_rigging_modules(rig, action, shared):
    frames, modules, channels = {}, [], get_bone_channels(action)
    for module in rig.data.mmt.rigging:
        if module.rigging in {'OPPOSABLE', 'PLANTIGRADE', 'DIGITIGRADE', 'SCALAR', 'SPLINE'}:
            module_file = rigging.functions.get_module_file(module.rigging)
            snap = getattr(module_file, 'set_snapped_kinematics', None)
            if snap:
                collection = rig.data.collections_all.get(module.module)
                names = {b.name for b in collection.bones} & shared if collection else set()
                frames[module.module] = {kp.co.x for name in names for props in channels.get(name, {}).values() for fc in props.values() for kp in fc.keyframe_points}
                controls = [rig.pose.bones[name] for name in get_module_names(rig, module, ('target', 'vector', 'pole', 'parent', 'control')) if name in rig.pose.bones]
                direct = getattr(module_file, 'set_snapped_direct', None)
                modules.append((module, snap, direct, controls))
    return frames, modules

def set_bones_cleared(context, rig, names):
    for name in names:
        pose_bone = rig.pose.bones.get(name)
        if pose_bone:
            pose_bone.location = (0.0, 0.0, 0.0)
            pose_bone.rotation_quaternion = Quaternion()
            pose_bone.rotation_euler = (0.0, 0.0, 0.0)
            pose_bone.scale = (1.0, 1.0, 1.0)
    context.view_layer.update()

def set_retargeting_rigging(context, original, rig, retarget, step_height=0.1):
    # keys every rigging module analytically from the actions own fcurves - no scene evaluation or view layer updates anywhere except splines own iterative snap (still evaluated live)...
    shared = {pb.name for pb in original.pose.bones} & {pb.name for pb in rig.pose.bones}
    # bones tagged as a ROOT module - no longer locked to rest during evaluation, but still needed to mute their own Root Transform chains and keep their real keys when clearing forwards at the end...
    roots = {module.settings.suffices['root'].affix for module in rig.data.mmt.rigging
        if module.rigging == 'ROOT' and module.settings.suffices['root'].affix}
    children = get_root_children(rig, roots)
    set_constraints_muted(rig, shared, children, True)
    # the caller resets its own action back to whatever was active before calling us, so keyframe_insert needs this set explicitly or every key lands on the wrong (or no) action...
    if not rig.animation_data:
        rig.animation_data_create()
    rig.animation_data.action = retarget
    rig.animation_data.action_slot = retarget.slots[0]
    channels = get_bone_channels(retarget)
    frames = sorted({kp.co.x for props in channels.values() for curves in props.values() for fc in curves.values() for kp in fc.keyframe_points})
    for module in rig.data.mmt.rigging:
        if module.rigging not in {'OPPOSABLE', 'PLANTIGRADE', 'DIGITIGRADE', 'SCALAR'}:
            continue
        suffices, prefices = module.settings.suffices, module.settings.prefices
        chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'root', 'pivot'}]
        if not chain:
            continue
        forwards = [rig.pose.bones.get(prefices['forward'].affix + suffices[n].affix) for n in chain + ['ending']]
        target = rig.pose.bones.get(prefices['target'].affix + suffices['ending'].affix)
        vector = rig.pose.bones.get(prefices['vector'].affix + suffices[chain[0]].affix)
        pole = rig.pose.bones.get(prefices['pole'].affix + suffices[chain[0]].affix)
        if any(pb is None for pb in forwards) or not target or not vector or not pole:
            continue
        target.rotation_mode = 'QUATERNION'
        vector.rotation_mode = 'QUATERNION'
        # plantigrades foot parent/control: blend between "child of ball" and "child of target" transforms...
        ball_pb = rig.pose.bones.get(prefices['forward'].affix + suffices['pivot'].affix) if module.rigging == 'PLANTIGRADE' else None
        parent_pb = rig.pose.bones.get(prefices['parent'].affix + suffices['ending'].affix) if ball_pb else None
        control_pb = rig.pose.bones.get(prefices['control'].affix + suffices['ending'].affix) if ball_pb else None
        if parent_pb:
            parent_pb.rotation_mode = 'QUATERNION'
        if control_pb:
            control_pb.rotation_mode = 'XYZ'
        rest_rotation_0 = forwards[0].bone.matrix_local.to_quaternion()
        # figure out once which of vectors own rest cardinal axes points toward the pole, then read that same axis off its live posed matrix every frame instead of recomputing secondary independently...
        rest_points = [pb.bone.matrix_local.translation for pb in forwards]
        _, rest_secondary, _, _ = rigging.functions.get_chain_normals(rest_points)
        rest_axes = rigging.functions.get_bone_axes(vector.bone, ['+X', '-X', '+Z', '-Z'])
        pole_axis_name, _ = utilities.functions.get_closest_axis(rest_secondary, rest_axes)
        # get_shortest_roll always targets z, so the matched rest axis gives a fixed per-bone secondary sign, applied once up front...
        vector_z_sign = 1.0 if pole_axis_name == '+Z' else -1.0
        for frame in frames:
            cache = {}
            matrices = get_evaluated_matrices(forwards, channels, frame, cache)
            ending_matrix = matrices[-1]
            points = [m.translation for m in matrices]
            get_matrix = lambda pb: get_evaluated_matrix(pb, channels, frame, cache)
            # build the cardinal-axis override from this frames own matrix, not the live (unscrubbed) bone...
            axis_setting = module.settings.axis
            override = None
            if axis_setting != 'AUTO':
                first_axes = matrices[0].to_3x3()
                cardinal = {'+X': first_axes.col[0], '-X': -first_axes.col[0],
                    '+Z': first_axes.col[2], '-Z': -first_axes.col[2]}
                override = cardinal[axis_setting]
            # a chain thats genuinely straight has no real bend signal, so override secondary with rest_secondary rotated by however far the first bone has turned since rest...
            if override is None:
                chain_length, chain_direction = utilities.functions.get_distance_direction(points[0], points[-1])
                dominant = Vector((0.0, 0.0, 0.0))
                for point in points[1:-1]:
                    projection = (point - points[0]).dot(chain_direction)
                    perpendicular = point - (points[0] + (chain_direction * projection))
                    if perpendicular.length > dominant.length:
                        dominant = perpendicular
                delta = matrices[0].to_quaternion() @ rest_rotation_0.inverted()
                tracked_secondary = delta @ rest_secondary
                if dominant.length <= (chain_length * 0.01):
                    override = tracked_secondary
                # a genuine hyperextension flips secondary correctly, but the pole should hold its side regardless, so negate back onto the tracked side when they disagree...
                elif dominant.dot(tracked_secondary) < 0.0:
                    override = -dominant
            primary, secondary, _, length = rigging.functions.get_chain_normals(points, override=override)
            center = points[0] + (primary * (length * module.settings.position))

            # plantigrade: target is a live child of the rotator chain hanging off parent, so keying it here too would double up the ankles position - parent alone determines it in that case...
            if not parent_pb:
                rigging.functions.set_snapped_target(target, ending_matrix, get_matrix)
                set_bone_keyed(target, frame)

            # same shared setters the interactive snap uses, with the fixed per-bone secondary sign already applied...
            vector_matrix = rigging.functions.set_snapped_vector(vector, get_matrix, ending_matrix, primary, secondary * vector_z_sign, vector.parent)
            set_bone_keyed(vector, frame)
            # poles desired position reads off whichever of vectors own axes was established above as "toward pole"...
            posed_axes = {'+X': vector_matrix.to_3x3().col[0], '-X': -vector_matrix.to_3x3().col[0],
                '+Z': vector_matrix.to_3x3().col[2], '-Z': -vector_matrix.to_3x3().col[2]}
            position = center + (posed_axes[pole_axis_name].normalized() * module.settings.offset)
            rigging.functions.set_snapped_pole(pole, position, vector_matrix, get_matrix)
            set_bone_keyed(pole, frame)

            if parent_pb and control_pb:
                control_x, parent_local = rigging.functions.get_snapped_parent(parent_pb, ball_pb, forwards[-1], get_matrix, step_height)
                control_pb.rotation_euler.x = control_x
                set_bone_keyed(control_pb, frame)
                parent_pb.location = parent_local.translation
                parent_pb.rotation_quaternion = parent_local.to_quaternion()
                set_bone_keyed(parent_pb, frame)

    # spline still needs its own iterative, live-evaluated snap, with the same frame-scrubbing as above...
    spline_frames, all_modules = get_rigging_modules(rig, retarget, shared)
    spline_modules = [entry for entry in all_modules if entry[0].rigging == 'SPLINE']
    if spline_modules:
        context.view_layer.objects.active = rig
        keyframes = sorted(set().union(*(spline_frames[module.module] for module, _, _, _ in spline_modules)))
        rotations = {}
        for frame in keyframes:
            context.scene.frame_set(int(frame), subframe=frame - int(frame))
            for module, snap, direct, controls in spline_modules:
                if frame in spline_frames[module.module] and snap(context, module, clear=False):
                    for control in controls:
                        if control.rotation_mode == 'QUATERNION':
                            rotation = control.rotation_quaternion.copy()
                            previous = rotations.get(control.name)
                            if previous is not None and rotation.dot(previous) < 0.0:
                                rotation.negate()
                                control.rotation_quaternion = rotation
                            rotations[control.name] = rotation
                        set_bone_keyed(control, frame)

    # forward bones only get their curves removed if they have constraints (keeps unconstrained shared/anchor bones like a clavicle)...
    forwards_to_clear = set()
    for module in rig.data.mmt.rigging:
        collection = rig.data.collections_all.get(module.module)
        if collection and module.rigging in {'OPPOSABLE', 'PLANTIGRADE', 'DIGITIGRADE', 'SCALAR', 'SPLINE', 'TWIST'}:
            forwards_to_clear.update(name for name in (shared & {b.name for b in collection.bones}) if rig.pose.bones[name].constraints)
    forwards_to_clear.difference_update(roots)
    for layer in retarget.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for index in reversed(range(len(channelbag.fcurves))):
                    fcurve = channelbag.fcurves[index]
                    match = re.match(r'pose\.bones\["(.+)"\]\.', fcurve.data_path)
                    if match and match.group(1) in forwards_to_clear:
                        channelbag.fcurves.remove(channelbag.fcurves[index])
    # clear forwards after removing their keys... (otherwise they keep their last evaluated pose)
    set_bones_cleared(context, rig, forwards_to_clear)
    set_constraints_muted(rig, shared, children, False)
    context.view_layer.update()
    return retarget

def set_retargeted_action(context, action, source, target, step_height=0.1, only_selected=False):
    if action:
        # get the targets armatures and redirect to the highest priority one...
        rig, orient, origin = utilities.functions.get_armature_hierarchy(target)
        target = rig or orient or origin
        # the retarget math below leans on both armatures own world matrices, so their object transforms need clearing first, restoring once we're done...
        stored_source = utilities.functions.get_stored_transform(source)
        stored_target = utilities.functions.get_stored_transform(target)
        utilities.functions.set_cleared_transform(source)
        utilities.functions.set_cleared_transform(target)
        context.view_layer.update()
        try:
            # map the raw armatures own bone names onto whatever target actually is - a rigs forward bones may carry a user prefix, or be an unrelated shared bone name entirely. respects the hierarchy: anchored on oriented when there is one, original otherwise, or straight identity as a last resort...
            anchor = orient or origin or target
            forward = get_forward_names(origin, orient, rig, target) or {pb.name: pb.name for pb in target.pose.bones}
            reverse = {mapped: raw for raw, mapped in forward.items()}
            target_names = {pb.name for pb in target.pose.bones}
            # get all the names of all the bones... (still keyed by the anchor armatures own raw names, shared with source)
            names = {name for name in forward if forward[name] in target_names} & {pb.name for pb in source.pose.bones}
            channels = get_bone_channels(action)
            frames = sorted({kp.co.x for fcs in channels.values() for props in fcs.values() for fc in props.values() for kp in fc.keyframe_points})
            if names and frames:
                # get the names in hierarchic order... (walked off the anchor, since its topology is what forward/reverse are mapped against)
                ordered = get_ordered_names(anchor, names)
                # get the retargeted rest rotations from the target to the source...
                rest = get_retarget_rotations(target, source, names, ordered, forward)
                # get the swing and correction rotations needed to adjust the fcruve transforms...
                rotations = {name: get_bone_rotations(source, target, name, rest, forward, reverse) for name in names}
                retarget = bpy.data.actions.new(name=action.name + "_Retargeted")
                if not target.animation_data:
                    target.animation_data_create()
                active = target.animation_data.action
                target.animation_data.action = retarget
                for name in ordered:
                    target_pb = target.pose.bones[forward[name]]
                    source_pb = source.pose.bones[name]
                    if rotations[name] and (not only_selected or target_pb.select):
                        swing, correction, source_translation, target_translation = rotations[name]
                        props = channels.get(name, {})
                        # key transforms together at this bones own source times...
                        frames = sorted({kp.co.x for curves in props.values() for fc in curves.values() for kp in fc.keyframe_points})
                        target_pb.rotation_mode = 'QUATERNION'
                        target_pb.rotation_quaternion = get_retargeted_rotation(target_pb.mmt.rotation, swing, correction, Quaternion())
                        target_pb.location = Vector((0.0, 0.0, 0.0))
                        for frame in frames:
                            basis = get_evaluated_basis(source_pb, channels, frame)
                            target_pb.rotation_quaternion = get_retargeted_rotation(target_pb.mmt.rotation, swing, correction, basis.to_quaternion())
                            if name == 'root':
                                # preserve root motion in world space... (it should not inherit the bones retarget transport)...
                                target_pb.location = target.matrix_world.inverted() @ (source.matrix_world @ basis.to_translation())
                            else:
                                target_pb.location = get_retargeted_translation(target_pb.mmt.translation, swing, source_translation, target_translation, basis.to_translation())
                            set_bone_keyed(target_pb, frame)
                target.animation_data.action = active
                if rig:
                    retarget = set_retargeting_rigging(context, source, rig, retarget, step_height)
                return retarget

            return None
        finally:
            utilities.functions.set_restored_transform(source, stored_source)
            utilities.functions.set_restored_transform(target, stored_target)
            context.view_layer.update()

    return None

def set_retargeted_meshes(armature, target, max_length=None, use_actions=False, only_selected=False):
    # if we are retargeting actions with the armature and meshes... 
    if use_actions:
        # Preserve the source pose while the armature is converted to its new rest pose.
        data = armature.data.copy()
        source = bpy.data.objects.new(armature.name + "_ACTIONS", data)
        bpy.context.scene.collection.objects.link(source)
        source.matrix_world = armature.matrix_world.copy()
        # copy the armatures nla data into the duplicate and clear its animation data...
        tracks, actions = utilities.functions.get_copied_nla(armature)
        utilities.functions.set_copied_nla(source, tracks, actions)
        armature.animation_data_clear()
    # redirect target to origin if it exists... (target returned as original if no hierarchy found)
    rig, orient, target = utilities.functions.get_armature_hierarchy(target)
    # the retarget math below leans on both armatures own world matrices, so their object transforms need clearing first, restoring once we're done...
    stored_armature = utilities.functions.get_stored_transform(armature)
    stored_target = utilities.functions.get_stored_transform(target)
    utilities.functions.set_cleared_transform(armature)
    utilities.functions.set_cleared_transform(target)
    target.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    try:
        # convert the originals sockets to skeletal meshes before retargeting (include hidden meshes)...
        weighted, attached = utilities.functions.get_armature_meshes(armature, bpy.context.scene.objects)
        # unhide everything we're about to touch, so it can be selected/entered/duplicated...
        hidden = utilities.functions.get_hidden_objects({armature, *weighted, *attached})
        utilities.functions.set_objects_unhidden(hidden)
        skinning.functions.set_unsocketed_meshes(attached)
        meshes = weighted + attached
        result, original = armature, armature
        bpy.ops.object.select_all(action='DESELECT')
        # pose the result armature into the existing armatures bone directions, keeping it's own proportions...
        names = {pb.name for pb in result.pose.bones} & {pb.name for pb in target.pose.bones}
        ordered = get_ordered_names(result, names)
        for name in ordered:
            # unselected bones are left alone, so they just follow whatever their already-posed parent inherits down to them...
            if not only_selected or result.pose.bones[name].select:
                set_bone_retargeted(result, target, name, names)
        bpy.context.view_layer.update()
        # snap unweighted coincident bones to their weighted anchors (eg. ik targets)...
        set_anchored_bones(result, meshes)
        bpy.context.view_layer.update()
        # bake that pose into the meshes too (rest is about to change underneath them), and as the new rest pose...
        utilities.functions.set_applied_meshes(meshes, original=False, include_armature=True)
        result.select_set(True)
        bpy.context.view_layer.objects.active = result
        bpy.ops.object.mode_set(mode='POSE')
        bpy.context.view_layer.update()
        bpy.ops.pose.armature_apply(selected=False)
        # finalize each bones tail/roll to the existing armatures convention, keeping it's own bone lengths...
        bpy.ops.object.mode_set(mode='EDIT')
        names = {pb.name for pb in result.pose.bones} & {b.name for b in target.data.bones}
        for name in names:
            result_eb = result.data.edit_bones[name]
            axes = rigging.functions.get_bone_axes(target.data.bones[name], ['+Y', '+Z'])
            result_eb.tail = result_eb.head + (axes['+Y'] * result_eb.length)
            result_eb.align_roll(axes['+Z'])
            if max_length and result_eb.length > max_length:
                result_eb.length = max_length
        bpy.ops.object.mode_set(mode='OBJECT')
        # then if we have actions to retarget from the old pose...
        if use_actions:
            # get the tracks and actions of the source armature that hasn't changed...
            tracks, actions = utilities.functions.get_copied_nla(source)
            # retarget the actions...
            retargets = []
            for action in actions:
                retarget = set_retargeted_action(bpy.context, action, source, result, only_selected=only_selected)
                retargets.append(retarget)
            # rename the retargeted actions and get rid of the old ones...
            for i, action in enumerate(actions):
                if action:
                    name = action.name
                    bpy.data.actions.remove(action)
                    if retargets[i]:
                        retargets[i].name = name
            # and get rid of the temporary source copy...
            data = source.data
            bpy.data.objects.remove(source, do_unlink=True)
            bpy.data.armatures.remove(data)
            # then rebuild the nla for the result armature...
            utilities.functions.set_copied_nla(result, tracks, retargets)
    finally:
        utilities.functions.set_restored_transform(armature, stored_armature)
        utilities.functions.set_restored_transform(target, stored_target)
        bpy.context.view_layer.update()
    # rehide anything that wasn't visible to begin with...
    for obj in hidden:
        obj.hide_set(True)
    # return the target to pose position...
    target.data.pose_position = 'POSE'
    return result

