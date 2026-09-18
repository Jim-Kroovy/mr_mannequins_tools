import bpy

from .. import _functions, _interface
from ... import utilities

def get_curl_defaults():
    """get rigging defaults and choose which operator settings to show..."""
    defaults = {
        # default settings...
        'suffices' : [
            {'name' : "origin", 'affix' : "", 'unique' : True, 'required' : False},
            # chain bones are added by selection...
            ],
        'offset' : 0.0, 'mirror' : False, 'axis' : 'AUTO',
        # default prefices...
        'prefices' : [
            {'name' : 'target', 'affix' : "ckt_", 'required' : True, 'unique' : True},
            {'name' : 'forward', 'affix' : "", 'required' : False, 'unique' : True},
            {'name' : 'stretch', 'affix' : "skc_", 'required' : True, 'unique' : True},
            {'name' : 'offset', 'affix' : "cko_", 'required' : True, 'unique' : True},
            ],
        # default color palettes...
        'colors' : [
            {'name' : 'origin', 'palette' : 'THEME13'},
            {'name' : 'target', 'palette' : 'THEME01'},
            {'name' : 'forward', 'palette' : 'THEME13'},
            {'name' : 'stretch', 'palette' : 'THEME10'},
            {'name' : 'offset', 'palette' : 'THEME10'},
            ],
        # and default custom shapes...
        'shapes' : [
            {'name' : 'origin', 'mesh' : 'STRIPS_SINGLE', 'translation' : (0.0, 0.5, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'target', 'mesh' : 'STRIPS_SINGLE', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.5, 1.5, 1.5), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'forward', 'mesh' : 'STRIPS_SINGLE', 'translation' : (0.0, 0.5, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'stretch', 'mesh' : 'DASH_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            {'name' : 'offset', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.5, 0.5, 0.5), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+Z'},
            ]
        }
    return defaults

def add_curl_bones(oriented, rig, settings):
    """add curl rigging bones (one target drives the offset chain)..."""
    # get the settings needed...
    suffices, prefices = settings.suffices, settings.prefices
    added = {}

    # add the origin bone if the settings have one and it doesn't already exist on the rigging armature...
    added[prefices['forward'].affix + suffices['origin'].affix] = {}
    existing = rig.data.edit_bones.get(prefices['forward'].affix + suffices['origin'].affix)
    if suffices['origin'].affix and not existing:
        prefix, suffix = prefices['forward'].affix, suffices['origin'].affix
        origin_eb, first_eb = oriented.data.edit_bones.get(suffix), oriented.data.edit_bones.get(suffices['first'].affix)
        length, _ = utilities.functions.get_distance_direction(origin_eb.head, first_eb.head)
        name = _functions.add_shared_bone(oriented, rig, prefix, suffix, 'origin', search=True, length=length)
        added[name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}
    elif suffices['origin'].affix and existing and settings.shared and not _functions.get_is_root(rig, existing.name):
        added[existing.name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'origin'}

    # for each bone in the chain... (skip non-chain bones)...
    chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'root', 'pivot'}]
    tails, parents = [n for n in chain[1:]], [suffices['origin'].name] + [n for n in chain[:-1]]
    layers = ['forward', 'stretch', 'offset']
    # each forward bone gets an even share of the total start to end distance, not its own native length...
    first_eb, last_eb = oriented.data.edit_bones.get(suffices[chain[0]].affix), oriented.data.edit_bones.get(suffices[chain[-1]].affix)
    end = _functions.get_bone_tail(last_eb, None)
    total, _ = utilities.functions.get_distance_direction(first_eb.head, end)
    length = total / len(chain)
    for index, suffix in enumerate(chain):
        # get the oriented and tail edit bones...
        oriented_eb = oriented.data.edit_bones.get(suffices[suffix].affix)
        tail_eb = None
        if index < len(tails):
            tail_eb = oriented.data.edit_bones.get(suffices[tails[index]].affix)
        # set head to oriented bone head and tail along the closest axis to the next bone, at the even length...
        natural_tail = _functions.get_bone_tail(oriented_eb, tail_eb)
        _, direction = utilities.functions.get_distance_direction(oriented_eb.head, natural_tail)
        axes = _functions.get_bone_axes(oriented_eb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
        _, axis = utilities.functions.get_closest_axis(direction, axes)
        head, tail = oriented_eb.head, oriented_eb.head + (axis * length)
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
            # curl chain bones have limited rigging conflicts... (twist bones can use them)...
            groups = ['limited', 'secondary'] if layer == 'forward' else ['tertiary']
            # the ending forward bone needs to have things connected to it though...
            if layer == 'forward' and index == len(chain) - 1:
                groups = ['general', 'secondary']
                # and adopt anything already rigged off it elsewhere, so add order never breaks the hierarchy...
                _functions.set_bone_hierarchy(oriented, rig, suffices[suffix].affix, name)
            added[name] = {'groups' : groups, 'color' : layer, 'shape' : layer}

    # get the first chain bone to position the target bone...
    first_eb = rig.data.edit_bones[prefices['forward'].affix + suffices['first'].affix]
    # add the target bone as a duplicate of the first chain bone... (drives transforms for all chain bones)...
    name = prefices['target'].affix + suffices['first'].affix
    head, tail = first_eb.head, first_eb.tail
    rolls, parent = [first_eb.z_axis], prefices['forward'].affix + suffices['origin'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'target'}

    # return the bones we added with their groups, colors and shapes...
    rig.update_from_editmode()
    return added

def set_curl_bones(oriented, rig, settings):
    """set cascading curl and offset distance constraints (edit mode, after updating new bones)..."""
    suffices, prefices = settings.suffices, settings.prefices
    target = prefices['target'].affix + suffices['first'].affix
    # for the bones in the chain...
    ordinals = [s.name for s in suffices[1:]]
    chain = [s.affix for s in suffices[1:]]
    for index, suffix in enumerate(chain):
        forward = prefices['forward'].affix + suffix
        stretch = prefices['stretch'].affix + suffix
        offset = prefices['offset'].affix + suffix
        axes = settings.axes.get(ordinals[index])
        use = [axes.x, axes.y, axes.z] if axes else [True, True, True]

        # the forward bones copy rotation with rotation inheritance drivers...
        constraint = {'subtarget' : offset, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'BEFORE', 'name' : "Copy Offset Rotation"}
        _functions.add_rotation_constraints(rig, forward, constraint, {}, {}, drive=True)
        # and the forward bones copy the offset bones location too... (off by default, local to local space)...
        constraint = {'subtarget' : offset, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'offset' : True, 'influence' : 0.0, 'name' : "Copy Offset Location"}
        _functions.add_location_constraints(rig, forward, constraint, {})
        # the oriented bones inherit transforms from their forward rigging bone... (isolated to child of)...
        _functions.add_parent_constraints(oriented, rig, suffix, forward)

        # the stretch bones copy rotation from the target in local space, on whichever axes are set...
        constraint = {'subtarget' : target, 'use' : use, 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'BEFORE', 'name' : "Copy Target Rotation"}
        _functions.add_rotation_constraints(rig, stretch, constraint, {}, {})
        # and copy scale from the target in local space...
        constraint = {'subtarget' : target, 'use' : [True, True, True], 'power' : 1.0, 'uniform' : False, 'offset' : False, 'additive' : False, 'space' : ['LOCAL', 'LOCAL'], 'name' : "Copy Target Scale"}
        _functions.add_scale_constraints(rig, stretch, constraint, {})
        # the first stretch bone also copies the targets own location, so moving the target can reposition the whole chain...
        if index == 0:
            constraint = {'subtarget' : target, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'offset' : False, 'name' : "Copy Target Location"}
            _functions.add_location_constraints(rig, stretch, constraint, {})

        # the offset bones copy the stretch bones rotation and location in world space...
        offset_pb = rig.pose.bones.get(offset)
        copy_rot = offset_pb.constraints.new('COPY_ROTATION')
        copy_rot.name = "Copy Stretch Rotation"
        copy_rot.target, copy_rot.subtarget = rig, stretch
        copy_rot.target_space, copy_rot.owner_space, copy_rot.mix_mode = 'WORLD', 'WORLD', 'REPLACE'
        copy_loc = offset_pb.constraints.new('COPY_LOCATION')
        copy_loc.name = "Copy Stretch Location"
        copy_loc.target, copy_loc.subtarget = rig, stretch
        copy_loc.target_space, copy_loc.owner_space = 'WORLD', 'WORLD'
        # then limit their distance to their own stretch bones tail on top...
        limit_dist = offset_pb.constraints.new('LIMIT_DISTANCE')
        limit_dist.name, limit_dist.target, limit_dist.subtarget = "Limit Offset Distance", rig, stretch
        limit_dist.head_tail, limit_dist.distance = 1.0, rig.data.bones[stretch].length
        limit_dist.target_space, limit_dist.owner_space = 'WORLD', 'WORLD'

def add_curl_rigging(oriented, rig, settings):
    # define the unique rigging module identifier...
    ending = utilities.functions.get_ordinal_index(len(settings.suffices) - 1).lower()
    module = "Curl (" + settings.suffices['first'].affix + " - " + settings.suffices[ending].affix + ")"
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
    # add and get all the curl specific bones...
    added = add_curl_bones(oriented, rig, settings)
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
    set_curl_bones(oriented, rig, settings)
    # go back into object mode to reselect anything we deselected...
    bpy.ops.object.mode_set(mode='OBJECT')
    selected.append(rig)
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # set the bones groups, colors and shapes... (leaving edit mode required for setting color for some reason)...
    defaults = get_curl_defaults()
    first = settings.prefices['forward'].affix + settings.suffices['first'].affix
    for name, items in added.items():
        _functions.set_bone_groups(rig, name, items['groups'] if items else [], module)
        if items:
            _functions.set_bone_color(rig, name, settings.colors[items['color']])
            # the origins own roll isn't chain aware, so let the first chain bone decide which of its own axes to use...
            reference = first if items['shape'] == 'origin' else None
            _functions.set_bone_shape(rig, name, settings.shapes[items['shape']], [tertiary, primary, secondary], 'CURL', settings.offset, defaults['offset'], reference)
    # then return our mode to whatever it was, and rehide anything that wasn't visible to begin with...
    bpy.ops.object.mode_set(mode=last_mode)
    for obj in hidden:
        obj.hide_set(True)
    return module, added

def invoke_curl_module(context, module):
    defaults = get_curl_defaults()
    _functions.set_default_settings(module.settings, defaults)
    # overlay whatever naming/colors/shapes were last used for this rigging type, if any...
    saved = _functions.get_saved_defaults(module.rigging)
    _functions.merge_saved_defaults(module.settings, saved)
    # try and get existing armatures...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
    oriented = oriented or original
    # selected pose bones seem to respect hierarchy... (isolate them to the oriented armature)...
    selection = [pb for pb in (context.selected_pose_bones or []) if pb.id_data == oriented]
    if len(selection) < 2:
        _functions.add_chain_names(module.settings, 2)
        # curl needs at least two bones to be relevant...
        print("Select at least two chain bones.")
        return True
    module.settings.axes.clear()
    for index, bone in enumerate(selection):
        # so we can detect the bones used to add the rigging...
        suffix = module.settings.suffices.add()
        suffix.name = utilities.functions.get_ordinal_index(index + 1).lower()
        suffix.affix, suffix.unique, suffix.required = bone.name, True, True
        # one set of curl axes per ordinal bone, defaults keep the current copy-all-axes behaviour...
        module.settings.axes.add().name = suffix.name
    # restore saved axis toggles after rebuilding ordinal entries from the current selection...
    saved_axes = saved.get('settings', {}).get('axes', []) if saved else []
    saved_axes = {entry.get('name'): entry for entry in saved_axes if entry.get('name')}
    for axes in module.settings.axes:
        values = saved_axes.get(axes.name)
        if values:
            for prop in ('x', 'y', 'z'):
                if prop in values:
                    setattr(axes, prop, values[prop])
    # set the origin if the first chain bone has a parent...
    origin = selection[0].parent
    module.settings.suffices['origin'].affix = origin.name if origin else ""
    # default to hands off if another modules bone collection already claims the origin...
    module.settings.shared = _functions.get_shared_default(rig, module.settings.prefices['forward'].affix + module.settings.suffices['origin'].affix)
    _functions.set_auto_mirror(module.settings, selection, origin)
    # auto detect a sensible fallback axis from the first chain bones own axes...
    points = [pb.head for pb in selection]
    axis = _functions.get_chain_axis(points, selection[0].bone)
    module.settings.axis = axis
    return True

def draw_curl_settings(layout, oriented, module):
    # define the curl only settings to show...
    settings = ['suffices', 'axis', 'offset', 'mirror', 'shared']
    # need to check suffices for validity...
    suffices = [b for b in module.settings.suffices]
    validity = _functions.get_naming_validity(suffices)
    _interface.show_operator_settings(layout, module, oriented, settings, validity)

def execute_curl_module(context, module):
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
    # check the rigging for curl specific conflicts... (checks constraints and collections)...
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
    name, added = add_curl_rigging(oriented, rig, module.settings)
    # tagging module with its own real identifier first keeps these settings anchored under it...
    module.module = name
    if do_mirror:
        # check the mirrored rigging for curl specific conflicts...
        validity = _functions.get_rigging_validity(oriented, rig, mirrored_suffices, conflicts, module.module)
        if not all(validity.values()):
            # conflicting rigging already exists - report only, mirrored failure isn't fatal...
            print("rigging already exists for mirrored bones...")
        else:
            # if all the mirrored bone name suffices are valid... (no need to check prefices)...
            validity = _functions.get_naming_validity(mirrored_suffices)
            if all(validity.values()):
                # add the mirrored rigging module, giving it its own list entry since it never goes through mmt.add...
                mirrored_name, mirrored_added = add_curl_rigging(oriented, rig, module.mirrored)
                _functions.add_mirrored_module(rig, module.rigging, mirrored_name, module.mirrored)
                _functions.link_mirrored_modules(rig, module, mirrored_name)
                added.update(mirrored_added)
    return added

def draw_curl_controls(layout, rig, module):
    # each chain bone gets its own dropdown, exposing its forward influence plus its offsets own...
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

    # the last chain bone is general, not limited, and is parented to the last of the ordered bones...
    ending_name = next((n for n in module_names & general_names & forward_names
        if rig.data.bones[n].parent and rig.data.bones[n].parent.name == ordered[-1]), None)
    if ending_name:
        ordered.append(ending_name)

    for index, name in enumerate(ordered):
        pose_bone = rig.pose.bones.get(name)
        copy_rot = pose_bone.constraints.get("Copy Offset Rotation") if pose_bone else None
        if not copy_rot:
            continue
        # the offset bone is whatever the forwards own rotation constraint is targeting...
        offset_pb = rig.pose.bones.get(copy_rot.subtarget)
        label = utilities.functions.get_ordinal_index(index + 1)
        header, panel = layout.panel("mmt_curl_" + name, default_closed=True)
        header.label(text=label)
        if panel and offset_pb:
            # the stretch bone is whatever the offsets own distance limit is targeting...
            limit_dist = offset_pb.constraints.get("Limit Offset Distance")
            stretch_pb = rig.pose.bones.get(limit_dist.subtarget) if limit_dist else None
            col = panel.column()
            if stretch_pb:
                stretch_rot = stretch_pb.constraints.get("Copy Target Rotation")
                if stretch_rot:
                    row = col.row(align=True)
                    row.prop(stretch_rot, "influence", text="Rotation Influence")
                    toggles = row.row(align=True)
                    toggles.ui_units_x = 3.5
                    toggles.prop(stretch_rot, "use_x", text="X", toggle=True)
                    toggles.prop(stretch_rot, "use_y", text="Y", toggle=True)
                    toggles.prop(stretch_rot, "use_z", text="Z", toggle=True)
            copy_loc = pose_bone.constraints.get("Copy Offset Location")
            if copy_loc:
                col.prop(copy_loc, "influence", text="Location Influence")


