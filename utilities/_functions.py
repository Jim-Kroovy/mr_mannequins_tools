import bpy
import re
import os
import importlib.util

from mathutils import Vector, Matrix
from bpy_extras import anim_utils

from .. import shaping

def get_addon_preferences(context):
    # this files own package is always "<root>.utilities" - stripping the trailing segment gives the addons real registered name, whether installed as a legacy addon ("mr_mannequins_tools") or as an extension ("bl_ext.<repo>.mr_mannequins_tools")...
    root = __package__.rsplit('.', 1)[0]
    return context.preferences.addons[root].preferences

def get_bone_order(armature, names):
    ordered = []
    def walk(bones):
        for bone in bones:
            if bone.name in names:
                ordered.append(bone.name)
            walk(bone.children)
    walk([bone for bone in armature.data.bones if bone.parent is None])
    return ordered

def get_edit_direction(from_eb, to_ebs):
    center = Vector((0.0, 0.0, 0.0))
    for to_eb in to_ebs:
        center += to_eb.head
    center /= len(to_ebs)
    direction = center - from_eb.head
    return direction.normalized() if direction.length > 1e-5 else None

def get_primary_child(children):
    if len(children) == 1:
        return children[0]
    siblings = {child.name for child in children}
    unpaired = []
    for child in children:
        mirror_name, _ = get_mirrored_name(child.name)
        if not mirror_name or mirror_name not in siblings:
            unpaired.append(child)
    return unpaired[0] if len(unpaired) == 1 else None

def get_weighted_names(meshes):
    weighted = set()
    for mesh in meshes:
        weighted.update(group.name for group in mesh.vertex_groups)
    return weighted

def get_coincident_clusters(armature, threshold=0.0001):
    positions = {pose_bone.name: pose_bone.bone.head_local for pose_bone in armature.pose.bones}
    names, used, clusters = list(positions), set(), []
    for index, name in enumerate(names):
        if name in used:
            continue
        cluster = [name]
        for other in names[index + 1:]:
            if other not in used and (positions[name] - positions[other]).length <= threshold:
                cluster.append(other)
                used.add(other)
        if len(cluster) > 1:
            clusters.append(cluster)
        used.add(name)
    return clusters

def get_matrix_matched(a, b, tolerance=0.0001):
    return all(abs(a[row][column] - b[row][column]) < tolerance for row in range(4) for column in range(4))

def get_unit_scaling(context, inverse=False):
    scale = context.scene.unit_settings.scale_length
    if inverse:
        if abs(round(scale, 3)) > 0.0:
            return 1.0 / scale
        else:
            return 1.0
    return scale

def get_current_objects(context):
    # if there is no object then mode must be object...
    mode = context.object.mode if context.object else 'OBJECT'
    # selected objects is also empty if there is no contextual object...
    selected = [o for o in bpy.context.selected_objects] if bpy.context.object else []
    # active object can be nothing so just get it...
    active = context.view_layer.objects.active
    return mode, selected, active

def set_current_objects(mode, selected, active, deselect=True):
    # if we have objects to reselect or an active to set...
    if selected or active:
        # reselecting requires object mode...
        bpy.ops.object.mode_set(mode='OBJECT')
        # usually deselection is also required...
        if deselect:
            bpy.ops.object.select_all(action='DESELECT')
        # select the selected objects... (as long as they still exist)...
        for ob in selected:
            if ob:
                ob.select_set(True)
        # if we have an active object set it...
        if active:
            bpy.context.view_layer.objects.active = active
    # then optionally return our mode to whatever it was...
    if mode:
        bpy.ops.object.mode_set(mode=mode)

