import bpy
import math
import re
import contextlib

from mathutils import Vector, Quaternion, Matrix, Euler

from .. import utilities
from .. import skinning
from .. import rigging
from .. import orientation

def set_target_items(preferences, original, prefer_rig=True, include_oriented=False):
    # cache the armature picker items, one entry per character at its highest available tier (or oriented/original only when prefer_rig is off, since posing never uses a rig) - none first to avoid an accidental selection. include_oriented also lists the active armatures own oriented sibling even when its rig is higher, eg. retargeting the actions oriented already carried down from original, onto the rig...
    armatures = []
    for o in bpy.data.objects:
        if o.type == 'ARMATURE' and o != original:
            rig, oriented, orig = utilities.functions.get_armature_hierarchy(o)
            highest = (rig or oriented or orig) if prefer_rig else (oriented or orig)
            if o == highest:
                armatures.append(o)
    if include_oriented:
        _, active_oriented, _ = utilities.functions.get_armature_hierarchy(original)
        if active_oriented and active_oriented != original and active_oriented not in armatures:
            armatures.append(active_oriented)
    armatures.sort(key=lambda o: o.name)
    items = [('NONE', "None", "", 'NONE', 0)] + [(o.name, o.name, "", 'ARMATURE_DATA', i + 1) for i, o in enumerate(armatures)]
    preferences.target_items = items

def set_copied_retargeting(source, target, name):
    # copies a bones retargeting settings by name - used both for bone creation and cascading edits down the hierarchy...
    source_pb, target_pb = source.pose.bones.get(name), target.pose.bones.get(name)
    if not (source_pb and target_pb):
        return
    target_pb.mmt.updating = True
    target_pb.mmt.rotation = source_pb.mmt.rotation
    target_pb.mmt.translation = source_pb.mmt.translation
    target_pb.mmt.mirror = source_pb.mmt.mirror
    target_pb.mmt.mapping.clear()
    for mapping in source_pb.mmt.mapping:
        target_pb.mmt.mapping.add().name = mapping.name
    target_pb.mmt.updating = False

def set_cascaded_retargeting(armature, name):
    # keeps a bones retargeting settings identical across the whole oriented/rigging/original hierarchy, regardless of which one it was actually edited on...
    for other in utilities.functions.get_armature_hierarchy(armature):
        if other and other != armature:
            set_copied_retargeting(armature, other, name)

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
                set_cascaded_retargeting(armature, mirrored_name)
        set_cascaded_retargeting(armature, pose_bone.name)
    finally:
        self.updating = False

def update_bone_mapping(self, context):
    armature = self.id_data
    if not (isinstance(armature, bpy.types.Object) and armature.type == 'ARMATURE'):
        return
    pose_bone = next((pb for pb in armature.pose.bones if any(mapping == self for mapping in pb.mmt.mapping)), None)
    if not (pose_bone and not pose_bone.mmt.updating):
        return
    pose_bone.mmt.updating = True
    try:
        set_cascaded_retargeting(armature, pose_bone.name)
    finally:
        pose_bone.mmt.updating = False

def get_descendant_bones(pose_bone):
    # every pose bone beneath this one in the hierarchy, recursively...
    descendants = []
    for child in pose_bone.children:
        descendants.append(child)
        descendants.extend(get_descendant_bones(child))
    return descendants

def update_copy_children(self, context):
    # a momentary "button" disguised as a bool, so it draws via layout.prop() and gets property-split alignment for free - fires once then resets itself off...
    if self.updating:
        return
    self.updating = True
    try:
        if self.copy_children:
            armature = self.id_data
            pose_bone = next((pb for pb in armature.pose.bones if pb.mmt == self), None) if isinstance(armature, bpy.types.Object) and armature.type == 'ARMATURE' else None
            if pose_bone:
                for descendant in get_descendant_bones(pose_bone):
                    descendant.mmt.rotation = self.rotation
                    descendant.mmt.translation = self.translation
                    descendant.mmt.mirror = self.mirror
            self.copy_children = False
    finally:
        self.updating = False

def get_mapped_name(pose_bone, names):
    # the bones own name if it's already in there, otherwise the first mapping entry that is - checked on this bone and its same-named counterparts elsewhere in the original/oriented/rigging hierarchy, since mapping is only ever authored on whichever tier the user happened to be editing...
    if pose_bone.name in names:
        return pose_bone.name
    tiers = [t for t in utilities.functions.get_armature_hierarchy(pose_bone.id_data) if t]
    counterparts = {t.pose.bones[pose_bone.name] for t in tiers if pose_bone.name in t.pose.bones}
    counterparts.add(pose_bone)
    for counterpart in counterparts:
        mapped = next((m.name for m in counterpart.mmt.mapping if m.name in names), None)
        if mapped:
            return mapped
    return None

