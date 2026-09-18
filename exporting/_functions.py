import bpy
import os
import re
import json
import subprocess

from .. import utilities

def get_safe_name(name):
    # replace non alphanumeric runs with underscores (safe export paths)...
    return re.sub(r'[^0-9a-zA-Z]+', '_', name).strip('_')

def get_mesh_armature(mesh):
    # if the mesh has a valid armature modifier...
    if any(m.type == 'ARMATURE' and m.object for m in mesh.modifiers):
        # return the first valid armature modifier object...
        for mod in mesh.modifiers:
            if mod.type == 'ARMATURE' and mod.object:
                return mod.object
    # else if the mesh has a valid armature parent and is attached to a valid bone within the parent armature...
    elif mesh.parent and mesh.parent.type == 'ARMATURE' and mesh.parent_type == 'BONE' and mesh.parent_bone in mesh.parent.data.bones:
        # return the meshes parent...
        return mesh.parent
    else:
        return None

def get_export_assets(only_selected=False):
    # limit candidates to selected objects or all objects...
    objects = bpy.context.selected_objects if only_selected else list(bpy.data.objects)
    # separate the armatures and meshes...
    armatures = [o for o in objects if o.type == 'ARMATURE']
    meshes = [o for o in objects if o.type == 'MESH']
    # iterate through meshes to pick up their armatures and flag statics...
    statics, targets = [], {}
    for mesh in meshes:
        armature = get_mesh_armature(mesh)
        if armature and armature not in armatures:
            armatures.append(armature)
        elif not armature:
            statics.append(mesh.name)
    # iterate through armatures to build the export targets dictionary...
    for armature in armatures:
        rig, oriented, original = utilities.functions.get_armature_hierarchy(armature)
        export = original if original else oriented
        if export not in targets:
            weighted, attached = utilities.functions.get_armature_meshes(armature, meshes)
            rig = rig if rig else oriented if oriented else original
            # detect all actions (apply the export method later)...
            actions = utilities.functions.get_armature_actions(rig, method='ALL')
            targets[export.name] = {'sockets' : [a.name for a in attached], 'skeletals' : [w.name for w in weighted], 'actions' : [a.name for a in actions]}
    return statics, targets

def export_file_fbx(filepath, settings, animation=False, nla_strips=False):
    # the export folder (a plain string field, not a real file-browser path) might not exist yet...
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # call the FBX exporter with fixed and variable settings...
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        # fixed settings...
        check_existing=False, use_selection=True, use_visible=True, use_active_collection=False,
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE', use_space_transform=True,
        bake_space_transform=False, use_mesh_modifiers=False, use_mesh_modifiers_render=False, add_leaf_bones=False,
        use_subsurf=False, use_custom_props=False, armature_nodetype='NULL', object_types={'ARMATURE', 'MESH'}, use_armature_deform_only=False,
        bake_anim_use_all_bones=True, bake_anim_use_nla_strips=nla_strips, bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
        path_mode='AUTO', embed_textures=False, batch_mode='OFF', use_batch_own_dir=False,
        # variable settings...
        global_scale=1.0, axis_forward=settings.forward, axis_up=settings.upward,
        mesh_smooth_type=settings.smoothing, colors_type=settings.colors, prioritize_active_color=settings.prioritize,
        use_mesh_edges=settings.edges, use_tspace=settings.tangents, use_triangles=settings.triangles,
        primary_bone_axis=settings.primary, secondary_bone_axis=settings.secondary,
        bake_anim=settings.animations if animation else False, bake_anim_step=settings.step, bake_anim_simplify_factor=settings.simplify,
        use_metadata=settings.use_metadata,
        )

