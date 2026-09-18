import bpy

from mathutils import Vector, Quaternion

from .. import _functions, _interface
from ... import utilities

def get_plantigrade_defaults():
    """get rigging defaults and choose which operator settings to show..."""
    defaults = {
        'suffices' : [
            {'name' : "origin", 'affix' : "", 'unique' : True, 'required' : False},
            # chain bones and ending are added by selection, pivot is detected from ending's first child...
            {'name' : "root", 'affix' : "", 'unique' : True, 'required' : False},
            ],
        'offset' : 0.3, 'position' : 0.5, 'mirror' : False, 'floor' : True, 'axis' : 'AUTO',
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
            {'name' : 'rotator', 'affix' : "rkt_", 'required' : True, 'unique' : True},
            {'name' : 'control', 'affix' : "ckt_", 'required' : True, 'unique' : True},
            {'name' : 'floor', 'affix' : "fvt_", 'required' : True, 'unique' : True},
            {'name' : 'root', 'affix' : "", 'required' : False, 'unique' : False},
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
            {'name' : 'control', 'affix' : 'THEME01'},
            {'name' : 'floor', 'palette' : 'THEME01'},
            {'name' : 'root', 'palette' : 'THEME01'},
            ],
        # and default custom shapes...
        'shapes' : [
            {'name' : 'origin', 'mesh' : 'RING_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'target', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (2.0, 2.0, 2.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'parent', 'mesh' : 'SQUING_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (4.0, 2.0, 2.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'pole', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'vector', 'mesh' : 'ARROW_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'forward', 'mesh' : 'RING_HALF', 'translation' : (0.0, 0.2, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'inverse', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.5, 0.5, 0.5), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'offset', 'mesh' : 'BALL_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.3, 0.3, 0.3), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'stretch', 'mesh' : 'DASH_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'ending', 'mesh' : 'RING_HALF', 'translation' : (0.0, -0.5, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (3.0, 3.0, 3.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '+X'},
            {'name' : 'pivot', 'mesh' : 'RING_QUARTER', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (3.0, 3.0, 3.0), 'space' : 'CHAIN', 'forward' : '-Z', 'upward' : '-Y'},
            {'name' : 'rotator', 'mesh' : 'BALL_QUARTER', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.5, 0.5, 0.5), 'space' : 'CHAIN', 'forward' : '-Z', 'upward' : '-Y'},
            {'name' : 'control', 'mesh' : 'STRIPS_QUARTER', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (2.0, 2.0, 2.0), 'space' : 'CHAIN', 'forward' : '+Y', 'upward' : '-Z'},
            {'name' : 'floor', 'mesh' : 'CIRCLE_HALF', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.5, 1.5, 1.5), 'space' : 'CHAIN', 'forward' : '-Y', 'upward' : '+X'},
            {'name' : 'root', 'mesh' : 'CIRCLE_FULL', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'WORLD', 'forward' : '+Z', 'upward' : '-Y'},
            ]
        }
    return defaults