def get_mirrored_name(name):
    # split on seperators... (while keeping them)...
    mirror, splits, side = "", re.split('([_ .])', name), ''
    # get dictionaries of switched side affices...
    lefts = {"L" : "R", "l" : "r", "LEFT" : "RIGHT", "Left" : "Right", "left" : "right"}
    rights = {"R" : "L", "r" : "l", "RIGHT" : "LEFT", "Right" : "Left", "right" : "left"}
    # then iterate through the splits...
    for split in splits:
        # putting the name back together with swapped side affices...
        mirror = mirror + (lefts[split] if split in lefts else rights[split] if split in rights else split)
        # and setting the side of the new name... (overriding current side if multiple are found)...
        if split in rights or split in lefts:
            side = 'LEFT' if split in rights else 'RIGHT' if split in lefts else ''
    # and return the name and side... (if it's not equal to the name that came in)...
    return mirror if mirror != name else "", side if mirror != name else ''

def get_mapped_range(value, start_min, start_max, end_min, end_max, clamp=False, default=1.0):
    # avoid division by zero if start range is collapsed...
    if start_max == start_min:
        # and just interpolate from end_min to end_max using a default alpha...
        result = end_min + ((end_max - end_min) * default)
    else:
        result = end_min + ((value - start_min) / (start_max - start_min)) * (end_max - end_min)
    # if we want to clamp the result...
    if clamp:
        # clamp it to the end min/max...
        return max(min(result, max(end_min, end_max)), min(end_min, end_max))
    else:
        return result

def get_distance_direction(start, end):
    # get our delta between the two vectors...
    delta = end - start
    # if it's 0.0 we return empty distance and direction...
    if delta.length == 0.0:
        return 0.0, Vector((0, 0, 0))
    else:
        # else return delta vector length and normalized...
        return delta.length, delta.normalized()

def get_line_distance(start, origin, direction):
    # shift to axis central space...
    local = start - origin
    # project onto direction...
    length = local.dot(direction)
    projection = direction * length
    # subtract projection to flatten...
    flattened = local - projection
    # we might as well get the closest point...
    point = origin + projection
    # how far it is along the line from the origin... (either direction from it)...
    delta = point - origin
    # and make distance not absolute...
    distance = delta.length * ((length > 0) * 2 - 1)
    return flattened.length, point, distance

def get_closest_vector(start, ends):
    # simply get the closest vector to start from an array of ends...
    closest, floor = None, float('inf')
    for end in ends:
        distance, _ = get_distance_direction(start, end)
        if abs(distance) < floor:
            closest, floor = end, distance
    return closest

def get_closest_axis(start, axes):
    # simply get the closest direction to start from an array of ends...
    closest, floor, result = None, float('inf'), 'X'
    for axis, direction in axes.items():
        distance, _ = get_distance_direction(start, direction)
        if abs(distance) < floor:
            closest, floor, result = direction, distance, axis
    return result, closest