def set_mapped_names(armature, target):
    # rename incoming bones onto the targets own naming wherever a mapping resolves one, so plain exact-name matching everywhere else in retargeting just works... returns {old_name: new_name} for every rename actually made, so callers can carry the same translation onto anything else keyed by the old names (eg. action fcurves)...
    names = {b.name for b in armature.data.bones}
    renamed = {}
    for target_pb in target.pose.bones:
        mapped = get_mapped_name(target_pb, names)
        if mapped and mapped != target_pb.name:
            armature.data.bones[mapped].name = target_pb.name
            renamed[mapped] = target_pb.name
    return renamed

def get_mapped_names(armature, target):
    # the same correspondence set_mapped_names would rename onto, without touching a single bone - {armature_name: target_name} for every one of the armatures own bones that a mapping (or an exact match) resolves against the target...
    names = {b.name for b in armature.data.bones}
    forward = {}
    for target_pb in target.pose.bones:
        mapped = get_mapped_name(target_pb, names)
        if mapped:
            forward[mapped] = target_pb.name
    return forward

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
    # the raw (unsnapped) direction to a child or averaged children - snapping to the nearest axis was tried and discarded, it injects pure discretization error...
    target = Vector((0.0, 0.0, 0.0))
    for to_pb in to_pbs:
        target += to_pb.head
    target /= len(to_pbs)
    direction = target - from_pb.head
    if direction.length < 0.0001:
        return None
    return (armature.matrix_world.to_3x3() @ direction).normalized()

def get_local_rotation(source_pb, armature_rotation, world_rotation):
    # bring a world-space rotation back out of the armatures own object rotation, and into this bones local pose space, relative to its already posed parent...
    world_out = armature_rotation.inverted() @ world_rotation
    parent_pb = source_pb.parent
    if parent_pb:
        parent_pose = parent_pb.matrix.to_quaternion()
        rest_relative = (parent_pb.bone.matrix_local.inverted() @ source_pb.bone.matrix_local).to_quaternion()
    else:
        parent_pose = Quaternion()
        rest_relative = source_pb.bone.matrix_local.to_quaternion()
    return (parent_pose @ rest_relative).inverted() @ world_out

def set_bone_retargeted(source, target, name, forward):
    source_pb, target_pb = source.pose.bones[name], target.pose.bones[forward[name]]
    # the source bone hasn't been touched yet, so its current matrix is still hanging naturally off its already posed parent...
    source_matrix = source.matrix_world.to_3x3() @ source_pb.matrix.to_3x3()
    source_children = [c for c in source_pb.children if c.name in forward]
    target_direction = source_direction = None
    if source_children:
        primary = utilities.functions.get_primary_child(source_children)
        aim_children = [primary] if primary else source_children
        target_children = [target.pose.bones[forward[c.name]] for c in aim_children]
        # the raw direction to the primary child (or their average) - no axis snapping, that would inject pure discretization error unrelated to the real difference...
        target_direction = get_joint_direction(target, target_pb, target_children)
        source_direction = get_joint_direction(source, source_pb, aim_children)
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
        armature_rotation = source.matrix_world.to_3x3().to_quaternion()
        basis_rotation = get_local_rotation(source_pb, armature_rotation, target_world)
    else:
        # nothing usable to aim towards, so just hang naturally off the now correctly posed parent...
        basis_rotation = Quaternion()
    # optionally stretch the bone to match the target bones length instead of keeping its own...
    y_scale = 1.0
    # proportional bone lengths can be enabled here when maintain_proportions is disabled...
    source_pb.matrix_basis = Matrix.LocRotScale(Vector((0.0, 0.0, 0.0)), basis_rotation, Vector((1.0, y_scale, 1.0)))
    bpy.context.view_layer.update()
    return source_pb