def bake_armature_actions(armature, actions, group="Export"):
    # get the rigging armature if there is one and the actions to bake...
    rig, oriented, original = utilities.functions.get_armature_hierarchy(armature)
    rig = rig if rig else oriented if oriented else original
    # save current objects and mode...
    mode, selected, active = utilities.functions.get_current_objects(bpy.context)
    # if we have auto keying enabled, turn it off... (just incase)...
    auto = bpy.context.scene.tool_settings.use_keyframe_insert_auto
    bpy.context.scene.tool_settings.use_keyframe_insert_auto = False
    # ensure we are in object mode...
    bpy.ops.object.mode_set(mode='OBJECT')
    # deselect all objects and select only the armature to bake to...
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    # if the target doesn't have animation data, create it...
    if not armature.animation_data:
        armature.animation_data_create()
    # jump into pose mode...
    bpy.ops.object.mode_set(mode='POSE')
    # iterate through the actions...
    bakes = []
    for act in actions:
        # capture the original name...
        name = act.name
        # clear the animated armatures pose transforms...
        for pb in rig.pose.bones:
            pb.location, pb.scale, pb.rotation_euler = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]
            pb.rotation_quaternion, pb.rotation_axis_angle = [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]
        # make the action active on the animated armature... (and its matching slot)...
        rig.animation_data.action = act
        slot = utilities.functions.get_action_slot(act, rig)
        if slot:
            rig.animation_data.action_slot = slot
        # bake the action to the the target armature...
        bpy.ops.nla.bake(frame_start=int(round(act.frame_range[0], 0)), frame_end=int(round(act.frame_range[1], 0)),
            step=1, only_selected=False, visual_keying=True, clear_constraints=False, clear_parents=False,
            use_current_action=False, clean_curves=False, bake_types={'POSE'})
        # rename the original action directly to free its name (rig and armature may be the same)...
        act.name = "BAKED_" + name
        armature.animation_data.action.name = name
        # flag it with custom properties and add it to the return array...
        bake = armature.animation_data.action
        bake["Exchange Name"] = name
        bake["Exchange Type"] = group
        bakes.append(bake)
    # restore auto keying...
    bpy.context.scene.tool_settings.use_keyframe_insert_auto = auto
    # restore current objects and mode...
    utilities.functions.set_current_objects(mode, selected, active)
    # return all the baked actions...
    return bakes

def export_static_meshes(meshes, settings, directory):
    # iterate through the meshes...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for mesh in meshes:
        # selecting them and making them active...
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        # if we are batch exporting...
        if settings.meshes.batch:
            # get the file name and path... (with folder if any)...
            filename = get_safe_name(mesh.name) + ".fbx"
            filepath = os.path.join(directory, filename)
            if settings.meshes.folder:
                filepath = os.path.join(directory, os.path.join(settings.meshes.folder, filename))
            # and export the static mesh to it's own file...
            bpy.context.view_layer.objects.active = mesh
            export_file_fbx(filepath, settings.filmbox, animation=False)
            mesh.select_set(False)
    # if we are not batch exporting...
    if not settings.meshes.batch:
        # statics aren't tied to any one armature, so name the merged file after the blend itself...
        name = os.path.splitext(os.path.basename(bpy.data.filepath))[0] if bpy.data.filepath else "Static"
        filename = get_safe_name(name) + "_Meshes.fbx"
        filepath = os.path.join(directory, filename)
        if settings.meshes.folder:
            filepath = os.path.join(directory, os.path.join(settings.meshes.folder, filename))
        # and export all meshes to the same file...
        export_file_fbx(filepath, settings.filmbox, animation=False)

def export_skeletal_meshes(armature, meshes, settings, directory, name):
    # the armature must be renamed to "Armature" to stop an extra root bone...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    armature.select_set(True)
    existing = bpy.data.objects.get("Armature")
    if existing and existing != armature:
        existing.name = armature.name
    armature.name = "Armature"
    armature.data.pose_position = 'REST'
    # iterate through the meshes...
    for mesh in meshes:
        # selecting them and making them active...
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        # if we are batch exporting...
        if settings.meshes.batch:
            # get the file name and path... (with folder if any)...
            filename = get_safe_name(mesh.name) + ".fbx"
            filepath = os.path.join(directory, filename)
            if settings.meshes.folder:
                filepath = os.path.join(directory, os.path.join(settings.meshes.folder, filename))
            # and export the skeletal mesh to it's own file...
            bpy.context.view_layer.objects.active = mesh
            export_file_fbx(filepath, settings.filmbox, animation=False)
            mesh.select_set(False)
    # if we are not batch exporting...
    if not settings.meshes.batch:
        # get the file name and path... (with folder if any)...
        filename = get_safe_name(name) + "_Meshes.fbx"
        filepath = os.path.join(directory, filename)
        if settings.meshes.folder:
            filepath = os.path.join(directory, os.path.join(settings.meshes.folder, filename))
        # and export all meshes to the same file...
        export_file_fbx(filepath, settings.filmbox, animation=False)

