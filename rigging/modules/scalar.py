import bpy

from mathutils import Vector, Quaternion, Matrix

from .. import _functions, _interface
from ... import utilities

def get_scalar_defaults():
    """get rigging defaults and choose which operator settings to show..."""
    defaults = {
        # default settings...
        'suffices' : [
            {'name' : "origin", 'affix' : "", 'unique' : True, 'required' : False},
            # rest of bones are added by selection...
            ],
        'offset' : 0.05, 'position' : 0.25, 'mirror' : False, 'floor' : False, 'axis' : 'AUTO',
        # default prefices...
        'prefices' : [
            {'name' : 'target', 'affix' : "ikt_", 'required' : True, 'unique' : True},
            {'name' : 'parent', 'affix' : "ikp_", 'required' : True, 'unique' : True},
            {'name' : 'pole', 'affix' : "pvt_", 'required' : True, 'unique' : True},
            {'name' : 'vector', 'affix' : "ikv_", 'required' : True, 'unique' : True},
            {'name' : 'forward', 'affix' : "", 'required' : False, 'unique' : True},
            {'name' : 'inverse', 'affix' : "ikc_", 'required' : True, 'unique' : True},
            {'name' : 'offset', 'affix' : "iko_", 'required' : True, 'unique' : True},
            {'name' : 'stretch', 'affix' : "skc_", 'required' : True, 'unique' : True},
            {'name' : 'floor', 'affix' : "fvt_", 'required' : True, 'unique' : True},
            ],
        # default color palettes...
        'colors' : [
            {'name' : 'origin', 'palette' : 'THEME13'},
            {'name' : 'target', 'palette' : 'THEME01'},
            {'name' : 'parent', 'palette' : 'THEME01'},
            {'name' : 'pole', 'palette' : 'THEME01'},
            {'name' : 'vector', 'palette' : 'THEME01'},
            {'name' : 'forward', 'palette' : 'THEME13'},
            {'name' : 'inverse', 'palette' : 'THEME10'},
            {'name' : 'offset', 'palette' : 'THEME10'},
            {'name' : 'stretch', 'palette' : 'THEME10'},
            {'name' : 'floor', 'palette' : 'THEME01'},
            ],
        # and default custom shapes...
        'shapes' : [
            {'name' : 'origin', 'mesh' : 'RING_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'target', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'parent', 'mesh' : 'RING_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.5, 1.5, 1.5), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'pole', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'vector', 'mesh' : 'ARROW_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'forward', 'mesh' : 'RING_HALF', 'translation' : (0.0, 0.5, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'inverse', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.5, 0.5, 0.5), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'offset', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.3, 0.3, 0.3), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'stretch', 'mesh' : 'DASH_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'floor', 'mesh' : 'CIRCLE_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '-Y', 'upward' : '+Z'},
            ]
        }
    return defaults

