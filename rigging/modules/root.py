import bpy

from mathutils import Vector

from .. import _functions, _interface
from ... import utilities

def get_root_defaults():
    """get rigging defaults and choose which operator settings to show..."""
    defaults = {
        # default settings...
        'suffices' : [
            {'name' : 'root', 'affix' : "", 'unique' : False, 'required' : True},
            # motion bones are added by selection...
            ],
        # default prefices...
        'prefices' : [
            {'name' : 'root', 'affix' : "", 'required' : False, 'unique' : True},
            {'name' : 'child', 'affix' : "", 'required' : False, 'unique' : True},
            ],
        # default color palettes...
        'colors' : [
            {'name' : 'root', 'palette' : 'THEME01'},
            {'name' : 'child', 'palette' : 'THEME01'},
            ],
        # and default custom shapes...
        'shapes' : [
            {'name' : 'root', 'mesh' : 'COMPASS_FULL', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.0, 1.0, 1.0), 'space' : 'WORLD', 'forward' : '+Z', 'upward' : '+X'},
            {'name' : 'child', 'mesh' : 'CIRCLE_FULL', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (1.5, 1.5, 1.5), 'space' : 'WORLD', 'forward' : '+Z', 'upward' : '+X'},
            ]
        }
    return defaults

def add_root_bones(oriented, rig, settings):
    """add a rig root and unparented motion bones (follow the root through child of constraints)..."""
    suffices, prefices, added = settings.suffices, settings.prefices, {}

    # add a plain mirror of the root bone if it doesn't already exist on the rigging armature...
    added[prefices['root'].affix + suffices['root'].affix] = {}
    existing = rig.data.edit_bones.get(prefices['root'].affix + suffices['root'].affix)
    if not existing:
        prefix, suffix = prefices["root"].affix, suffices['root'].affix
        name = _functions.add_shared_bone(oriented, rig, prefix, suffix, 'root', search=True)
        added[name] = {'groups' : ['general', 'primary'], 'color' : 'root', 'shape' : 'root'}
        length = oriented.dimensions.y if oriented.dimensions.y > oriented.dimensions.x else oriented.dimensions.x
        rig_eb = rig.data.edit_bones[name]
        rig_eb.tail = rig_eb.head + (Vector((0.0, 1.0, 0.0)) * length)
        rig_eb.align_roll(Vector((0.0, 0.0, 1.0)))
    else:
        # nothing else can ever claim a root bone, so a rebuild always keeps reclaiming its own...
        added[existing.name] = {'groups' : ['general', 'primary'], 'color' : 'root', 'shape' : 'root'}


    # for each selected bone... (skip the root itself)...
    children = [s.name for s in suffices if s.name != 'root']
    for suffix in children:
        # add a child bone matching the selected bones own geometry if it doesn't already exist, left unparented...
        added[prefices['child'].affix + suffices[suffix].affix] = {}
        existing = rig.data.edit_bones.get(prefices['child'].affix + suffices[suffix].affix)
        if not existing:
            prefix, affix = prefices["child"].affix, suffices[suffix].affix
            name = _functions.add_shared_bone(oriented, rig, prefix, affix, 'root', search=True)
            added[name] = {'groups' : ['general', 'primary'], 'color' : 'child', 'shape' : 'child'}
            # size the shape to span all of its own descendants so it hugs whatever part of the character it drives...
            oriented_eb = oriented.data.edit_bones.get(affix)
            heads = [c.head for c in oriented_eb.children_recursive]
            rig_eb = rig.data.edit_bones[name]
            length = max((max(h.x for h in heads) - min(h.x for h in heads)), (max(h.y for h in heads) - min(h.y for h in heads))) if len(heads) > 1 else 0.0
            length = length if length > 0.0 else rig_eb.length
            rig_eb.tail = rig_eb.head + (Vector((0.0, 1.0, 0.0)) * length)
            rig_eb.align_roll(Vector((0.0, 0.0, 1.0)))
            rig_eb.parent = None
        else:
            # nothing else can ever claim a root bone, so a rebuild always keeps reclaiming its own...
            added[existing.name] = {'groups' : ['general', 'primary'], 'color' : 'child', 'shape' : 'child'}

    # return the bones we added with their groups, colors and shapes...
    rig.update_from_editmode()
    return added

