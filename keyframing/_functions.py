import bpy
import math

from mathutils import Vector, Matrix

from .. import utilities

def get_inherited_bones(pose_bone):
    # every bone on the same armature this one inherits its transform from, through parents and child of constraints...
    armature, inherited, pending = pose_bone.id_data, set(), [pose_bone]
    while pending:
        bone = pending.pop()
        followed = [bone.parent] + [armature.pose.bones.get(c.subtarget) for c in bone.constraints if c.type == 'CHILD_OF' and not c.mute and c.influence > 0.0 and c.target == armature]
        for b in followed:
            # only walk each bone once...
            if b and b.name not in inherited:
                inherited.add(b.name)
                pending.append(b)
    return inherited

def set_transferred_motion(armature, source_name, target_name, direction):
    # moves the sources travel along a world direction onto the target, keying location only and countering the source so it doesn't move in the world...
    action = armature.animation_data.action if armature.animation_data else None
    source, target = armature.pose.bones.get(source_name), armature.pose.bones.get(target_name)
    direction = Vector(direction)
    if not action:
        raise ValueError("The active armature has no active action")
    elif action.library or not getattr(action, 'is_editable', True):
        raise ValueError("The active action '" + action.name + "' is linked/read only")
    elif not source or not target:
        raise ValueError("Source and target must both be bones on '" + armature.name + "' (got '" + source_name + "' and '" + target_name + "')")
    elif source == target:
        raise ValueError("Source and target can't be the same bone ('" + source_name + "')")
    elif direction.length < 1e-6:
        raise ValueError("Direction can't be zero")
    direction.normalize()
    # store where the scene was so it can go back...
    scene = bpy.context.scene
    current = scene.frame_current, scene.frame_subframe
    frames = get_transfer_frames(action)
    try:
        set_transferred_frames(armature, source, target, direction, frames)
    finally:
        scene.frame_set(current[0], subframe=current[1])
    return len(frames)

def get_transfer_frames(action):
    # every whole frame inside the actions frame range...
    return list(range(math.ceil(action.frame_range[0]), math.floor(action.frame_range[1]) + 1))

def set_transferred_frames(armature, source, target, direction, frames):
    # the transfer itself, sampled and keyed into whichever action and slot are active... (the direction is already normalized)...
    scene = bpy.context.scene
    # which way round they inherit decides what the sources own travel is and who ends up where... (pelvis follows root, or root drags pelvis, or neither)...
    source_follows, target_follows = target.name in get_inherited_bones(source), source.name in get_inherited_bones(target)
    matrices, bases, worlds = {source.name: {}, target.name: {}}, {source.name: {}, target.name: {}}, {}
    # snapshot every frame before touching a single key, so new keys can't change what later frames sample...
    for frame in frames:
        scene.frame_set(frame)
        worlds[frame] = armature.matrix_world.copy()
        for pose_bone in (source, target):
            matrices[pose_bone.name][frame] = pose_bone.matrix.copy()
            bases[pose_bone.name][frame] = pose_bone.matrix_basis.copy()
    # solve each frame from the snapshot...
    first = frames[0]
    source_start = (worlds[first] @ matrices[source.name][first]).translation
    target_start = (worlds[first] @ matrices[target.name][first]).translation
    solved, expected = {}, {}
    for frame in frames:
        world = worlds[frame]
        source_world, target_world = (world @ matrices[source.name][frame]).translation, (world @ matrices[target.name][frame]).translation
        source_progress = (source_world - source_start).dot(direction)
        target_progress = (target_world - target_start).dot(direction)
        # a source that follows the target already carries the targets travel, so only what's left is its own... (stops existing directional motion doubling up)...
        travel = direction * (source_progress - (target_progress if source_follows else 0.0))
        transfer = world.to_3x3().inverted() @ travel
        # the target takes the travel and the source gives it up, each solved through whatever sits in front of its basis (parents, rest, child of)...
        for pose_bone, shift in ((target, transfer), (source, -transfer)):
            basis = bases[pose_bone.name][frame]
            front = matrices[pose_bone.name][frame].to_3x3() @ basis.to_3x3().inverted()
            if abs(front.determinant()) < 1e-9:
                raise ValueError("'" + pose_bone.name + "' can't be moved by its location at frame " + str(frame) + " (check its constraints and scale)")
            solved[(pose_bone.name, frame)] = basis.translation + front.inverted() @ shift
        # where they should both end up in the world, a bone that inherits the other gets its move back through it...
        expected[frame] = (source_world - travel + (travel if source_follows else Vector()), target_world + travel - (travel if target_follows else Vector()))
    # now key the lot...
    for frame in frames:
        for pose_bone in (target, source):
            pose_bone.location = solved[(pose_bone.name, frame)]
            pose_bone.keyframe_insert('location', frame=frame)
    # then make sure every frame really landed there... (anything the location can't fully drive gets caught instead of half transferred)...
    for frame in frames:
        scene.frame_set(frame)
        reached = ((armature.matrix_world @ source.matrix).translation - expected[frame][0]).length, ((armature.matrix_world @ target.matrix).translation - expected[frame][1]).length
        if max(reached) > 1e-4:
            raise ValueError("'" + source.name + "' and '" + target.name + "' couldn't be solved at frame " + str(frame) + " (check their constraints)")

def get_transfer_entries(armature, entries):
    # checks every (action, direction) entry before anything gets touched, giving back (action, slot, normalized direction, frames)...
    checked, seen = [], set()
    for index, (action, direction) in enumerate(entries, 1):
        label = "Entry " + str(index) + (" ('" + action.name + "')" if action else "")
        direction = Vector(direction)
        if not action:
            raise ValueError(label + " has no action")
        elif action.library or not getattr(action, 'is_editable', True):
            raise ValueError(label + " is linked/read only")
        elif action in seen:
            raise ValueError(label + " is listed more than once")
        elif not all(math.isfinite(c) for c in direction) or direction.length < 1e-6:
            raise ValueError(label + " needs a direction that isn't zero")
        frames = get_transfer_frames(action)
        slot = utilities.functions.get_action_slot(action, armature)
        if not frames:
            raise ValueError(label + " has no whole frame to sample")
        elif not slot:
            raise ValueError(label + " has no slot that animates '" + armature.name + "'")
        seen.add(action)
        checked.append((action, slot, direction.normalized(), frames))
    return checked

def set_transferred_actions(armature, source_name, target_name, entries):
    # transfers the sources travel onto the target in every (action, direction) entry, in place, all or nothing...
    animation = armature.animation_data
    source, target = armature.pose.bones.get(source_name), armature.pose.bones.get(target_name)
    if not source or not target:
        raise ValueError("Source and target must both be bones on '" + armature.name + "' (got '" + source_name + "' and '" + target_name + "')")
    elif source == target:
        raise ValueError("Source and target can't be the same bone ('" + source_name + "')")
    elif animation and animation.use_tweak_mode:
        raise ValueError("Exit NLA tweak mode on '" + armature.name + "' first")
    elif not entries:
        raise ValueError("Add at least one action to transfer motion in")
    checked = get_transfer_entries(armature, entries)
    created = not animation
    if created:
        animation = armature.animation_data_create()
    # remember the scene and pose so everything goes back...
    scene = bpy.context.scene
    current = scene.frame_current, scene.frame_subframe
    previous, previous_slot = animation.action, animation.action_slot
    poses = {b.name: (b.location.copy(), b.rotation_quaternion.copy(), b.rotation_euler.copy(), tuple(b.rotation_axis_angle), b.scale.copy()) for b in armature.pose.bones}
    # only the source and targets location gets keyed, so only those curves need backing up...
    paths = {('pose.bones["' + n + '"].location', i) for n in (source.name, target.name) for i in range(3)}
    backups = []
    try:
        for action, slot, direction, frames in checked:
            # backed up before it gets keyed, groups included since new curves can make new groups...
            groups = {c: set(c.groups) for l in action.layers for s in l.strips for c in s.channelbags}
            backups.append((action, get_curve_backup(action, paths), groups))
            # every action starts from the same pose, so unkeyed channels can't carry over from the last one...
            for pose_bone in armature.pose.bones:
                pose_bone.location, pose_bone.rotation_quaternion, pose_bone.rotation_euler, pose_bone.rotation_axis_angle, pose_bone.scale = poses[pose_bone.name]
            # each action gets sampled and keyed on its own slot...
            animation.action = action
            animation.action_slot = slot
            if animation.action != action or animation.action_slot != slot:
                raise ValueError("Blender wouldn't make '" + action.name + "' active on its slot '" + slot.identifier + "'")
            set_transferred_frames(armature, source, target, direction, frames)
    except Exception:
        # put every action back exactly as it was... (not just the one that failed)...
        for action, backup, groups in reversed(backups):
            set_curve_restored(action, paths, backup)
            for channelbag, kept in groups.items():
                for group in [g for g in channelbag.groups if g not in kept]:
                    channelbag.groups.remove(group)
        raise
    finally:
        # whatever was active before goes back, evaluated where we started...
        animation.action = previous
        if previous_slot:
            animation.action_slot = previous_slot
        for pose_bone in armature.pose.bones:
            pose_bone.location, pose_bone.rotation_quaternion, pose_bone.rotation_euler, pose_bone.rotation_axis_angle, pose_bone.scale = poses[pose_bone.name]
        if created:
            armature.animation_data_clear()
        scene.frame_set(current[0], subframe=current[1])
    return [(action.name, len(frames)) for action, _, _, frames in checked]

