import bpy
import os

from mathutils import Matrix

from .. import utilities
from .. import retargeting
from .. import orientation
from .. import templates

def get_root_offset(armature):
    # an animation only exports root can sit at a different height than a skinned one... (so rest poses get compared relative to this)
    root = next((b for b in armature.data.bones if not b.parent), None)
    return root.matrix_local.translation if root else None

def get_bone_matched(a, offset_a, b, offset_b):
    # root-relative comparison still carries some FBX export quantization noise (observed up to ~0.002 on deep finger chains), so this needs a looser tolerance than the default...
    a, b = a.copy(), b.copy()
    a.translation -= offset_a
    b.translation -= offset_b
    return utilities.functions.get_matrix_matched(a, b, tolerance=0.005)

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
                # aaaand if the rest poses are the same, relative to each armatures own root...
                offset, existing_offset = get_root_offset(armature), get_root_offset(existing)
                if offset is not None and existing_offset is not None:
                    if all(get_bone_matched(armature.data.bones[n].matrix_local, offset, bones[n].matrix_local, existing_offset) for n in names):
                        # we return the matched armature...
                        return existing
    # if there is no match return nothing...
    return None

def get_available_name(base, taken):
    # the next name free in both namespaces, blender suffixes object and mesh names independently... (matches its .001 convention)
    candidate, index = base, 1
    while candidate in taken:
        candidate = base + ".%03d" % index
        index += 1
    return candidate

def get_leaf_bones(armature, meshes):
    # bones that actually deform something, ie. some mesh has a vertex group for them...
    deformers = {name for mesh in meshes for name in mesh.vertex_groups.keys()}
    leaves = []
    for eb in armature.data.edit_bones:
        is_childless = not eb.children
        parent_deforms = eb.parent and eb.parent.name in deformers
        self_deforms = eb.name in deformers
        if is_childless and parent_deforms and not self_deforms:
            leaves.append(eb)
    return leaves

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
        # rename imported meshes after their file, each candidate reserved against object and mesh names combined... (sorted so selection order can't pick who stays unsuffixed)
        mesh_objects, mesh_data = set(meshes), {m.data for m in meshes}
        taken = {o.name for o in bpy.data.objects if o not in mesh_objects} | {d.name for d in bpy.data.meshes if d not in mesh_data}
        for mesh in sorted(meshes, key=lambda m: m.name):
            name = get_available_name(filename, taken)
            mesh.name = name
            mesh.data.name = name
            taken.add(name)
        # fbx import makes suffixed duplicates when a name collides, so switch onto what already exists... (same as the template loader)
        templates.functions.set_deduplicated_assets(meshes)
        statics = statics + [m for m in meshes if not m.find_armature()]
        removals = removals + [o for o in objects if o.type == 'EMPTY']
        # iterate through armatures to build the import armature dictionary...
        for armature in armatures:
            # see if we cna get an already imported armature and rename actions to their file name...
            existing = get_matched_armature(armature, skeletons.keys())
            for action in [a for a in bpy.data.actions if a not in actions]:
                action.name = filename
            # if the armature already exists append any new skeletal meshes and actions... (and append it for removal)
            if existing:
                bound_skeletals = [m for m in meshes if m.find_armature() == armature]
                # the first mesh-bearing source keeps naming authority - once the survivor has skeletal meshes, later matches (mesh or animation-only) can add to it but never rename it or provoke .001 churn...
                had_no_skeletals = not skeletons[existing]['skeletals']
                skeletons[existing]['skeletals'] = skeletons[existing]['skeletals'] + bound_skeletals
                skeletons[existing]['actions'] = skeletons[existing]['actions'] + [a for a in bpy.data.actions if a not in actions]
                # the existing armature had no skeletals until now, so it takes the filename and the import gets removed...
                if bound_skeletals and had_no_skeletals:
                    existing.name = filename + "_Skeleton"
                    existing.data.name = filename + "_Skeleton"
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