def get_ordinal_index(index):
    # if you have a million bones in a chain you deserve the errors...
    units = ["Zero","One","Two","Three","Four","Five","Six","Seven","Eight","Nine"]
    teens = ["Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen","Seventeen","Eighteen","Nineteen"]
    tens = ["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"]
    # numder strings...
    ordinal_units = ["Zeroth","First","Second","Third","Fourth","Fifth","Sixth","Seventh","Eighth","Ninth"]
    ordinal_teens = ["Tenth","Eleventh","Twelfth","Thirteenth","Fourteenth","Fifteenth","Sixteenth","Seventeenth","Eighteenth","Nineteenth"]
    ordinal_tens = ["","","Twentieth","Thirtieth","Fortieth","Fiftieth","Sixtieth","Seventieth","Eightieth","Ninetieth"]

    def cardinal_under_100(index):
        if index < 10: return units[index]
        if index < 20: return teens[index - 10]
        return tens[index // 10] if index % 10 == 0 else f"{tens[index // 10]} {units[index % 10]}"

    def ordinal_under_100(index):
        if index < 10: return ordinal_units[index]
        if index < 20: return ordinal_teens[index - 10]
        return ordinal_tens[index // 10] if index % 10 == 0 else f"{tens[index // 10]} {ordinal_units[index % 10]}"

    def cardinal_under_1000(index):
        if index < 100: return cardinal_under_100(index)
        return f"{units[index // 100]} Hundred" if index % 100 == 0 else f"{units[index // 100]} Hundred {cardinal_under_100(index % 100)}"

    def ordinal_under_1000(index):
        if index < 100: return ordinal_under_100(index)
        return f"{units[index // 100]} Hundredth" if index % 100 == 0 else f"{units[index // 100]} Hundred {ordinal_under_100(index % 100)}"

    if index < 1000: return ordinal_under_1000(index)

    thousands, remainder = divmod(index, 1000)
    return f"{cardinal_under_1000(thousands)} Thousandth" if remainder == 0 else f"{cardinal_under_1000(thousands)} Thousand {ordinal_under_1000(remainder)}"

def get_letter_index(index):
    # spreadsheet column style - a, b, ... z, aa, ab, ... az, ba, ... - short, and never runs out regardless of how many...
    letters, index = "", index + 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(97 + remainder) + letters
    return letters

def get_hidden_objects(objects):
    # objects that select_set() would silently fail to select... (hidden, or excluded from the view layer)...
    return [o for o in objects if o and not o.visible_get()]

def set_objects_unhidden(selection):
    view = bpy.context.view_layer
    for obj in selection:
        obj.hide_set(False)
        obj.hide_viewport = False
        for coll in obj.users_collection:
            coll.hide_viewport = False
            # layer collections have no name-based lookup...
            stack, layer = [view.layer_collection], None
            while stack:
                current = stack.pop()
                if current.collection == coll:
                    layer = current
                    break
                stack.extend(current.children)
            if layer:
                layer.hide_viewport = False
                layer.exclude = False

def set_objects_localized(objects):
    # library-linked objects/data are read-only, so scaling or otherwise editing them for export needs making them local first...
    for obj in objects:
        if obj.library is not None:
            obj.make_local()
        if obj.data and obj.data.library is not None:
            obj.data.make_local()

def set_mesh_transforms(mesh, location, rotation, scale, matrix=None):
    # save children's world matrices... (if any)...
    children = {c : c.matrix_world.copy() for c in mesh.children}
    # an override matrix lets a caller bake another transform instead of its own...
    if matrix is None:
        # decompose the meshes basis matrix...
        loc, rot, sca = mesh.matrix_basis.decompose()
        # recompose it with only the channels we want applied...
        t = Matrix.Translation(loc) if not location else Matrix.Identity(4)
        r = rot.to_matrix().to_4x4() if not rotation else Matrix.Identity(4)
        s = Matrix.Diagonal(Vector((*sca, 1.0))) if not scale else Matrix.Identity(4)
        apply_matrix = (t @ r @ s).inverted() @ mesh.matrix_basis
    else:
        apply_matrix = matrix
    # update all the vertices and shape key data in a single pass...
    shapes = mesh.data.shape_keys.key_blocks if mesh.data.shape_keys else []
    for v in mesh.data.vertices:
        v.co = apply_matrix @ v.co
        for shape in shapes:
            shape.data[v.index].co = apply_matrix @ shape.data[v.index].co
    # clear the transform channels we applied...
    if location:
        mesh.location = (0.0, 0.0, 0.0)
    if rotation:
        # always clear all three rotation modes...
        mesh.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        mesh.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        mesh.rotation_euler = (0.0, 0.0, 0.0)
    if scale:
        mesh.scale = (1.0, 1.0, 1.0)
    # update the view layer before restoring children matrices...
    bpy.context.view_layer.update()
    for child, world_matrix in children.items():
        child.matrix_world = world_matrix

def set_armature_transforms(armature, meshes, actions, location, rotation, scale):
    # save children's world matrices... (if any)...
    children = {c : c.matrix_world.copy() for c in armature.children}
    # decompose the armatures basis matrix...
    loc, rot, sca = armature.matrix_basis.decompose()
    # recompose it with only the channels we want applied...
    t = Matrix.Translation(loc) if not location else Matrix.Identity(4)
    r = rot.to_matrix().to_4x4() if not rotation else Matrix.Identity(4)
    s = Matrix.Diagonal(Vector((*sca, 1.0))) if not scale else Matrix.Identity(4)
    apply_matrix = (t @ r @ s).inverted() @ armature.matrix_basis
    # bake scale, rotation and location separately (only rotation should recalculate roll)...
    bake_loc, bake_rot, bake_sca = apply_matrix.decompose()
    bake_scale_matrix = Matrix.Diagonal((*bake_sca, 1.0))
    bake_rotation_matrix = bake_rot.to_matrix().to_4x4()
    bake_location_matrix = Matrix.Translation(bake_loc)
    # jump into edit mode to bake the matrix into every bones rest transform...
    mode, selected, active = get_current_objects(bpy.context)
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode='EDIT')
    for bone in armature.data.edit_bones:
        # applied in the same order they compose in, scale first, then rotation, then location...
        if scale:
            bone.transform(bake_scale_matrix, scale=True, roll=False)
        if rotation:
            bone.transform(bake_rotation_matrix, scale=True, roll=True)
        if location:
            bone.transform(bake_location_matrix, scale=True, roll=False)
    # restore the mode we were in before...
    set_current_objects(mode, selected, active)
    # clear the transform channels we applied...
    if location:
        armature.location = (0.0, 0.0, 0.0)
    if rotation:
        # always clear all three rotation modes...
        armature.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        armature.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
        armature.rotation_euler = (0.0, 0.0, 0.0)
    if scale:
        armature.scale = (1.0, 1.0, 1.0)
    # update the view layer before restoring children matrices...
    bpy.context.view_layer.update()
    for child, matrix in children.items():
        child.matrix_world = matrix
    # bake the same matrix into the weighted meshes, so they stay in bind pose alignment with the baked bones...
    for mesh in meshes:
        set_mesh_transforms(mesh, location, rotation, scale, matrix=apply_matrix)
    # and correct the given actions location keyframes for whatever uniform scale was baked into the bones...
    if scale:
        scaling = apply_matrix.to_scale().x
        for action in actions:
            for fc in get_action_fcurves(action):
                if fc.data_path.endswith('.location'):
                    for key in fc.keyframe_points:
                        key.co.y *= scaling
                        key.handle_left.y *= scaling
                        key.handle_right.y *= scaling
                    fc.update()
    

def set_applied_modifiers(mesh, basis=None, include_armature=False):
    # get any/all armature modifiers...
    armatures = [m for m in mesh.modifiers if m.type == 'ARMATURE']
    last = armatures[-1] if armatures else None
    # the last armature modifier normally stays live for ongoing animation, unless the caller wants it baked in too...
    if last and not include_armature:
        # we temporarirly mute it...
        last.show_viewport = False
    # get the dependency graph to evaluate the object's modifiers...
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = mesh.evaluated_get(depsgraph)
    # create a new mesh from the evaluated object with all unmuted modifiers...
    mesh_from_modifiers = bpy.data.meshes.new_from_object(obj_eval)
    # replace the original object's mesh with the new mesh (with applied modifiers)...
    mesh.data = mesh_from_modifiers
    # free the evaluated mesh... (to save memory)...
    obj_eval.to_mesh_clear()
    # remember the last armature modifiers settings before it's removed below, so we can recreate it...
    restore = (last.name, last.object, last.vertex_group, last.invert_vertex_group) if (last and include_armature) else None
    # then iterate over all modifiers again...
    for mod in mesh.modifiers:
        # if this is the last armature modifier, and we didn't bake it in, it should be un muted...
        if mod == last and not include_armature:
            mod.show_viewport = True
        else:
            # else it's been applied or ignored so remove it...
            mesh.modifiers.remove(mod)
    # if we baked the last armature modifiers deformation in, add a fresh equivalent back for ongoing use...
    if restore:
        name, target, vertex_group, invert_vertex_group = restore
        new_mod = mesh.modifiers.new(name=name, type='ARMATURE')
        new_mod.object, new_mod.vertex_group, new_mod.invert_vertex_group = target, vertex_group, invert_vertex_group

def set_mirrored_materials(mesh):
    for i, material in enumerate(mesh.data.materials):
        name, side = get_mirrored_name(material.name)
        # if we can get a mirrored name and side...
        if name and side:
            # if that mirrored name already exists on the object...
            if name in mesh.data.materials:
                mirror = mesh.data.materials.get(name)
            # else check if the material already exists in the .blend...
            elif name in bpy.data.materials:
                mirror = bpy.data.materials.get(name)
                mesh.data.materials.append(mirror)
            else:
                # else create a duplicate of the material and use that...
                mirror = material.copy()
                mirror.name = name
                mesh.data.materials.append(mirror)
            # then find the mirror materials index... (it should always be found)...
            index = mesh.data.materials.find(mirror.name)
            # get all the polys on the opposing side of the mesh using the existing materials index...
            polys = [p for p in mesh.data.polygons if (p.material_index == i and (p.center.x < 0.0 if side == 'RIGHT' else p.center.x > 0.0))]
            # and switch them for the mirrored materials index...
            for p in polys:
                p.material_index = index

def set_applied_meshes(meshes, original=True, modifiers=True, parent=False, location=False, rotation=False, scale=False, include_armature=False):
    # duplicate the meshes if we want to keep the originals...
    if original:
        bpy.ops.object.select_all(action='DESELECT')
        for mesh in meshes:
            mesh.select_set(True)
        bpy.ops.object.duplicate(linked=False)
        meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    for mesh in meshes:
        # make sure no verts are selected or hidden... (not sure why)...
        for v in mesh.data.vertices:
            v.select = False
            v.hide = False
        # if we want to apply modifiers... (preserving shape keys)...
        if modifiers:
            # break any/all shape keys out into individual meshes...
            shapes = shaping.functions.get_shape_meshes(mesh)
            # if we have shape meshes...
            if shapes:
                # save the name of the basis and kill all shape keys...
                basis = mesh.data.shape_keys.key_blocks[0].name
                mesh.shape_key_clear()
                print("\nPreserving shape keys... '" + mesh.name + "'")
            # get any X mirror modifiers that we are about to apply...
            mirror = any(m.type == 'MIRROR' and m.use_axis[0] and m.show_viewport for m in mesh.modifiers)
            # apply all modifiers to the original mesh... (not including last armature one, unless overridden)...
            set_applied_modifiers(mesh, include_armature=include_armature)
            # if we had X mirror modifiers...
            if mirror:
                # we can attempt to mirror materials...
                set_mirrored_materials(mesh)
            # if we have shape meshes...
            if shapes:
                # add back the basis key to the mesh...
                mesh.shape_key_add(name=basis, from_mix=False)
                # iterate through the shape meshes...
                for m in shapes:
                    # applying their modifiers...
                    set_applied_modifiers(m, basis=mesh)
                    # if the shape mesh has the same amount of vertices as the original...
                    if len(m.data.vertices) == len(mesh.data.vertices):
                        # join it back to the orignal mesh as a shape key...
                        mesh.shape_key_add(name=m.name, from_mix=False)
                        shape = mesh.data.shape_keys.key_blocks.get(m.name)
                        for i, v in enumerate(shape.data):
                            v.co = m.data.vertices[i].co
                        shape.value = 0.0
                        print("Preserved shape key... '" + m.name + "' vertex count: " + str(len(m.data.vertices)) + "/" + str(len(mesh.data.vertices)))
                    else:
                        # else report the issue...
                        print("Cancelled shape key... '" + m.name + "' vertex count: " + str(len(m.data.vertices)) + "/" + str(len(mesh.data.vertices)))
                    # and get rid of them...
                    bpy.data.objects.remove(m)
        # if we want to clear the parent... (to optionally include its transforms)...
        if parent:
            # save a copy of the current world matrix...
            world_matrix = mesh.matrix_world.copy()
            # clear the parenting...
            mesh.parent, mesh.parent_type, mesh.parent_bone = None, 'OBJECT', ""
            # set the world matrix back and update the view layer...
            mesh.matrix_world = world_matrix
            bpy.context.view_layer.update()
        # if we want to apply any transform channels...
        if location or rotation or scale:
            set_mesh_transforms(mesh, location, rotation, scale)

def set_cleaned_meshes(meshes, prefix="DEL_", shapes=False, groups=False, materials=False):
    # iterate on all input meshes...
    for mesh in meshes:
        # if we want to clean shapes... (and the mesh has them)...
        if shapes and mesh.data.shape_keys:
            # get the shape keys we want to remove by their prefix...
            clean_shapes = [s for s in mesh.data.shape_keys.key_blocks if s.name.startswith(prefix)]
            # and remove them...
            for shape in clean_shapes:
                mesh.shape_key_remove(shape)
        # if we want to clean vertex groups...
        if groups:
            # get the vertex groups we want to remove by their prefix...
            clean_groups = [g for g in mesh.vertex_groups if g.name.startswith(prefix)]
            # and remove them...
            for group in clean_groups:
                mesh.vertex_groups.remove(group)
        # if we want to clean materials...
        if materials:
            # get material slot indices matching the prefix... (material collections cannot remove by material)...
            clean_materials = [i for i, m in enumerate(mesh.data.materials) if m.name.startswith(prefix)]
            # and pop them out... (but it does have a pop function for some reason, weird)...
            for i in reversed(clean_materials):
                mesh.data.materials.pop(index=i)

def get_armature_hierarchy(armature):
    # resolve the armature trio from any member of the rigging hierarchy...
    if armature.type != 'ARMATURE':
        return None, None, None
    oriented, original, rig = None, None, None
    kind = armature.get('Armature Type')
    if kind == "Original":
        original = armature
        oriented = original.parent if original.parent and original.parent.get('Armature Type') == "Oriented" else None
    elif kind == "Rigging":
        rig = armature
        oriented = next((child for child in rig.children if child.get('Armature Type') == "Oriented"), None)
    elif kind == "Oriented":
        oriented = armature
    elif kind is None:
        # an untagged armature is the original input before an oriented sibling exists...
        original = armature
    if oriented:
        if not rig and oriented.parent and oriented.parent.get('Armature Type') == "Rigging":
            rig = oriented.parent
        if not original:
            original = next((child for child in oriented.children if child.get('Armature Type') == "Original"), None)
    return rig, oriented, original

def get_stored_transform(obj):
    # grab every rotation mode along with location/scale, so whichever one is active gets restored correctly...
    return obj.location.copy(), obj.rotation_quaternion.copy(), obj.rotation_euler.copy(), obj.rotation_axis_angle[:], obj.scale.copy()

def set_cleared_transform(obj):
    # world-space retargeting math assumes identity object transforms, so this needs clearing first (and restoring after)...
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)