def set_bone_twisted(source, target, name, forward):
    # swing only fixes the aim direction, so twist the rest of the way onto whichever target axis Z now sits closest to - same closest-axis idea used when building an oriented armature...
    source_pb, target_pb = source.pose.bones[name], target.pose.bones[forward[name]]
    posed_axes = rigging.functions.get_bone_axes(source_pb, ['+Y', '+Z'])
    posed_y = (source.matrix_world.to_3x3() @ posed_axes['+Y']).normalized()
    posed_z = (source.matrix_world.to_3x3() @ posed_axes['+Z']).normalized()
    target_axes = rigging.functions.get_bone_axes(target_pb, ['+X', '-X', '+Z', '-Z'])
    target_directions = [(target.matrix_world.to_3x3() @ v).normalized() for v in target_axes.values()]
    closest = utilities.functions.get_closest_vector(posed_z, target_directions)
    # only a pure roll around the bones own (already fixed) aim direction is actually achievable, so project the closest target axis onto the plane perpendicular to it first...
    desired_z = closest - (closest.dot(posed_y) * posed_y)
    if desired_z.length >= 0.0001:
        twist = posed_z.rotation_difference(desired_z.normalized())
        source_matrix = source.matrix_world.to_3x3() @ source_pb.matrix.to_3x3()
        world = (twist.to_matrix() @ source_matrix).to_quaternion()
        armature_rotation = source.matrix_world.to_3x3().to_quaternion()
        basis_rotation = get_local_rotation(source_pb, armature_rotation, world)
        source_pb.matrix_basis = Matrix.LocRotScale(Vector((0.0, 0.0, 0.0)), basis_rotation, Vector((1.0, 1.0, 1.0)))
        bpy.context.view_layer.update()
    return source_pb

def set_bone_posed(source, target, name, forward):
    # twist right after this bones own swing, not in a later pass - a child swings off its parents current matrix, so the parent must fully finish first or its twist drags an already-posed child along...
    set_bone_retargeted(source, target, name, forward)
    return set_bone_twisted(source, target, name, forward)

def set_armature_posed(armature, target, only_selected=False):
    # poses the armature into the targets bone directions only, no renaming/meshes/rest/actions touched - uses target exactly as given, no Original-tier redirect like set_retargeted_meshes...
    stored_armature = utilities.functions.get_stored_transform(armature)
    stored_target = utilities.functions.get_stored_transform(target)
    utilities.functions.set_cleared_transform(armature)
    utilities.functions.set_cleared_transform(target)
    target.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    try:
        # resolves differently-named bones (eg. a Mixamo rig) against the target via its bone mapping, without renaming anything...
        forward = get_mapped_names(armature, target)
        ordered = get_ordered_names(armature, set(forward))
        for name in ordered:
            # unselected bones are left alone, so they just follow whatever their already-posed parent inherits down to them...
            if not only_selected or armature.pose.bones[name].select:
                set_bone_posed(armature, target, name, forward)
        bpy.context.view_layer.update()
    finally:
        target.data.pose_position = 'POSE'
        utilities.functions.set_restored_transform(armature, stored_armature)
        utilities.functions.set_restored_transform(target, stored_target)
        bpy.context.view_layer.update()

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

def set_retargeted_rigging(original, target, max_length, rename=True):
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
    working = set_retargeted_meshes(working_source, target, max_length, rename=rename)
    # this armature now fits the target, so it inherits the targets own retargeting settings too - regardless of selection...
    for name in {pb.name for pb in working.pose.bones} & {pb.name for pb in target.pose.bones}:
        set_copied_retargeting(target, working, name)
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

def get_bone_rotations(source, target, name, forward=None):
    # Convert animation bases exactly between the paired bones armature-space
    # rests.  Conjugating by this fixed difference keeps identity at identity
    # while expressing every animated delta in the targets own rest axes.
    forward = forward or {}
    from_bone, to_bone = source.data.bones.get(name), target.data.bones.get(forward.get(name, name))
    if not (from_bone and to_bone):
        return None
    source_rest = from_bone.matrix_local.to_quaternion()
    target_rest = to_bone.matrix_local.to_quaternion()
    transport = target_rest.inverted() @ source_rest
    return transport, transport.inverted(), get_bone_translation(from_bone), get_bone_translation(to_bone)

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
        # no extra offset on top of rest, mirrors get_retargeted_rotation's own identity return - target_translation is already baked into the hierarchy via bone.matrix_local in get_evaluated_matrix, so returning it here doubled it...
        return Vector((0.0, 0.0, 0.0))
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

