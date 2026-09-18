import bpy

from .. import _functions, _interface
from ... import utilities

def get_twist_defaults():
    """get rigging defaults and choose which operator settings to show..."""
    defaults = {
        # default settings...
        'suffices' : [
            {'name' : "origin", 'affix' : "", 'unique' : True, 'required' : False},
            # chain bones are added by selection...
            ],
        'offset' : 0.1, 'mirror' : False, 'inverse' : False, 'axis' : 'AUTO',
        # default prefices...
        'prefices' : [
            {'name' : 'pole', 'affix' : "tvt_", 'required' : True, 'unique' : True},
            {'name' : 'forward', 'affix' : "", 'required' : False, 'unique' : True},
            {'name' : 'vector', 'affix' : "tkv_", 'required' : True, 'unique' : True},
            ],
        # default color palettes...
        'colors' : [
            {'name' : 'origin', 'palette' : 'THEME13'},
            {'name' : 'pole', 'palette' : 'THEME04'},
            {'name' : 'forward', 'palette' : 'THEME13'},
            ],
        # and default custom shapes...
        'shapes' : [
            {'name' : 'origin', 'mesh' : 'RING_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'BONE', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'pole', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'forward', 'mesh' : 'BICONE_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'vector', 'mesh' : 'ARROW_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.5, 0.5, 0.5), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            ]
        }
    return defaults

def get_twist_axis(target, axis):
    # auto picks whichever target bone axis points furthest from the world origin...
    axes = _functions.get_bone_axes(target, ['+X', '-X', '+Z', '-Z'])
    if axis == 'AUTO':
        axis, direction = utilities.functions.get_closest_axis(target.head.normalized(), axes)
        return axis, direction
    return axis, axes[axis]

def add_twist_bones(oriented, rig, settings):
    """add twist rigging bones (a locked track vector reads target twist)..."""
    # declare some variables...
    suffices, prefices, added = settings.suffices, settings.prefices, {}

    # if the origin is the target the vector needs its parent instead, so it's not rigidly locked to the targets own twist...
    parent_eb = None
    if suffices['origin'].affix == suffices['target'].affix:
        oriented_eb = oriented.data.edit_bones.get(suffices['origin'].affix).parent
        added[prefices['forward'].affix + oriented_eb.name] = {}
        existing = rig.data.edit_bones.get(prefices['forward'].affix + oriented_eb.name)
        if oriented_eb and not existing:
            prefix, suffix = prefices['forward'].affix, oriented_eb.name
            name = _functions.add_shared_bone(oriented, rig, prefix, suffix, 'origin', search=True)
            added[name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
        parent_eb = rig.data.edit_bones.get(prefices['forward'].affix + oriented_eb.name)

    # add the origin bone if there is one and it doesn't already exist on the rigging armature...
    added[prefices['forward'].affix + suffices['origin'].affix] = {}
    existing = rig.data.edit_bones.get(prefices['forward'].affix + suffices['origin'].affix)
    if suffices['origin'].affix and not existing:
        prefix, suffix = prefices['forward'].affix, suffices['origin'].affix
        name = _functions.add_shared_bone(oriented, rig, prefix, suffix, 'origin', search=True)
        added[name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
    elif suffices['origin'].affix and existing and settings.shared and not _functions.get_is_root(rig, existing.name):
        added[existing.name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
    origin_eb = rig.data.edit_bones.get(prefices['forward'].affix + suffices['origin'].affix)

    # for each bone in the chain... (skip non-chain bones, sorted nearest-to-origin first)...
    chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'target'}]
    heads = {s: oriented.data.edit_bones.get(suffices[s].affix).head for s in chain}
    chain.sort(key=lambda s: (heads[s] - origin_eb.head).length)

    # ending is auto detected on invoke, either the target itself or its furthest child...
    ending_eb = oriented.data.edit_bones.get(suffices['ending'].affix)
    # each forward bone gets an even share of the total start to end distance, not its own native length...
    total, _ = utilities.functions.get_distance_direction(origin_eb.head, ending_eb.head)
    length = total / len(chain)

    for index, suffix in enumerate(chain):
        # add a forward bone matching each chain bones own geometry, parented to the origin...
        oriented_eb = oriented.data.edit_bones.get(suffices[suffix].affix)
        next_eb = oriented.data.edit_bones.get(suffices[chain[index + 1]].affix) if index < len(chain) - 1 else ending_eb
        name, parent = prefices['forward'].affix + suffices[suffix].affix, origin_eb.name if origin_eb else ""
        # set head to oriented bone head and tail along the closest axis to the next bone...
        _, direction = utilities.functions.get_distance_direction(oriented_eb.head, next_eb.head)
        axes = _functions.get_bone_axes(oriented_eb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
        _, axis = utilities.functions.get_closest_axis(direction, axes)
        head, tail = oriented_eb.head, oriented_eb.head + (axis * length)
        # calulate roll closest to the origin bone... (or shortest roll if there isn't one)...
        axes = _functions.get_roll_axes(oriented_eb, head, tail)
        rolls = [utilities.functions.get_closest_vector(origin_eb.z_axis, axes.values())] if origin_eb else axes.values()
        _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
        # twist chain bones shouldn't be used by anything...
        added[name] = {'groups' : ['limited', 'secondary'], 'color' : 'forward', 'shape' : 'forward'}

    # add the twist target bone if it doesn't already exist on the rigging armature...
    added[prefices['forward'].affix + suffices['target'].affix] = {}
    existing = rig.data.edit_bones.get(prefices['forward'].affix + suffices['target'].affix)
    if not existing:
        prefix, suffix = prefices['forward'].affix, suffices['target'].affix
        name = _functions.add_shared_bone(oriented, rig, prefix, suffix, 'origin', search=True)
        added[name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
    target_eb = rig.data.edit_bones.get(prefices['forward'].affix + suffices['target'].affix)

    # pole bone parented to the targets forward bone, so it carries its full rotation including twist...
    axis, direction = get_twist_axis(target_eb, settings.axis)
    name = prefices['pole'].affix + suffices['target'].affix
    head, tail = target_eb.head + (direction * settings.offset), target_eb.head
    rolls, parent = [target_eb.z_axis], prefices['forward'].affix + suffices['target'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['limited', 'tertiary'], 'color' : 'pole', 'shape' : 'pole'}

    # vector bone parented to the origin, locked tracks the pole for its Y rotation...
    name = prefices['vector'].affix + suffices['target'].affix
    head, tail = target_eb.head, target_eb.head + (target_eb.y_axis * (target_eb.length * 1.0))
    rolls = [target_eb.z_axis, -target_eb.z_axis] if axis.endswith('X') else [target_eb.x_axis, -target_eb.x_axis]
    parent = parent_eb.name if parent_eb else origin_eb.name
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['limited', 'tertiary'], 'color' : 'pole', 'shape' : 'vector'}

    # return the bones we added with their groups, colors and shapes...
    rig.update_from_editmode()
    return added

def set_twist_bones(oriented, rig, settings):
    """set rigging constraints and drivers (edit mode, after updating new bones)..."""
    suffices, prefices = settings.suffices, settings.prefices
    origin_eb = rig.data.edit_bones[prefices['forward'].affix + suffices['origin'].affix]
    chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'target', 'root', 'pivot'}]
    heads = {s: oriented.data.edit_bones.get(suffices[s].affix).head for s in chain}
    chain.sort(key=lambda s: (heads[s] - origin_eb.head).length)

    # the chain is distributed along the origin to ending span...
    ending_eb = oriented.data.edit_bones.get(suffices['ending'].affix)
    distance, direction = utilities.functions.get_distance_direction(origin_eb.head, ending_eb.head)

    pole = prefices['pole'].affix + suffices['target'].affix
    vector = prefices['vector'].affix + suffices['target'].affix
    target = prefices['forward'].affix + suffices['target'].affix

    for name in chain:
        suffix = suffices[name].affix
        forward = prefices['forward'].affix + suffix
        # influence tapers along the chain, closer to the far end of the span gets more twist... (reversed if inverse)...
        _, _, along = utilities.functions.get_line_distance(heads[name], origin_eb.head, direction)
        influence = min(max(along / distance, 0.0), 1.0) if distance else 1.0
        influence = 1 - influence if settings.inverse else influence
        # the forward bones copy the vectors Y rotation only, inverted if the chain is set to inverse...
        constraint = {'subtarget' : vector, 'use' : [False, True, False], 'invert' : [False, settings.inverse, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'BEFORE', 'influence' : influence, 'name' : "Copy Vector Rotation"}
        _functions.add_rotation_constraints(rig, forward, constraint, {}, {})
        # the oriented bones inherit transforms from their forward rigging bone... (isolated to child of)...
        _functions.add_parent_constraints(oriented, rig, suffix, forward)

    # vector locked-tracks the pole target, locked to Y, so its own Y rotation is the targets twist...
    vector_eb, target_eb = rig.data.edit_bones[vector], rig.data.edit_bones[target]
    _, direction = get_twist_axis(target_eb, settings.axis)
    # find whichever of the vector bones own axes is closest to the pole, and map it to the track axis enum...
    axes = _functions.get_bone_axes(vector_eb, ['+X', '-X', '+Z', '-Z'])
    closest, _ = utilities.functions.get_closest_axis(direction, axes)
    tracks = {'+X' : 'TRACK_X', '-X' : 'TRACK_NEGATIVE_X', '+Z' : 'TRACK_Z', '-Z' : 'TRACK_NEGATIVE_Z'}
    vector_pb = rig.pose.bones.get(vector)
    # copy the targets own location first, so the track direction below is measured from the targets current position...
    copy_loc = vector_pb.constraints.new('COPY_LOCATION')
    copy_loc.name = "Copy Target Location"
    copy_loc.target, copy_loc.subtarget = rig, target
    copy_loc.target_space, copy_loc.owner_space = 'WORLD', 'WORLD'
    track = vector_pb.constraints.new('LOCKED_TRACK')
    track.name = "Locked Pole Track"
    track.target, track.subtarget = rig, pole
    track.track_axis, track.lock_axis = tracks[closest], 'LOCK_Y'

def add_twist_rigging(oriented, rig, settings):
    # define the unique rigging module identifier...
    module = "Twist (" + settings.suffices['origin'].affix + " - " + settings.suffices['ending'].affix + ")"
    # save our current mode... (if there is no contextual object then we must be in object mode)...
    last_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    selected = [o for o in bpy.context.selected_objects] if bpy.context.object else []
    # oriented/rig are commonly hidden while animating elsewhere, unhide them so they can be selected/entered...
    hidden = utilities.functions.get_hidden_objects({oriented, rig})
    utilities.functions.set_objects_unhidden(hidden)
    # ensure we have nothing else selected and take the armatures into edit mode...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    oriented.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    # add and get all the twist specific bones...
    added = add_twist_bones(oriented, rig, settings)
    rig.update_from_editmode()
    # get the chain normals from rigging bones while still in edit mode...
    origin_eb = rig.data.edit_bones[settings.prefices['forward'].affix + settings.suffices['origin'].affix]
    ending_eb = oriented.data.edit_bones[settings.suffices['ending'].affix]
    # for twist chains primary is simply the direction from origin to ending...
    _, primary = utilities.functions.get_distance_direction(origin_eb.head, ending_eb.head)
    # tertiary is resolved from the origin bones own axes... (AUTO detects it, otherwise the user has overridden it)...
    _, tertiary = get_twist_axis(origin_eb, settings.axis)
    # secondary completes the right handed set from tertiary and primary...
    secondary = tertiary.cross(primary)
    # update from edit mode so we can set things in pose mode...
    rig.update_from_editmode()
    # set all the constraints and drivers...
    set_twist_bones(oriented, rig, settings)
    # go back into object mode to reselect anything we deselected...
    bpy.ops.object.mode_set(mode='OBJECT')
    selected.append(rig)
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # set the bones groups, colors and shapes... (leaving edit mode required for setting color for some reason)...
    defaults = get_twist_defaults()
    for name, items in added.items():
        _functions.set_bone_groups(rig, name, items['groups'] if items else [], module)
        if items:
            _functions.set_bone_color(rig, name, settings.colors[items['color']])
            _functions.set_bone_shape(rig, name, settings.shapes[items['shape']], [tertiary, primary, secondary], 'TWIST', settings.offset, defaults['offset'])
    # then return our mode to whatever it was, and rehide anything that wasn't visible to begin with...
    bpy.ops.object.mode_set(mode=last_mode)
    for obj in hidden:
        obj.hide_set(True)
    return module, added

def invoke_twist_module(context, module):
    defaults = get_twist_defaults()
    _functions.set_default_settings(module.settings, defaults)
    # overlay whatever naming/colors/shapes were last used for this rigging type, if any...
    _functions.merge_saved_defaults(module.settings, _functions.get_saved_defaults(module.rigging))
    # try and get existing armatures...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
    oriented = oriented or original
    # selected pose bones seem to respect hierarchy... (isolate them to the oriented armature)...
    active = oriented.data.bones.active
    selection = [pb for pb in (context.selected_pose_bones or []) if pb.id_data == oriented and pb.bone != active]
    if len(selection) < 1:
        _functions.add_chain_names(module.settings, 1, ending=True)
        # twist needs at least one twist bone and an ending bone to form a chain...
        print("Select at least one twist bone and a target.")
        return True
    # add ordinal chain bones from all but the last selected bone...
    for index, bone in enumerate(selection):
        # so we can detect the bones used to add the rigging...
        suffix = module.settings.suffices.add()
        suffix.name = utilities.functions.get_ordinal_index(index + 1).lower()
        suffix.affix, suffix.unique, suffix.required = bone.name, True, True
    # target is always the active bone, not unique - the same bone can drive more than one twist chain...
    target = module.settings.suffices.add()
    target.name, target.affix, target.unique, target.required = 'target', active.name, False, True
    # closest chain bone to targets parent - if its actually nearer the target, the chain sits alongside it...
    parent = active.parent
    if parent:
        # prefer hierarchy for one twist bone... (distance can assign lowerarm twists to hands)...
        def is_under(bone, ancestor):
            while bone:
                if bone == ancestor:
                    return True
                bone = bone.parent
            return False

        in_active_chain = any(is_under(pb.bone, active) for pb in selection)
        in_parent_chain = any(is_under(pb.bone, parent) for pb in selection)
        if in_active_chain:
            # a twist below the target uses the target as origin... (preserves thigh inverse chains)...
            beside_target = True
        elif in_parent_chain:
            # sibling twists under the targets parent use the parent-to-target span... (distance can mislead)...
            beside_target = False
        else:
            closest = min(selection, key=lambda pb: (pb.head - parent.head_local).length)
            beside_target = (closest.head - parent.head_local).length >= (closest.head - active.head_local).length
    else:
        beside_target = True
    if beside_target:
        # the target is its own origin - auto detect the furthest immediate child as the ending instead...
        origin = active
        ending = max(active.children, key=lambda c: (c.head_local - active.head_local).length) if active.children else active
    else:
        origin, ending = parent, active
    module.settings.suffices['origin'].affix = origin.name if origin else ""
    # default to hands off if another modules bone collection already claims the origin...
    module.settings.shared = _functions.get_shared_default(rig, module.settings.prefices['forward'].affix + module.settings.suffices['origin'].affix)
    end = module.settings.suffices.add()
    end.name, end.affix, end.unique, end.required = 'ending', ending.name, False, False
    _functions.set_auto_mirror(module.settings, selection + [active, ending], origin)
    # initialize the offset using the scenes unit scale...
    module.settings.offset = module.settings.offset * utilities.functions.get_unit_scaling(context, inverse=True)
    module.settings.inverse = active == origin
    return True

def draw_twist_settings(layout, oriented, module):
    # define the twist only settings to show...
    settings = ['suffices', 'axis', 'offset', 'inverse', 'mirror', 'shared']
    # need to check suffices for validity...
    suffices = [b for b in module.settings.suffices]
    validity = _functions.get_naming_validity(suffices)
    _interface.show_operator_settings(layout, module, oriented, settings, validity)

def execute_twist_module(context, module):
    # if we can get both rig and oriented armatures...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
    oriented = oriented or original
    if not oriented:
        return None
    # if we do not have a rigging armature...
    if not rig:
        # add one that will serve as the new target...
        rig = _functions.add_rigging_armature(oriented)
    # get the prefices and suffices we want to use to construct the rigging...
    suffices = [b for b in module.settings.suffices]
    prefices = [n for n in module.settings.prefices]
    # twist chains are usually the last thing added so they shouldn't conflict with anything...
    conflicts = []
    validity = _functions.get_rigging_validity(oriented, rig, suffices, conflicts, module)
    if not all(validity.values()):
        # conflicting rigging already exists - cancel...
        print("rigging already exists for these bones...")
        return None
    # if all the bone name suffices are valid...
    validity = _functions.get_naming_validity(suffices)
    if not all(validity.values()):
        return None
    # and all the prefices are also valid...
    validity = _functions.get_naming_validity(prefices)
    if not all(validity.values()):
        return None
    # work out mirroring now, before module.module below reassigns the list entry these settings/mirrored live inside of...
    do_mirror = module.settings.mirror and not module.is_mirrored
    mirrored_suffices = None
    if do_mirror:
        # update the settings with the mirrored names... (validity check catch issues)...
        _functions.set_mirrored_settings(module.settings, module.mirrored)
        # get the mirrored suffices we want to use to construct the rigging...
        mirrored_suffices = [s for s in module.mirrored.suffices]
    # add the rigging module...
    name, added = add_twist_rigging(oriented, rig, module.settings)
    # tagging module with its own real identifier first keeps these settings anchored under it...
    module.module = name
    if do_mirror:
        # check the mirrored rigging for twist specific conflicts...
        validity = _functions.get_rigging_validity(oriented, rig, mirrored_suffices, conflicts, module.module)
        if not all(validity.values()):
            # conflicting rigging already exists - report only, mirrored failure isn't fatal...
            print("rigging already exists for mirrored bones...")
        else:
            # if all the mirrored bone name suffices are valid... (no need to check prefices)...
            validity = _functions.get_naming_validity(mirrored_suffices)
            if all(validity.values()):
                # add the mirrored rigging module, giving it its own list entry since it never goes through mmt.add...
                mirrored_name, mirrored_added = add_twist_rigging(oriented, rig, module.mirrored)
                _functions.add_mirrored_module(rig, module.rigging, mirrored_name, module.mirrored)
                _functions.link_mirrored_modules(rig, module, mirrored_name)
                added.update(mirrored_added)
    return added

def draw_twist_controls(layout, rig, module):
    # each chain bone gets its own dropdown, exposing how much twist reaches it...
    collection = rig.data.collections_all.get(module)
    if not collection:
        return
    index = 0
    for bone in collection.bones:
        pose_bone = rig.pose.bones.get(bone.name)
        constraint = pose_bone.constraints.get("Copy Vector Rotation") if pose_bone else None
        if not constraint or constraint.type != 'COPY_ROTATION':
            continue
        label = utilities.functions.get_ordinal_index(index + 1)
        header, panel = layout.panel("mmt_twist_" + bone.name, default_closed=True)
        header.label(text=label)
        if panel:
            panel.prop(constraint, "influence", text="Rotation Influence")
        index += 1