def add_scalar_bones(oriented, rig, settings):
    """add scalar rigging bones (including the ik target parent)..."""
    # get the settings needed...
    suffices, prefices = settings.suffices, settings.prefices
    offset, position, added = settings.offset, settings.position, {}

    # add the origin bone if the settings have one and it doesn't already exist on the rigging armature...
    added[prefices['forward'].affix + suffices['origin'].affix] = {}
    existing = rig.data.edit_bones.get(prefices['forward'].affix + suffices['origin'].affix)
    if suffices['origin'].affix and not existing:
        prefix, suffix = prefices["forward"].affix, suffices['origin'].affix
        origin_eb, first_eb = oriented.data.edit_bones.get(suffix), oriented.data.edit_bones.get(suffices['first'].affix)
        length, _ = utilities.functions.get_distance_direction(origin_eb.head, first_eb.head)
        name = _functions.add_shared_bone(oriented, rig, prefix, suffix, 'origin', search=True, length=length)
        added[name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
    elif suffices['origin'].affix and existing and settings.shared and not _functions.get_is_root(rig, existing.name):
        added[existing.name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
    
    # for each bone in the chain... (skip non-chain bones)...
    chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'root', 'pivot'}]
    # scalar has no distinct ending bone, the last ordinal chain bone is the ending...
    ending = utilities.functions.get_ordinal_index(len(suffices) - 1).lower()
    tails, parents = [n for n in chain[1:]], [suffices['origin'].name] + [n for n in chain[:-1]]
    layers = ['forward', 'inverse', 'offset', 'stretch']
    for index, suffix in enumerate(chain):
        # get the oriented and tail edit bones...
        oriented_eb = oriented.data.edit_bones.get(suffices[suffix].affix)
        tail_eb = None
        if index < len(tails):
            tail_eb = oriented.data.edit_bones.get(suffices[tails[index]].affix)
        head, tail = oriented_eb.head, _functions.get_bone_tail(oriented_eb, tail_eb, length=oriented_eb.length if index == len(chain) - 1 else 0.0)
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
            _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
            # the last forward bone doubles as the ending, adopt anything already rigged off it elsewhere...
            if layer == 'forward' and index == len(chain) - 1:
                _functions.set_bone_hierarchy(oriented, rig, suffices[suffix].affix, name)
            # copy chain bones have limited rigging conflicts... (twist bones can use them)...
            groups = ['limited', 'secondary'] if layer == 'forward' else ['tertiary']
            # the ending forward bone needs to have things connected to it though...
            if layer == 'forward' and index == len(chain) - 1:
                groups = ['general', 'secondary']
            added[name] = {'groups' : groups, 'color' : layer, 'shape' : layer}
    
    # get the first and ending bones in the chain... (from the rigging armature)...
    first_eb = rig.data.edit_bones[prefices['forward'].affix + suffices['first'].affix]
    ending_eb = rig.data.edit_bones[prefices['forward'].affix + suffices[ending].affix]

    # get the primary, secondary directions, length and center of the chain...
    points = [rig.data.edit_bones[suffices[n].affix].head for n in chain] + [ending_eb.tail]
    primary, secondary, tertiary, length = _functions.get_chain_normals(points, fallback=_functions.get_axis_fallback(points, first_eb, settings.axis), override=_functions.get_axis_override(first_eb, settings.axis))
    center = first_eb.head + (primary * (length * position))

    # add the ik parent bone as a duplicate of the first chain bone...
    name = prefices['parent'].affix + suffices['first'].affix
    head, tail = first_eb.head, first_eb.tail
    rolls, parent = [first_eb.z_axis], prefices['forward'].affix + suffices['origin'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'parent'}

    # add the ik target bone at the tail of the ending bone... (oriented to end bone)...
    name = prefices['target'].affix + suffices[ending].affix
    head, tail = ending_eb.tail, ending_eb.tail + (ending_eb.y_axis * (ending_eb.length * 0.5))
    rolls, parent = [secondary, -secondary], prefices['parent'].affix + suffices['first'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'target'}

    # create the vector bone oriented along the chains direction and rolled towards secondary direction...
    name = prefices['vector'].affix + suffices['first'].affix
    head, tail = first_eb.head, center
    rolls, parent = [secondary, -secondary], prefices['parent'].affix + suffices['first'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'vector'}

    # add the pole target at the position point offset along the secondary axis...
    name = prefices['pole'].affix + suffices['first'].affix
    head, tail = center + (secondary * offset), center
    rolls, parent = [primary * -1], prefices['vector'].affix + suffices['first'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'pole'}

    # create the floor bone at the IK target's XY position at floor level...
    if settings.floor:
        name = prefices['floor'].affix + suffices[ending].affix
        target_eb = rig.data.edit_bones[prefices['target'].affix + suffices[ending].affix]
        target_axes = [target_eb.x_axis, target_eb.x_axis * -1, target_eb.y_axis, target_eb.y_axis * -1, target_eb.z_axis, target_eb.z_axis * -1]
        floor_direction = utilities.functions.get_closest_vector(Vector((0.0, -1.0, 0.0)), target_axes)
        floor_head = Vector((ending_eb.tail.x, ending_eb.tail.y, 0.0))
        floor_tail = floor_head + (floor_direction * ending_eb.length)
        rolls, parent = [Vector((0.0, 0.0, 1.0))], ""
        _functions.add_rigging_bone(rig, name, parent, floor_head, floor_tail, rolls)
        added[name] = {'groups' : ['primary'], 'color' : 'floor', 'shape' : 'floor'}

    # return the bones we added with their groups, colors and shapes...
    rig.update_from_editmode()
    return added