def set_retargeted_action(context, action, source, target, step_height=0.1, only_selected=False, rename=True):
    if action:
        # get the targets armatures and redirect to the highest priority one...
        rig, orient, origin = utilities.functions.get_armature_hierarchy(target)
        target = rig or orient or origin
        # map the raw armatures own bone names onto whatever target actually is - a rigs forward bones may carry a user prefix, or be an unrelated shared bone name entirely. respects the hierarchy: anchored on oriented when there is one, original otherwise, or straight identity as a last resort...
        anchor = orient or origin or target
        # rename onto a disposable duplicate rather than source itself, so a live/shared source armature never gets permanently renamed just for this - the action gets duplicated and its fcurve paths carried onto the same renames, so the duplicates keys line up with its own new bone names (source and its action are otherwise never touched)...
        duplicate, duplicate_action, action_name = None, None, action.name
        if rename:
            data = source.data.copy()
            duplicate = bpy.data.objects.new(source.name + "_MAPPED", data)
            bpy.context.scene.collection.objects.link(duplicate)
            duplicate.matrix_world = source.matrix_world.copy()
            renamed = set_mapped_names(duplicate, anchor)
            if renamed:
                duplicate_action = action.copy()
                for fc in utilities.functions.get_action_fcurves(duplicate_action):
                    match = re.match(r'pose\.bones\["(.+?)"\](.*)', fc.data_path)
                    if match and match.group(1) in renamed:
                        fc.data_path = 'pose.bones["' + renamed[match.group(1)] + '"]' + match.group(2)
                action = duplicate_action
            source = duplicate
        # the retarget math below leans on both armatures own world matrices, so their object transforms need clearing first, restoring once we're done...
        stored_source = utilities.functions.get_stored_transform(source)
        stored_target = utilities.functions.get_stored_transform(target)
        utilities.functions.set_cleared_transform(source)
        utilities.functions.set_cleared_transform(target)
        context.view_layer.update()
        try:
            forward = get_forward_names(origin, orient, rig, target) or {pb.name: pb.name for pb in target.pose.bones}
            target_names = {pb.name for pb in target.pose.bones}
            # get all the names of all the bones... (still keyed by the anchor armatures own raw names, shared with source)
            names = {name for name in forward if forward[name] in target_names} & {pb.name for pb in source.pose.bones}
            channels = get_bone_channels(action)
            frames = sorted({kp.co.x for fcs in channels.values() for props in fcs.values() for fc in props.values() for kp in fc.keyframe_points})
            if names and frames:
                # get the names in hierarchic order... (walked off the anchor, since its topology is what the forward mapping is based on)
                ordered = get_ordered_names(anchor, names)
                # Every mapped pair uses the same exact rest-space basis conversion;
                # skeleton proportions are handled independently by translation mode.
                rotations = {name: get_bone_rotations(source, target, name, forward) for name in names}
                retarget = bpy.data.actions.new(name=action_name + "_Retargeted")
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
                            # root used to get a hand rolled world-space shortcut here, skipping swings axis conversion between the two rest conventions entirely - it needs the same treatment as every other bone, same as its rotation just above...
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
            if duplicate:
                data = duplicate.data
                bpy.data.objects.remove(duplicate, do_unlink=True)
                bpy.data.armatures.remove(data)
            if duplicate_action:
                bpy.data.actions.remove(duplicate_action)

    return None

def get_bone_rest(armature, name):
    # a bones own rest orientation relative to its parent, undoing the parents own armature-space rest first...
    bone = armature.data.bones[name]
    if bone.parent:
        return (bone.parent.matrix_local.inverted() @ bone.matrix_local).to_quaternion()
    return bone.matrix_local.to_quaternion()

def set_corrected_actions(armature, corrections):
    # a rest orientation change invalidates any keyed rotation/translation, so re-key every frame through the same correction - kept separate from cross-armature retargeting since this never changes bones/armature, only rest...
    if armature.animation_data:
        _, actions = utilities.functions.get_copied_nla(armature)
        active = armature.animation_data.action
        try:
            for action in actions:
                if action:
                    armature.animation_data.action = action
                    channels = get_bone_channels(action)
                    for name, correction in corrections.items():
                        pose_bone = armature.pose.bones.get(name)
                        props = channels.get(name, {})
                        if pose_bone and props:
                            frames = sorted({kp.co.x for curves in props.values() for fc in curves.values() for kp in fc.keyframe_points})
                            for frame in frames:
                                basis = get_evaluated_basis(pose_bone, channels, frame)
                                if 'rotation_quaternion' in props:
                                    pose_bone.rotation_mode = 'QUATERNION'
                                    pose_bone.rotation_quaternion = correction @ basis.to_quaternion()
                                    pose_bone.keyframe_insert('rotation_quaternion', frame=frame)
                                elif 'rotation_euler' in props:
                                    pose_bone.rotation_euler = (correction @ basis.to_quaternion()).to_euler(pose_bone.rotation_mode)
                                    pose_bone.keyframe_insert('rotation_euler', frame=frame)
                                if 'location' in props:
                                    pose_bone.location = correction @ basis.to_translation()
                                    pose_bone.keyframe_insert('location', frame=frame)
        finally:
            armature.animation_data.action = active

