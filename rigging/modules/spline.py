import bpy

from mathutils import Vector, Matrix, Quaternion

from .. import _functions, _interface
from ... import utilities

def get_spline_defaults():
    """get rigging defaults and choose which operator settings to show..."""
    defaults = {
        # default settings...
        'suffices' : [
            {'name' : "origin", 'affix' : "", 'unique' : True, 'required' : False},
            # no default chain when the length is variable...
            ],
        'offset' : -0.3, 'count' : 3, 'mirror' : False, 'axis' : 'AUTO',
        # default prefices...
        'prefices' : [
            {'name' : 'target', 'affix' : "ikt_", 'required' : True, 'unique' : True},
            {'name' : 'parent', 'affix' : "ikp_", 'required' : True, 'unique' : True},
            {'name' : 'vector', 'affix' : "ikv_", 'required' : True, 'unique' : True},
            {'name' : 'forward', 'affix' : "", 'required' : False, 'unique' : True},
            {'name' : 'stretch', 'affix' : "skc_", 'required' : True, 'unique' : True},
            {'name' : 'offset', 'affix' : "iko_", 'required' : True, 'unique' : True},
            ],
        # default color palettes...
        'colors' : [
            {'name' : 'origin', 'palette' : 'THEME13'},
            {'name' : 'target', 'palette' : 'THEME01'},
            {'name' : 'parent', 'palette' : 'THEME01'},
            {'name' : 'forward', 'palette' : 'THEME13'},
            {'name' : 'stretch', 'palette' : 'THEME10'},
            {'name' : 'offset', 'palette' : 'THEME10'},
            ],
        # and default custom shapes...
        'shapes' : [
            {'name' : 'origin', 'mesh' : 'RING_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'target', 'mesh' : 'STRIPS_SINGLE', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (2.0, 2.0, 2.5), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'parent', 'mesh' : 'RING_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (3.0, 3.0, 3.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'forward', 'mesh' : 'STRIPS_SINGLE', 'translation' : (0.0, 0.5, -1.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (4.0, 3.0, 2.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'stretch', 'mesh' : 'DASH_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'offset', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.5, 0.5, 0.5), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            ]
        }
    return defaults

def add_spline_bones(oriented, rig, settings):
    """add spline rigging bones (including the ik targets)..."""
    # get the settings needed...
    suffices, prefices = settings.suffices, settings.prefices
    offset, count, added = settings.offset, settings.count, {}

    # add the origin bone if the settings have one and it doesn't already exist on the rigging armature...
    added[prefices['forward'].affix + suffices['origin'].affix] = {}
    existing = rig.data.edit_bones.get(prefices['forward'].affix + suffices['origin'].affix)
    if suffices['origin'].affix and not existing:
        prefix, suffix = prefices["forward"].affix, suffices['origin'].affix
        name = _functions.add_shared_bone(oriented, rig, prefix, suffix, 'origin', search=True)
        added[name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
    elif suffices['origin'].affix and existing and settings.shared and not _functions.get_is_root(rig, existing.name):
        added[existing.name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
    
    # for each bone in the chain... (skip non-chain bones)...
    chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'root', 'pivot'}]
    tails, parents = [n for n in chain[1:]], [suffices['origin'].name] + [n for n in chain[:-1]]
    layers = ['forward', 'stretch', 'offset']
    for index, suffix in enumerate(chain):
        # get the oriented and tail edit bones...
        oriented_eb = oriented.data.edit_bones.get(suffices[suffix].affix)
        tail_eb = None
        if index < len(tails):
            tail_eb = oriented.data.edit_bones.get(suffices[tails[index]].affix)
        head, tail = oriented_eb.head, _functions.get_bone_tail(oriented_eb, tail_eb)
        # get the axes of the bone that are not closest to the tail direction...
        axes = _functions.get_roll_axes(oriented_eb, head, tail)
        # add a bone for each prefix...
        for layer in layers:
            # first bones share the first parent... (later layers chain to their own kind)...
            name = prefices[layer].affix + suffices[suffix].affix
            rolls, parent = axes.values(), prefices['forward' if index == 0 else layer].affix + suffices[parents[index]].affix
            # if this is not the first bone...
            if index > 0:
                # calulate roll closest to parents z axis...
                parent_eb = rig.data.edit_bones[parent]
                rolls = [utilities.functions.get_closest_vector(parent_eb.z_axis, axes.values())]
            rig_eb = _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
            # the last forward bone doubles as the ending, adopt anything already rigged off it elsewhere...
            if layer == 'forward' and index == len(chain) - 1:
                _functions.set_bone_hierarchy(oriented, rig, suffices[suffix].affix, name)
            # only the stretch bones need uninherited rotation, forward and offset stay normal so fk cascades...
            rig_eb.use_inherit_rotation = layer != 'stretch'
            # spline chain bones have limited rigging conflicts... (twist bones can use them)...
            groups = ['limited', 'secondary'] if layer == 'forward' else ['tertiary']
            # expose the start and end forward bones for connections (keep stretch and offset hidden)...
            if layer == 'forward' and (index == 0 or index == len(chain) - 1):
                groups = ['general', 'secondary']
            added[name] = {'groups' : groups, 'color' : layer, 'shape' : layer}

    # add the target parent bone as a copy of the first chain bone... (but using the offset length)...
    rig_eb = rig.data.edit_bones.get(prefices['forward'].affix + suffices['first'].affix)
    name = prefices['parent'].affix + suffices['first'].affix
    # point the parent control toward the chain end... (offset sign never reverses its axis)...
    head, tail = rig_eb.head, rig_eb.head + (rig_eb.y_axis * abs(offset))
    # left unparented, it picks up the origin through a child of instead, so root motion isn't fought over by two hierarchies...
    rolls, parent = [rig_eb.z_axis], ""
    # it should use the target group and colors but it's own shape...
    parent_eb =_functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'parent'}
    # get the the total length of the chain bones...
    forwards = [prefices["forward"].affix + suffices[c].affix for c in chain]
    total = sum([rig.data.edit_bones.get(n).length for n in forwards[:-1]])
    # iterate through the chain bones...
    distance, spread, targets = 0.0, total / (count - 1), []
    for index, suffix in enumerate(chain[:-1]):
        # get the bone segment...
        name = prefices['forward'].affix + suffices[suffix].affix
        forward_eb = rig.data.edit_bones.get(name)
        segment = [distance, distance + forward_eb.length]
        # iterate through the target sections...
        for section in range(0, count):
            # if the target position is within the bone range...
            position = spread * section
            if position >= segment[0] and position <= segment[1]:
                # the name may need to have a number definition...
                name = prefices['target'].affix + suffices[suffix].affix
                if name in rig.data.edit_bones:
                    affix = str(index) if index >= 10 else ("0" + str(index))
                    name = prefices['target'].affix + affix + "_" + suffices[suffix].affix
                # caclulate the head from the difference between position and current... (on bone direction)...
                head = forward_eb.head + (forward_eb.y_axis * (position - segment[0]))
                # and the tail from the desired X or Z axis offset...
                tail = head + (forward_eb.z_axis * offset)
                # align roll to the chain bones Y axis and parent to the target parent...
                rolls, parent = [forward_eb.y_axis], parent_eb.name
                # add the bone and assign it to use target groups, color and shape...
                _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
                added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'target'}
                # and append the targets name...
                targets.append(name)
        # increment the bone distance travelled...
        distance += forward_eb.length

    # give each forward bone an even share of the total start to end distance, not its own natural length...
    first_eb, last_eb = oriented.data.edit_bones.get(suffices[chain[0]].affix), oriented.data.edit_bones.get(suffices[chain[-1]].affix)
    span, _ = utilities.functions.get_distance_direction(first_eb.head, _functions.get_bone_tail(last_eb, None))
    for index, suffix in enumerate(chain):
        rig_eb = rig.data.edit_bones.get(prefices['forward'].affix + suffices[suffix].affix)
        rig_eb.length = span / len(chain)
    # return the bones we added with their groups, colors and shapes...
    rig.update_from_editmode()
    return added, targets

def set_spline_bones(oriented, rig, settings, targets):
    """set rigging constraints and drivers (edit mode, after updating new bones)..."""
    # get the settings, names and variables needed...
    suffices, prefices = settings.suffices, settings.prefices
    count = settings.count
    chain = [s.name for s in suffices[1:]]
    stretches = [prefices["stretch"].affix + suffices[c].affix for c in chain]
    offsets = [prefices["offset"].affix + suffices[c].affix for c in chain]
    forwards = [prefices["forward"].affix + suffices[c].affix for c in chain]
    parent = prefices['parent'].affix + suffices['first'].affix
    parent_eb = rig.data.edit_bones.get(parent)
    head = parent_eb.head.copy()
    # get the point locations of all the bones in the chain... (including tail of the last bone)...
    points = [rig.data.edit_bones.get(n).head.copy() - head for n in stretches]
    points.append(rig.data.edit_bones.get(stretches[len(stretches) - 1]).tail.copy() - head)
    # get the lengths and total length of the chain bones... (all the way to the last bones tail, not it's head)...
    lengths = [rig.data.edit_bones.get(n).length for n in stretches]
    total = sum(lengths)

    # go into object mode and deselect everything...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    # create a new curve with some basic display settings...
    name = oriented.name + " (" + suffices[chain[0]].affix + " - " + suffices[chain[-1]].affix + ")"
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions, data.bevel_depth = '3D', 0.0
    # assign to an object and parent to the armature and link to collections...
    curve = bpy.data.objects.new(name, data)
    for collection in rig.users_collection:
        collection.objects.link(curve)
    # set the curves location before parenting, while its world and local space still match...
    curve.matrix_world.translation = head
    # parented directly, not via parent_set(keep_transform=True) - that reads active bone context unreliable here...
    parent_pb = rig.pose.bones.get(parent)
    parent_bone = rig.data.bones.get(parent)
    curve.parent, curve.parent_type, curve.parent_bone = rig, 'BONE', parent
    parent_matrix = rig.matrix_world @ parent_pb.matrix @ Matrix.Translation((0.0, parent_bone.length, 0.0))
    curve.matrix_parent_inverse = parent_matrix.inverted()
    bpy.ops.object.select_all(action='DESELECT')
    curve.select_set(True)
    bpy.context.view_layer.objects.active = curve
    # add all the points for the chain and take the curve into edit mode...
    spline = curve.data.splines.new(type='NURBS')
    spline.points.add(len(points) - 1)
    spline.use_endpoint_u, spline.use_endpoint_v = True, True
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.curve.select_all(action='DESELECT')

    # iterate through the points... (count can never be greater than the bone count or less than start/end)...
    position, spread = 0.0, total / (count - 1)
    for index, co in enumerate(points):
        # get the spline point and set its position...
        point = curve.data.splines[0].points[index]
        point.co = Vector((co.x, co.y, co.z, 1.0))
        # iterate through the target sections...
        for section in range(0, count - 1):
            # if the point position is within the target section...
            segment = [spread * section, spread * (section + 1)]
            if position >= segment[0] and position <= segment[1]:
                # get the strength of the position within the segment...
                strength = utilities.functions.get_mapped_range(position, segment[0], segment[1], 0.0, 1.0)
                prior, post = targets[section], targets[section + 1]
                # hook the curve points between the targets... (one minused to ease off prior)...
                _functions.add_hook_modifiers(rig, curve, index, prior, post, strength)
                # if this is not the last point...
                if index < len(points) - 1:
                    # increment the position to the next point distance... (clamped to total)...
                    position = max(0.0, min(position + lengths[index], total))
                    # add twist drivers to stretchy spline bones using each targets closest axis...
                    dest_bb = rig.data.bones.get(stretches[index])
                    mappings = []
                    for target in targets:
                        source_axes = _functions.get_bone_axes(rig.data.bones.get(target), ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
                        mapping = {}
                        for axis_index, label in enumerate(['+X', '+Y', '+Z']):
                            direction = _functions.get_bone_axes(dest_bb, [label])[label]
                            closest, _ = utilities.functions.get_closest_axis(direction, source_axes)
                            mapping[axis_index] = (closest[1], 1 if closest[0] == '+' else -1)
                        mappings.append(mapping)
                    # taper linearly past half the influence width... (width one matches the old fixed taper)...
                    position_fraction, half_width = section + strength, settings.influences / 2.0
                    weights = [round(max(0.0, 1.0 - abs(position_fraction - t) / half_width), 3) for t in range(len(targets))]
                    # keep only the strongest influences... (guards against near-zero float drift)...
                    kept = set(sorted(range(len(weights)), key=lambda t: weights[t], reverse=True)[:settings.influences])
                    # keep endpoint targets addressable beyond the positive falloff range...
                    weights = [max(w, 0.001) if t in kept else 0.0 for t, w in enumerate(weights)]
                    _functions.add_spline_drivers(rig, stretches[index], forwards[index], targets, mappings, weights)
                # and break section iteration...
                break

    # follow the optional origin through a child of constraint...
    origin = prefices['forward'].affix + suffices['origin'].affix
    origin_bb = rig.data.bones.get(origin)
    if origin_bb:
        parent_pb = rig.pose.bones.get(parent)
        child_of = parent_pb.constraints.new('CHILD_OF')
        child_of.name, child_of.show_expanded = "Parent Transform", False
        child_of.target, child_of.subtarget = rig, origin
        child_of.inverse_matrix = origin_bb.matrix_local.inverted()

    # for the bones in the chain...
    for index, suffix in enumerate(chain):
        # get the names of the bones in the chains we created...
        forward = prefices['forward'].affix + suffices[suffix].affix
        stretch = prefices['stretch'].affix + suffices[suffix].affix
        offset = prefices['offset'].affix + suffices[suffix].affix

        # copy stretch rotation to offset in world space (use a distinct constraint name)...
        offset_pb = rig.pose.bones.get(offset)
        copy_rot = offset_pb.constraints.new('COPY_ROTATION')
        copy_rot.name = "Copy Stretch Rotation"
        copy_rot.target, copy_rot.subtarget = rig, stretch
        copy_rot.target_space, copy_rot.owner_space, copy_rot.mix_mode = 'WORLD', 'WORLD', 'REPLACE'
        # the last offset bone copies the location of it's stretch bone in world space instead, for now...
        if index == len(chain) - 1:
            copy_loc = offset_pb.constraints.new('COPY_LOCATION')
            copy_loc.name = "Copy Stretch Location"
            copy_loc.target, copy_loc.subtarget = rig, stretch
            copy_loc.target_space, copy_loc.owner_space = 'WORLD', 'WORLD'
        else:
            # the other offset bones copy the location of their own stretch bones in world space...
            copy_loc = offset_pb.constraints.new('COPY_LOCATION')
            copy_loc.name = "Copy Stretch Location"
            copy_loc.target, copy_loc.subtarget = rig, stretch
            copy_loc.target_space, copy_loc.owner_space = 'WORLD', 'WORLD'
            # then limit their distance to their own stretch bones tail on top...
            limit_dist = offset_pb.constraints.new('LIMIT_DISTANCE')
            limit_dist.name, limit_dist.target, limit_dist.subtarget = "Limit Offset Distance", rig, stretch
            limit_dist.head_tail, limit_dist.distance = 1.0, rig.data.bones[stretch].length
            limit_dist.target_space, limit_dist.owner_space = 'WORLD', 'WORLD'
            # the first one doubles as the first bones own location influence, off by default...
            if index == 0:
                limit_dist.influence = 0.0

        # every stretch bone also picks up the target parents own rotation, so the whole spline twists with it...
        copy = {'subtarget' : parent, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL_OWNER_ORIENT', 'LOCAL'], 'mode' : 'BEFORE', 'name' : "Copy Parent Rotation"}
        _functions.add_rotation_constraints(rig, stretch, copy, {}, {})

        # the forward bones copy the rotation of the offset bones... (before original in parent or local space)...
        copy = {'subtarget' : offset, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'BEFORE', 'name' : "Copy Offset Rotation"}
        _functions.add_rotation_constraints(rig, forward, copy, {}, {}, drive=True)
        # copy offset location to forward in local space (off by default, hidden for the first bone)...
        copy = {'subtarget' : offset, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'offset' : True, 'influence' : 1.0 if index == 0 else 0.0, 'name' : "Copy Offset Location"}
        _functions.add_location_constraints(rig, forward, copy, {})
        # the oriented bones inherit transforms from their rigging bone... (isolated to child of)...
        _functions.add_parent_constraints(oriented, rig, suffices[suffix].affix, forward)
        # set stretching influence... (spread gently through the chain from zero)...
        rig.pose.bones[forward].ik_stretch = (0.25 / len(chain)) * (index + 1)
        # this is to keep keys off mechanical bones and ensure they stay the same between the chains...
        _functions.add_kinematic_drivers(rig, stretch, forward)
        # if these are the last bones in the chain...
        if index == len(chain) - 1:
            # the stretch bone needs a spline IK constraint to the curve...
            stretch_pb = rig.pose.bones.get(stretch)
            sk = stretch_pb.constraints.new('SPLINE_IK')
            sk.target, sk.chain_count = curve, len(chain)
    
    # then apply the stretch, offset and forward chains position to rest pose... (so nothing moves from rest)...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # other rigging can have been parented onto our bones since (eg. an origin adopted via set_bone_hierarchy)...
    applied = set(stretches + offsets + forwards)
    detached = [(b.name, b.parent.name) for b in rig.data.bones if b.parent and b.parent.name in applied and b.name not in applied]
    if detached:
        # detach it first, so applying our own rest never bakes a compensating pose into bones that aren't ours...
        bpy.ops.object.mode_set(mode='EDIT')
        for name, _ in detached:
            rig.data.edit_bones[name].parent = None
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='DESELECT')
    for name in stretches + offsets + forwards:
        pose_bone = rig.pose.bones.get(name)
        pose_bone.select = True
    bpy.ops.pose.armature_apply(selected=True)
    bpy.ops.pose.select_all(action='DESELECT')
    # the forwards rest just moved, so the oriented bones child of constraints need their inverse matrix refreshed...
    _functions.set_parent_constraints(oriented, rig)
    if detached:
        # then reattach whatever we detached, now the rest change cant leak a pose into it anymore...
        bpy.ops.object.mode_set(mode='EDIT')
        for name, parent in detached:
            rig.data.edit_bones[name].parent = rig.data.edit_bones[parent]
        bpy.ops.object.mode_set(mode='OBJECT')

def add_spline_rigging(oriented, rig, settings):
    # define the unique rigging module identifier...
    ending = utilities.functions.get_ordinal_index(len(settings.suffices) - 1).lower()
    module = "Spline (" + settings.suffices['first'].affix + " - " + settings.suffices[ending].affix + ")"
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
    # add and get all the spline specific bones... (and the names of the targets)...
    added, targets = add_spline_bones(oriented, rig, settings)
    rig.update_from_editmode()
    # get the chain normals from rigging bones while still in edit mode... (no ending bone, last bones tail is)...
    chain = [s.name for s in settings.suffices if s.name != 'origin']
    first_eb = rig.data.edit_bones[settings.prefices['forward'].affix + settings.suffices['first'].affix]
    ending_eb = rig.data.edit_bones[settings.prefices['forward'].affix + settings.suffices[ending].affix]
    points = [rig.data.edit_bones[settings.suffices[n].affix].head for n in chain] + [ending_eb.tail]
    primary, secondary, tertiary, _ = _functions.get_chain_normals(points, fallback=_functions.get_axis_fallback(points, first_eb, settings.axis), override=_functions.get_axis_override(first_eb, settings.axis))
    # update from edit mode so we can set things in pose mode...
    rig.update_from_editmode()
    # set all the constraints and drivers...
    set_spline_bones(oriented, rig, settings, targets)
    # go back into object mode to reselect anything we deselected...
    bpy.ops.object.mode_set(mode='OBJECT')
    selected.append(rig)
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # set the bones groups, colors and shapes... (leaving edit mode required for setting color for some reason)...
    defaults = get_spline_defaults()
    first = settings.prefices['forward'].affix + settings.suffices['first'].affix
    for name, items in added.items():
        _functions.set_bone_groups(rig, name, items['groups'] if items else [], module)
        if items:
            _functions.set_bone_color(rig, name, settings.colors[items['color']])
            # the origins own roll isn't chain aware, so let the first chain bone decide which of its own axes to use...
            reference = first if items['shape'] == 'origin' else None
            _functions.set_bone_shape(rig, name, settings.shapes[items['shape']], [tertiary, primary, secondary], 'SPLINE', settings.offset, defaults['offset'], reference)
    # then return our mode to whatever it was, and rehide anything that wasn't visible to begin with...
    bpy.ops.object.mode_set(mode=last_mode)
    for obj in hidden:
        obj.hide_set(True)
    return module, added

def invoke_spline_module(context, module):
    defaults = get_spline_defaults()
    _functions.set_default_settings(module.settings, defaults)
    # overlay whatever naming/colors/shapes were last used for this rigging type, if any...
    _functions.merge_saved_defaults(module.settings, _functions.get_saved_defaults(module.rigging))
    # try and get existing armatures...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
    oriented = oriented or original
    # selected pose bones seem to respect hierarchy... (isolate them to the oriented armature)...
    selection = [pb for pb in (context.selected_pose_bones or []) if pb.id_data == oriented]
    if len(selection) < 3:
        _functions.add_chain_names(module.settings, 2)
        # spline needs at least two chain bones to form a curve...
        print("Select at least three chain bones.")
        return True
    for index, bone in enumerate(selection):
        # so we can detect the bones used to add the rigging...
        suffix = module.settings.suffices.add()
        suffix.name = utilities.functions.get_ordinal_index(index + 1).lower()
        suffix.affix, suffix.unique, suffix.required = bone.name, True, True
    # set the origin if we find one...
    origin = selection[0].parent
    module.settings.suffices['origin'].affix = origin.name if origin else ""
    # default to hands off if another modules bone collection already claims the origin...
    module.settings.shared = _functions.get_shared_default(rig, module.settings.prefices['forward'].affix + module.settings.suffices['origin'].affix)
    # offer mirroring only when the complete flipped chain exists... (including its origin)...
    _functions.set_auto_mirror(module.settings, selection, origin)
    # auto detect a sensible fallback axis from the first chain bones own axes...
    points = [pb.head for pb in selection]
    axis = _functions.get_chain_axis(points, selection[0].bone)
    module.settings.axis = axis
    # initialize the offset using the scenes unit scale...
    module.settings.offset = module.settings.offset * utilities.functions.get_unit_scaling(context, inverse=True)
    return True

def draw_spline_settings(layout, oriented, module):
    # define the spline only settings to show...
    settings = ['suffices', 'axis', 'offset', 'count', 'influences', 'mirror', 'shared']
    # need to check suffices for validity...
    suffices = [b for b in module.settings.suffices]
    validity = _functions.get_naming_validity(suffices)
    _interface.show_operator_settings(layout, module, oriented, settings, validity)

def execute_spline_module(context, module):
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
    # check the rigging for plantigrade specific conflicts... (checks constraints and collections)...
    conflicts = ["Opposable", "Plantigrade", "Digitigrade", "Spline", "Scalar", "Curl", "Custom", "Twist"]
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
    name, added = add_spline_rigging(oriented, rig, module.settings)
    # tagging module with its own real identifier first keeps these settings anchored under it...
    module.module = name
    if do_mirror:
        # check the mirrored rigging for spline specific conflicts...
        validity = _functions.get_rigging_validity(oriented, rig, mirrored_suffices, conflicts, module.module)
        if not all(validity.values()):
            # conflicting rigging already exists - report only, mirrored failure isn't fatal...
            print("rigging already exists for mirrored bones...")
        else:
            # if all the mirrored bone name suffices are valid... (no need to check prefices)...
            validity = _functions.get_naming_validity(mirrored_suffices)
            if all(validity.values()):
                # add the mirrored rigging module, giving it its own list entry since it never goes through mmt.add...
                mirrored_name, mirrored_added = add_spline_rigging(oriented, rig, module.mirrored)
                _functions.add_mirrored_module(rig, module.rigging, mirrored_name, module.mirrored)
                _functions.link_mirrored_modules(rig, module, mirrored_name)
                added.update(mirrored_added)
    return added

def draw_spline_controls(layout, rig, module):
    # show each forward bones copy rotation influence, everything else is controlled by bones and drivers...
    collection = rig.data.collections_all.get(module)
    if not collection:
        return
    chain_names = set()
    for bone in collection.bones:
        pose_bone = rig.pose.bones.get(bone.name)
        constraint = pose_bone.constraints.get("Copy Offset Rotation") if pose_bone else None
        if constraint and constraint.type == 'COPY_ROTATION':
            chain_names.add(bone.name)

    # walk the chain in parent to child order, purely structurally, so we can label them ordinally...
    ordered = []
    current = next((n for n in chain_names if not (rig.data.bones[n].parent and rig.data.bones[n].parent.name in chain_names)), None)
    while current:
        ordered.append(current)
        current = next((n for n in chain_names if rig.data.bones[n].parent and rig.data.bones[n].parent.name == current), None)

    # the first bones offset bone name is built from the modules own fixed default affixes...
    defaults = get_spline_defaults()
    affixes = {p['name'] : p['affix'] for p in defaults['prefices']}

    for index, name in enumerate(ordered):
        pose_bone = rig.pose.bones.get(name)
        label = utilities.functions.get_ordinal_index(index + 1)
        header, panel = layout.panel("mmt_ik_settings_" + name, default_closed=True)
        header.label(text=label + " Bone")
        if panel:
            col = panel.column(align=True)
            copy_rot = pose_bone.constraints.get("Copy Offset Rotation")
            col.prop(copy_rot, "influence", text="Rotation Influence")
            # expose the first bones offset distance limit instead of its Copy Offset Location...
            if index == 0:
                offset_pb = rig.pose.bones.get(affixes['offset'] + name)
                limit_dist = offset_pb.constraints.get("Limit Offset Distance") if offset_pb else None
                if limit_dist:
                    col.prop(limit_dist, "influence", text="Location Influence")
            else:
                copy_loc = pose_bone.constraints.get("Copy Offset Location")
                if copy_loc:
                    col.prop(copy_loc, "influence", text="Location Influence")
            # every target has it's own twist influence on this bone, so any bone can be pulled toward any target...
            for prop_name in pose_bone.keys():
                if prop_name.endswith(" Influence"):
                    col.prop(pose_bone, '["' + prop_name + '"]', text=prop_name)

    # snapping needs the forward chain to already be posed in fk, which only makes sense once the module is built...
    layout.separator()
    layout.operator("mmt.snap", text="Snap IK to FK", icon='CON_KINEMATIC')

def get_target_names(rig, module, prefices, first_name, last_name):
    # find targets by collection and rest order (original bone lengths changed during build)...
    collection = rig.data.collections_all.get(module)
    if not collection:
        return []
    prefix = prefices['target'].affix
    target_bones = [b for b in collection.bones if b.name.startswith(prefix)]
    # bone.head/.tail are parent relative, need the _local variants for armature space rest positions...
    first_head, last_tail = rig.data.bones[first_name].head_local, rig.data.bones[last_name].tail_local
    primary = (last_tail - first_head)
    if primary.length > 1e-6:
        primary.normalize()
        target_bones.sort(key=lambda b: (b.head_local - first_head).dot(primary))
    return [b.name for b in target_bones]

def get_resampled_points(points, count):
    # sample evenly along the path (return segment indices for tangents too)...
    segment_lengths = [(points[i + 1] - points[i]).length for i in range(len(points) - 1)]
    total = sum(segment_lengths)
    spread = total / (count - 1) if count > 1 else 0.0
    points_out, segments_out, segment_index, segment_start = [], [], 0, 0.0
    for section in range(count):
        target_distance = spread * section
        while segment_index < len(segment_lengths) - 1 and segment_start + segment_lengths[segment_index] < target_distance:
            segment_start += segment_lengths[segment_index]
            segment_index += 1
        segment_length = segment_lengths[segment_index] if segment_lengths[segment_index] > 1e-9 else 1e-9
        fraction = min(max((target_distance - segment_start) / segment_length, 0.0), 1.0)
        points_out.append(points[segment_index] + (points[segment_index + 1] - points[segment_index]) * fraction)
        segments_out.append(segment_index)
    return points_out, segments_out

def set_snapped_kinematics(context, module, clear=True):
    # snap the ik targets onto the forward chains current fk pose, so switching to ik doesn't pop...
    rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
    if not rig:
        return False
    settings = module.settings
    suffices, prefices = settings.suffices, settings.prefices
    chain = [s.name for s in suffices[1:]]
    forward_pbs = [rig.pose.bones.get(prefices['forward'].affix + suffices[n].affix) for n in chain]
    if any(pb is None for pb in forward_pbs):
        return False
    # capture the forward chains current pose before touching anything...
    original_rotations = [pb.matrix_basis.to_quaternion() for pb in forward_pbs]
    original_locations = [pb.location.copy() for pb in forward_pbs]
    points = [pb.head.copy() for pb in forward_pbs] + [forward_pbs[-1].tail.copy()]
    # warn rather than fail - too few targets for this poses curvature is a Count setting fix, not something to solve here...
    suggested_count = _functions.get_suggested_count(points)
    if suggested_count > settings.count:
        print("Spline snap: this pose has more curvature than %d target(s) can accurately represent - consider raising Count to %d or more." % (settings.count, suggested_count))
    # resample the fk chain by arc length at the same fractions add_spline_bones originally placed targets at...
    resampled, segments = get_resampled_points(points, settings.count)
    first_name, last_name = prefices['forward'].affix + suffices[chain[0]].affix, prefices['forward'].affix + suffices[chain[-1]].affix
    target_names = get_target_names(rig, module.module, prefices, first_name, last_name)
    target_pbs = [rig.pose.bones.get(name) for name in target_names]
    if len(target_pbs) != settings.count or any(pb is None for pb in target_pbs):
        return False
    _functions.set_bones_reset(*target_pbs)
    # align z to the tangent and y outwards (negate for the roll flip baked into forward rest)...
    desired_tangents, desired_rotations = [], []
    for point, segment_index in zip(resampled, segments):
        tangent = points[segment_index + 1] - points[segment_index]
        if tangent.length < 1e-6:
            tangent = forward_pbs[segment_index].y_axis.copy()
        tangent.normalize()
        out = -forward_pbs[segment_index].z_axis
        y_axis = out - (out.dot(tangent) * tangent)
        if y_axis.length < 1e-6:
            y_axis = Vector((0.0, 1.0, 0.0)) - (Vector((0.0, 1.0, 0.0)).dot(tangent) * tangent)
        y_axis.normalize()
        x_axis = y_axis.cross(tangent)
        desired_tangents.append(tangent)
        desired_rotations.append(Matrix((x_axis, y_axis, tangent)).transposed())
    # snap the target parent onto the first forward bone directly, so the whole chain doesn't inherit a stale parent offset...
    parent_pb = rig.pose.bones.get(prefices['parent'].affix + suffices['first'].affix)
    if parent_pb:
        # the parent shares the forward chains own rest convention, so match its rotation the same way the initial retarget converts world to local...
        parent_pb.rotation_mode = 'QUATERNION'
        rest_relative = parent_pb.bone.matrix_local.to_quaternion()
        parent_pb.rotation_quaternion = rest_relative.inverted() @ forward_pbs[0].matrix.to_quaternion()
        _functions.set_settled_position(parent_pb, points[0])
    for target_pb, point, desired_rotation in zip(target_pbs, resampled, desired_rotations):
        if target_pb:
            desired = Matrix.Translation(point) @ desired_rotation.to_4x4()
            # convert unconstrained spline targets directly from armature to basis space...
            if not target_pb.constraints:
                parent = target_pb.parent
                parent_args = ({'parent_matrix': parent.matrix,
                    'parent_matrix_local': parent.bone.matrix_local} if parent else {})
                target_pb.matrix_basis = target_pb.bone.convert_local_to_pose(
                    desired, target_pb.bone.matrix_local, invert=True, **parent_args)
            else:
                _functions.set_settled_matrix(target_pb, desired)
    bpy.context.view_layer.update()
    # nudge targets one at a time with fresh state (keep rotations fixed to avoid divergence)...
    stretch_pbs = [rig.pose.bones.get(prefices['stretch'].affix + suffices[n].affix) for n in chain]
    for outer in range(12):
        converged = True
        for i, target_pb in enumerate(target_pbs):
            if not target_pb:
                continue
            current_points = [pb.head.copy() for pb in stretch_pbs] + [stretch_pbs[-1].tail.copy()]
            current_resampled, _ = get_resampled_points(current_points, settings.count)
            error = resampled[i] - current_resampled[i]
            if error.length > 1e-3:
                target_pb.location += target_pb.matrix_basis.to_3x3() @ target_pb.matrix.to_3x3().inverted() @ error
                bpy.context.view_layer.update()
                converged = False
        if converged:
            break
    # only clear as much of the forward chains own rotation and location as their constraints are actually taking over...
    if clear:
        for pb, original_rotation, original_location in zip(forward_pbs, original_rotations, original_locations):
            copy_rotation = pb.constraints.get("Copy Offset Rotation")
            rotation_influence = copy_rotation.influence if copy_rotation else 1.0
            cleared = original_rotation.slerp(Quaternion(), rotation_influence)
            pb.rotation_quaternion = cleared
            pb.rotation_euler = cleared.to_euler(pb.rotation_mode if pb.rotation_mode in {'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'} else 'XYZ')
            angle, axis = cleared.angle, cleared.axis
            pb.rotation_axis_angle = [angle, axis.x, axis.y, axis.z] if angle else [0.0, 0.0, 1.0, 0.0]
            copy_location = pb.constraints.get("Copy Offset Location")
            location_influence = copy_location.influence if copy_location else 1.0
            pb.location = original_location.lerp(Vector(), location_influence)
        bpy.context.view_layer.update()
    return True