def add_plantigrade_bones(oriented, rig, settings):
    """add plantigrade rigging bones (including the ik target parent and rotators)..."""
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
    # add the root bone if the settings have one and it doesn't already exist on the rigging armature...
    added[prefices['root'].affix + suffices['root'].affix] = {}
    existing = rig.data.edit_bones.get(prefices['root'].affix + suffices['root'].affix)
    if suffices['root'].affix and not existing:
        prefix, suffix = prefices["root"].affix, suffices['root'].affix
        name = _functions.add_shared_bone(oriented, rig, prefix, suffix, 'root', search=True)
        added[name] = {'groups' : ['general', 'primary'], 'color' : 'root', 'shape' : 'root'}
    
    # for each bone in the chain... (skip non-chain bones)...
    chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'root', 'pivot'}]
    tails, parents = [n for n in chain[1:]] + [suffices['ending'].name], [suffices['origin'].name] + [n for n in chain[:-1]]
    layers, length = ['forward', 'inverse', 'offset', 'stretch'], 0.0
    for index, suffix in enumerate(chain):
        # get the oriented and tail edit bones...
        oriented_eb = oriented.data.edit_bones.get(suffices[suffix].affix)
        tail_eb = oriented.data.edit_bones.get(suffices[tails[index]].affix)
        head, tail = oriented_eb.head, _functions.get_bone_tail(oriented_eb, tail_eb)
        # accumulate the length of the chain...
        length += utilities.functions.get_distance_direction(head, tail)[0]
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
            # plantigrade chain bones have limited rigging conflicts... (twist bones can use them)...
            groups = ['limited', 'secondary'] if layer == 'forward' else ['tertiary']
            added[name] = {'groups' : groups, 'color' : layer, 'shape' : layer}
    
    # get some of the oriented bones the rigging bones are created from...
    first_eb = rig.data.edit_bones[prefices['forward'].affix + suffices[chain[0]].affix]
    ending_eb = oriented.data.edit_bones.get(suffices['ending'].affix)
    pivot_eb = oriented.data.edit_bones.get(suffices['pivot'].affix)

    # get the primary, secondary directions, length and center of the chain...
    points = [rig.data.edit_bones[suffices[n].affix].head for n in chain] + [ending_eb.head]
    primary, secondary, tertiary, length = _functions.get_chain_normals(points, fallback=_functions.get_axis_fallback(points, first_eb, settings.axis), override=_functions.get_axis_override(first_eb, settings.axis))
    center = first_eb.head + (primary * (length * position))

    # get the foot direction and distance... (flattened on Z axis)...
    start, end = Vector((ending_eb.head.x, ending_eb.head.y, 0.0)), Vector((pivot_eb.head.x, pivot_eb.head.y, 0.0))
    distance, direction = utilities.functions.get_distance_direction(start, end)

    # add the foot forward bone pointing straight down from the ankle...
    name = prefices['forward'].affix + suffices['ending'].affix
    head, tail = ending_eb.head, Vector((ending_eb.head.x, ending_eb.head.y, 0.0))
    rolls, parent = [direction, direction * -1], prefices['forward'].affix + suffices[chain[-1]].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
    # adopt any bones already rigged off the ending bone elsewhere, so add order never breaks the hierarchy...
    _functions.set_bone_hierarchy(oriented, rig, suffices['ending'].affix, name)
    # the ending forward bone needs to have things connected to it though...
    added[name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'ending'}

    # and the inverse foot bone identically...
    name = prefices['inverse'].affix + suffices['ending'].affix
    parent = prefices['inverse'].affix + suffices[chain[-1]].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
    added[name] = {'groups' : ['tertiary'], 'color' : 'inverse', 'shape' : 'inverse'}

    # and the offset foot bone identically... (chains to its own kind, same as inverse above)...
    name = prefices['offset'].affix + suffices['ending'].affix
    parent = prefices['offset'].affix + suffices[chain[-1]].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
    added[name] = {'groups' : ['tertiary'], 'color' : 'offset', 'shape' : 'offset'}

    # add the ball forward bone oriented along the foot direction...
    name = prefices['forward'].affix + suffices['pivot'].affix
    head, tail = pivot_eb.head, pivot_eb.head + (direction * (distance * 0.5))
    rolls, parent = [Vector((0.0, 0.0, -1.0))], prefices['forward'].affix + suffices['ending'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
    added[name] = {'groups' : ['general', 'secondary'], 'color' : 'forward', 'shape' : 'pivot'}
    
    # and the inverse ball bone identically...
    name = prefices['inverse'].affix + suffices['pivot'].affix
    parent = prefices['inverse'].affix + suffices['ending'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls, scale='ALIGNED')
    added[name] = {'groups' : ['tertiary'], 'color' : 'inverse', 'shape' : 'inverse'}
    
    # add the foot parent bone on the floor oriented along the inverse foot direction... (never parented, child of instead)...
    name = prefices['parent'].affix + suffices['ending'].affix
    head = start + (direction * (distance * 0.5))
    tail = head + (-direction * distance)
    rolls = [Vector((0.0, 0.0, 1.0))]
    _functions.add_rigging_bone(rig, name, "", head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'parent'}
    
    # add the ball rotator bone oriented along the inverse foot direction...
    name = prefices['rotator'].affix + suffices['pivot'].affix
    head, tail = pivot_eb.head, pivot_eb.head + (-direction * distance)
    rolls, parent = [Vector((0.0, 0.0, 1.0))], prefices['parent'].affix + suffices['ending'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['tertiary'], 'color' : 'inverse', 'shape' : 'rotator'}
    
    # add the foot rotator bone oriented along the inverse foot direction...
    name = prefices['rotator'].affix + suffices['ending'].affix
    head = Vector((ending_eb.head.x, ending_eb.head.y, pivot_eb.head.z))
    tail = head + (-direction * distance)
    rolls, parent = [Vector((0.0, 0.0, 1.0))], prefices['rotator'].affix + suffices['pivot'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['tertiary'], 'color' : 'inverse', 'shape' : 'rotator'}
    
    # add the foot target bone pointing straight down from the ankle...
    name = prefices['target'].affix + suffices['ending'].affix
    head, tail = ending_eb.head, Vector((ending_eb.head.x, ending_eb.head.y, 0.0))
    rolls, parent = [direction, -direction], prefices['rotator'].affix + suffices['ending'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'target'}
    
    # add the foot control bone oriented along the inverse foot direction... (at the ankle)...
    name = prefices['control'].affix + suffices['ending'].affix
    head, tail = ending_eb.head, ending_eb.head + (-direction * distance)
    rolls, parent = [Vector((0.0, 0.0, 1.0))], prefices['parent'].affix + suffices['ending'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'control'}

    # create the vector bone oriented along the chains direction and rolled towards the knee...
    name = prefices['vector'].affix + suffices[chain[0]].affix
    head, tail = first_eb.head, center
    rolls, parent = [secondary, -secondary], prefices['forward'].affix + suffices['origin'].affix
    _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'vector'}

    # add the pole target at the position point offset along the secondary axis... (never parented, child of instead)...
    name = prefices['pole'].affix + suffices[chain[0]].affix
    head, tail = center + (secondary * offset), center
    rolls = [-primary]
    _functions.add_rigging_bone(rig, name, "", head, tail, rolls)
    added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'pole'}
    
    # create the floor bone on the floor the same as the foot parent bone...
    if settings.floor:
        name = prefices['floor'].affix + suffices['ending'].affix
        head = start + (direction * (distance * 0.5))
        tail = head + (-direction * distance)
        rolls, parent = [Vector((0.0, 0.0, 1.0))], ""
        _functions.add_rigging_bone(rig, name, parent, head, tail, rolls)
        added[name] = {'groups' : ['primary'], 'color' : 'target', 'shape' : 'floor'}
    
    # return the bones we added with their groups, colors and shapes...
    rig.update_from_editmode()
    return added