def set_restored_transform(obj, transform):
    location, rotation_quaternion, rotation_euler, rotation_axis_angle, scale = transform
    obj.location = location
    obj.rotation_quaternion = rotation_quaternion
    obj.rotation_euler = rotation_euler
    obj.rotation_axis_angle = rotation_axis_angle
    obj.scale = scale

def get_armature_meshes(armature, selection):
    weighted = [o for o in selection if o.type == 'MESH' and any(m.type == 'ARMATURE' and m.object == armature for m in o.modifiers)]
    attached = [o for o in selection if o.type == 'MESH' and o.parent == armature and o.parent_type == 'BONE' and o.parent_bone in armature.data.bones]
    return weighted, attached

def get_action_fcurves(action):
    # actions store their fcurves behind layers/strips/channelbags now... (the slotted action system)...
    return [fc for l in action.layers for s in l.strips for c in s.channelbags for fc in c.fcurves]

def get_action_slot(act, armature):
    # find the slot whose bone fcurves best match this armature...
    best, best_count = None, 0
    for slot in act.slots:
        if slot.target_id_type not in ('UNSPECIFIED', armature.id_type):
            continue
        channelbag = anim_utils.action_get_channelbag_for_slot(act, slot)
        if not channelbag:
            continue
        bones = [fc.data_path.partition('"')[2].split('"')[0] for fc in channelbag.fcurves if '"' in fc.data_path]
        matched = sum(1 for b in bones if b in armature.data.bones)
        if matched > best_count:
            best, best_count = slot, matched
    return best