def get_redirected_bones(armature, root):
    # the root plus every other independent control... (root level bones that don't inherit anything through a child of, by structure not by name)...
    return [root] + [b for b in armature.pose.bones if b != root and b.parent is None and not any(c.type == 'CHILD_OF' for c in b.constraints)]

def set_redirected_rotation(pose_bone, rotation, previous):
    # writes the solved rotation into whichever rotation mode the bone uses, staying compatible with the previous value to avoid flips...
    if pose_bone.rotation_mode == 'QUATERNION':
        rotation.make_compatible(previous)
        pose_bone.rotation_quaternion = rotation
        path = 'rotation_quaternion'
    elif pose_bone.rotation_mode == 'AXIS_ANGLE':
        # axis angle stores the angle first...
        axis, angle = rotation.to_axis_angle()
        pose_bone.rotation_axis_angle = (angle, *axis)
        path = 'rotation_axis_angle'
    else:
        pose_bone.rotation_euler = rotation.to_euler(pose_bone.rotation_mode, previous)
        path = 'rotation_euler'
    return path

def set_redirected_motion(armature, root_name, axis, angle):
    # rotates the roots animation (and every independent control) around a world axis through the world origin, keying location and rotation only...
    action = armature.animation_data.action if armature.animation_data else None
    root = armature.pose.bones.get(root_name)
    if not action:
        raise ValueError("The active armature has no active action")
    elif action.library or not getattr(action, 'is_editable', True):
        raise ValueError("The active action '" + action.name + "' is linked/read only")
    elif not root:
        raise ValueError("'" + root_name + "' isn't a bone on '" + armature.name + "'")
    elif abs(angle) < 1e-6:
        raise ValueError("Angle can't be zero")
    scene = bpy.context.scene
    current = scene.frame_current, scene.frame_subframe
    frames = list(range(math.ceil(action.frame_range[0]), math.floor(action.frame_range[1]) + 1))
    bones = get_redirected_bones(armature, root)
    rotation = Matrix.Rotation(angle, 4, axis)
    snapshots = {b.name: {} for b in bones}
    try:
        # snapshot every frame before touching a single key...
        for frame in frames:
            scene.frame_set(frame)
            world = armature.matrix_world.copy()
            for pose_bone in bones:
                previous = pose_bone.rotation_quaternion.copy() if pose_bone.rotation_mode == 'QUATERNION' else pose_bone.rotation_euler.copy()
                snapshots[pose_bone.name][frame] = (world, pose_bone.matrix.copy(), pose_bone.matrix_basis.copy(), previous)
        for pose_bone in bones:
            for frame in frames:
                world, pose, basis, previous = snapshots[pose_bone.name][frame]
                # rotate the whole world matrix (position and orientation) then bring it back into armature space...
                redirected = world.inverted() @ rotation @ world @ pose
                # solved through whatever sits in front of the basis, so it doesn't care how the bone is oriented at rest...
                location, quaternion, _ = (basis @ pose.inverted() @ redirected).decompose()
                pose_bone.location = location
                pose_bone.keyframe_insert('location', frame=frame)
                pose_bone.keyframe_insert(set_redirected_rotation(pose_bone, quaternion, previous), frame=frame)
    finally:
        scene.frame_set(current[0], subframe=current[1])
    return len(bones), len(frames)

def set_redirected_action(armature, root_name, axis, angle, name, keep_original, stash_action, target_names=()):
    # redirects a copy of the active action into a new active action, stashing or removing the original... (returns name, bones, frames, chains, controls)
    animation = armature.animation_data
    source = animation.action if animation else None
    name = str(name).strip()
    if not source:
        raise ValueError("'" + armature.name + "' has no active action to redirect")
    elif source.library or not getattr(source, 'is_editable', True):
        raise ValueError("The active action '" + source.name + "' is linked/read only")
    elif animation.use_tweak_mode:
        raise ValueError("Exit NLA tweak mode on '" + armature.name + "' first")
    elif not armature.pose.bones.get(root_name):
        raise ValueError("'" + root_name + "' isn't a bone on '" + armature.name + "'")
    elif abs(angle) < 1e-6:
        raise ValueError("Angle can't be zero")
    elif not name:
        raise ValueError("The new action needs a name")
    # removing the original can't take anyone elses animation with it...
    if not keep_original:
        others = sorted(i.name for i in bpy.data.user_map(subset={source})[source] if i != armature)
        if others:
            raise ValueError("The original '" + source.name + "' is also used by " + ", ".join(others) + ", so it can't be removed (keep the original instead)")
    # just a batch of one action with one direction...
    return set_redirected_actions(armature, root_name, ((source, ((axis, angle, name),)),), keep_original, stash_action, target_names)[0][1][0]

def set_redirect_directions(entry):
    # resizes an actions directions to exactly its count, trimmed off the end so authored ones are kept... (new ones get named after the action)...
    while len(entry.directions) > entry.direction_count:
        entry.directions.remove(len(entry.directions) - 1)
    while len(entry.directions) < entry.direction_count:
        entry.directions.add().action_name = entry.action

def get_redirect_entries(armature, root_name, entries, keep_original, target_names):
    # checks every (action, ((axis, angle, name), ...)) entry before anything gets touched, giving back (action, slot, ((axis, angle, name), ...))...
    animation, root = armature.animation_data, armature.pose.bones.get(root_name)
    targets = [n for n in target_names if n != root_name]
    missing = [n for n in targets if n not in armature.pose.bones]
    if not root:
        raise ValueError("'" + root_name + "' isn't a bone on '" + armature.name + "'")
    elif animation and animation.use_tweak_mode:
        raise ValueError("Exit NLA tweak mode on '" + armature.name + "' first")
    elif missing:
        raise ValueError("Not bones on '" + armature.name + "': " + ", ".join(missing))
    elif not entries:
        raise ValueError("Add at least one action to redirect")
    # a selection that can't be countered gets caught now rather than halfway through...
    if targets:
        get_countered_targets(armature, root, targets)
    checked, seen = [], set()
    for index, (action, directions) in enumerate(entries, 1):
        label = "Entry " + str(index) + (" ('" + action.name + "')" if action else "")
        if not action:
            raise ValueError(label + " has no action")
        elif action.library or not getattr(action, 'is_editable', True):
            raise ValueError(label + " is linked/read only")
        elif action in seen:
            raise ValueError(label + " is listed more than once")
        elif not directions:
            raise ValueError(label + " needs at least one direction")
        # the active action keeps the slot it's on, anything else gets the slot that animates this armature...
        slot = animation.action_slot if animation and animation.action == action and animation.action_slot else utilities.functions.get_action_slot(action, armature)
        if not slot:
            raise ValueError(label + " has no slot that animates '" + armature.name + "'")
        for number, (axis, angle, name) in enumerate(directions, 1):
            where = label + " direction " + str(number) + ": "
            if axis not in ('X', 'Y', 'Z'):
                raise ValueError(where + "The axis has to be X, Y or Z")
            elif not math.isfinite(angle) or abs(angle) < 1e-6:
                raise ValueError(where + "Angle can't be zero")
            elif not str(name).strip():
                raise ValueError(where + "The new action needs a name")
        # removing the original can't take anyone elses animation with it...
        if not keep_original:
            others = sorted(i.name for i in bpy.data.user_map(subset={action})[action] if i != armature)
            if others:
                raise ValueError("The original '" + action.name + "' is also used by " + ", ".join(others) + ", so it can't be removed (keep the original instead)")
        seen.add(action)
        checked.append((action, slot, tuple((axis, angle, str(name).strip()) for axis, angle, name in directions)))
    return checked