def set_scalar_bones(oriented, rig, settings):
    """set rigging constraints and drivers (edit mode, after updating new bones)..."""
    suffices, prefices = settings.suffices, settings.prefices
    ending = utilities.functions.get_ordinal_index(len(suffices) - 1).lower()
    target = prefices['target'].affix + suffices[ending].affix
    pole = prefices['pole'].affix + suffices['first'].affix
    # for the bones in the chain...
    chain = [s.affix for s in suffices[1:]]
    for index, suffix in enumerate(chain):
        # get the names of the bones in the chains we created...
        forward = prefices['forward'].affix + suffix
        inverse = prefices['inverse'].affix + suffix
        offset = prefices['offset'].affix + suffix
        stretch = prefices['stretch'].affix + suffix

        # copy each inverse bones world location to its offset (including the last)...
        copy = {'subtarget' : inverse, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['WORLD', 'WORLD'], 'offset' : False, 'name' : "Copy Inverse Location"}
        _functions.add_location_constraints(rig, offset, copy, {})
        # then limit their distance to their own inverse bones tail on top...
        limit_dist = rig.pose.bones.get(offset).constraints.new('LIMIT_DISTANCE')
        limit_dist.name, limit_dist.target, limit_dist.subtarget = "Limit Offset Distance", rig, inverse
        limit_dist.head_tail, limit_dist.distance = 1.0, rig.data.bones[inverse].length
        limit_dist.target_space, limit_dist.owner_space = 'WORLD', 'WORLD'
        # and always copy the rotation of their own inverse bones in world space...
        copy = {'subtarget' : inverse, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['WORLD', 'WORLD'], 'mode' : 'REPLACE', 'name' : "Copy Inverse Rotation"}
        _functions.add_rotation_constraints(rig, offset, copy, {}, {})

        # the forward bones copy the rotation of the offset bones... (before original in parent or local space)...
        copy = {'subtarget' : offset, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'BEFORE', 'name' : "Copy Offset Rotation"}
        _functions.add_rotation_constraints(rig, forward, copy, {}, {}, drive=True)
        # and the forward bones copy the offset bones location too... (off by default, local to local space)...
        copy = {'subtarget' : offset, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'offset' : True, 'influence' : 0.0, 'name' : "Copy Offset Location"}
        _functions.add_location_constraints(rig, forward, copy, {})
        # the oriented bones inherit transforms from their rigging bone... (isolated to child of)...
        _functions.add_parent_constraints(oriented, rig, suffix, forward)

        # set stretching influence... (spread gently through the chain from zero)...
        rig.pose.bones[forward].ik_stretch = (0.25 / len(chain)) * (index + 1)
        # both the stretch and inverse bones copy the kinematic settings of the forward bone...
        _functions.add_kinematic_drivers(rig, inverse, forward)
        # this is to keep keys off mechanical bones and ensure they stay the same between the chains...
        _functions.add_kinematic_drivers(rig, stretch, forward)

        # the inverse bone copies the Y scale of the stretch bone... (limited to 1.0 to stop drifting)...
        copy = {'subtarget' : stretch, 'use' : [False, True, False], 'power' : 1.0, 'uniform' : False, 'offset' : False, 'additive' : False, 'space' : ['LOCAL', 'LOCAL'], 'name' : "Copy Stretch Scale"}
        limit = {'use' : [False, True, False], 'min' : [1.0, 1.0, 1.0], 'max' : [1.5, 1.5, 1.5], 'space' : 'LOCAL', 'name' : "Limit Inverse Scale"}
        _functions.add_scale_constraints(rig, inverse, copy, limit)
        # and copies the scale of the pole target... (for tweaking chain tension)...
        copy = {'subtarget' : pole, 'use' : [True, True, True], 'power' : 1 / len(chain), 'uniform' : False, 'offset' : True, 'additive' : False, 'space' : ['LOCAL_OWNER_ORIENT', 'LOCAL'], 'name' : "Copy Pole Scale"}
        _functions.add_scale_constraints(rig, inverse, copy, {})

        # if this is the first chain bone...
        if index == 0:
            # the inverse bone has a copy rotation to the stretch bone... (to mimic the pole oriented stretch bone)...
            copy = {'subtarget' : stretch, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'REPLACE', 'influence' : 1.0, 'name' : "Copy Stretch Rotation"}
            _functions.add_rotation_constraints(rig, inverse, copy, {}, {})
        # if it is not...
        else:
            # inverse and stretch bones have a copy rotation to the pole target... (for tweaking chain rotation)...
            copy = {'subtarget' : pole, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'BEFORE', 'influence' : (0.5 / (len(chain) - 1)) * index, 'name' : "Copy Pole Rotation"}
            _functions.add_rotation_constraints(rig, inverse, copy, {}, {})
            _functions.add_rotation_constraints(rig, stretch, copy, {}, {})
            # and if these are the last bones in the chain...
            if index == len(chain) - 1:
                # the stretch bone has an IK constraint... (with stretching)...
                ik = {'target' : target, 'pole' : pole, 'length' : len(chain), 'stretch' : True, 'name' : "Stretch IK"}
                _functions.add_kinematic_constraints(rig, stretch, ik)
                # the inverse bone has an IK constraint... (no pole, so its own ik limits govern the bend instead)...
                ik = {'target' : target, 'pole' : "", 'length' : len(chain), 'stretch' : False, 'name' : "Inverse IK"}
                _functions.add_kinematic_constraints(rig, inverse, ik)

    # the vector bone has a damped track to the target...
    vector = prefices['vector'].affix + suffices['first'].affix
    vector_pb = rig.pose.bones.get(vector)
    damp_track = vector_pb.constraints.new('DAMPED_TRACK')
    damp_track.name = "Damped Target Track"
    damp_track.target, damp_track.subtarget = rig, prefices['target'].affix + suffices[ending].affix
    # and copies inverse universal scale of its ik parent...
    parent = prefices['parent'].affix + suffices['first'].affix
    copy = {'subtarget' : parent, 'use' : [True, True, True], 'power' : -1.0, 'uniform' : True, 'offset' : True, 'additive' : False, 'space' : ['LOCAL_OWNER_ORIENT', 'LOCAL'], 'name' : "Copy Parent Scale"}
    _functions.add_scale_constraints(rig, vector, copy, {})

    # the target bone has a floor constraint...
    if settings.floor:
        target_pb = rig.pose.bones.get(target)
        floor_con = target_pb.constraints.new('FLOOR')
        floor_con.target, floor_con.subtarget = rig, prefices['floor'].affix + suffices[ending].affix
        floor_con.floor_location, floor_con.use_rotation, floor_con.name = 'FLOOR_Z', True, "Target Floor"