def set_stashed_action(armature, action):
    # stash an action as a muted nla track, so several actions can coexist on one armature...
    if not armature.animation_data:
        armature.animation_data_create()
    track = armature.animation_data.nla_tracks.new()
    track.name, track.mute, track.lock = action.name, True, True
    strip = track.strips.new(action.name, int(action.frame_range[0]), action)
    slot = get_action_slot(action, armature)
    if slot:
        strip.action_slot = slot

def get_copied_nla(armature):
    # keep every action in first-use order... (the nla settings refer back to this list by index)
    if armature.animation_data:
        # active action is always the first action...
        active = armature.animation_data.action
        actions, indices, tracks = [active], {active : 0}, []
        # for each track in the nla...
        for track in armature.animation_data.nla_tracks:
            # get it's settings...
            saved = {'name': track.name, 'mute': track.mute, 'lock': track.lock, 'solo': track.is_solo, 'strips': []}
            # then iterate through the strips...
            for strip in track.strips:
                # if the action has already been appended use it's index...
                if strip.action in indices:
                    index = indices[strip.action]
                else:
                    # else we add the action and get the index by length...
                    index = len(actions)
                    actions.append(strip.action)
                    indices[strip.action] = index
                # append all the strips settings to the saved track data...
                saved['strips'].append({
                    'action': index, 'name': strip.name, 'frame_start': strip.frame_start,
                    'action_frame_start': strip.action_frame_start, 'action_frame_end': strip.action_frame_end,
                    'blend_in': strip.blend_in, 'blend_out': strip.blend_out, 'blend_type': strip.blend_type,
                    'extrapolation': strip.extrapolation, 'influence': strip.influence, 'repeat': strip.repeat,
                    'scale': strip.scale, 'use_auto_blend': strip.use_auto_blend, 'use_reverse': strip.use_reverse,
                    'use_sync_length': strip.use_sync_length, 'use_animated_influence': strip.use_animated_influence,
                    'use_animated_time': strip.use_animated_time, 'use_animated_time_cyclic': strip.use_animated_time_cyclic})
            # and append all the saved track data to the tracks...
            tracks.append(saved)
        # return the track and action lists...
        return tracks, actions
    else:
        # if there was no aniamtion data return empty...
        return [], []