def set_redirected_actions(armature, root_name, entries, keep_original, stash_action, target_names=()):
    # redirects a fresh copy of every source action once per direction (countering any target bones on each), all or nothing...
    checked = get_redirect_entries(armature, root_name, entries, keep_original, target_names)
    created = not armature.animation_data
    animation = armature.animation_data if not created else armature.animation_data_create()
    scene = bpy.context.scene
    current = scene.frame_current, scene.frame_subframe
    previous, previous_slot, tracks, track = animation.action, animation.action_slot, list(animation.nla_tracks), animation.nla_tracks.active
    # stashing can change how the existing nla looks, so its selection, mute and lock get put back...
    states = [(t, t.select, t.mute, t.lock, [(s, s.select) for s in t.strips]) for t in tracks]
    # redirecting poses the bones as it keys, so their channels get put back afterwards...
    poses = {b.name: (b.location.copy(), b.rotation_quaternion.copy(), b.rotation_euler.copy(), tuple(b.rotation_axis_angle), b.scale.copy()) for b in armature.pose.bones}
    targets = [n for n in target_names if n != root_name]
    selected = set(targets + [root_name])
    made, results = [], []
    try:
        for source, slot, directions in checked:
            outputs = []
            for axis, angle, name in directions:
                # every direction starts from the untouched original, never from the last copy...
                action = source.copy()
                made.append(action)
                # a taken name just gets blenders usual .001 suffix...
                action.name = name
                # only the copy gets redirected, on the same slot the original was using...
                animation.action = action
                copied = next((s for s in action.slots if s.identifier == slot.identifier), None)
                if copied:
                    animation.action_slot = copied
                # only authored motion gets redirected, so leftover unkeyed offsets are cleared... (the first sampled frame puts back whatever the copy keys)...
                for pose_bone in armature.pose.bones:
                    pose_bone.location, pose_bone.rotation_quaternion, pose_bone.rotation_euler, pose_bone.rotation_axis_angle = (0, 0, 0), (1, 0, 0, 0), (0, 0, 0), (0, 0, 1, 0)
                bones, frames = set_redirected_motion(armature, root_name, axis, angle)
                # then the targets get countered on that same copy, around where the redirected root ended up...
                chains, controls = set_countered_motion(armature, root_name, targets, axis, angle)[:2] if targets else (0, 0)
                outputs.append((action, copied, bones, frames, chains, controls))
            results.append((source, outputs))
        # a kept original only gets stashed if the nla isn't already holding onto it...
        if keep_original:
            for source, _, _ in checked:
                if not any(s.action == source for t in animation.nla_tracks for s in t.strips):
                    utilities.functions.set_stashed_action(armature, source)
        # and the redirected actions get stashed too if wanted, named after whatever names they actually ended up with...
        if stash_action:
            for action in made:
                if not any(s.action == action for t in animation.nla_tracks for s in t.strips):
                    utilities.functions.set_stashed_action(armature, action)
        # put the nla state back...
        for t, select, mute, lock, strips in states:
            t.select, t.mute, t.lock = select, mute, lock
            for s, strip_select in strips:
                s.select = strip_select
        if track:
            animation.nla_tracks.active = track
        # kept originals with stashed results leave whatever was active alone, otherwise the last redirected one is active on its copied slot...
        active, active_slot = (previous, previous_slot) if keep_original and stash_action else results[-1][1][-1][:2]
        animation.action = active
        if active and active_slot:
            animation.action_slot = active_slot
        if animation.action != active or (active and active_slot and animation.action_slot != active_slot):
            raise ValueError("Blender wouldn't make '" + (active.name if active else "nothing") + "' the active action")
        # the selected bones get their transforms cleared and everything else put back...
        for pose_bone in armature.pose.bones:
            if pose_bone.name in selected:
                pose_bone.location, pose_bone.rotation_quaternion, pose_bone.rotation_euler, pose_bone.rotation_axis_angle, pose_bone.scale = (0, 0, 0), (1, 0, 0, 0), (0, 0, 0), (0, 0, 1, 0), (1, 1, 1)
            else:
                pose_bone.location, pose_bone.rotation_quaternion, pose_bone.rotation_euler, pose_bone.rotation_axis_angle, pose_bone.scale = poses[pose_bone.name]
        # then a quick frame jog so blender evaluates the active actions pose where we started...
        scene.frame_set(current[0] + 1)
        scene.frame_set(current[0], subframe=current[1])
    except Exception:
        # put everything back exactly as it was... (no partial actions, stashes or pose left behind)...
        for t in list(animation.nla_tracks):
            if t not in tracks:
                animation.nla_tracks.remove(t)
        for t, select, mute, lock, strips in states:
            t.select, t.mute, t.lock = select, mute, lock
            for s, strip_select in strips:
                s.select = strip_select
        if track:
            animation.nla_tracks.active = track
        animation.action = previous
        if previous_slot:
            animation.action_slot = previous_slot
        for action in made:
            bpy.data.actions.remove(action)
        for pose_bone in armature.pose.bones:
            pose_bone.location, pose_bone.rotation_quaternion, pose_bone.rotation_euler, pose_bone.rotation_axis_angle, pose_bone.scale = poses[pose_bone.name]
        if created:
            armature.animation_data_clear()
        scene.frame_set(current[0], subframe=current[1])
        raise
    summary = [(source.name, [(o[0].name,) + o[2:] for o in outputs]) for source, outputs in results]
    # originals only go once every redirected action has been made...
    if not keep_original:
        for source, _, _ in checked:
            utilities.functions.remove_stashed_action(armature, source)
            bpy.data.actions.remove(source)
    return summary

def get_spline_targets(armature):
    # every target of this add-ons spline modules mapped to its target parent, from the saved module settings... (only our own rigs, nothing gets guessed)...
    targets = {}
    for module in getattr(getattr(armature.data, 'mmt', None), 'rigging', []):
        # spline targets are children of the first parent bone...
        if module.rigging == 'SPLINE':
            prefices, suffices = module.settings.prefices, module.settings.suffices
            if 'parent' in prefices and 'target' in prefices and 'first' in suffices:
                parent = armature.pose.bones.get(prefices['parent'].affix + suffices['first'].affix)
                for child in (parent.children if parent else []):
                    if child.name.startswith(prefices['target'].affix):
                        targets[child.name] = parent.name
    return targets

def get_countered_targets(armature, root, names):
    # splits the targets into root to tip hierarchy chains and independent controls, by structure not by name... (spline targets are always controls)...
    selected = {n for n in names if n != root.name}
    splines = {n: p for n, p in get_spline_targets(armature).items() if n in selected}
    for parent in set(splines.values()):
        # a selected spline parent that follows the root already carries the redirect, so it just passes it through to its targets...
        if parent in selected and armature.pose.bones[parent].parent is None and any(c.type == 'CHILD_OF' and not c.mute and c.influence > 0.999
            and c.target == armature and c.subtarget == root.name for c in armature.pose.bones[parent].constraints):
            selected.discard(parent)
    selected -= set(splines)
    bones = [armature.pose.bones[n] for n in sorted(selected)]
    chains, controls = [], []
    for pose_bone in bones:
        children = [c for c in pose_bone.children if c.name in selected]
        if len(children) > 1:
            raise ValueError("'" + pose_bone.name + "' has more than one selected child, branching selections aren't supported")
        elif pose_bone.parent is None and not children:
            # a free bone is a control unless it follows something through a child of...
            if any(c.type == 'CHILD_OF' for c in pose_bone.constraints):
                raise ValueError("'" + pose_bone.name + "' inherits through a Child Of constraint, select what it follows instead")
            controls.append(pose_bone)
        elif not (pose_bone.parent and pose_bone.parent.name in selected):
            # the start of a chain, walk down through the single selected child...
            chain = [pose_bone]
            while children:
                chain.append(children[0])
                children = [c for c in chain[-1].children if c.name in selected]
            chains.append(chain)
    return chains, controls + [armature.pose.bones[n] for n in sorted(splines)]

