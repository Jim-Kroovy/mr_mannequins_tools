import bpy
import os

from .. import utilities
from .. import retargeting
from .. import orientation
from .. import templates

def import_file_fbx(filepath, filmbox):
    # call the FBX importer with fixed and variable settings...
    bpy.ops.import_scene.fbx(
        filepath=filepath,
        # fixed settings...
        use_custom_props=True, use_custom_props_enum_as_string=True, use_anim=True,
        # variable settings...
        use_manual_orientation=filmbox.manual_orientation, global_scale=filmbox.scaling,
        axis_forward=filmbox.forward, axis_up=filmbox.upward,
        use_custom_normals=filmbox.use_custom_normals,
        use_image_search=filmbox.use_image_search,
        use_alpha_decals=filmbox.use_alpha_decals, decal_offset=filmbox.decal_offset,
        anim_offset=filmbox.anim_offset,
        ignore_leaf_bones=filmbox.ignore_leaf_bones, force_connect_children=filmbox.force_connect_children,
        automatic_bone_orientation=filmbox.automatic_bone_orientation,
        primary_bone_axis=filmbox.primary, secondary_bone_axis=filmbox.secondary,
        use_prepost_rot=filmbox.use_prepost_rot,
        )

def get_matched_armature(armature, armatures):
    # an armature already known with the exact same named bones at the exact same rests, ie. the same skeleton...
    names = {b.name for b in armature.data.bones}
    for existing in armatures:
        # if all the bone names are the same between the armature and the candidate...
        if names == {b.name for b in existing.data.bones}:
            # and if the hierarchy is the same...
            bones = existing.data.bones
            if all((b.parent.name if b.parent else None) == (bones[b.name].parent.name if bones[b.name].parent else None) for b in armature.data.bones):
                # aaaand if the rest poses are the same...
                if all(utilities.functions.get_matrix_matched(armature.data.bones[n].matrix_local, bones[n].matrix_local) for n in names):
                    # we return the matched armature...
                    return existing
    # if there is no match return nothing...
    return None

def get_imported_assets(context, filepaths, settings):
    statics, skeletons, removals = [], {}, []
    for filepath in filepaths:
        # get existing actions and import the fbx file...
        actions = {a for a in bpy.data.actions}
        import_file_fbx(filepath, settings.filmbox)
        filename = os.path.splitext(os.path.basename(filepath))[0]
        # separate the armatures and meshes... (they become selected once imported)...
        objects = bpy.context.selected_objects
        armatures = [o for o in objects if o.type == 'ARMATURE']
        meshes = [o for o in objects if o.type == 'MESH']
        # fbx import creates fresh numbered-suffix materials/images whenever a name collides with something already in the file, so switch onto whatever already exists instead of leaving duplicates behind, same as the template loader...
        templates.functions.set_deduplicated_assets(meshes)
        statics = statics + [m for m in meshes if not m.find_armature()]
        removals = removals + [o for o in objects if o.type == 'EMPTY']
        # iterate through armatures to build the import armature dictionary...
        for armature in armatures:
            # see if we cna get an already imported armature and rename actions to their file name...
            existing = get_matched_armature(armature, skeletons.keys())
            for action in [a for a in bpy.data.actions if a not in actions]:
                action.name = filename
                utilities.functions.set_stashed_action(existing or armature, action)
            # if the armature already exists append any new skeletal meshes and actions... (and append it for removal)
            if existing:
                skeletons[existing]['skeletals'] = skeletons[existing]['skeletals'] + [m for m in meshes if m.find_armature() == armature]
                skeletons[existing]['actions'] = skeletons[existing]['actions'] + [a for a in bpy.data.actions if a not in actions]
                removals.append(armature)
            else:
                # if doesn't already exist then create its entry with its meshes and actions and name it after the file...
                skeletons[armature] = {}
                skeletons[armature]['skeletals'] = [m for m in meshes if m.find_armature() == armature]
                skeletons[armature]['actions'] = [a for a in bpy.data.actions if a not in actions]
                skeletons[armature]['name'] = armature.name
                armature.name = filename + "_Skeleton"
                armature.data.name = filename + "_Skeleton"
    return statics, skeletons, removals