def set_retargeted_meshes(armature, target, max_length=None, rename=True):
    _, oriented, original = utilities.functions.get_armature_hierarchy(armature)
    # redirect target to oriented if it exists... (target returned as original if no hierarchy found)
    _, target, _ = utilities.functions.get_armature_hierarchy(target)
    # translate the incoming bones onto the targets own naming before anything else touches them...
    if rename:
        set_mapped_names(armature, target)
    # save every bones own rest orientation before anything bakes over it, so the difference can carry every stashed action through afterwards - the pose itself is assumed to already be set (Set Retarget Pose, plus any manual cleanup), this only ever bakes whatever is currently there...
    old_rests = {pb.name: get_bone_rest(armature, pb.name) for pb in armature.pose.bones}
    # convert the originals sockets to skeletal meshes before retargeting (include hidden meshes)...
    weighted, attached = utilities.functions.get_armature_meshes(armature, bpy.context.scene.objects)
    # unhide everything we're about to touch, so it can be selected/entered/duplicated...
    hidden = utilities.functions.get_hidden_objects({armature, *weighted, *attached})
    utilities.functions.set_objects_unhidden(hidden)
    skinning.functions.set_unsocketed_meshes(attached)
    meshes = weighted + attached
    result = armature
    bpy.ops.object.select_all(action='DESELECT')
    # snap unweighted coincident bones to their weighted anchors (eg. ik targets)...
    set_anchored_bones(result, meshes)
    bpy.context.view_layer.update()
    # bake the current pose into the meshes too (rest is about to change underneath them), and as the new rest pose...
    utilities.functions.set_applied_meshes(meshes, original=False, include_armature=True)
    result.select_set(True)
    bpy.context.view_layer.objects.active = result
    bpy.ops.object.mode_set(mode='POSE')
    bpy.context.view_layer.update()
    bpy.ops.pose.armature_apply(selected=False)
    # carry every stashed action through the rest change that just caused, bone by bone...
    new_rests = {name: get_bone_rest(result, name) for name in old_rests}
    corrections = {name: new_rests[name].inverted() @ old_rests[name] for name in old_rests}
    set_corrected_actions(result, corrections)
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
    # rehide anything that wasn't visible to begin with...
    for obj in hidden:
        obj.hide_set(True)
    return result

def get_missing_names(original_eb, source, forward):
    # walks the source chain from this bones mapped parent down to its own mapped counterpart, collecting any bones in between that no original bone already claims - these are the gaps enforce_hierarchy pads with duplicates...
    parent_eb = original_eb.parent
    if not parent_eb or parent_eb.name not in forward:
        return []
    source_bone = source.data.bones.get(forward[original_eb.name])
    if not source_bone:
        return []
    parent_target, claimed = forward[parent_eb.name], set(forward.values())
    missing, walker = [], source_bone.parent
    while walker and walker.name != parent_target:
        if walker.name in claimed:
            return []
        missing.append(walker.name)
        walker = walker.parent
    if not walker:
        return []
    missing.reverse()
    return missing

def set_padded_bones(original, source, forward):
    # enforce_hierarchy - splice a duplicate bone in for every source bone a shorter original chain skips over, so both skeletons keep the same joint count - each injected bones head sits the same fraction along the real parent-donor gap as its counterpart sits along the targets chain, direction/roll come from the target too like every other mapped bone...
    padding = {}
    for name in list(forward):
        original_eb = original.data.edit_bones.get(name)
        missing = get_missing_names(original_eb, source, forward) if original_eb else []
        if not missing:
            continue
        parent_eb = original_eb.parent
        chain_target = [source.data.bones[forward[parent_eb.name]]] + [source.data.bones[n] for n in missing] + [source.data.bones[forward[name]]]
        cumulative = [0.0]
        for i in range(1, len(chain_target)):
            cumulative.append(cumulative[-1] + (chain_target[i].head_local - chain_target[i - 1].head_local).length)
        total, steps = cumulative[-1], len(chain_target) - 1
        fractions = [c / total if total > 1e-6 else i / steps for i, c in enumerate(cumulative)]
        real_start, real_end = parent_eb.head, original_eb.head
        positions = [real_start.lerp(real_end, f) for f in fractions]
        for i, missing_name in enumerate(missing):
            new_eb = original.data.edit_bones.get(missing_name)
            if not new_eb:
                new_eb = original.data.edit_bones.new(missing_name)
                new_eb.use_connect = False
            axes = rigging.functions.get_bone_axes(source.data.bones[missing_name], ['+Y', '+Z'])
            new_eb.head = positions[i + 1]
            new_eb.tail = new_eb.head + axes['+Y'] * (positions[i + 2] - positions[i + 1]).length
            new_eb.align_roll(axes['+Z'])
            new_eb.parent = parent_eb
            parent_eb = new_eb
        original_eb.parent = parent_eb
        padding[name] = missing
    return padding