def add_scalar_rigging(oriented, rig, settings):
    # define the unique rigging module identifier...
    ending = utilities.functions.get_ordinal_index(len(settings.suffices) - 1).lower()
    module = "Scalar (" + settings.suffices['first'].affix + " - " + settings.suffices[ending].affix + ")"
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
    # add and get all the scalar specific bones...
    added = add_scalar_bones(oriented, rig, settings)
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
    set_scalar_bones(oriented, rig, settings)
    # go back into object mode to reselect anything we deselected...
    bpy.ops.object.mode_set(mode='OBJECT')
    selected.append(rig)
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # set the bones groups, colors and shapes... (leaving edit mode required for setting color for some reason)...
    defaults = get_scalar_defaults()
    first = settings.prefices['forward'].affix + settings.suffices['first'].affix
    for name, items in added.items():
        _functions.set_bone_groups(rig, name, items['groups'] if items else [], module)
        if items:
            _functions.set_bone_color(rig, name, settings.colors[items['color']])
            # the origins own roll isn't chain aware, so let the first chain bone decide which of its own axes to use...
            reference = first if items['shape'] == 'origin' else None
            _functions.set_bone_shape(rig, name, settings.shapes[items['shape']], [tertiary, primary, secondary], 'SCALAR', settings.offset, defaults['offset'], reference)
    # then return our mode to whatever it was, and rehide anything that wasn't visible to begin with...
    bpy.ops.object.mode_set(mode=last_mode)
    for obj in hidden:
        obj.hide_set(True)
    return module, added