def set_copied_nla(armature, tracks, actions):
    # make sure the armature has animation data...
    data = armature.animation_data_create()
    # clear the old active action and tracks...
    data.action = None
    for track in list(data.nla_tracks):
        data.nla_tracks.remove(track)
    # the first action is always the active action...
    if actions and actions[0]:
        data.action = actions[0]
        slot = get_action_slot(data.action, armature)
        if slot:
            data.action_slot = slot
    # now rebuild each nla track...
    for saved in tracks:
        track = data.nla_tracks.new()
        track.name, track.mute, track.lock, track.is_solo = saved['name'], saved['mute'], saved['lock'], saved['solo']
        # and add all it's strips...
        for settings in saved['strips']:
            action = actions[settings['action']]
            strip = track.strips.new(settings['name'], int(settings['frame_start']), action)
            # apply the strips saved settings...
            for name, value in settings.items():
                if name not in {'action', 'name', 'frame_start'}:
                    setattr(strip, name, value)
            # and restore the action slot...
            slot = get_action_slot(action, armature)
            if slot:
                strip.action_slot = slot

def get_armature_actions(armature, method='ALL'):
    # active only wants whatever action is currently assigned, if any...
    if method == 'ACTIVE':
        if armature.animation_data and armature.animation_data.action:
            return [armature.animation_data.action]
        return []
    # only include muted tracks for stashed actions (push down tracks remain active)...
    if method == 'STASHED':
        if not armature.animation_data:
            return []
        tracks = [t for t in armature.animation_data.nla_tracks if t.mute]
        return list({s.action for t in tracks for s in t.strips if s.action})
    # all wants every action referencing the armatures bones, regardless of how its assigned...
    return [a for a in bpy.data.actions if any(fc.data_path.partition('"')[2].split('"')[0] in armature.data.bones for fc in get_action_fcurves(a))]