def get_closest_segment(point, points):
    # which segment of a polyline a point sits closest to, how far along it (0 at points[i], 1 at points[i + 1], clamped so a point beyond either end pins to that ends bone rather than extrapolating), and how far away it actually is...
    best_distance, best_index, best_fraction = None, 0, 0.0
    for i in range(len(points) - 1):
        segment = points[i + 1] - points[i]
        length_squared = segment.length_squared
        fraction = ((point - points[i]).dot(segment) / length_squared) if length_squared > 1e-9 else 0.0
        fraction = max(0.0, min(1.0, fraction))
        distance = (point - (points[i] + segment * fraction)).length_squared
        if best_distance is None or distance < best_distance:
            best_distance, best_index, best_fraction = distance, i, fraction
    return best_index, best_fraction, best_distance

def set_padded_source(mesh, to_local, source_name, chains):
    # redistributes one vertex groups existing weight along whichever candidate chain each weighted vertex actually sits closest to, blending between whichever two bones its closest point falls between - a donor only has its own chain, but a shared parent gets one candidate per sibling so it cant bleed onto a neighbour...
    source_group = mesh.vertex_groups.get(source_name)
    if not source_group:
        return
    for vertex in mesh.data.vertices:
        weight = next((g.weight for g in vertex.groups if g.group == source_group.index), 0.0)
        if weight <= 0.0:
            continue
        point = to_local @ vertex.co
        best = None
        for names, points in chains:
            index, fraction, distance = get_closest_segment(point, points)
            if best is None or distance < best[3]:
                best = (names, index, fraction, distance)
        names, index, fraction, _ = best
        start_name, end_name = names[index], names[index + 1]
        start_weight, end_weight = weight * (1.0 - fraction), weight * fraction
        remaining = 0.0
        for group_name, group_weight in ((start_name, start_weight), (end_name, end_weight)):
            if group_name == source_name:
                remaining += group_weight
            else:
                group = mesh.vertex_groups.get(group_name) or mesh.vertex_groups.new(name=group_name)
                group.add([vertex.index], group_weight, 'ADD')
        source_group.add([vertex.index], remaining, 'REPLACE')

def set_padded_weights(original, meshes, padding):
    # method 1 - redistribute the parent and donor bones existing vertex weight across the padded chain(s) between them, letting a shared parent (eg. several metacarpals off one hand) pick whichever sibling chain each vertex actually sits closest to...
    chains_by_parent, donor_chains = {}, []
    for donor_name, injected_names in padding.items():
        donor_bone = original.data.bones.get(donor_name)
        first_injected = original.data.bones.get(injected_names[0]) if donor_bone else None
        parent_bone = first_injected.parent if first_injected else None
        if not donor_bone or not parent_bone:
            continue
        names = [parent_bone.name] + injected_names + [donor_name]
        points = [parent_bone.head_local] + [original.data.bones[n].head_local for n in injected_names] + [donor_bone.head_local]
        chains_by_parent.setdefault(parent_bone.name, []).append((names, points))
        donor_chains.append((donor_name, names, points))
    for mesh in meshes:
        to_local = original.matrix_world.inverted() @ mesh.matrix_world
        for parent_name, chains in chains_by_parent.items():
            set_padded_source(mesh, to_local, parent_name, chains)
        for donor_name, names, points in donor_chains:
            set_padded_source(mesh, to_local, donor_name, [(names, points)])