def set_imported_assets(context, settings, statics, skeletons, removals, debug=False):
    scaling = bpy.context.scene.unit_settings.scale_length / 0.01
    # we need to select everything we imported...
    bpy.ops.object.select_all(action='DESELECT')
    for static in statics:
        static.select_set(True)
    for skeleton, assets in skeletons.items():
        skeleton.select_set(True)
        for skeletal in assets['skeletals']:
            skeletal.select_set(True)
            # ensure armature modifiers target the skeleton...
            for mod in skeletal.modifiers:
                if mod.type == 'ARMATURE':
                    mod.object = skeleton
        # skeletons may need root bones added...
        bpy.context.view_layer.objects.active = skeleton
        bpy.ops.object.mode_set(mode='EDIT')
        root_eb = skeleton.data.edit_bones.get(assets['name'])
        if root_eb is None:
            orphans = [b for b in skeleton.data.edit_bones if b.parent is None]
            root_eb = skeleton.data.edit_bones.new(assets['name'])
            length = settings.orientation.max_length * scaling
            length = length if length > 0.0 else 0.1
            head, tail, roll = (0.0, 0.0, 0.0), (0.0, length, 0.0), 0.0
            root_eb.head, root_eb.tail, root_eb.roll = head, tail, roll
            for orphan in orphans:
                orphan.parent = root_eb
        bpy.ops.object.mode_set(mode='OBJECT')
        # actions may need root motion rewritten and scaled from the object level transforms onto the root bone...
        channels = {'location', 'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle', 'scale'}
        for action in assets['actions']:
            for fc in utilities.functions.get_action_fcurves(action):
                if fc.data_path in channels:
                    fc.data_path = 'pose.bones["' + assets['name'] + '"].' + fc.data_path
                    for key in fc.keyframe_points:
                        key.co.y *= scaling
                        key.handle_left.y *= scaling
                        key.handle_right.y *= scaling
                    fc.update()
            # decimating before retargeting means theres less for retargeting/applying to process, thinning has no such preference so it just defaults to here whenever decimate itself isn't running after instead...
            decimate = settings.cleaning.decimate == 'PRE'
            if decimate or (settings.cleaning.decimate != 'POST' and settings.cleaning.spacing > 0):
                retargeting.functions.set_cleaned_action(context, skeleton, action, decimate, settings.cleaning.margin, settings.cleaning.spacing)
    # clear all transforms and parenting...
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    target = bpy.data.objects.get(settings.retargeting.target)
    # we need to apply transforms to everything...
    for skeleton, assets in skeletons.items():
        utilities.functions.set_armature_transforms(skeleton, assets['skeletals'], assets['actions'], True, True, True)
        # stash all the actions on the armature...
        for action in assets['actions']:
            utilities.functions.set_stashed_action(skeleton, action)
        # unless retargeting says otherwise below, the skeletons own actions are the final ones to decimate after...
        finals = [(skeleton, action) for action in assets['actions']]
        # if we have a target...
        if target:
            # get its armatures... (if they exist)
            rig, orient, origin = utilities.functions.get_armature_hierarchy(target)
            # if we are retargeting skeletal meshes... (and we have them)
            if settings.retargeting.meshes and assets['skeletals']:
                # retarget the meshes with all associated actions to the target...
                result = retargeting.functions.set_retargeted_meshes(skeleton, origin, use_actions=True)
                # if we should create oriented armatures...
                if settings.orientation.orient:
                    # orient them and retarget all the actions to the oriented armature... (retargeting twice seems silly but it's fast without rigging)
                    length = settings.orientation.max_length if settings.orientation.max_length > 0.0 else None
                    original_shape, oriented_shape = settings.orientation.original_shape, settings.orientation.oriented_shape
                    oriented, original = orientation.functions.add_oriented_armature(result, length, original_shape, oriented_shape, use_actions=False)
                    result = original
                # the retargeted actions replaced the originals under the same names, read back whatever actually landed on the result...
                _, retargeted = utilities.functions.get_copied_nla(result)
                finals = [(result, action) for action in retargeted if action]
            # else if we are retargeting actions and there are no skeletal meshes... (this is an animation only skeleton)
            elif settings.retargeting.actions and assets['actions'] and not assets['skeletals']:
                # retarget onto the rig if there is one, else the plain target armature...
                bpy.ops.object.mode_set(mode='OBJECT')
                destination = rig if rig else origin
                retargeted = []
                for action in assets['actions']:
                    retarget = retargeting.functions.set_retargeted_action(context, action, skeleton, target, step_height=settings.retargeting.step_height)
                    name = action.name
                    bpy.data.actions.remove(action, do_unlink=True)
                    if retarget:
                        retarget.name = name
                        utilities.functions.set_stashed_action(destination, retarget)
                        retargeted.append(retarget)
                # unlike the meshes branch above, skeleton here was only ever a source to read the action off of, so it needs the same removals cleanup instead of being left behind in the scene...
                removals.append(skeleton)
                finals = [(destination, action) for action in retargeted]
        # and if we are decimating (with thinning bundled alongside it) after retargeting, do it last, on wherever the actions actually ended up...
        if settings.cleaning.decimate == 'POST':
            for armature, action in finals:
                retargeting.functions.set_cleaned_action(context, armature, action, True, settings.cleaning.margin, settings.cleaning.spacing)
    # if we aren't debugging...
    if not debug:
        # clean everything we don't need up...
        for obj in removals:
            data = obj.data if obj.type == 'ARMATURE' else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if data:
                bpy.data.armatures.remove(data)