def invoke_scalar_module(context, module):
    defaults = get_scalar_defaults()
    _functions.set_default_settings(module.settings, defaults)
    # overlay whatever naming/colors/shapes were last used for this rigging type, if any...
    _functions.merge_saved_defaults(module.settings, _functions.get_saved_defaults(module.rigging))
    # try and get existing armatures...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
    oriented = oriented or original
    # selected pose bones seem to respect hierarchy... (isolate them to the oriented armature)...
    selection = [pb for pb in (context.selected_pose_bones or []) if pb.id_data == oriented]
    if len(selection) < 2:
        _functions.add_chain_names(module.settings, 2)
        # scalar needs at least two chain bones...
        print("Select at least two chain bones.")
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
    _functions.set_auto_mirror(module.settings, selection, origin)
    # auto detect a sensible fallback axis from the first chain bones own axes...
    points = [pb.head for pb in selection]
    axis = _functions.get_chain_axis(points, selection[0].bone)
    module.settings.axis = axis
    # initialize the offset using the scenes unit scale...
    heads = [b.head for b in selection[1:-1]]
    # scalar has no distinct ending bone, so the chain actually runs to the last bones tail...
    module.settings.position = _functions.get_central_position(selection[0].head, selection[-1].tail, heads)
    module.settings.offset = module.settings.offset * utilities.functions.get_unit_scaling(context, inverse=True)
    return True

def draw_scalar_settings(layout, oriented, module):
    # define the scalar only settings to show...
    settings = ['suffices', 'axis', 'offset', 'position', 'floor', 'mirror', 'shared']
    # need to check suffices for validity...
    suffices = [b for b in module.settings.suffices]
    validity = _functions.get_naming_validity(suffices)
    _interface.show_operator_settings(layout, module, oriented, settings, validity)

def execute_scalar_module(context, module):
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
    name, added = add_scalar_rigging(oriented, rig, module.settings)
    # tagging module with its own real identifier first keeps these settings anchored under it...
    module.module = name
    if do_mirror:
        # check the mirrored rigging for scalar specific conflicts...
        validity = _functions.get_rigging_validity(oriented, rig, mirrored_suffices, conflicts, module.module)
        if not all(validity.values()):
            # conflicting rigging already exists - report only, mirrored failure isn't fatal...
            print("rigging already exists for mirrored bones...")
        else:
            # if all the mirrored bone name suffices are valid... (no need to check prefices)...
            validity = _functions.get_naming_validity(mirrored_suffices)
            if all(validity.values()):
                # add the mirrored rigging module, giving it its own list entry since it never goes through mmt.add...
                mirrored_name, mirrored_added = add_scalar_rigging(oriented, rig, module.mirrored)
                _functions.add_mirrored_module(rig, module.rigging, mirrored_name, module.mirrored)
                _functions.link_mirrored_modules(rig, module, mirrored_name)
                added.update(mirrored_added)
    return added