def get_shapes_directory():
    # custom bone shapes live in the rigging modules own shapes folder, regardless of who's asking...
    addon = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(addon, "rigging", "shapes")

def get_shape_mesh(identifier):
    directory = get_shapes_directory()
    filename = identifier.lower() + ".py"
    filepath = os.path.join(directory, filename)
    # if the directory exists and is writable...
    shape = None
    if os.path.exists(filepath):
        # specify the module that needs to be imported relative to the path of the module...
        spec = importlib.util.spec_from_file_location(filename, filepath)
        # creates a new module based on spec...
        module = importlib.util.module_from_spec(spec)
        # executes the module in its own namespace when a module is imported or reloaded...
        spec.loader.exec_module(module)
        # if we got the module...
        if module:
            # if the shape doesn't already exist...
            shape = bpy.data.objects.get(module.shape['name'])
            if shape is None:
                data = module.shape
                mesh = bpy.data.meshes.new(module.shape['name'])
                mesh.from_pydata(data['vertices'], data['edges'], data['faces'])
                shape = bpy.data.objects.new(module.shape['name'], mesh)
                if data['sharps']:
                    attribute = shape.data.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
                    for i, sharp in enumerate(data['sharps']):
                        attribute.data[i].value = sharp
                    # sharp faces is pointless for bone shapes... (no pun intended)...
                    if shape.data.attributes.get("sharp_face"):
                        shape.data.attributes.remove(shape.data.attributes["sharp_face"])
    # return the shape... (or None if we couldn't get it)...
    return shape