def set_countered_motion(armature, root_name, target_names, axis, angle):
    # rotates the targets (counter to a redirect) around the roots animated world position, hierarchy chains spread it evenly, independent controls are moved and rotated around it...
    action = armature.animation_data.action if armature.animation_data else None
    root = armature.pose.bones.get(root_name)
    missing = [n for n in target_names if n not in armature.pose.bones]
    if not action:
        raise ValueError("The active armature has no active action")
    elif action.library or not getattr(action, 'is_editable', True):
        raise ValueError("The active action '" + action.name + "' is linked/read only")
    elif not root:
        raise ValueError("'" + root_name + "' isn't a bone on '" + armature.name + "'")
    elif missing:
        raise ValueError("Not bones on '" + armature.name + "': " + ", ".join(missing))
    elif not [n for n in target_names if n != root_name]:
        raise ValueError("Select at least one bone other than the active root")
    elif abs(angle) < 1e-6:
        raise ValueError("Angle can't be zero")
    # get what's being countered and remember the scene...
    chains, controls = get_countered_targets(armature, root, target_names)
    scene = bpy.context.scene
    current = scene.frame_current, scene.frame_subframe
    frames = list(range(math.ceil(action.frame_range[0]), math.floor(action.frame_range[1]) + 1))
    bones = [b for chain in chains for b in chain] + controls
    snapshots = {b.name: {} for b in bones}
    pivots = {}
    try:
        # snapshot every frame before touching a single key...
        for frame in frames:
            scene.frame_set(frame)
            world = armature.matrix_world.copy()
            pivots[frame] = (world, (world @ root.matrix).translation.copy())
            for pose_bone in bones:
                previous = pose_bone.rotation_quaternion.copy() if pose_bone.rotation_mode == 'QUATERNION' else pose_bone.rotation_euler.copy()
                snapshots[pose_bone.name][frame] = (pose_bone.matrix.copy(), pose_bone.matrix_basis.copy(), previous)
        # chains spread the angle along their bones...
        for chain in chains:
            # each bone adds an equal share, the parents already carry everything before it so the tip ends up with the whole lot...
            for pose_bone in chain:
                for frame in frames:
                    world, _ = pivots[frame]
                    pose, basis, previous = snapshots[pose_bone.name][frame]
                    step = world.to_3x3().inverted() @ Matrix.Rotation(-angle / len(chain), 3, axis) @ world.to_3x3()
                    # solved through whatever sits in front of the basis (parents, rest, before original copy rotations)...
                    front = (pose @ basis.inverted()).to_3x3()
                    rotation = (front.inverted() @ step @ front @ basis.to_3x3()).to_quaternion()
                    pose_bone.keyframe_insert(set_redirected_rotation(pose_bone, rotation, previous), frame=frame)
        # independent controls orbit the root instead...
        for pose_bone in controls:
            for frame in frames:
                world, pivot = pivots[frame]
                pose, basis, previous = snapshots[pose_bone.name][frame]
                # orbit the whole world matrix around the roots position at this frame...
                countered = Matrix.Translation(pivot) @ Matrix.Rotation(-angle, 4, axis) @ Matrix.Translation(-pivot)
                location, rotation, _ = (basis @ pose.inverted() @ world.inverted() @ countered @ world @ pose).decompose()
                pose_bone.location = location
                pose_bone.keyframe_insert('location', frame=frame)
                pose_bone.keyframe_insert(set_redirected_rotation(pose_bone, rotation, previous), frame=frame)
    finally:
        scene.frame_set(current[0], subframe=current[1])
    return len(chains), len(controls), len(frames)

def get_locomotion_phases(armature, names, active, forward):
    # rings the feet around their footprint centre (seen from the direction of travel) with the active foot first, even counts alternate, odd counts stagger evenly...
    world = armature.matrix_world
    positions = {n: (world @ armature.pose.bones[n].matrix).translation for n in names}
    centre = sum(positions.values(), Vector((0.0, 0.0, 0.0))) / len(names)
    lateral = Vector((0.0, 0.0, 1.0)).cross(forward)
    ring = sorted(names, key=lambda n: (math.atan2((positions[n] - centre).dot(lateral), (positions[n] - centre).dot(forward)), n))
    start = ring.index(active)
    ring = ring[start:] + ring[:start]
    if len(ring) % 2 == 0:
        phases = {n: 0.0 if i % 2 == 0 else 0.5 for i, n in enumerate(ring)}
    else:
        phases = {n: i / len(ring) for i, n in enumerate(ring)}
    return phases

def get_cyclic_offset(phase, step_length, step_height):
    # stance slides from a quarter step forward to a quarter step back, swing smoothly returns while lifting... (as forward and upward amounts)...
    phase = phase % 1.0
    # first half of the step, the foot slides back along the ground...
    if phase < 0.5:
        progress = phase / 0.5
        forward, upward = (step_length * 0.25) - (progress * step_length * 0.5), 0.0
    else:
        progress = (phase - 0.5) / 0.5
        smooth = progress * progress * (3.0 - (2.0 * progress))
        forward, upward = (-step_length * 0.25) + (smooth * step_length * 0.5), step_height * math.sin(math.pi * progress)
    return forward, upward

def set_solved_location(armature, pose_bone, position):
    # moves the bones location so its head lands on a world position, solved through whatever sits in front of its basis (parents, child of, rest)...
    world = armature.matrix_world
    basis, pose = pose_bone.matrix_basis, pose_bone.matrix
    inherited = (pose @ basis.inverted_safe()).to_3x3()
    if abs(inherited.determinant()) < 1e-9:
        raise ValueError("'" + pose_bone.name + "' can't be moved by its location (locked or non-invertible)")
    target = world.inverted() @ position
    pose_bone.location = basis.translation + (inherited.inverted() @ (target - pose.translation))

def get_world_rotation(angles):
    """the world rotation for (pitch, yaw, roll) on fixed world axes... (yaw about Z, then pitch about X, then roll about Y)..."""
    pitch, yaw, roll = angles
    return Matrix.Rotation(roll, 3, 'Y') @ Matrix.Rotation(pitch, 3, 'X') @ Matrix.Rotation(yaw, 3, 'Z')

def set_solved_matrix(armature, pose_bone, matrix, scale=False):
    # moves and turns the bone so it lands on a world matrix, solved through whatever sits in front of its basis... (returns the rotation path it set)... (scale is only set when asked)...
    world = armature.matrix_world
    basis, pose = pose_bone.matrix_basis, pose_bone.matrix
    if abs(pose.to_3x3().determinant()) < 1e-12:
        raise ValueError("'" + pose_bone.name + "' can't be turned by its rotation (locked or non-invertible)")
    previous = pose_bone.rotation_quaternion.copy() if pose_bone.rotation_mode == 'QUATERNION' else pose_bone.rotation_euler.copy()
    location, rotation, scaling = (basis @ pose.inverted() @ world.inverted() @ matrix).decompose()
    pose_bone.location = location
    if scale:
        pose_bone.scale = scaling
    return set_redirected_rotation(pose_bone, rotation, previous)

def get_turned_error(armature, pose_bone, rotation):
    # how far the bones evaluated world orientation ended up from where it was asked to turn...
    actual = (armature.matrix_world @ pose_bone.matrix).to_3x3().normalized()
    desired = rotation.normalized()
    return max(abs(actual[i][j] - desired[i][j]) for i in range(3) for j in range(3))

def get_reached_error(armature, pose_bone, position):
    # how far the bones evaluated head ended up from where it was asked to go...
    return ((armature.matrix_world @ pose_bone.matrix).translation - position).length

def get_scaled_error(armature, pose_bone, matrix):
    # how far (as a fraction) each of the bones evaluated world axis lengths ended up from the ones it was asked to scale to...
    actual, desired = (armature.matrix_world @ pose_bone.matrix).to_3x3(), matrix.to_3x3()
    return max(abs((actual.col[i].length / desired.col[i].length) - 1.0) for i in range(3))

def set_cyclic_action(action, start, end, offset, fcurves=None):
    # marks the action as a cycle over its keys and makes every curve (or just the given ones) actually repeat... (travelling location curves carry their offset into each repeat)...
    action.use_frame_range = True
    action.frame_start, action.frame_end = start, end
    action.use_cyclic = True
    for fcurve in fcurves if fcurves is not None else utilities.functions.get_action_fcurves(action):
        # only add cycles if it isn't there already... (location can offset each loop)
        if not any(m.type == 'CYCLES' for m in fcurve.modifiers):
            cycles = fcurve.modifiers.new(type='CYCLES')
            mode = 'REPEAT_OFFSET' if offset and fcurve.data_path.endswith('.location') else 'REPEAT'
            cycles.mode_before, cycles.mode_after = mode, mode

def get_swing_entries(bones, swings, authored):
    # validates the swing entries into plain (bone, pivot, minimum, maximum, frequency) tuples... (the gait bones are already spoken for)...
    entries = []
    for index, swing in enumerate(swings or ()):
        bone, pivot, minimum, maximum, frequency = swing
        label = "Swing " + str(index + 1)
        if not bones.get(bone) or not bones.get(pivot):
            raise ValueError(label + " needs an existing bone and pivot (got '" + str(bone) + "' and '" + str(pivot) + "')")
        elif bone == pivot:
            raise ValueError(label + " can't swing '" + bone + "' around itself")
        elif any(e[0] == bone for e in entries):
            raise ValueError(label + " swings '" + bone + "' which is already swung by another entry")
        elif bone in authored:
            raise ValueError(label + " can't swing '" + bone + "', the root, pelvis and feet are already driven by the gait")
        elif frequency < 1 or int(frequency) != frequency:
            raise ValueError(label + " needs a whole number frequency of at least 1")
        elif len(minimum) != 3 or len(maximum) != 3 or not all(math.isfinite(v) for v in tuple(minimum) + tuple(maximum)):
            raise ValueError(label + " needs finite X, Y and Z min and max angles")
        entries.append((bone, pivot, Vector(minimum), Vector(maximum), int(frequency)))
    return entries