def draw_scalar_controls(layout, rig, module):
    # forward bones drive their inverse/stretch counterparts via drivers, so editing them is enough...
    collection = rig.data.collections_all.get(module)
    if not collection:
        return
    forward = _functions.get_bone_collection(rig, "Secondary")
    limited = _functions.get_bone_collection(rig, "Limited")
    general = _functions.get_bone_collection(rig, "General")
    forward_names = {b.name for b in forward.bones} if forward else set()
    limited_names = {b.name for b in limited.bones} if limited else set()
    general_names = {b.name for b in general.bones} if general else set()
    module_names = {b.name for b in collection.bones}

    # walk the chain in parent to child order, purely structurally, so we can label them ordinally...
    chain_names = module_names & limited_names & forward_names
    ordered = []
    current = next((n for n in chain_names if not (rig.data.bones[n].parent and rig.data.bones[n].parent.name in chain_names)), None)
    while current:
        ordered.append(current)
        current = next((n for n in chain_names if rig.data.bones[n].parent and rig.data.bones[n].parent.name == current), None)
    if not ordered:
        return

    # scalar has no distinct ending bone, the last ordinal chain bone is general, not limited, instead...
    ending_name = next((n for n in module_names & general_names & forward_names
        if rig.data.bones[n].parent and rig.data.bones[n].parent.name == ordered[-1]), None)
    if ending_name:
        ordered.append(ending_name)

    # target bone name is built from the modules own fixed default affixes...
    defaults = get_scalar_defaults()
    affixes = {p['name'] : p['affix'] for p in defaults['prefices']}
    target_pb = rig.pose.bones.get(affixes['target'] + ending_name) if ending_name else None

    # the targets own variables sit at the top, always visible...
    if target_pb:
        col = layout.column(align=True)
        floor_con = target_pb.constraints.get("Target Floor")
        if floor_con:
            col.prop(floor_con, "influence", text="Floor Influence")

    for index, name in enumerate(ordered):
        pose_bone = rig.pose.bones.get(name)
        if not pose_bone:
            continue
        label = utilities.functions.get_ordinal_index(index + 1)
        header, panel = layout.panel("mmt_ik_settings_" + name, default_closed=True)
        header.label(text=label + " Bone")
        if panel:
            col = panel.column(align=True)
            copy_rot = pose_bone.constraints.get("Copy Offset Rotation")
            if copy_rot:
                col.prop(copy_rot, "influence", text="Rotation Influence")
            copy_loc = pose_bone.constraints.get("Copy Offset Location")
            if copy_loc:
                col.prop(copy_loc, "influence", text="Location Influence")
            col.prop(pose_bone, "ik_stretch", text="IK Stretch")
            for axis in "xyz":
                axis_row = col.row(align=True)
                axis_row.prop(pose_bone, "lock_ik_" + axis, text="")
                axis_row.prop(pose_bone, "ik_stiffness_" + axis, text=axis.upper())
                axis_row.prop(pose_bone, "use_ik_limit_" + axis, text="", icon='CON_ROTLIMIT', toggle=True)
                axis_row.prop(pose_bone, "ik_min_" + axis, text="")
                axis_row.prop(pose_bone, "ik_max_" + axis, text="")

    # snapping needs the forward chain to already be posed in fk, which only makes sense once the module is built...
    layout.separator()
    layout.operator("mmt.snap", text="Snap IK to FK", icon='CON_KINEMATIC')