def export_socket_meshes(meshes, settings, directory):
    # iterate through the meshes...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for mesh in meshes:
        # selecting them and making them active...
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        # socket meshes always batch export... (otherwise what's the point)...
        suffix = "_" + mesh.parent_bone
        mesh.parent = None
        mesh.location, mesh.scale, mesh.rotation_euler = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], [0.0, 0.0, 0.0]
        mesh.rotation_quaternion, mesh.rotation_axis_angle = [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]
        # get the file name and path... (with folder if any, unless it already ends with the bone name)...
        name = mesh.name + (suffix if settings.meshes.suffix and not mesh.name.endswith(suffix) else "")
        filename = get_safe_name(name) + ".fbx"
        filepath = os.path.join(directory, filename)
        if settings.meshes.folder:
            filepath = os.path.join(directory, os.path.join(settings.meshes.folder, filename))
        # and export the socket mesh to it's own file...
        export_file_fbx(filepath, settings.filmbox, animation=False)
        mesh.select_set(False)

def export_baked_actions(armature, actions, settings, directory, name):
    # ensure we are in object mode with nothing selected...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    # make sure only the export armature is selected...
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    # the armature must be renamed to "Armature" to stop an extra root bone...
    existing = bpy.data.objects.get("Armature")
    if existing and existing != armature:
        existing.name = armature.name
    armature.name = "Armature"
    # mute all of its constraints...
    for pb in armature.pose.bones:
        for con in pb.constraints:
            con.enabled = False
    armature.data.pose_position = 'POSE'
    bpy.context.view_layer.update()
    # batching writes one file per action, otherwise every action bakes into one files animation stacks instead...
    if settings.action.batch:
        for action in actions:
            armature.animation_data.action = action
            armature.animation_data.action_slot = action.slots[0]
            bpy.context.scene.frame_start = int(action.frame_range[0])
            bpy.context.scene.frame_end = int(action.frame_range[1])
            filename = get_safe_name(action["Exchange Name"]) + ".fbx"
            filepath = os.path.join(directory, filename)
            if settings.action.folder:
                filepath = os.path.join(directory, os.path.join(settings.action.folder, filename))
            export_file_fbx(filepath, settings.filmbox, animation=True)
    else:
        # mute existing tracks and add one per baked action (merged export)...
        existing_tracks = list(armature.animation_data.nla_tracks)
        muted = [track.mute for track in existing_tracks]
        for track in existing_tracks:
            track.mute = True
        tracks = []
        for action in actions:
            track = armature.animation_data.nla_tracks.new()
            track.name, track.mute = action["Exchange Name"], False
            track.strips.new(track.name, int(action.frame_range[0]), action)
            tracks.append(track)
        armature.animation_data.action = None
        filename = get_safe_name(name) + "_Actions.fbx"
        filepath = os.path.join(directory, filename)
        if settings.action.folder:
            filepath = os.path.join(directory, os.path.join(settings.action.folder, filename))
        export_file_fbx(filepath, settings.filmbox, animation=True, nla_strips=True)
        # remove our temporary tracks and restore whatever was already there...
        for track in tracks:
            armature.animation_data.nla_tracks.remove(track)
        for track, was_muted in zip(existing_tracks, muted):
            track.mute = was_muted
    # remove the scratch baked actions and restore each original ones name... (in case of multiple armatures)...
    for action in actions:
        original_name = action["Exchange Name"]
        bpy.data.actions.remove(action)
        original = bpy.data.actions.get("BAKED_" + original_name)
        original.name = original_name

