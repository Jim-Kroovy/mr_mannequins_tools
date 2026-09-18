import bpy
import os
import re

def get_library_directory():
    # the folder scanned for this addon's template .blend files...
    directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library")
    os.makedirs(directory, exist_ok=True)
    return directory

def get_library_files():
    # sorted template names, derived from whatever .blend files are sat in the library folder...
    directory = get_library_directory()
    return sorted(os.path.splitext(f)[0] for f in os.listdir(directory) if f.lower().endswith(".blend"))

def set_template_items(preferences):
    # dynamic enum item cache, shared by the add-template operator and the Add > Templates menu...
    files = get_library_files()
    items = [(n, n.replace("_", " "), "", 'ASSET_MANAGER', i) for i, n in enumerate(files)]
    if not items:
        items = [('NONE', "No Saved Templates", "", 'NONE', 0)]
    preferences.template_items = items

def is_valid_id(id_block):
    # a prior dedup pass, or Blender's own undo/redo of these raw bpy.data edits, may have already freed this...
    try:
        id_block.users
        return True
    except ReferenceError:
        return False

def set_deduplicated_shapes(objects):
    # nobody needs more than one copy of a custom shape per file, reassign appended duplicates to the original...
    duplicates = set()
    for obj in objects:
        if obj.type != 'ARMATURE':
            continue
        for pose_bone in obj.pose.bones:
            shape = pose_bone.custom_shape
            if not shape:
                continue
            match = re.match(r'^(.*)\.\d{3}$', shape.name)
            if not match:
                continue
            original = bpy.data.objects.get(match.group(1))
            if not original or original == shape or original in objects:
                continue
            pose_bone.custom_shape = original
            duplicates.add(shape)
    # remove any duplicate that no bone points to any more...
    removed = set()
    for shape in duplicates:
        if is_valid_id(shape) and shape.users == 0:
            data = shape.data
            bpy.data.objects.remove(shape, do_unlink=True)
            removed.add(shape)
            if data.users == 0:
                bpy.data.meshes.remove(data)
    return removed

def set_deduplicated_materials(objects):
    # same idea as set_deduplicated_shapes, but for materials appended again on a repeated template...
    duplicates, seen = set(), set()
    for obj in objects:
        if obj.type != 'MESH' or obj.data in seen:
            continue
        seen.add(obj.data)
        materials = obj.data.materials
        for index, material in enumerate(materials):
            if not material:
                continue
            match = re.match(r'^(.*)\.\d{3}$', material.name)
            if not match:
                continue
            original = bpy.data.materials.get(match.group(1))
            if not original or original == material:
                continue
            materials[index] = original
            duplicates.add(material)
    # remove any duplicate that no mesh points to any more...
    removed = set()
    for material in duplicates:
        if is_valid_id(material) and material.users == 0:
            bpy.data.materials.remove(material)
            removed.add(material)
    return removed

def set_deduplicated_images(materials):
    # same idea again, but for the image textures a material's nodes reference...
    duplicates = set()
    for material in materials:
        if not material or not material.use_nodes or not material.node_tree:
            continue
        for node in material.node_tree.nodes:
            if node.type != 'TEX_IMAGE' or not node.image:
                continue
            image = node.image
            match = re.match(r'^(.*)\.\d{3}$', image.name)
            if not match:
                continue
            original = bpy.data.images.get(match.group(1))
            if not original or original == image:
                continue
            node.image = original
            duplicates.add(image)
    # remove any duplicate that no material points to any more...
    removed = set()
    for image in duplicates:
        if is_valid_id(image) and image.users == 0:
            bpy.data.images.remove(image)
            removed.add(image)
    return removed

def set_deduplicated_assets(objects):
    # dedupe images before their materials, since removing a duplicate material doesn't cascade-remove the images its node tree referenced, so collect them all while still reachable, then dedupe materials...
    materials = {m for obj in objects if obj.type == 'MESH' for m in obj.data.materials if m}
    set_deduplicated_images(materials)
    set_deduplicated_materials(objects)

def load_saved_template(context, name, ignore_armatures, ignore_meshes, ignore_materials, ignore_animations):
    filepath = os.path.join(get_library_directory(), name + ".blend")
    if not os.path.exists(filepath):
        return None, "template file not found"
    with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)
    # custom shapes are their own objects too, but stay referenced on the armature rather than linked into the scene...
    shapes, used = set(), set()
    for obj in data_to.objects:
        if not obj or obj.type != 'ARMATURE':
            continue
        for con in obj.constraints:
            target = getattr(con, 'target', None)
            if target:
                used.add(target)
        for pb in obj.pose.bones:
            if pb.custom_shape:
                shapes.add(pb.custom_shape)
            for con in pb.constraints:
                target = getattr(con, 'target', None)
                if target:
                    used.add(target)
    # keep armatures, meshes and their required dependencies... (like spline curves)...
    objects = [obj for obj in data_to.objects if obj and obj not in shapes and (obj.type in {'ARMATURE', 'MESH'} or obj in used)]
    for obj in data_to.objects:
        if obj and obj not in objects and obj not in shapes:
            bpy.data.objects.remove(obj, do_unlink=True)
    if not objects:
        return None, "template contained no armature or mesh objects"
    for obj in objects:
        context.collection.objects.link(obj)
    # drop whatever categories were asked to be ignored...
    kept = []
    for obj in objects:
        if (obj.type == 'ARMATURE' and ignore_armatures) or (obj.type == 'MESH' and ignore_meshes):
            obj_type, data = obj.type, obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data.users == 0:
                bpy.data.armatures.remove(data) if obj_type == 'ARMATURE' else bpy.data.meshes.remove(data)
        else:
            kept.append(obj)
    for obj in kept:
        if obj.type == 'ARMATURE' and ignore_animations:
            obj.animation_data_clear()
        elif obj.type == 'MESH' and ignore_materials:
            obj.data.materials.clear()
    if ignore_armatures:
        # tidy up modifiers left aiming at the armature that just got removed...
        for obj in kept:
            if obj.type == 'MESH':
                for mod in [m for m in obj.modifiers if m.type == 'ARMATURE' and m.object is None]:
                    obj.modifiers.remove(mod)
    set_deduplicated_assets(kept)
    # dropping this from shapes too, since deduplication may have already removed it from bpy.data...
    shapes -= set_deduplicated_shapes(kept)
    # any shape nothing points to any more, whether it lost its armature or got deduplicated away, can go...
    for shape in shapes:
        if is_valid_id(shape) and shape.users == 0:
            data = shape.data
            bpy.data.objects.remove(shape, do_unlink=True)
            if data.users == 0:
                bpy.data.meshes.remove(data)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in kept:
        obj.select_set(True)
    if kept:
        context.view_layer.objects.active = kept[-1]
    return kept, None