def set_snapped_direct(context, module):
    # solve the standard parent and target (leave constrained setups to the evaluated snap)...
    rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
    if not rig or module.settings.floor:
        return False
    suffices, prefices = module.settings.suffices, module.settings.prefices
    chain = [s.name for s in suffices if s.name != 'origin']
    if not chain:
        return False
    forwards = [rig.pose.bones.get(prefices['forward'].affix + suffices[n].affix) for n in chain]
    parent = rig.pose.bones.get(prefices['parent'].affix + suffices['first'].affix)
    ending = utilities.functions.get_ordinal_index(len(suffices) - 1).lower()
    target = rig.pose.bones.get(prefices['target'].affix + suffices[ending].affix)
    if any(pb is None for pb in forwards + [parent, target]):
        return False
    if parent.constraints or target.constraints or target.parent != parent:
        return False
    if any(not pb.bone.use_local_location or pb.bone.inherit_scale != 'FULL' for pb in (parent, target)):
        return False
    paths = tuple(pb.path_from_id() + '.' for pb in (parent, target))
    if rig.animation_data and any(fc.data_path.startswith(paths) for fc in rig.animation_data.drivers):
        return False
    ancestor = parent.parent
    args = {'parent_matrix': ancestor.matrix, 'parent_matrix_local': ancestor.bone.matrix_local} if ancestor else {}
    rest = parent.bone.convert_local_to_pose(Matrix.Identity(4), parent.bone.matrix_local, **args)
    if any(abs(v - 1.0) > 1e-6 for v in rest.to_scale()) or abs(rest.to_3x3().determinant() - 1.0) > 1e-6:
        return False
    offset = parent.bone.matrix_local.inverted() @ target.bone.matrix_local
    tail = forwards[-1].tail.copy()
    desired = Matrix.Translation(tail) @ forwards[-1].matrix.to_3x3().to_4x4()
    current = (rest @ offset).translation - rest.translation
    direction = tail - rest.translation
    if current.length < 1e-6 or direction.length < 1e-6:
        return False
    alignment = current.normalized().rotation_difference(direction.normalized())
    rotation = rest.to_quaternion()
    basis_rotation = rotation.inverted() @ (alignment @ rotation)
    scale = direction.length / current.length
    parent_basis = Matrix.LocRotScale(Vector(), basis_rotation, Vector((scale, scale, scale)))
    parent_matrix = rest @ parent_basis
    target_rest = parent_matrix @ offset
    target_rotation = target_rest.to_quaternion().inverted() @ desired.to_quaternion()
    seeded = []
    for name, forward in zip(chain, forwards):
        for prefix in ('inverse', 'stretch'):
            bone = rig.pose.bones.get(prefices[prefix].affix + suffices[name].affix)
            if bone is None:
                return False
            seeded.append((bone, forward.matrix_basis.to_quaternion()))
    parent.rotation_mode = target.rotation_mode = 'QUATERNION'
    parent.matrix_basis = parent_basis
    parent.rotation_quaternion = basis_rotation
    target.matrix_basis = Matrix.Identity(4)
    target.location = target_rest.inverted() @ tail
    target.rotation_quaternion = target_rotation
    for bone, rotation in seeded:
        bone.rotation_mode = 'QUATERNION'
        bone.rotation_quaternion = rotation
    return True