def set_swung_bones(armature, entries, relative, bases, cycles, frame):
    # swings every entry rigidly around its pivots live position by world X then Y then Z angles... (all from one unswung snapshot, so order never matters)...
    bones = armature.pose.bones
    # put the swings back to their unswung pose, so pivots that swing themselves still read as unswung...
    for bone, _, _, _, _ in entries:
        location, quaternion, euler, axis_angle, _ = bases[bone]
        bones[bone].location, bones[bone].rotation_quaternion, bones[bone].rotation_euler, bones[bone].rotation_axis_angle = location, quaternion, euler, axis_angle
    bpy.context.view_layer.update()
    world = armature.matrix_world
    pivots = {p: (world @ bones[p].matrix).copy() for _, p, _, _, _ in entries}
    desired = {}
    for bone, pivot, minimum, maximum, frequency in entries:
        blend = (1.0 - math.cos(2.0 * math.pi * frequency * cycles)) * 0.5
        angles = minimum + ((maximum - minimum) * blend)
        rotation = Matrix.Rotation(angles.z, 4, 'Z') @ Matrix.Rotation(angles.y, 4, 'Y') @ Matrix.Rotation(angles.x, 4, 'X')
        point = pivots[pivot].translation
        desired[bone] = Matrix.Translation(point) @ rotation @ Matrix.Translation(-point) @ pivots[pivot] @ relative[bone]
    # a few passes lets swings that inherit from other swings settle onto their own targets...
    paths, settled = {}, False
    for attempt in range(len(entries) + 1):
        # not settled yet, so solve the desired matrices again...
        if not settled:
            for bone in desired:
                paths[bone] = set_solved_matrix(armature, bones[bone], desired[bone])
            bpy.context.view_layer.update()
            settled = all(get_reached_error(armature, bones[b], m.translation) < 1e-5 and get_turned_error(armature, bones[b], m.to_3x3()) < 1e-5 for b, m in desired.items())
    for index, (bone, _, _, _, _) in enumerate(entries):
        if get_reached_error(armature, bones[bone], desired[bone].translation) > 1e-4 or get_turned_error(armature, bones[bone], desired[bone].to_3x3()) > 1e-4:
            raise ValueError("Swing " + str(index + 1) + " ('" + bone + "') can't reach its swung transform (check its constraints, locks and the armature objects scale)")
        bones[bone].keyframe_insert('location', frame=frame)
        bones[bone].keyframe_insert(paths[bone], frame=frame)

def set_generated_locomotion(armature, root_name, pelvis_name, target_names, active_name, root_motion, direction, speed, step_height, step_length, pelvic_bob, loop_count, pelvis_offset=(0.0, 0.0, 0.0), pelvis_rotation_offset=(0.0, 0.0, 0.0), pelvic_rotation=(0.0, 0.0, 0.0), swings=None, action_name=None):
    # keys a looping procedural gait into a new action, feet stepping in phase around the active foot, the pelvis bobbing and optionally the root travelling...
    bones = armature.pose.bones
    targets = list(dict.fromkeys(target_names))
    planar = Vector((direction[0], direction[1], 0.0))
    pelvis_offset = Vector(pelvis_offset)
    pelvis_rotation_offset, pelvic_rotation = tuple(pelvis_rotation_offset), tuple(pelvic_rotation)
    if not bones.get(root_name) or not bones.get(pelvis_name) or root_name == pelvis_name:
        raise ValueError("Root and pelvis must be two different bones on '" + armature.name + "'")
    elif len(targets) < 2 or any(n not in bones for n in targets):
        raise ValueError("Select at least two foot targets on '" + armature.name + "'")
    elif active_name not in targets:
        raise ValueError("The active bone must be one of the selected foot targets")
    elif root_name in targets or pelvis_name in targets:
        raise ValueError("The root and pelvis can't also be foot targets")
    elif speed <= 0.0 or step_length <= 0.0 or loop_count < 1 or step_height < 0.0 or pelvic_bob < 0.0:
        raise ValueError("Speed, step length and loops must be positive, step height and pelvic bob can't be negative")
    elif planar.length < 1e-6:
        raise ValueError("Direction needs some horizontal (XY) component")
    elif not all(math.isfinite(v) for v in pelvis_offset):
        raise ValueError("Pelvis offset must be a finite vector")
    elif len(pelvis_rotation_offset) != 3 or len(pelvic_rotation) != 3 or not all(math.isfinite(v) for v in pelvis_rotation_offset + pelvic_rotation):
        raise ValueError("Pelvis rotation offset and pelvic rotation must be finite (pitch, yaw, roll) angles")
    # validate the swings and work out the directions...
    entries = get_swing_entries(bones, swings, [root_name, pelvis_name] + targets)
    forward, upward = planar.normalized(), Vector((0.0, 0.0, 1.0))
    # store the scene state and work out the frames...
    scene = bpy.context.scene
    current = scene.frame_current, scene.frame_subframe
    scene_range = scene.frame_start, scene.frame_end
    fps = scene.render.fps / scene.render.fps_base
    cycle_frames = max(2, round((step_length / speed) * fps))
    first = scene.frame_current
    frames = list(range(first, first + (cycle_frames * loop_count) + 1))
    root, pelvis = bones[root_name], bones[pelvis_name]
    # the neutral pose everything is generated around, captured before any action changes...
    world = armature.matrix_world
    neutral = {n: (world @ bones[n].matrix).translation.copy() for n in [root_name, pelvis_name] + targets}
    # the pelvis only gets turned (and rotation keys) when either rotation layer is actually used...
    turning = any(v != 0.0 for v in pelvis_rotation_offset + pelvic_rotation)
    orientation = (world @ pelvis.matrix).to_3x3() if turning else None
    phases = get_locomotion_phases(armature, targets, active_name, forward)
    # each swing rides rigidly on its pivot, so remember where it sat relative to it...
    relative = {b: (world @ bones[p].matrix).inverted() @ (world @ bones[b].matrix) for b, p, _, _, _ in entries}
    bases = {b.name: (b.location.copy(), b.rotation_quaternion.copy(), b.rotation_euler.copy(), tuple(b.rotation_axis_angle), b.scale.copy()) for b in bones}
    # get the animation data ready, remembering what's there...
    if not armature.animation_data:
        armature.animation_data_create()
    previous, previous_slot = armature.animation_data.action, armature.animation_data.action_slot
    tracks = list(armature.animation_data.nla_tracks)
    # a blank name falls back to the old automatic one, blender adds .001 etc. itself if it's taken...
    action_name = str(action_name).strip() if action_name is not None else ""
    action = bpy.data.actions.new(action_name or armature.name + "_Locomotion")
    keyed = ([root] if root_motion else []) + [pelvis] + [bones[n] for n in targets] + [bones[e[0]] for e in entries]
    try:
        # stash whatever was active (once) so it isn't lost, then key into the fresh action...
        if previous and not any(s.action == previous for t in tracks for s in t.strips):
            utilities.functions.set_stashed_action(armature, previous)
        armature.animation_data.action = action
        for frame in frames:
            scene.frame_set(frame)
            cycles = (frame - first) / cycle_frames
            travel = forward * (step_length * cycles) if root_motion else Vector((0.0, 0.0, 0.0))
            bob = upward * (-pelvic_bob * (1.0 - math.cos(4.0 * math.pi * cycles)) * 0.5)
            # the rotation bob eases exactly like the dip (sin squared) but swaps sides on every other one...
            sine = math.sin(2.0 * math.pi * cycles)
            pulse = sine * abs(sine)
            # the pelvis offset is a constant world shift (eg. a crouch) that the travel and bob layer on top of...
            desired = {pelvis_name: neutral[pelvis_name] + pelvis_offset + travel + bob}
            if root_motion:
                desired[root_name] = neutral[root_name] + travel
            for name in targets:
                ahead, lift = get_cyclic_offset(phases[name] + cycles, step_length, step_height)
                desired[name] = neutral[name] + travel + (forward * ahead) + (upward * lift)
            # the constant rotation offset plus the alternating rotation bob...
            turned = get_world_rotation([o + (pulse * b) for o, b in zip(pelvis_rotation_offset, pelvic_rotation)]) @ orientation if turning else None
            # root first, then the pelvis, then the feet, each solved against the live state of whatever they inherit from...
            for group in ([root] if root_motion else [], [pelvis], [bones[n] for n in targets]):
                for pose_bone in group:
                    # the turning pelvis solves from its own position and the turned rotation...
                    if turning and pose_bone == pelvis:
                        path = set_solved_matrix(armature, pose_bone, Matrix.Translation(desired[pose_bone.name]) @ turned.to_4x4())
                        pose_bone.keyframe_insert(path, frame=frame)
                    else:
                        set_solved_location(armature, pose_bone, desired[pose_bone.name])
                    pose_bone.keyframe_insert('location', frame=frame)
                bpy.context.view_layer.update()
                for pose_bone in group:
                    if get_reached_error(armature, pose_bone, desired[pose_bone.name]) > 1e-4:
                        raise ValueError("'" + pose_bone.name + "' can't reach its generated position (check its constraints and locks)")
                    elif turning and pose_bone == pelvis and get_turned_error(armature, pose_bone, turned) > 1e-4:
                        raise ValueError("'" + pose_bone.name + "' can't reach its generated rotation (check its constraints, locks and the armature objects scale)")
            # then the swings, layered on top of the finished gait...
            if entries:
                set_swung_bones(armature, entries, relative, bases, cycles, frame)
        # planted feet must not drift, so every generated key is linear...
        for fcurve in utilities.functions.get_action_fcurves(action):
            for point in fcurve.keyframe_points:
                point.interpolation = 'LINEAR'
        set_cyclic_action(action, frames[0], frames[-1], root_motion)
        # playback skips the terminal key, it's the same pose as the next cycles first frame...
        scene.frame_start, scene.frame_end = frames[0], frames[-1] - 1
    except Exception:
        # put everything back exactly as it was... (no partial action, stash or pose left behind)...
        for track in list(armature.animation_data.nla_tracks):
            if track not in tracks:
                armature.animation_data.nla_tracks.remove(track)
        armature.animation_data.action = previous
        if previous and previous_slot:
            armature.animation_data.action_slot = previous_slot
        bpy.data.actions.remove(action)
        scene.frame_start, scene.frame_end = scene_range
        for name, (location, quaternion, euler, axis_angle, scale) in bases.items():
            bones[name].location, bones[name].rotation_quaternion, bones[name].rotation_euler, bones[name].rotation_axis_angle, bones[name].scale = location, quaternion, euler, axis_angle, scale
        raise
    finally:
        scene.frame_set(current[0], subframe=current[1])
    # the speed we actually got after rounding to whole frames...
    realized = step_length / (cycle_frames / fps)
    return action, len(frames), cycle_frames, realized, len(keyed)

