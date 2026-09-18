import bpy

from mathutils import Vector

from .. import _functions, _interface
from ... import utilities

def get_custom_defaults():
    """get rigging defaults and choose which operator settings to show..."""
    defaults = {
        # no default suffices, they're accumulated one per selected bone...
        'suffices' : [],
        # default prefices...
        'prefices' : [
            {'name' : 'forward', 'affix' : "", 'required' : False, 'unique' : True},
            ],
        # default color palettes...
        'colors' : [
            {'name' : 'forward', 'palette' : 'THEME13'},
            ],
        # and default custom shapes...
        'shapes' : [
            {'name' : 'forward', 'mesh' : 'BALL_FULL', 'translation' : (0.0, 0.0, 0.0), 'rotation' : (0.0, 0.0, 0.0), 'scale' : (0.5, 0.5, 0.5)},
            ]
        }
    return defaults

def add_custom_bones(oriented, rig, settings):
    # one plain shared bone per suffix, matching the oriented bones own geometry, no chain or extra constraints...
    suffices, prefices, added = settings.suffices, settings.prefices, {}
    for suffix in suffices:
        prefix, affix = prefices['forward'].affix, suffix.affix
        added[prefix + affix] = {}
        existing = rig.data.edit_bones.get(prefix + affix)
        if not existing:
            name = _functions.add_shared_bone(oriented, rig, prefix, affix, 'origin', search=True)
            # limited (not general) - only twist can attach here, every other module lists Custom in its own conflicts...
            added[name] = {'groups' : ['limited', 'primary'], 'color' : 'forward', 'shape' : 'forward'}
        elif settings.shared:
            added[existing.name] = {'groups' : ['limited', 'primary'], 'color' : 'forward', 'shape' : 'forward'}
    rig.update_from_editmode()
    return added

def add_custom_rigging(oriented, rig, settings):
    # define the unique rigging module identifier...
    module = "Custom (" + ", ".join(s.affix for s in settings.suffices) + ")"
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
    # add all the custom bones...
    added = add_custom_bones(oriented, rig, settings)
    rig.update_from_editmode()
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
            _functions.set_bone_shape(rig, name, settings.shapes[items['shape']], axes, "")
    # then return our mode to whatever it was, and rehide anything that wasn't visible to begin with...
    bpy.ops.object.mode_set(mode=last_mode)
    for obj in hidden:
        obj.hide_set(True)
    return module, added

def invoke_custom_module(context, module):
    defaults = get_custom_defaults()
    _functions.set_default_settings(module.settings, defaults)
    # overlay whatever naming/colors/shapes were last used for this rigging type, if any...
    _functions.merge_saved_defaults(module.settings, _functions.get_saved_defaults(module.rigging))
    # try and get existing armatures...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
    oriented = oriented or original
    if not oriented:
        return False
    # selected pose bones seem to respect hierarchy... (isolate them to the oriented armature)...
    selection = [pb for pb in (context.selected_pose_bones or []) if pb.id_data == oriented]
    if not selection:
        print("Select at least one bone to build custom rigging for.")
        return False
    # add ordinal bones from everything selected... (no root/chain distinction, every bone is equal)...
    for index, bone in enumerate(selection):
        suffix = module.settings.suffices.add()
        suffix.name = utilities.functions.get_ordinal_index(index + 1).lower()
        suffix.affix, suffix.unique, suffix.required = bone.name, True, True
    # default to hands off if another modules bone collection already claims any of these bones...
    prefix = module.settings.prefices['forward'].affix
    module.settings.shared = all(_functions.get_shared_default(rig, prefix + s.affix) for s in module.settings.suffices)
    return True

def draw_custom_settings(layout, oriented, module):
    settings = ['suffices', 'shared']
    suffices = [b for b in module.settings.suffices]
    validity = _functions.get_naming_validity(suffices)
    _interface.show_operator_settings(layout, module, oriented, settings, validity)

def execute_custom_module(context, module):
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
    # custom bones can be built on top of anything shareable, they just can't be a shared target themselves...
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
    name, added = add_custom_rigging(oriented, rig, module.settings)
    module.module = name
    return added