def set_imported_assets(context, settings, statics, skeletons, removals, target, debug=False):
    scaling = bpy.context.scene.unit_settings.scale_length / 0.01
    # we need to select everything we imported...
    bpy.ops.object.select_all(action='DESELECT')
    for static in statics:
        static.select_set(True)
    for skeleton, assets in skeletons.items():
        skeleton.select_set(True)
        # bones should show through the meshes they came in with...
        skeleton.show_in_front = True
       
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
        # no root bone yet, so add one and parent the orphans to it...
        if root_eb is None:
            orphans = [b for b in skeleton.data.edit_bones if b.parent is None]
            root_eb = skeleton.data.edit_bones.new(assets['name'])
            length = settings.orientation.max_length * scaling
            length = length if length > 0.0 else 0.1
            head, tail, roll = (0.0, 0.0, 0.0), (0.0, length, 0.0), 0.0
            root_eb.head, root_eb.tail, root_eb.roll = head, tail, roll
            for orphan in orphans:
                orphan.parent = root_eb
        # if we have skeletal meshes and want to remove leaf bones...
        if assets['skeletals'] and settings.cleaning.leaf_bones:
            # we can more accurately remove leaf bones...
            leaves = get_leaf_bones(skeleton, assets['skeletals'])
            for eb in leaves:
                skeleton.data.edit_bones.remove(eb)
        bpy.ops.object.mode_set(mode='OBJECT')
        # actions may need root motion rewritten and scaled from the object level transforms onto the root bone...
        channels = {'location', 'rotation_euler', 'rotation_quaternion', 'rotation_axis_angle', 'scale'}
        for action in assets['actions']:
            for fc in utilities.functions.get_action_fcurves(action):
                # root channels move onto the new root bone, with their values scaled to match...
                if fc.data_path in channels:
                    fc.data_path = 'pose.bones["' + assets['name'] + '"].' + fc.data_path
                    for key in fc.keyframe_points:
                        key.co.y *= scaling
                        key.handle_left.y *= scaling
                        key.handle_right.y *= scaling
                    fc.update()
            # decimate before retargeting so there's less to process... (thinning has no preference, so it runs here when decimate isn't running after)
            decimate = settings.cleaning.decimate == 'BEFORE'
            if decimate or (settings.cleaning.decimate != 'AFTER' and settings.cleaning.spacing > 0):
                retargeting.functions.set_cleaned_action(context, skeleton, action, decimate, settings.cleaning.margin, settings.cleaning.spacing)
    # clear all transforms and parenting...
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
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
                # pose the fresh import into the targets own bone directions first, then bake that pose in and carry the stashed actions through it...
                retargeting.functions.set_armature_posed(skeleton, origin)
                result = retargeting.functions.set_retargeted_meshes(skeleton, origin)
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
                # retarget onto the armature highest in the hierarchy...
                bpy.ops.object.mode_set(mode='OBJECT')
                destination = rig if rig else orient if orient else origin
                # snapshot before the loop removes source actions... (so the receiver matches this skeletons active and stashed state)
                active_source_action = skeleton.animation_data.action if skeleton.animation_data else None
                retargeted = []
                active_retarget = None
                for action in assets['actions']:
                    retarget = retargeting.functions.set_retargeted_action(context, action, skeleton, target, step_height=settings.retargeting.step_height)
                    was_active = action == active_source_action
                    name = action.name
                    bpy.data.actions.remove(action, do_unlink=True)
                    # stash the retargeted action under its final name...
                    if retarget:
                        retarget.name = name
                        utilities.functions.set_stashed_action(destination, retarget)
                        retargeted.append(retarget)
                        if was_active:
                            active_retarget = retarget
                # unlike the meshes branch above, skeleton here was only ever a source to read the action off of, so it needs the same removals cleanup instead of being left behind in the scene...
                removals.append(skeleton)
                finals = [(destination, action) for action in retargeted]
                # preserve the imported skeletons own active-vs-stashed state instead of always promoting the last result, leaving the slot to blender...
                if active_retarget:
                    destination.animation_data.action = active_retarget
                elif destination.animation_data:
                    # no active result, so don't leave the old action assigned...
                    destination.animation_data.action = None
                    if retargeted:
                        # no retargeted result stays active - clear the pose too, or the receiver visually stays on whatever frame was last evaluated during retargeting...
                        retargeting.functions.set_pose_reset(destination)
        # and if we are decimating (with thinning bundled alongside it) after retargeting, do it last, on wherever the actions actually ended up...
        if settings.cleaning.decimate == 'AFTER':
            for armature, action in finals:
                retargeting.functions.set_cleaned_action(context, armature, action, True, settings.cleaning.margin, settings.cleaning.spacing)
        # a mesh bearing character finishes at rest, clearing the action alone leaves bones frozen... (animation only skeletons keep their own state from above)
        if assets['skeletals']:
            for final_armature in {armature for armature, action in finals}:
                if final_armature.animation_data:
                    final_armature.animation_data.action = None
                for pose_bone in final_armature.pose.bones:
                    pose_bone.matrix_basis = Matrix.Identity(4)
            context.view_layer.update()
    # if we aren't debugging...
    if not debug:
        # clean everything we don't need up...
        for obj in removals:
            data = obj.data if obj.type == 'ARMATURE' else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if data:
                bpy.data.armatures.remove(data)