def get_looping_entries(bones, entries):
    # validates the looping entries into plain (bone, min location, max location, min rotation, max rotation, cycle offset, min scale, max scale) tuples...
    checked = []
    for index, entry in enumerate(entries or ()):
        bone, minimum_location, maximum_location, minimum_rotation, maximum_rotation, cycle_offset, minimum_scale, maximum_scale = entry
        label = "Looping bone " + str(index + 1) + " ('" + str(bone) + "')"
        vectors = (minimum_location, maximum_location, minimum_rotation, maximum_rotation)
        if not bones.get(bone):
            raise ValueError(label + " isn't a bone on this armature")
        elif any(e[0] == bone for e in checked):
            raise ValueError(label + " is listed more than once")
        elif any(len(v) != 3 for v in vectors) or not all(math.isfinite(c) for v in vectors for c in v):
            raise ValueError(label + " needs finite X, Y and Z min and max values")
        elif not math.isfinite(cycle_offset) or cycle_offset < 0.0 or cycle_offset > 1.0:
            raise ValueError(label + " needs a cycle offset between 0 and 1")
        # scale is a multiplier on whatever scale the action already has, so it has to stay above zero...
        elif any(len(v) != 3 for v in (minimum_scale, maximum_scale)) or not all(math.isfinite(c) and c > 0.0 for v in (minimum_scale, maximum_scale) for c in v):
            raise ValueError(label + " needs finite X, Y and Z min and max scale factors above zero")
        checked.append((bone, Vector(minimum_location), Vector(maximum_location), Vector(minimum_rotation), Vector(maximum_rotation), float(cycle_offset), Vector(minimum_scale), Vector(maximum_scale)))
    return checked

def get_looped_matrix(base, blend, entry):
    # scales the bone along its own local axes, turns it around its own head by world X then Y then Z, then shifts it by the world location offset...
    _, minimum_location, maximum_location, minimum_rotation, maximum_rotation, _, minimum_scale, maximum_scale = entry
    location = minimum_location + ((maximum_location - minimum_location) * blend)
    angles = minimum_rotation + ((maximum_rotation - minimum_rotation) * blend)
    factors = minimum_scale + ((maximum_scale - minimum_scale) * blend)
    rotation = Matrix.Rotation(angles.z, 3, 'Z') @ Matrix.Rotation(angles.y, 3, 'Y') @ Matrix.Rotation(angles.x, 3, 'X')
    # the factors go on the right so they multiply the bones local axes, never world ones... (world axis non uniform scale would shear)...
    looped = (rotation @ base.to_3x3() @ Matrix.Diagonal(factors)).to_4x4()
    looped.translation = base.translation + location
    return looped

def get_curve_backup(action, paths):
    # everything about the curves we're about to key, so a failed commit can put the same action back exactly...
    backup = {}
    for fcurve in utilities.functions.get_action_fcurves(action):
        # back up the keys of every path we're about to touch...
        if (fcurve.data_path, fcurve.array_index) in paths:
            points = [(tuple(k.co), tuple(k.handle_left), tuple(k.handle_right), k.handle_left_type, k.handle_right_type, k.interpolation, k.easing, k.back, k.amplitude, k.period, k.type) for k in fcurve.keyframe_points]
            backup[(fcurve.data_path, fcurve.array_index)] = (points, len(fcurve.modifiers))
    return backup

def set_curve_point(point, values):
    point.co, point.handle_left, point.handle_right = values[0], values[1], values[2]
    point.handle_left_type, point.handle_right_type, point.interpolation = values[3], values[4], values[5]
    point.easing, point.back, point.amplitude, point.period, point.type = values[6], values[7], values[8], values[9], values[10]

def get_curve_channelbag(action, fcurve):
    # the channelbag (slotted action) an fcurve lives in...
    return next(c for l in action.layers for s in l.strips for c in s.channelbags if any(f == fcurve for f in c.fcurves))

def set_curve_restored(action, paths, backup):
    # puts the backed up curves back on the same action... (curves that didn't exist before get removed again)...
    for fcurve in utilities.functions.get_action_fcurves(action):
        key = (fcurve.data_path, fcurve.array_index)
        if key in paths and key not in backup:
            get_curve_channelbag(action, fcurve).fcurves.remove(fcurve)
        elif key in backup:
            # put the backed up modifiers and keys back...
            points, modifiers = backup[key]
            while len(fcurve.modifiers) > modifiers:
                fcurve.modifiers.remove(fcurve.modifiers[-1])
            fcurve.keyframe_points.clear()
            fcurve.keyframe_points.add(len(points))
            for point, values in zip(fcurve.keyframe_points, points):
                set_curve_point(point, values)