def set_root_bones(oriented, rig, settings):
    """set rigging constraints and drivers (edit mode, after updating new bones)..."""
    suffices, prefices = settings.suffices, settings.prefices
    root, root_name = prefices['root'].affix + suffices['root'].affix, suffices['root'].affix

    # the rig root just gets locked in local space, off by default until the user wants to lock it...
    root_pb = rig.pose.bones.get(root)
    limit_loc = root_pb.constraints.new('LIMIT_LOCATION')
    limit_loc.name, limit_loc.show_expanded = "Lock Location", False
    limit_loc.use_min_x, limit_loc.use_min_y, limit_loc.use_min_z = True, True, True
    limit_loc.use_max_x, limit_loc.use_max_y, limit_loc.use_max_z = True, True, True
    limit_loc.owner_space, limit_loc.influence = 'LOCAL', 0.0
    limit_rot = root_pb.constraints.new('LIMIT_ROTATION')
    limit_rot.name, limit_rot.show_expanded = "Lock Rotation", False
    limit_rot.use_limit_x, limit_rot.use_limit_y, limit_rot.use_limit_z = True, True, True
    limit_rot.owner_space, limit_rot.influence = 'LOCAL', 0.0
    limit_sca = root_pb.constraints.new('LIMIT_SCALE')
    limit_sca.name, limit_sca.show_expanded = "Lock Scale", False
    limit_sca.use_min_x, limit_sca.use_min_y, limit_sca.use_min_z = True, True, True
    limit_sca.use_max_x, limit_sca.use_max_y, limit_sca.use_max_z = True, True, True
    limit_sca.min_x, limit_sca.min_y, limit_sca.min_z = 1.0, 1.0, 1.0
    limit_sca.max_x, limit_sca.max_y, limit_sca.max_z = 1.0, 1.0, 1.0
    limit_sca.owner_space, limit_sca.influence = 'LOCAL', 0.0

    # the actual root then just inherits from its own rigging bone like everything else does...
    _functions.add_parent_constraints(oriented, rig, root_name, root)

    # each selected bone picks up the roots motion through its own duplicate, off by default too...
    chain, leader = [s.name for s in suffices if s.name != 'root'], None
    for suffix in chain:
        name = prefices['child'].affix + suffices[suffix].affix
        child_pb = rig.pose.bones.get(name)
        for con in child_pb.constraints:
            child_pb.constraints.remove(con)
        child_of = child_pb.constraints.new('CHILD_OF')
        child_of.name, child_of.show_expanded = "Root Transform", False
        child_of.target, child_of.subtarget = rig, root
        child_of.inverse_matrix = rig.data.bones.get(root).matrix_local.inverted()
        # every child of after the first has its influence driven from the first, so the user only sees one...
        if leader is None:
            leader = name
        else:
            drv = child_of.driver_add('influence')
            var = drv.driver.variables.new()
            var.name, var.type = 'influence', 'SINGLE_PROP'
            var.targets[0].id = rig
            var.targets[0].data_path = 'pose.bones["' + leader + '"].constraints["Root Transform"].influence'
            drv.driver.expression = 'influence'
            for mod in drv.modifiers:
                drv.modifiers.remove(mod)
        # the oriented bone inherits transforms from its own child rigging bone... (isolated to child of)...
        _functions.add_parent_constraints(oriented, rig, suffices[suffix].affix, name)