def set_cleared_transforms(item, location, rotation, scale):
    if location:
        item.location = (0.0, 0.0, 0.0)
    if rotation:
        item.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        item.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        item.rotation_euler = (0.0, 0.0, 0.0)
    if scale:
        item.scale = (1.0, 1.0, 1.0)

# statics and targets cache static and skeletal meshes by armature...
def export_filmbox_assets(directory, settings, statics, targets):
    # get our scaling from the input scaling setting and the current unit scale into FBX units...
    scaling = settings.filmbox.scaling * (bpy.context.scene.unit_settings.scale_length / 0.01)
    bpy.context.scene.unit_settings.scale_length = 0.01
    bpy.context.scene.unit_settings.length_unit = 'CENTIMETERS'
    # linked library armatures/meshes can't be scaled or edited in place, so make everything we're about to touch local first...
    objects = {bpy.data.objects[n] for n in statics}
    for target, assets in targets.items():
        rig, oriented, original = utilities.functions.get_armature_hierarchy(bpy.data.objects[target])
        objects.update(a for a in (rig, oriented, original) if a)
        objects.update(bpy.data.objects[n] for n in assets['sockets'] + assets['skeletals'])
    utilities.functions.set_objects_localized(objects)
    # run the cleanup settings first as it could reduce processing anything that might be removed...
    if settings.clean.prefix and settings.meshes.export:
        meshes = [bpy.data.objects[n] for n in statics]
        for _, assets in targets.items():
            sockets = [bpy.data.objects[n] for n in assets['sockets']]
            skeletals = [bpy.data.objects[n] for n in assets['skeletals']]
            meshes = meshes + sockets + skeletals
        prefix, shapes = settings.clean.prefix, settings.clean.shapes
        groups, materials = settings.clean.groups, settings.clean.materials
        utilities.functions.set_cleaned_meshes(meshes, prefix, shapes, groups, materials)
    # if we have static meshes...
    if statics and settings.meshes.export and settings.meshes.static:
        # make sure they aren't hidden...
        meshes = [bpy.data.objects[n] for n in statics]
        utilities.functions.set_objects_unhidden(meshes)
        # statics always get their transforms fully cleared, same as skeletal/socket meshes...
        for mesh in meshes:
            set_cleared_transforms(mesh, True, True, True)
            # before we apply fbx scaling...
            mesh.location *= scaling
            mesh.scale *= scaling
        # then we apply everything we want to apply to the meshes...
        utilities.functions.set_applied_meshes(meshes, original=False, modifiers=settings.meshes.modifiers, parent=False,
            location=False, rotation=False, scale=False)
        # and yeet them out to fbx...
        export_static_meshes(meshes, settings, directory)
    # transform armatures and their assets...
    for target, assets in targets.items():
        # get the armature and make sure none of it's siblings are hidden... (if any)...
        armature = bpy.data.objects[target]
        rigging_armature, oriented_armature, original_armature = utilities.functions.get_armature_hierarchy(armature)
        rigging_armature = rigging_armature if rigging_armature else oriented_armature if oriented_armature else armature
        utilities.functions.set_objects_unhidden([a for a in (oriented_armature, original_armature, rigging_armature) if a])
        # prefer the oriented plain name... (the target is an original with no oriented counterpart)...
        name = oriented_armature.name if oriented_armature else target
        # export socket meshes... (if any)...
        if assets['sockets'] and settings.meshes.export and settings.meshes.socket:
            meshes = [bpy.data.objects[n] for n in assets['sockets']]
            utilities.functions.set_objects_unhidden(meshes)
            # sockets always get their scale baked, since they're about to be detached and zeroed...
            for mesh in meshes:
                # we never want to apply any transform channels to socket meshes...
                set_cleared_transforms(mesh, True, True, True)
                # then apply scaling...
                mesh.scale *= scaling
            # they might only need their modifiers applied...
            utilities.functions.set_applied_meshes(meshes, original=False, modifiers=settings.meshes.modifiers, parent=False,
                location=False, rotation=False, scale=True)
            export_socket_meshes(meshes, settings, directory)
        # get and prepare skeletal meshes... (if any)...
        meshes = []
        if assets['skeletals'] and settings.meshes.export and settings.meshes.skeletal:
            # skeletal meshes should follow the armature via the set_armature_transforms function...
            meshes = [bpy.data.objects[n] for n in assets['skeletals']]
            utilities.functions.set_objects_unhidden(meshes)
            # they just might need their modifiers applied...
            utilities.functions.set_applied_meshes(meshes, original=False, modifiers=settings.meshes.modifiers, parent=False,
                location=False, rotation=False, scale=True)
        # prepare armature actions, respecting the chosen export method (active/stashed/all)...
        actions = utilities.functions.get_armature_actions(rigging_armature, method=settings.action.method) if assets['actions'] and settings.action.export else []
        baked = bake_armature_actions(armature, actions, group="Export") if actions else []
        # inject the fbx scaling factor into the armature before baking it, its meshes and its actions down...
        armature.scale *= scaling
        utilities.functions.set_armature_transforms(armature, meshes, baked, False, False, True)
        # and export the skeletal meshes along with their armature...
        if meshes and settings.meshes.export and settings.meshes.skeletal:
            export_skeletal_meshes(armature, meshes, settings, directory, name)
         # and export the baked actions along with their armature...
        if actions:
            export_baked_actions(armature, baked, settings, directory, name)