def set_rest_rebased_action(action, source, target, original_rests, applied_rests, padding=None):
    # Carry an action through a rest-pose replacement. This is deliberately not
    # ordinary retargeting: identity in the old rest must not become identity in
    # the new rest, because the applied pose has already been baked into the
    # meshes. Preserve the old originals deformation after factoring that baked
    # pose out, then solve the matching basis on the rebuilt oriented hierarchy.
    if not action:
        return None
    channels = get_bone_channels(action)
    frames = sorted({kp.co.x for props in channels.values() for curves in props.values()
        for fc in curves.values() for kp in fc.keyframe_points})
    names = ({pb.name for pb in source.pose.bones} & {pb.name for pb in target.pose.bones}
        & set(original_rests) & set(applied_rests))
    if not names or not frames:
        return None
    padding = padding or {}
    injected = {injected_name: donor_name for donor_name, injected_names in padding.items()
        for injected_name in injected_names if injected_name in target.pose.bones}
    keyed = names | set(injected)
    rebased = bpy.data.actions.new(name=action.name + "_Rebased")
    if not target.animation_data:
        target.animation_data_create()
    active = target.animation_data.action
    target.animation_data.action = rebased
    previous = {}

    def get_desired_matrix(pose_bone, frame, source_cache, desired_cache):
        if pose_bone.name in desired_cache:
            return desired_cache[pose_bone.name]
        if pose_bone.name in names:
            source_pb = source.pose.bones[pose_bone.name]
            source_matrix = get_evaluated_matrix(source_pb, channels, frame, source_cache)
            source_rest = source_pb.bone.matrix_local
            # old oriented pose -> old original pose -> remove the pose baked
            # during Apply -> express on the new oriented rest...
            matrix = (source_matrix @ source_rest.inverted() @ original_rests[pose_bone.name]
                @ applied_rests[pose_bone.name].inverted() @ pose_bone.bone.matrix_local)
        elif pose_bone.parent:
            parent_matrix = get_desired_matrix(pose_bone.parent, frame, source_cache, desired_cache)
            matrix = parent_matrix @ pose_bone.parent.bone.matrix_local.inverted() @ pose_bone.bone.matrix_local
        else:
            matrix = pose_bone.bone.matrix_local.copy()
        desired_cache[pose_bone.name] = matrix
        return matrix

    try:
        ordered = get_ordered_names(target, keyed)
        for frame in frames:
            source_cache, desired_cache = {}, {}
            # Choose a share for each injected chain from the donors preliminary
            # exact basis. The donor itself is solved again against the resulting
            # animated parent below, so the split cannot move the donor or any of
            # its original descendants.
            splits = {}
            for donor_name, injected_names in padding.items():
                donor_pb = target.pose.bones.get(donor_name)
                chain = [name for name in injected_names if name in injected]
                if not donor_pb or not chain:
                    continue
                matrix = get_desired_matrix(donor_pb, frame, source_cache, desired_cache)
                if donor_pb.parent:
                    parent_matrix = get_desired_matrix(donor_pb.parent, frame, source_cache, desired_cache)
                    basis = (donor_pb.bone.matrix_local.inverted()
                        @ donor_pb.parent.bone.matrix_local @ parent_matrix.inverted() @ matrix)
                else:
                    basis = donor_pb.bone.matrix_local.inverted() @ matrix
                splits[donor_name] = Quaternion().slerp(basis.to_quaternion(), 1.0 / (len(chain) + 1))

            bases, actual_cache = {}, {}

            def get_actual_matrix(pose_bone):
                if pose_bone.name in actual_cache:
                    return actual_cache[pose_bone.name]
                basis = bases.get(pose_bone.name, Matrix.Identity(4))
                if pose_bone.parent:
                    parent_matrix = get_actual_matrix(pose_bone.parent)
                    matrix = parent_matrix @ pose_bone.parent.bone.matrix_local.inverted() @ pose_bone.bone.matrix_local @ basis
                else:
                    matrix = pose_bone.bone.matrix_local @ basis
                actual_cache[pose_bone.name] = matrix
                return matrix

            for name in ordered:
                pose_bone = target.pose.bones[name]
                if name in injected:
                    basis = Matrix.LocRotScale(Vector((0.0, 0.0, 0.0)), splits.get(injected[name], Quaternion()), Vector((1.0, 1.0, 1.0)))
                else:
                    matrix = get_desired_matrix(pose_bone, frame, source_cache, desired_cache)
                    if pose_bone.parent:
                        parent_matrix = get_actual_matrix(pose_bone.parent)
                        basis = (pose_bone.bone.matrix_local.inverted()
                            @ pose_bone.parent.bone.matrix_local @ parent_matrix.inverted() @ matrix)
                    else:
                        basis = pose_bone.bone.matrix_local.inverted() @ matrix
                bases[name] = basis
                # This bone cannot already be cached: hierarchy order always
                # processes a parent before any keyed descendant.
                get_actual_matrix(pose_bone)
                location, rotation, scale = basis.decompose()
                prior = previous.get(name)
                if prior is not None and rotation.dot(prior) < 0.0:
                    rotation.negate()
                previous[name] = rotation.copy()
                pose_bone.rotation_mode = 'QUATERNION'
                pose_bone.location, pose_bone.rotation_quaternion, pose_bone.scale = location, rotation, scale
                set_bone_keyed(pose_bone, frame)
    finally:
        target.animation_data.action = active
    return rebased