def set_snapped_kinematics(context, module, clear=True):
    # snap the ik target and pole onto the forward chains current fk pose so switching to ik doesn't pop - unlike opposable/plantigrade, scalar has no distinct ending bone or "Root/Vector Transform" child ofs, just parent (a duplicate of the first chain bone) rotating and scaling to aim+stretch target/pole/vector toward the reach point...
    rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
    if not rig:
        return False
    context.view_layer.update()
    settings = module.settings
    suffices, prefices = settings.suffices, settings.prefices
    ending = utilities.functions.get_ordinal_index(len(suffices) - 1).lower()
    chain = [s.name for s in suffices if s.name != 'origin']
    forwards = [rig.pose.bones.get(prefices['forward'].affix + suffices[n].affix) for n in chain]
    if any(pb is None for pb in forwards):
        return False
    parent_pb = rig.pose.bones.get(prefices['parent'].affix + suffices['first'].affix)
    target_pb = rig.pose.bones.get(prefices['target'].affix + suffices[ending].affix)
    vector_pb = rig.pose.bones.get(prefices['vector'].affix + suffices['first'].affix)
    pole_pb = rig.pose.bones.get(prefices['pole'].affix + suffices['first'].affix)

    # capture the forward chains current pose before touching anything...
    original_rotations = [pb.matrix_basis.to_quaternion() for pb in forwards]
    original_locations = [pb.location.copy() for pb in forwards]

    matrices = [pb.matrix.copy() for pb in forwards]
    # scalar has no distinct ending bone - the last chain bones own tail is the actual reach point...
    ending_matrix = Matrix.Translation(forwards[-1].tail.copy()) @ matrices[-1].to_3x3().to_4x4()
    points = [m.translation for m in matrices] + [ending_matrix.translation]
    # resolved once from rest data - the chains natural bend direction and forwards[0]s rest rotation, needed below to track which side it should bend toward independent of live geometry...
    rest_points = [pb.bone.matrix_local.translation for pb in forwards] + [forwards[-1].bone.tail_local]
    _, rest_secondary, _, _ = _functions.get_chain_normals(rest_points)
    rest_rotation_0 = forwards[0].bone.matrix_local.to_quaternion()
    # a chain thats genuinely straight has no real bend signal, so override secondary with rest_secondary rotated by however far forwards[0] has turned since rest...
    override = _functions.get_axis_override(forwards[0], settings.axis)
    if override is None:
        chain_length, chain_direction = utilities.functions.get_distance_direction(points[0], points[-1])
        dominant = Vector((0.0, 0.0, 0.0))
        for point in points[1:-1]:
            projection = (point - points[0]).dot(chain_direction)
            perpendicular = point - (points[0] + (chain_direction * projection))
            if perpendicular.length > dominant.length:
                dominant = perpendicular
        delta = forwards[0].matrix.to_quaternion() @ rest_rotation_0.inverted()
        tracked_secondary = delta @ rest_secondary
        if dominant.length <= (chain_length * 0.01):
            override = tracked_secondary
        # a genuine hyperextension flips secondary correctly, but the pole should hold its side regardless, so negate back onto the tracked side when they disagree...
        elif dominant.dot(tracked_secondary) < 0.0:
            override = -dominant
    primary, secondary, _, length = _functions.get_chain_normals(points, override=override)
    center = points[0] + (primary * (length * settings.position))

    # rotate then scale parent so the vector/target/pole assembly at its fixed rest offset reaches the tail - a rotation cant change that offset distance, so both solve in one shot with no re-measuring...
    parent_rest_offset = parent_pb.bone.matrix_local.inverted() @ target_pb.bone.matrix_local
    current_estimate = (parent_pb.matrix @ parent_rest_offset).translation
    current_direction = current_estimate - parent_pb.head
    desired_direction = ending_matrix.translation - parent_pb.head
    parent_pb.rotation_mode = 'QUATERNION'
    if current_direction.length > 1e-6 and desired_direction.length > 1e-6:
        alignment = current_direction.normalized().rotation_difference(desired_direction.normalized())
        world_rotation = parent_pb.matrix.to_quaternion()
        parent_pb.rotation_quaternion = parent_pb.rotation_quaternion @ world_rotation.inverted() @ (alignment @ world_rotation)
        parent_pb.scale = parent_pb.scale * (desired_direction.length / current_direction.length)

    # resolve once from rest data which of vectors own axes points toward the pole, apply that fixed sign to secondary, then read the same axis back off vectors own live just-solved matrix for poles position...
    rest_pole_axes = _functions.get_bone_axes(vector_pb.bone, ['+X', '-X', '+Z', '-Z'])
    pole_axis_name, _ = utilities.functions.get_closest_axis(rest_secondary, rest_pole_axes)
    vector_z_sign = 1.0 if pole_axis_name == '+Z' else -1.0
    vector_matrix = _functions.set_snapped_vector(vector_pb, lambda pb: pb.matrix.copy(), ending_matrix, primary, secondary * vector_z_sign, vector_pb.parent)
    posed_axes = {'+X': vector_matrix.to_3x3().col[0], '-X': -vector_matrix.to_3x3().col[0],
        '+Z': vector_matrix.to_3x3().col[2], '-Z': -vector_matrix.to_3x3().col[2]}
    position = center + (posed_axes[pole_axis_name].normalized() * settings.offset)
    _functions.set_snapped_pole(pole_pb, position, vector_matrix, lambda pb: pb.matrix.copy())

    # snap target directly too, correcting the small residual left after parents own rotate+scale, by solving its local transform from its now-posed parent the same way set_snapped_vector does...
    target_base = parent_pb.matrix @ parent_rest_offset
    target_local = target_base.inverted() @ ending_matrix
    target_pb.rotation_mode = 'QUATERNION'
    target_pb.location = target_local.translation
    target_pb.rotation_quaternion = target_local.to_quaternion()

    # clear forward transforms only as far as constraints take over (keep the remaining pose)...
    if clear:
        for pb, original_rotation, original_location in zip(forwards, original_rotations, original_locations):
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
    return True