def export_filmbox_background(directory, settings, statics, targets):
    # runs the export in copy of the current file in a background Blender process...
    pid = str(os.getpid())
    blend_path = os.path.join(bpy.app.tempdir, "mmt_export_" + pid + ".blend")
    settings_path = os.path.join(bpy.app.tempdir, "mmt_export_" + pid + ".json")
    script_path = os.path.join(bpy.app.tempdir, "mmt_export_" + pid + ".py")
    try:
        # save flattened settings and asset names for the background export...
        payload = {'settings': utilities.functions.get_serialized_settings(settings), 'statics': statics, 'targets': targets}
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f)
        # save a disposable full copy of the current file... (doesn't touch the live session at all)...
        bpy.ops.wm.save_as_mainfile(filepath=blend_path, copy=True, check_existing=False)
        # write the background script that rebuilds the settings and runs the real export... (import path built from our own root package, since an extension install's real module name is "bl_ext.<repo>.mr_mannequins_tools", not the bare legacy name)...
        root = __package__.rsplit('.', 1)[0]
        script = (
            "import bpy, sys, json\n"
            "args = sys.argv[sys.argv.index('--') + 1:]\n"
            "directory, settings_path = args[0], args[1]\n"
            "from " + root + ".exporting import _functions as functions\n"
            "from " + root + ".exporting import _properties as properties\n"
            "from " + root + ".utilities import _functions as utility_functions\n"
            "with open(settings_path, 'r', encoding='utf-8') as f:\n"
            "    payload = json.load(f)\n"
            "bpy.types.Scene.mmt_export_background = bpy.props.PointerProperty(type=properties.MMT_PG_Export)\n"
            "settings = bpy.context.scene.mmt_export_background\n"
            "utility_functions.set_deserialized_settings(settings, payload['settings'])\n"
            "functions.export_filmbox_assets(directory, settings, payload['statics'], payload['targets'])\n"
            )
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script)
        # run the export in an isolated background instance...
        result = subprocess.run(
            [bpy.app.binary_path, "--background", blend_path, "--python-exit-code", "1", "--python", script_path, "--", directory, settings_path],
            capture_output=True, text=True)
        if result.returncode != 0:
            return False, "background export failed:\n" + result.stderr
        return True, None
    except (OSError, subprocess.SubprocessError) as error:
        return False, "background export failed (" + str(error) + ")"
    finally:
        for path in (blend_path, settings_path, script_path):
            if os.path.exists(path):
                os.remove(path)