def set_retargeted_armature(armature, target, max_length=None, rename=True, enforce_hierarchy=True):
    # base everything on the oriented/original pair - no more retargeting from just anything...
    _, oriented, original = utilities.functions.get_armature_hierarchy(armature)
    _, target, source = utilities.functions.get_armature_hierarchy(target)
    # hang onto the old oriented armature and its nla layout/actions if one already exists, until its actions have been transported onto the new one below - no existing oriented just means this is the first one ever built, so there's nothing to carry over...
    old_oriented, old_name = oriented, (oriented.name if oriented else None)
    tracks, actions = utilities.functions.get_copied_nla(old_oriented) if old_oriented else ([], [])
    # Snapshot both the old original rest and the pose about to be baked.  Action
    # migration below needs both to preserve deformation through that rest change.
    bpy.context.view_layer.update()
    original_rests = {b.name: b.matrix_local.copy() for b in original.data.bones}
    applied_rests = {pb.name: pb.matrix.copy() for pb in original.pose.bones}
    # convert the originals sockets to skeletal meshes before retargeting... (include hidden meshes)
    weighted, attached = utilities.functions.get_armature_meshes(original, bpy.context.scene.objects)
    # unhide everything we're about to touch, so it can be selected/entered/duplicated...
    touching = {original, *weighted, *attached}
    if old_oriented:
        touching.add(old_oriented)
    hidden = utilities.functions.get_hidden_objects(touching)
    utilities.functions.set_objects_unhidden(hidden)
    skinning.functions.set_unsocketed_meshes(attached)
    meshes = weighted + attached
    bpy.ops.object.select_all(action='DESELECT')
    # bake the current pose into the meshes too (rest is about to change underneath them), and as the new rest pose...
    utilities.functions.set_applied_meshes(meshes, original=False, include_armature=True)
    # apply the original armatures pose - still constraint-driven off the oriented armature, which hasn't been touched yet...
    original.select_set(True)
    bpy.context.view_layer.objects.active = original
    bpy.ops.object.mode_set(mode='POSE')
    bpy.context.view_layer.update()
    bpy.ops.pose.armature_apply(selected=False)
    # and clear all of it's constraints - whatever oriented armature they targeted is about to be replaced anyway...
    for pb in original.pose.bones:
        for con in list(pb.constraints):
            pb.constraints.remove(con)
    # then update it's bones in edit mode to use the target originals own orientation, keeping it's own bone lengths...
    bpy.ops.object.mode_set(mode='EDIT')
    forward = get_mapped_names(original, source)
    for name in forward:
        original_eb = original.data.edit_bones[name]
        axes = rigging.functions.get_bone_axes(source.data.bones[forward[name]], ['+Y', '+Z'])
        original_eb.tail = original_eb.head + (axes['+Y'] * original_eb.length)
        original_eb.align_roll(axes['+Z'])
        if max_length and original_eb.length > max_length:
            original_eb.length = max_length
    # pad out any chain the target has more bones in than original does, so both skeletons keep the same joint count...
    padding = set_padded_bones(original, source, forward) if enforce_hierarchy else {}
    bpy.ops.object.mode_set(mode='OBJECT')
    # hand the padded bones a proportional share of the donor bones existing vertex weight...
    if padding:
        set_padded_weights(original, weighted, padding)
    if not old_oriented:
        # no existing oriented armature to rebuild against - this is just applying the posed originals meshes and rest pose, building oriented itself is left to its own dedicated operator...
        if rename:
            set_mapped_names(original, source)
        for obj in hidden:
            obj.hide_set(True)
        return None, original
    # create a new oriented armature for the originals new bones... (to ensure similarity with the target) - the old one stays alive a little longer so its actions can be transported onto this one first...
    oriented, original = orientation.functions.add_oriented_armature(original, max_length)
    # Rebase every stashed action through the pose that was baked into the meshes.
    # This is distinct from cross-skeleton retargeting, whose identity-to-identity
    # rest mapping would discard the old animation baseline here.
    retargets = []
    for action in actions:
        retargeted = set_rest_rebased_action(action, old_oriented, oriented, original_rests, applied_rests, padding)
        retargets.append(retargeted)
    for i, action in enumerate(actions):
        if action:
            name = action.name
            bpy.data.actions.remove(action)
            if retargets[i]:
                retargets[i].name = name
    utilities.functions.set_copied_nla(oriented, tracks, retargets)
    # clear the active action and leftover pose so the new armature lands at rest - set_copied_nla carries over the old active action, so stash it first if it isn't already covered by a track...
    if oriented.animation_data:
        active = oriented.animation_data.action
        oriented.animation_data.action = None
        if active and not any(strip.action == active for track in oriented.animation_data.nla_tracks for strip in track.strips):
            utilities.functions.set_stashed_action(oriented, active)
    rigging.functions.set_bones_reset(*oriented.pose.bones)
    # get rid of the old oriented armature and reclaim its own name (object and data both) now its gone...
    data = old_oriented.data
    bpy.data.objects.remove(old_oriented, do_unlink=True)
    if data.users == 0:
        bpy.data.armatures.remove(data)
    oriented.name, oriented.data.name = old_name, old_name
    # finally we can optionally rename all the bones in the oriented and original armatures onto the targets own naming...
    if rename:
        set_mapped_names(original, source)
        set_mapped_names(oriented, target)
    # rehide anything that wasn't visible to begin with...
    for obj in hidden:
        obj.hide_set(True)
    return oriented, original