def set_shape_items(preferences):
    directory, items = get_shapes_directory(), [('NONE', "None", "", 'NONE', 0)]
    if os.path.exists(directory):
        # get all the .py files in the folder...
        for filename in os.listdir(directory):
            if filename.endswith(".py"):
                name = filename[:-3]
                # as legible items for the enum...
                item = (filename[:-3].upper(), name.replace("_", " ").title(), "", 'NONE', len(items))
                items.append(item)
        # set the shape enum item cache in preferences...
        preferences.shape_items = items

def get_shape_items(self, context):
    # shared dynamic items callback, so every custom shape picker across the addon can reference this directly...
    prefs = get_addon_preferences(context)
    set_shape_items(prefs)
    return prefs.shape_items

def get_serialized_settings(settings):
    # flattens any property group tree into plain data, generic enough for import/export/rigging settings alike...
    data = {}
    for prop in settings.bl_rna.properties:
        if prop.identifier == 'rna_type':
            continue
        value = getattr(settings, prop.identifier)
        if prop.type == 'COLLECTION':
            data[prop.identifier] = [get_serialized_settings(i) for i in value]
        elif prop.type == 'POINTER':
            data[prop.identifier] = get_serialized_settings(value)
        elif getattr(prop, 'is_array', False):
            data[prop.identifier] = list(value)
        else:
            data[prop.identifier] = value
    return data

def set_deserialized_settings(settings, data):
    # the inverse of get_serialized_settings... (writes plain data back into the settings)...
    for identifier, value in data.items():
        prop = settings.bl_rna.properties.get(identifier)
        if not prop:
            continue
        if prop.type == 'COLLECTION':
            collection = getattr(settings, identifier)
            collection.clear()
            for item in value:
                set_deserialized_settings(collection.add(), item)
        elif prop.type == 'POINTER':
            set_deserialized_settings(getattr(settings, identifier), value)
        else:
            setattr(settings, identifier, value)