def add_root_rigging(oriented, rig, settings):
    # define the unique rigging module identifier...
    module = "Root (" + settings.suffices['root'].affix + ")"
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
    # add and get all the root motion specific bones...
    added = add_root_bones(oriented, rig, settings)
    rig.update_from_editmode()
    # update from edit mode so we can set things in pose mode...
    rig.update_from_editmode()
    # set all the constraints...
    set_root_bones(oriented, rig, settings)
    # go back into object mode to reselect anything we deselected...
    bpy.ops.object.mode_set(mode='OBJECT')
    selected.append(rig)
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # set the bones groups, colors and shapes... (leaving edit mode required for setting color for some reason)...
    axes = [Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0))]
    for name, items in added.items():
        _functions.set_bone_groups(rig, name, items['groups'] if items else [], module)
        if items:
            _functions.set_bone_color(rig, name, settings.colors[items['color']])
            _functions.set_bone_shape(rig, name, settings.shapes[items['shape']], axes, 'ROOT')
    # then return our mode to whatever it was, and rehide anything that wasn't visible to begin with...
    bpy.ops.object.mode_set(mode=last_mode)
    for obj in hidden:
        obj.hide_set(True)
    return module, added

def invoke_root_module(context, module):
    defaults = get_root_defaults()
    _functions.set_default_settings(module.settings, defaults)
    # overlay whatever naming/colors/shapes were last used for this rigging type, if any...
    _functions.merge_saved_defaults(module.settings, _functions.get_saved_defaults(module.rigging))
    # try and get existing armatures...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
    oriented = oriented or original
    # use the active bone as root... (other selected bones are optional motion followers)...
    active = oriented.data.bones.active if oriented else None
    selection = [pb for pb in (context.selected_pose_bones or []) if pb.id_data == oriented and pb.bone != active]
    if not active:
        print("Select a root bone.")
        return False
    module.settings.suffices['root'].affix = active.name
    # add ordinal motion bones from everything else selected...
    for index, bone in enumerate(selection):
        # so we can detect the bones used to add the rigging...
        suffix = module.settings.suffices.add()
        suffix.name = utilities.functions.get_ordinal_index(index + 1).lower()
        suffix.affix, suffix.unique, suffix.required = bone.name, True, True
    return True

def draw_root_settings(layout, oriented, module):
    # define the root only settings to show...
    settings = ['suffices']
    # need to check suffices for validity...
    suffices = [b for b in module.settings.suffices]
    validity = _functions.get_naming_validity(suffices)
    _interface.show_operator_settings(layout, module, oriented, settings, validity)

def execute_root_module(context, module):
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
    # root motion just piggybacks on whatever else is already there, so it shouldn't conflict...
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
    # add the rigging module...
    name, added = add_root_rigging(oriented, rig, module.settings)
    module.module = name
    return added

def draw_root_controls(layout, rig, module):
    # show root locks and the shared motion influence (blend baked and followed motion)...
    collection = rig.data.collections_all.get(module)
    if not collection:
        return
    root_pb, motions = None, []
    for bone in collection.bones:
        pose_bone = rig.pose.bones.get(bone.name)
        if not pose_bone:
            continue
        if pose_bone.constraints.get("Lock Location"):
            root_pb = pose_bone
        else:
            motions.append(pose_bone)
    if root_pb:
        for name in ["Lock Location", "Lock Rotation", "Lock Scale"]:
            constraint = root_pb.constraints.get(name)
            if constraint:
                layout.prop(constraint, "influence", text=name)
    # only the leading motion bones child of is editable, the rest are driven from it...
    driven = {d.data_path for d in rig.animation_data.drivers} if rig.animation_data else set()
    for pose_bone in motions:
        path = 'pose.bones["' + pose_bone.name + '"].constraints["Root Transform"].influence'
        if path not in driven:
            child_of = pose_bone.constraints.get("Root Transform")
            if child_of:
                layout.prop(child_of, "influence", text="Root Influence")
            break