def set_looped_motion(armature, entries, speed, frequency, loop_count):
    # layers smooth world space location/rotation (and local scale factor) oscillations onto the active actions existing motion, in place...
    action = armature.animation_data.action if armature.animation_data else None
    bones = armature.pose.bones
    if not action:
        raise ValueError("The active armature has no active action to loop")
    elif action.library or not getattr(action, 'is_editable', True):
        raise ValueError("The active action '" + action.name + "' is linked/read only")
    elif not entries:
        raise ValueError("Select at least one bone to loop")
    elif speed <= 0.0 or not math.isfinite(speed):
        raise ValueError("Speed must be a positive number of loops per second")
    elif frequency < 1 or int(frequency) != frequency or loop_count < 1 or int(loop_count) != loop_count:
        raise ValueError("Frequency and loops must be whole numbers of at least 1")
    entries = get_looping_entries(bones, entries)
    # a bone with nothing to do isn't touched at all... (and only bones with scale factors get their scale solved and keyed)...
    active = [e for e in entries if any(c != 0.0 for v in e[1:5] for c in v) or any(c != 1.0 for v in e[6:8] for c in v)]
    scaled = {e[0] for e in active if any(c != 1.0 for v in e[6:8] for c in v)}
    scene = bpy.context.scene
    current = scene.frame_current, scene.frame_subframe
    scene_range = scene.frame_start, scene.frame_end
    fps = scene.render.fps / scene.render.fps_base
    cycle_frames = max(2, round((1.0 / speed) * fps))
    first = scene.frame_current
    frames = list(range(first, first + (cycle_frames * int(loop_count)) + 1))
    bases = {b.name: (b.location.copy(), b.rotation_quaternion.copy(), b.rotation_euler.copy(), tuple(b.rotation_axis_angle), b.scale.copy()) for b in bones}
    solved, paths, cyclic = {}, {}, True
    try:
        # snapshot the untouched action at every frame first, the oscillation is added on top of whatever it already does...
        snapshots = {}
        for frame in frames:
            scene.frame_set(frame)
            snapshots[frame] = {e[0]: (armature.matrix_world @ bones[e[0]].matrix).copy() for e in active}
        cyclic = all(max(abs(a - b) for ra, rb in zip(snapshots[frames[0]][e[0]], snapshots[frames[-1]][e[0]]) for a, b in zip(ra, rb)) < 1e-4 for e in active)
        # then solve every frame live (without keying) so anything unreachable cancels before the action is touched...
        for frame in frames:
            scene.frame_set(frame)
            cycles = (frame - first) / cycle_frames
            desired = {}
            for entry in active:
                blend = (1.0 - math.cos(2.0 * math.pi * ((frequency * cycles) + entry[5]))) * 0.5
                desired[entry[0]] = get_looped_matrix(snapshots[frame][entry[0]], blend, entry)
            settled = False
            for attempt in range(len(active) + 1):
                # not settled yet, so solve the desired matrices again...
                if not settled:
                    for name, matrix in desired.items():
                        paths[name] = set_solved_matrix(armature, bones[name], matrix, scale=name in scaled)
                    bpy.context.view_layer.update()
                    settled = all(get_reached_error(armature, bones[n], m.translation) < 1e-5 and get_turned_error(armature, bones[n], m.to_3x3()) < 1e-5
                        and (n not in scaled or get_scaled_error(armature, bones[n], m) < 1e-5) for n, m in desired.items())
            for name, matrix in desired.items():
                if get_reached_error(armature, bones[name], matrix.translation) > 1e-4 or get_turned_error(armature, bones[name], matrix.to_3x3()) > 1e-4 or (name in scaled and get_scaled_error(armature, bones[name], matrix) > 1e-4):
                    raise ValueError("'" + name + "' can't reach its looped transform (check its constraints, locks and the armature objects scale)")
                solved[(name, frame)] = (bones[name].location.copy(), tuple(getattr(bones[name], paths[name])), bones[name].scale.copy())
    except Exception:
        for name, (location, quaternion, euler, axis_angle, scale) in bases.items():
            bones[name].location, bones[name].rotation_quaternion, bones[name].rotation_euler, bones[name].rotation_axis_angle, bones[name].scale = location, quaternion, euler, axis_angle, scale
        scene.frame_set(current[0], subframe=current[1])
        raise
    # commit... (backing up only the curves we key, so a failure puts the same action back exactly)...
    keys = {('pose.bones["' + n + '"].location', i) for n in paths for i in range(3)} | {('pose.bones["' + n + '"].' + p, i) for n, p in paths.items() for i in range(4 if p != 'rotation_euler' else 3)}
    keys |= {('pose.bones["' + n + '"].scale', i) for n in scaled for i in range(3)}
    backup = get_curve_backup(action, keys)
    ranges = action.use_frame_range, action.frame_start, action.frame_end, action.use_cyclic
    try:
        for frame in frames:
            # evaluate the frame first, then put the solved values back on top... (keying a stale frame collapses new curves onto it)...
            scene.frame_set(frame)
            for name in paths:
                location, rotation, scale = solved[(name, frame)]
                bones[name].location = location
                setattr(bones[name], paths[name], rotation)
                bones[name].keyframe_insert('location', frame=frame)
                bones[name].keyframe_insert(paths[name], frame=frame)
                # only scaled bones get scale keys...
                if name in scaled:
                    bones[name].scale = scale
                    bones[name].keyframe_insert('scale', frame=frame)
        # generated keys are linear, keys outside the range keep their original handles...
        fcurves = [f for f in utilities.functions.get_action_fcurves(action) if (f.data_path, f.array_index) in keys]
        for fcurve in fcurves:
            outside = {v[0][0]: v for v in backup.get((fcurve.data_path, fcurve.array_index), ([], 0))[0] if not (frames[0] <= v[0][0] <= frames[-1])}
            for point in fcurve.keyframe_points:
                if frames[0] <= point.co[0] <= frames[-1]:
                    point.interpolation = 'LINEAR'
                elif point.co[0] in outside:
                    set_curve_point(point, outside[point.co[0]])
        # make the new fcurves cyclic and fit the scene to them...
        if fcurves:
            set_cyclic_action(action, frames[0], frames[-1], False, fcurves=fcurves)
            scene.frame_start, scene.frame_end = frames[0], frames[-1] - 1
    except Exception:
        set_curve_restored(action, keys, backup)
        action.use_frame_range, action.frame_start, action.frame_end, action.use_cyclic = ranges
        scene.frame_start, scene.frame_end = scene_range
        for name, (location, quaternion, euler, axis_angle, scale) in bases.items():
            bones[name].location, bones[name].rotation_quaternion, bones[name].rotation_euler, bones[name].rotation_axis_angle, bones[name].scale = location, quaternion, euler, axis_angle, scale
        raise
    finally:
        scene.frame_set(current[0], subframe=current[1])
    realized = fps / cycle_frames
    return len(frames), cycle_frames, realized, len(paths), cyclic

def set_looping_bones(settings, names):
    # matches the looping entries to the selected bones in name order, keeping the values of any already listed...
    props = ('minimum_location', 'maximum_location', 'minimum_rotation', 'maximum_rotation', 'minimum_scale', 'maximum_scale', 'cycle_offset')
    kept = {e.bone: {p: (tuple(getattr(e, p)) if p != 'cycle_offset' else e.cycle_offset) for p in props} for e in settings.bones}
    settings.bones.clear()
    for name in sorted(names):
        entry = settings.bones.add()
        entry.bone = name
        for prop, value in kept.get(name, {}).items():
            setattr(entry, prop, value)

def get_keyed_range(action):
    # the first and last keyed frame across every curve of the action... (None if nothing is keyed)...
    frames = [k.co.x for fc in utilities.functions.get_action_fcurves(action) for k in fc.keyframe_points]
    return (min(frames), max(frames)) if frames else None

def get_split_ranges(start, end, count):
    # evenly spread inclusive ranges that share their boundaries and land exactly on both ends... (rounding can never flip one, no ranges at zero)...
    bounds = [start + int(math.floor(((end - start) * i / count) + 0.5)) for i in range(count + 1)] if count else []
    return [(bounds[i], bounds[i + 1]) for i in range(count)]

def set_split_count(settings):
    # existing entries are user data - trim only from the end, or spread only new entries across the unfinished tail...
    while len(settings.splits) > settings.split_count:
        settings.splits.remove(len(settings.splits) - 1)
    missing = settings.split_count - len(settings.splits)
    start = settings.splits[-1].end if settings.splits else settings.source_start
    for split_start, split_end in get_split_ranges(start, settings.source_end, missing):
        entry = settings.splits.add()
        entry.name = settings.source_name + "_" + str(len(settings.splits)).zfill(2)
        entry.start, entry.end = split_start, split_end

def set_split_entries(settings, action):
    # fresh split entries for a different action (or keyed range), the same one keeps whatever was entered last time...
    start, end = get_keyed_range(action)
    source = (action.name, math.ceil(start - 1e-4), math.floor(end + 1e-4))
    # the source or count changed, so the splits start over...
    if source != (settings.source_name, settings.source_start, settings.source_end) or len(settings.splits) != settings.split_count:
        settings.source_name, settings.source_start, settings.source_end = source
        settings.splits.clear()
        set_split_count(settings)

def get_unmodified_value(fcurve, frame):
    # the curves own keyed value at a frame, its modifiers are muted just long enough to read it... (evaluate includes them)...
    mutes = [m.mute for m in fcurve.modifiers]
    try:
        for modifier in fcurve.modifiers:
            modifier.mute = True
        return fcurve.evaluate(frame)
    finally:
        for modifier, mute in zip(fcurve.modifiers, mutes):
            modifier.mute = mute