def set_plantigrade_bones(oriented, rig, settings):
    """set rigging constraints and drivers (edit mode, after updating new bones)..."""
    suffices, prefices = settings.suffices, settings.prefices
    chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'pivot', 'root'}]
    target = prefices['target'].affix + suffices['ending'].affix
    pole = prefices['pole'].affix + suffices[chain[0]].affix
    # for each bone in the chain...
    for index, name in enumerate(chain):
        suffix = suffices[name].affix
        # get the names of the bones in the chain we created...
        forward = prefices['forward'].affix + suffix
        inverse = prefices['inverse'].affix + suffix
        offset = prefices['offset'].affix + suffix
        stretch = prefices['stretch'].affix + suffix

        # the offset bones copy the location of their own inverse bones in world space...
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
        rig.pose.bones[forward].ik_stretch = 0.25 * ((index + 1) / len(chain)) ** 2
        # both the stretch and inverse bones copy the kinematic settings of the forward bone...
        _functions.add_kinematic_drivers(rig, inverse, forward)
        # this is to keep keys off mechanical bones and ensure they stay the same between the chains...
        _functions.add_kinematic_drivers(rig, stretch, forward)

        # the inverse bone copies the Y scale of the stretch bone... (limited to 1.0 to stop drifting)...
        copy = {'subtarget' : stretch, 'use' : [False, True, False], 'power' : 1.0, 'uniform' : False, 'offset' : False, 'additive' : False, 'space' : ['LOCAL', 'LOCAL'], 'name' : "Copy Stretch Scale"}
        limit = {'use' : [False, True, False], 'min' : [1.0, 1.0, 1.0], 'max' : [1.5, 1.5, 1.5], 'space' : 'LOCAL', 'name' : "Limit Inverse Scale"}
        _functions.add_scale_constraints(rig, inverse, copy, limit)
        # and the stretch bone gets scale drivers from the pole target... (for tweaking chain tension)...
        pole_power = 1 / len(chain)
        stretch_pb = rig.pose.bones.get(stretch)
        for axis_index, transform_type in enumerate(('SCALE_X', 'SCALE_Y', 'SCALE_Z')):
            drv = stretch_pb.driver_add('scale', axis_index)
            var = drv.driver.variables.new()
            var.name, var.type = 'pole_scale', 'TRANSFORMS'
            var.targets[0].id = rig
            var.targets[0].bone_target = pole
            var.targets[0].transform_type = transform_type
            var.targets[0].transform_space = 'TRANSFORM_SPACE'
            var.targets[0].rotation_mode = 'AUTO'
            drv.driver.expression = 'pole_scale ** ' + str(pole_power)
            # and remove any sneaky curve modifiers...
            for mod in drv.modifiers:
                drv.modifiers.remove(mod)

        # if this is the first chain bone...
        if index == 0:
            # the inverse bone has a copy rotation to the stretch bone... (to mimic the pole oriented stretch bone)...
            copy = {'subtarget' : stretch, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'REPLACE', 'influence' : 1.0, 'name' : "Copy Stretch Rotation"}
            _functions.add_rotation_constraints(rig, inverse, copy, {}, {})
        # if it is not...
        else:
            # inverse and stretch bones get rotation drivers from the pole target... (for tweaking chain rotation)...
            pole_influence = (0.5 / (len(chain) - 1)) * index
            for rotated in (inverse, stretch):
                rotated_pb = rig.pose.bones.get(rotated)
                rotated_pb.rotation_mode = 'XYZ'
                for axis_index, transform_type in enumerate(('ROT_X', 'ROT_Y', 'ROT_Z')):
                    drv = rotated_pb.driver_add('rotation_euler', axis_index)
                    var = drv.driver.variables.new()
                    var.name, var.type = 'pole_rotation', 'TRANSFORMS'
                    var.targets[0].id = rig
                    var.targets[0].bone_target = pole
                    var.targets[0].transform_type = transform_type
                    var.targets[0].transform_space = 'TRANSFORM_SPACE'
                    var.targets[0].rotation_mode = 'AUTO'
                    drv.driver.expression = str(pole_influence) + ' * pole_rotation'
                    # and remove any sneaky curve modifiers...
                    for mod in drv.modifiers:
                        drv.modifiers.remove(mod)
            # and if these are the last bones in the chain...
            if index == len(chain) - 1:
                # the stretch bone has an IK constraint... (with stretching)...
                ik = {'target' : target, 'pole' : pole, 'length' : len(chain), 'stretch' : True, 'name' : "Stretch IK"}
                _functions.add_kinematic_constraints(rig, stretch, ik)
                # the inverse bone has an IK constraint... (no pole, so its own ik limits govern the bend instead)...
                ik = {'target' : target, 'pole' : "", 'length' : len(chain), 'stretch' : False, 'name' : "Inverse IK"}
                _functions.add_kinematic_constraints(rig, inverse, ik)

    # the ball rotator copies the rotation of the control... (all axes limited on X axis)...
    name = prefices['rotator'].affix + suffices['pivot'].affix
    subtarget = prefices['control'].affix + suffices['ending'].affix
    copy = {'subtarget' : subtarget, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'REPLACE', 'name' : "Copy Control Rotation"}
    limit = {'use' : [True, False, False], 'min' : [0.0, 0.0, 0.0], 'max' : [90.0, 0.0, 0.0], 'space' : 'LOCAL'}
    _functions.add_rotation_constraints(rig, name, copy, limit, {})

    # the foot rotator copies the rotation of the control... (only X axis limited inverse from ball)...
    name = prefices['rotator'].affix + suffices['ending'].affix
    subtarget = prefices['control'].affix + suffices['ending'].affix
    copy = {'subtarget' : subtarget, 'use' : [True, False, False], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'REPLACE', 'name' : "Copy Control Rotation"}
    limit = {'use' : [True, False, False], 'min' : [-90.0, 0.0, 0.0], 'max' : [0.0, 0.0, 0.0], 'space' : 'LOCAL'}
    _functions.add_rotation_constraints(rig, name, copy, limit, {})

    # the ball inverse bone copies the inverse X rotation of the ball rotator... (replaced)...
    name = prefices['inverse'].affix + suffices['pivot'].affix
    subtarget = prefices['rotator'].affix + suffices['pivot'].affix
    copy = {'subtarget' : subtarget, 'use' : [True, False, False], 'invert' : [True, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'REPLACE', 'name' : "Copy Rotator Rotation"}
    _functions.add_rotation_constraints(rig, name, copy, {}, {})

    # the ball forwards bone copies the rotation of the inverse bone... (before original)...
    name = prefices['forward'].affix + suffices['pivot'].affix
    subtarget = prefices['inverse'].affix + suffices['pivot'].affix
    copy = {'subtarget' : subtarget, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'BEFORE', 'name' : "Copy Inverse Rotation"}
    _functions.add_rotation_constraints(rig, name, copy, {}, {}, drive=True)
    # oriented armature bones inherit transforms from their rigging bone... (isolated to child of)...
    _functions.add_parent_constraints(oriented, rig, suffices['pivot'].affix, name)

    # the foot inverse bone copies the rotation of the target... (replaced parent space)...
    name = prefices['inverse'].affix + suffices['ending'].affix
    subtarget = prefices['target'].affix + suffices['ending'].affix
    copy = {'subtarget' : subtarget, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL_WITH_PARENT', 'LOCAL_WITH_PARENT'], 'mode' : 'REPLACE', 'name' : "Copy Target Rotation"}
    _functions.add_rotation_constraints(rig, name, copy, {}, {})

    # the foot offset bone copies the location and rotation of it's inverse bone in world space...
    name = prefices['offset'].affix + suffices['ending'].affix
    subtarget = prefices['inverse'].affix + suffices['ending'].affix
    copy = {'subtarget' : subtarget, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['WORLD', 'WORLD'], 'offset' : False, 'name' : "Copy Inverse Location"}
    _functions.add_location_constraints(rig, name, copy, {})
    # then limit it's distance to the ik targets head, since it's created in the same place to begin with...
    limit_dist = rig.pose.bones.get(name).constraints.new('LIMIT_DISTANCE')
    limit_dist.name, limit_dist.target, limit_dist.subtarget = "Limit Offset Distance", rig, target
    limit_dist.head_tail, limit_dist.distance = 0.0, 0.0
    limit_dist.target_space, limit_dist.owner_space = 'WORLD', 'WORLD'
    copy = {'subtarget' : subtarget, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['WORLD', 'WORLD'], 'mode' : 'REPLACE', 'name' : "Copy Inverse Rotation"}
    _functions.add_rotation_constraints(rig, name, copy, {}, {})

    # the foot forwards bone copies the rotation of it's offset bone... (before original)...
    name = prefices['forward'].affix + suffices['ending'].affix
    subtarget = prefices['offset'].affix + suffices['ending'].affix
    copy = {'subtarget' : subtarget, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'mode' : 'BEFORE', 'name' : "Copy Offset Rotation"}
    _functions.add_rotation_constraints(rig, name, copy, {}, {}, drive=True)
    # and the foot forwards bone copies the offset bones location too... (off by default, local to local space)...
    copy = {'subtarget' : subtarget, 'use' : [True, True, True], 'invert' : [False, False, False], 'space' : ['LOCAL', 'LOCAL'], 'offset' : True, 'influence' : 0.0, 'name' : "Copy Offset Location"}
    _functions.add_location_constraints(rig, name, copy, {})
    # the oriented bones inherit transforms from their rigging bone... (isolated to child of)...
    _functions.add_parent_constraints(oriented, rig, suffices['ending'].affix, name)
    
    # before damp tracking to the target...
    vector_pb = rig.pose.bones.get(prefices['vector'].affix + suffices[chain[0]].affix)
    damp_track = vector_pb.constraints.new('DAMPED_TRACK')
    damp_track.name = "Damped Target Track"
    damp_track.target, damp_track.subtarget = rig, prefices['target'].affix + suffices['ending'].affix

    # the pole is never parented, it follows the ik vector bone with a plain child of instead...
    vector_bb = rig.data.bones.get(prefices['vector'].affix + suffices[chain[0]].affix)
    pole_pb = rig.pose.bones.get(pole)
    child_of = pole_pb.constraints.new('CHILD_OF')
    child_of.name, child_of.show_expanded = "Vector Transform", False
    child_of.target, child_of.subtarget = rig, vector_bb.name
    child_of.inverse_matrix = vector_bb.matrix_local.inverted()

    # driven from a custom property instead of edited directly, so the root driver can read it without a cycle...
    pole_pb["Vector Influence"] = 1.0
    pole_pb.id_properties_ui("Vector Influence").update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, default=1.0, subtype='FACTOR')
    drv = child_of.driver_add('influence')
    var = drv.driver.variables.new()
    var.name, var.type = 'vector_influence', 'SINGLE_PROP'
    var.targets[0].id = rig
    var.targets[0].data_path = 'pose.bones["' + pole + '"]["Vector Influence"]'
    drv.driver.expression = 'vector_influence'
    for mod in drv.modifiers:
        drv.modifiers.remove(mod)

    # if we have an ik root bone the foot parent, pole and floor (if any) get a child of to it too...
    if suffices['root'].affix:
        root_bb = rig.data.bones.get(prefices['root'].affix + suffices['root'].affix)
        foot_parent = prefices['parent'].affix + suffices['ending'].affix
        names = [foot_parent, pole]
        if settings.floor:
            names.append(prefices['floor'].affix + suffices['ending'].affix)
        for name in names:
            child_pb = rig.pose.bones.get(name)
            child_of = child_pb.constraints.new('CHILD_OF')
            child_of.name, child_of.show_expanded = "Root Transform", False
            child_of.target, child_of.subtarget = rig, root_bb.name
            child_of.inverse_matrix = root_bb.matrix_local.inverted()

        # the pole and floor (not the foot parent itself) get their root influence driven from the foot parents...
        for name in names[1:]:
            child_of = rig.pose.bones[name].constraints["Root Transform"]
            drv = child_of.driver_add('influence')
            var = drv.driver.variables.new()
            var.name, var.type = 'target_influence', 'SINGLE_PROP'
            var.targets[0].id = rig
            var.targets[0].data_path = 'pose.bones["' + foot_parent + '"].constraints["Root Transform"].influence'
            if name == pole:
                # multiplied by 1 - vector influence, so the vector child of can override the pole entirely...
                vector_var = drv.driver.variables.new()
                vector_var.name, vector_var.type = 'vector_influence', 'SINGLE_PROP'
                vector_var.targets[0].id = rig
                vector_var.targets[0].data_path = 'pose.bones["' + pole + '"]["Vector Influence"]'
                drv.driver.expression = 'target_influence * (1 - vector_influence)'
            else:
                drv.driver.expression = 'target_influence'
            # and remove any sneaky curve modifiers...
            for mod in drv.modifiers:
                drv.modifiers.remove(mod)

    # and the foot parent has a floor constraint...
    if settings.floor:
        parent_pb = rig.pose.bones.get(prefices['parent'].affix + suffices['ending'].affix)
        floor_con = parent_pb.constraints.new('FLOOR')
        floor_con.target, floor_con.subtarget = rig, prefices['floor'].affix + suffices['ending'].affix
        floor_con.floor_location, floor_con.use_rotation, floor_con.name = 'FLOOR_Z', True, "Parent Floor"

def add_plantigrade_rigging(oriented, rig, settings):
    # define the unique rigging module identifier...
    chain = [s.name for s in settings.suffices if s.name not in {'origin', 'ending', 'pivot', 'root'}]
    module = "Plantigrade (" + settings.suffices[chain[0]].affix + " - " + settings.suffices['ending'].affix + ")"
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
    # add and get all the plantigrade specific bones...
    added = add_plantigrade_bones(oriented, rig, settings)
    rig.update_from_editmode()
    # get the chain normals rigging bones while still in edit mode...
    first_eb = rig.data.edit_bones[settings.prefices['forward'].affix + settings.suffices[chain[0]].affix]
    ending_eb = oriented.data.edit_bones.get(settings.suffices['ending'].affix)
    points = points = [rig.data.edit_bones[settings.suffices[n].affix].head for n in chain] + [ending_eb.head]
    primary, secondary, tertiary, _ = _functions.get_chain_normals(points, fallback=_functions.get_axis_fallback(points, first_eb, settings.axis), override=_functions.get_axis_override(first_eb, settings.axis))
    # update from edit mode so we can set things in pose mode...
    rig.update_from_editmode()
    # set all the constraints and drivers...
    set_plantigrade_bones(oriented, rig, settings)
    # go back into object mode to reselect anything we deselected...
    bpy.ops.object.mode_set(mode='OBJECT')
    selected.append(rig)
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # set the bones groups, colors and shapes... (leaving edit mode required for setting color for some reason)...
    defaults = get_plantigrade_defaults()
    first = settings.prefices['forward'].affix + settings.suffices[chain[0]].affix
    for name, items in added.items():
        _functions.set_bone_groups(rig, name, items['groups'] if items else [], module)
        if items:
            _functions.set_bone_color(rig, name, settings.colors[items['color']])
            # the origins own roll isn't chain aware, so let the first chain bone decide which of its own axes to use...
            reference = first if items['shape'] == 'origin' else None
            _functions.set_bone_shape(rig, name, settings.shapes[items['shape']], [tertiary, primary, secondary], 'PLANTIGRADE', settings.offset, defaults['offset'], reference)
    # then return our mode to whatever it was, and rehide anything that wasn't visible to begin with...
    bpy.ops.object.mode_set(mode=last_mode)
    for obj in hidden:
        obj.hide_set(True)
    return module, added

def invoke_plantigrade_module(context, module):
    defaults = get_plantigrade_defaults()
    _functions.set_default_settings(module.settings, defaults)
    # overlay whatever naming/colors/shapes were last used for this rigging type, if any...
    _functions.merge_saved_defaults(module.settings, _functions.get_saved_defaults(module.rigging))
    # try and get existing armatures...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
    oriented = oriented or original
    # selected pose bones respect hierarchy... (isolate them to the oriented armature)...
    selection = [pb for pb in (context.selected_pose_bones or []) if pb.id_data == oriented]
    if len(selection) < 3:
        _functions.add_chain_names(module.settings, 2, ending=True)
        # plantigrade needs at least a thigh, calf and foot bone to form a valid ik chain...
        print("Select at least three chain bones (e.g. thigh, calf, foot).")
        return True
    # add ordinal chain bones from all but the last selected bone...
    for index, bone in enumerate(selection[:-1]):
        suffix = module.settings.suffices.add()
        suffix.name = utilities.functions.get_ordinal_index(index + 1).lower()
        suffix.affix, suffix.unique, suffix.required = bone.name, True, True
    # last selected bone is the ending...
    ending = module.settings.suffices.add()
    ending.name, ending.affix, ending.unique, ending.required = 'ending', selection[-1].name, True, True
    # auto-detect pivot from the first child of the ending bone...
    ending_pb = selection[-1]
    pivot = module.settings.suffices.add()
    pivot.name, pivot.unique, pivot.required = 'pivot', True, True
    pivot.affix = ending_pb.children[0].name if ending_pb.children else ""
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
    # initialize the offset using the scenes unit scale...
    heads = [b.head for b in selection[1:-1]]
    module.settings.position = _functions.get_central_position(selection[0].head, selection[-1].head, heads)
    module.settings.offset = module.settings.offset * utilities.functions.get_unit_scaling(context, inverse=True)
    return True

def draw_plantigrade_settings(layout, oriented, module):
    # define the plantigrade only settings to show...
    settings = ['suffices', 'axis', 'offset', 'position', 'floor', 'mirror', 'shared']
    # need to check suffices for validity...
    suffices = [b for b in module.settings.suffices]
    validity = _functions.get_naming_validity(suffices)
    _interface.show_operator_settings(layout, module, oriented, settings, validity)

def execute_plantigrade_module(context, module):
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
    suffices = [s for s in module.settings.suffices]
    prefices = [p for p in module.settings.prefices]
    # check the rigging for plantigrade specific conflicts... (checks constraints and collections)...
    conflicts = ["Opposable", "Plantigrade", "Digitigrade", "Spline", "Scalar", "Curl", "Custom", "Twist"]
    validity = _functions.get_rigging_validity(oriented, rig, suffices, conflicts, module.module)
    if not all(validity.values()):
        # conflicting rigging already exists - cancel...
        print("rigging already exists for these bones:", [name for name, valid in validity.items() if not valid])
        return None
    # if all the bone name suffices are valid...
    validity = _functions.get_naming_validity(suffices)
    if not all(validity.values()):
        print("Suffix validation failed...")
        print(validity)
        return None
    # and all the prefices are also valid...
    validity = _functions.get_naming_validity(prefices)
    if not all(validity.values()):
        print("Prefix validation failed...")
        print(validity)
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
    name, added = add_plantigrade_rigging(oriented, rig, module.settings)
    # tagging module with its own real identifier first keeps these settings anchored under it...
    module.module = name
    if do_mirror:
        # check the mirrored rigging for plantigrade specific conflicts...
        validity = _functions.get_rigging_validity(oriented, rig, mirrored_suffices, conflicts, module.module)
        if not all(validity.values()):
            # conflicting rigging already exists - report only, mirrored failure isn't fatal...
            print("rigging already exists for mirrored bones...")
        else:
            # if all the mirrored bone name suffices are valid... (no need to check prefices)...
            validity = _functions.get_naming_validity(mirrored_suffices)
            if all(validity.values()):
                # add the mirrored rigging module, giving it its own list entry since it never goes through mmt.add...
                mirrored_name, mirrored_added = add_plantigrade_rigging(oriented, rig, module.mirrored)
                _functions.add_mirrored_module(rig, module.rigging, mirrored_name, module.mirrored)
                _functions.link_mirrored_modules(rig, module, mirrored_name)
                added.update(mirrored_added)
    return added

def draw_plantigrade_controls(layout, rig, module):
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

    # parent the general foot to the last chain bone and the general pivot to the foot...
    ending_name = next((n for n in module_names & general_names & forward_names
        if rig.data.bones[n].parent and rig.data.bones[n].parent.name == ordered[-1]), None)

    # pole and foot parent bone names are built from the modules own fixed default affixes...
    defaults = get_plantigrade_defaults()
    affixes = {p['name'] : p['affix'] for p in defaults['prefices']}
    parent_pb = rig.pose.bones.get(affixes['parent'] + ending_name) if ending_name else None
    pole_pb = rig.pose.bones.get(affixes['pole'] + ordered[0])

    # the ball pivot forward bone is general too, but parents to the ending rather than the chain...
    pivot_name = next((n for n in module_names & general_names & forward_names
        if rig.data.bones[n].parent and rig.data.bones[n].parent.name == ending_name), None)
    pivot_pb = rig.pose.bones.get(pivot_name) if pivot_name else None

    # the targets own variables sit at the top, always visible...
    col = layout.column(align=True)
    if pivot_pb:
        copy_rot = pivot_pb.constraints.get("Copy Inverse Rotation")
        if copy_rot:
            col.prop(copy_rot, "influence", text="Pivot Influence")
    if pole_pb:
        if "Vector Influence" in pole_pb:
            col.prop(pole_pb, '["Vector Influence"]', text="Vector Influence")
    if parent_pb:
        root_transform = parent_pb.constraints.get("Root Transform")
        if root_transform:
            col.prop(root_transform, "influence", text="Root Influence")
        floor_con = parent_pb.constraints.get("Parent Floor")
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

    # the end bone gets it's own dropdown alongside the chain bones...
    if ending_name:
        ending_pb = rig.pose.bones.get(ending_name)
        header, panel = layout.panel("mmt_ik_settings_end", default_closed=True)
        header.label(text="End Bone")
        if panel:
            col = panel.column(align=True)
            copy_rot = ending_pb.constraints.get("Copy Offset Rotation")
            if copy_rot:
                col.prop(copy_rot, "influence", text="Rotation Influence")
            copy_loc = ending_pb.constraints.get("Copy Offset Location")
            if copy_loc:
                col.prop(copy_loc, "influence", text="Location Influence")

    # snapping needs the forward chain to already be posed in fk, which only makes sense once the module is built...
    layout.separator()
    layout.operator("mmt.snap", text="Snap IK to FK", icon='CON_KINEMATIC')

def set_snapped_direct(context, module):
    return _functions.set_snapped_chain_direct(context, module, parented=True)

def set_snapped_kinematics(context, module, clear=True):
    # snap the ik target and pole onto the forward chains current fk pose so switching to ik doesn't pop - forwards read pose_bone.matrix directly since their real rotation comes from a live "Copy Offset Rotation/Location" constraint, not their own basis...
    rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
    if not rig:
        return False
    context.view_layer.update()
    settings = module.settings
    suffices, prefices = settings.suffices, settings.prefices
    chain = [s.name for s in suffices if s.name not in {'origin', 'ending', 'pivot', 'root'}]
    forward_pbs = [rig.pose.bones.get(prefices['forward'].affix + suffices[n].affix) for n in chain]
    ending_pb = rig.pose.bones.get(prefices['forward'].affix + suffices['ending'].affix)
    pivot_pb = rig.pose.bones.get(prefices['forward'].affix + suffices['pivot'].affix)
    if not ending_pb or not pivot_pb or any(pb is None for pb in forward_pbs):
        return False
    parent_pb = rig.pose.bones.get(prefices['parent'].affix + suffices['ending'].affix)
    control_pb = rig.pose.bones.get(prefices['control'].affix + suffices['ending'].affix)
    vector_pb = rig.pose.bones.get(prefices['vector'].affix + suffices[chain[0]].affix)
    pole_pb = rig.pose.bones.get(prefices['pole'].affix + suffices[chain[0]].affix)

    # capture the forward chains current pose before touching anything...
    all_forwards = forward_pbs + [ending_pb, pivot_pb]
    original_rotations = [pb.matrix_basis.to_quaternion() for pb in all_forwards]
    original_locations = [pb.location.copy() for pb in all_forwards]

    ending_matrix = ending_pb.matrix.copy()
    points = [pb.matrix.translation.copy() for pb in forward_pbs] + [ending_matrix.translation]
    # resolved once from rest data - the chains natural bend direction and forwards[0]s rest rotation, needed below to track which side it should bend toward independent of live geometry...
    rest_points = [pb.bone.matrix_local.translation for pb in forward_pbs] + [ending_pb.bone.matrix_local.translation]
    _, rest_secondary, _, _ = _functions.get_chain_normals(rest_points)
    rest_rotation_0 = forward_pbs[0].bone.matrix_local.to_quaternion()
    # a chain thats genuinely straight has no real bend signal, so override secondary with rest_secondary rotated by however far forwards[0] has turned since rest...
    override = _functions.get_axis_override(forward_pbs[0], settings.axis)
    if override is None:
        chain_length, chain_direction = utilities.functions.get_distance_direction(points[0], points[-1])
        dominant = Vector((0.0, 0.0, 0.0))
        for point in points[1:-1]:
            projection = (point - points[0]).dot(chain_direction)
            perpendicular = point - (points[0] + (chain_direction * projection))
            if perpendicular.length > dominant.length:
                dominant = perpendicular
        delta = forward_pbs[0].matrix.to_quaternion() @ rest_rotation_0.inverted()
        tracked_secondary = delta @ rest_secondary
        if dominant.length <= (chain_length * 0.01):
            override = tracked_secondary
        # a genuine hyperextension flips secondary correctly, but the pole should hold its side regardless, so negate back onto the tracked side when they disagree...
        elif dominant.dot(tracked_secondary) < 0.0:
            override = -dominant
    primary, secondary, _, length = _functions.get_chain_normals(points, override=override)
    center = points[0] + (primary * (length * settings.position))

    # solve the foot parent/control through the balls own local rotation...
    if parent_pb and control_pb:
        control_x, parent_local = _functions.get_snapped_parent(parent_pb, pivot_pb, ending_pb, lambda pb: pb.matrix.copy())
        control_pb.rotation_mode = 'XYZ'
        control_pb.rotation_euler.x = control_x
        parent_pb.rotation_mode = 'QUATERNION'
        parent_pb.location = parent_local.translation
        parent_pb.rotation_quaternion = parent_local.to_quaternion()

    # resolve once from rest data which of vectors own axes points toward the pole, apply that fixed sign to secondary, then read the same axis back off vectors own live just-solved matrix for poles position...
    rest_axes = _functions.get_bone_axes(vector_pb.bone, ['+X', '-X', '+Z', '-Z'])
    pole_axis_name, _ = utilities.functions.get_closest_axis(rest_secondary, rest_axes)
    vector_z_sign = 1.0 if pole_axis_name == '+Z' else -1.0

    # align the vector, then solve the pole against whichever of its child ofs is actually active...
    vector_matrix = _functions.set_snapped_vector(vector_pb, lambda pb: pb.matrix.copy(), ending_matrix, primary, secondary * vector_z_sign, vector_pb.parent)
    posed_axes = {'+X': vector_matrix.to_3x3().col[0], '-X': -vector_matrix.to_3x3().col[0],
        '+Z': vector_matrix.to_3x3().col[2], '-Z': -vector_matrix.to_3x3().col[2]}
    position = center + (posed_axes[pole_axis_name].normalized() * settings.offset)
    _functions.set_snapped_pole(pole_pb, position, vector_matrix, lambda pb: pb.matrix.copy())

    # clear forward transforms only as far as constraints take over (keep the remaining pose)...
    if clear:
        for pb, original_rotation, original_location in zip(all_forwards, original_rotations, original_locations):
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