def set_frozen_handles(point):
    # stops blender recalculating a keys handles when its neighbours change, so the curve keeps its exact shape...
    for side in ('handle_left_type', 'handle_right_type'):
        if getattr(point, side) in ('AUTO', 'AUTO_CLAMPED'):
            setattr(point, side, 'ALIGNED')
        elif getattr(point, side) == 'VECTOR':
            setattr(point, side, 'FREE')

def get_bezier_split(before, after, frame):
    # splits the bezier segment between two keys at a frame without changing its shape... (k0 right handle, new left handle, new key, new right handle, k1 left handle)...
    p0, p1, p2, p3 = before.co.copy(), before.handle_right.copy(), after.handle_left.copy(), after.co.copy()
    low, high = 0.0, 1.0
    for _ in range(64):
        t = (low + high) * 0.5
        x = ((1 - t) ** 3 * p0.x) + (3 * (1 - t) ** 2 * t * p1.x) + (3 * (1 - t) * t ** 2 * p2.x) + (t ** 3 * p3.x)
        low, high = (t, high) if x < frame else (low, t)
    t = (low + high) * 0.5
    a, b, c = p0.lerp(p1, t), p1.lerp(p2, t), p2.lerp(p3, t)
    d, e = a.lerp(b, t), b.lerp(c, t)
    return a, d, d.lerp(e, t), e, c

def set_split_boundary(fcurve, frame, value):
    # keys the source pose at a boundary frame, shaped by the segment it lands in... (an existing key there is left alone)...
    points = fcurve.keyframe_points
    if not any(abs(k.co.x - frame) < 1e-4 for k in points):
        # indices only, inserting reallocates the keys so any held keyframe goes stale...
        before = next((i for i in reversed(range(len(points))) if points[i].co.x < frame), None)
        after = next((i for i in range(len(points)) if points[i].co.x > frame), None)
        split = get_bezier_split(points[before], points[after], frame) if before is not None and after is not None and points[before].interpolation == 'BEZIER' else None
        # freeze both neighbours so their handles stay put...
        if split:
            set_frozen_handles(points[before])
            set_frozen_handles(points[after])
        elif before is not None and after is None:
            # past the last key the curve was extrapolated, a straight line matches constant and linear extrapolation exactly...
            points[before].interpolation = 'LINEAR'
        segment = (points[before].interpolation, points[before].easing, points[before].back, points[before].amplitude, points[before].period) if before is not None else None
        points.insert(frame, split[2].y if split else value, options={'FAST'})
        index = before + 1 if before is not None else 0
        point = points[index]
        # the new point takes the split bezier handles...
        if split:
            point.handle_left_type, point.handle_right_type = 'ALIGNED', 'ALIGNED'
            points[before].handle_right, point.handle_left, point.handle_right, points[index + 1].handle_left = split[0], split[1], split[3], split[4]
            point.interpolation = 'BEZIER'
        elif segment and after is not None:
            # constant, linear (and any easing) carry on with the segments own interpolation...
            point.interpolation, point.easing, point.back, point.amplitude, point.period = segment
        else:
            point.interpolation = 'LINEAR'

def set_split_curve(fcurve, start, end):
    # trims one curve down to the inclusive source range, then moves the retained keys and handles so the split starts at frame 1...
    points = fcurve.keyframe_points
    # only touch fcurves that have keys...
    if len(points):
        values = get_unmodified_value(fcurve, start), get_unmodified_value(fcurve, end)
        inside = [i for i in range(len(points)) if start - 1e-4 <= points[i].co.x <= end + 1e-4]
        for index in (inside[0], inside[-1]) if inside else ():
            set_frozen_handles(points[index])
        set_split_boundary(fcurve, start, values[0])
        set_split_boundary(fcurve, end, values[1])
        for index in reversed([i for i in range(len(points)) if points[i].co.x < start - 1e-4 or points[i].co.x > end + 1e-4]):
            points.remove(points[index], fast=True)
        fcurve.update()
        delta = 1 - start
        # assigning co.x can move handles in some Blender contexts, so restore every coordinate from one untouched snapshot...
        positions = [(point.co.x, point.handle_left.x, point.handle_right.x) for point in points]
        for point, (co_x, left_x, right_x) in zip(points, positions):
            point.co.x, point.handle_left.x, point.handle_right.x = co_x + delta, left_x + delta, right_x + delta

def get_split_entries(source, entries, keep_original):
    # validates the split entries into plain (name, start, end) tuples before anything gets touched...
    keyed = get_keyed_range(source)
    checked = []
    if not keyed:
        raise ValueError("'" + source.name + "' has no keyframes to split")
    elif not entries:
        raise ValueError("Add at least one split")
    for index, (name, start, end) in enumerate(entries):
        name, start, end = str(name).strip(), int(start), int(end)
        existing = next((a for a in bpy.data.actions if a.name == name and not a.library), None)
        label = "Split " + str(index + 1) + " ('" + name + "')"
        if not name:
            raise ValueError("Split " + str(index + 1) + " needs a name")
        elif start > end:
            raise ValueError(label + " starts after it ends (" + str(start) + " > " + str(end) + ")")
        elif start < keyed[0] - 1e-4 or end > keyed[1] + 1e-4:
            raise ValueError(label + " (" + str(start) + " to " + str(end) + ") is outside the keyed range of '" + source.name + "' (" + str(round(keyed[0], 3)) + " to " + str(round(keyed[1], 3)) + ")")
        elif any(c[0] == name for c in checked):
            raise ValueError(label + " is listed more than once")
        elif existing and not (existing == source and not keep_original):
            raise ValueError(label + " is already the name of an action" + (" (it can only take the originals name when the original isn't kept)" if existing == source else ""))
        checked.append((name, start, end))
    return checked

def set_split_action(armature, entries, keep_original):
    # splits the active action into new stashed actions, one per inclusive (name, start, end) range, removing the original afterwards if it isn't kept...
    animation = armature.animation_data
    source = animation.action if animation else None
    if not source:
        raise ValueError("'" + armature.name + "' has no active action to split")
    elif source.library or not getattr(source, 'is_editable', True):
        raise ValueError("The active action '" + source.name + "' is linked/read only")
    elif animation.use_tweak_mode:
        raise ValueError("Exit NLA tweak mode on '" + armature.name + "' first")
    checked = get_split_entries(source, entries, keep_original)
    # removing the original can't take anyone elses animation with it...
    if not keep_original:
        others = sorted(i.name for i in bpy.data.user_map(subset={source})[source] if i != armature)
        if others:
            raise ValueError("The original '" + source.name + "' is also used by " + ", ".join(others) + ", so it can't be removed (keep the original instead)")
    previous, previous_slot, tracks, source_name = animation.action, animation.action_slot, list(animation.nla_tracks), source.name
    created, claimed = [], None
    try:
        for name, start, end in checked:
            action = source.copy()
            # the originals name can only be taken once the original has gone, until then it gets a placeholder...
            if name == source_name:
                action.name, claimed = name + "_split", action
            else:
                action.name = name
            if action.name != name and action != claimed:
                raise ValueError("Blender wouldn't name the split '" + name + "' (got '" + action.name + "')")
            created.append(action)
            # trim the copy to its range...
            for fcurve in utilities.functions.get_action_fcurves(action):
                set_split_curve(fcurve, start, end)
            for marker in [m for m in action.pose_markers if m.frame < start or m.frame > end]:
                action.pose_markers.remove(marker)
            delta = 1 - start
            for marker in action.pose_markers:
                marker.frame += delta
            # then fit its frame range and stash it...
            action.use_frame_range = True
            action.frame_start, action.frame_end = 1, end - start + 1
            utilities.functions.set_stashed_action(armature, action)
        if claimed:
            # the original steps aside so the split can have its exact name...
            source.name = source_name + "_original"
            claimed.name = source_name
            if claimed.name != source_name:
                raise ValueError("Blender wouldn't give the split the originals name '" + source_name + "' (got '" + claimed.name + "')")
    except Exception:
        # put everything back exactly as it was... (no partial actions or stash left behind)...
        for track in list(animation.nla_tracks):
            if track not in tracks:
                animation.nla_tracks.remove(track)
        animation.action = previous
        if previous_slot:
            animation.action_slot = previous_slot
        # the splits go first, one of them might be holding the originals name...
        for action in created:
            bpy.data.actions.remove(action)
        source.name = source_name
        raise
    # the source action goes away unless it's being kept...
    if not keep_original:
        animation.action = None
        utilities.functions.remove_stashed_action(armature, source)
        bpy.data.actions.remove(source)
    # the stash tracks follow their actions names... (the placeholder one included)...
    for track in animation.nla_tracks:
        for strip in track.strips:
            if strip.action in created:
                track.name = strip.name = strip.action.name
    return [(a.name, int(a.frame_start), int(a.frame_end)) for a in created]
