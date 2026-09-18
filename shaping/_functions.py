import bpy
import math
import time

from mathutils import Vector

from .. import utilities

def get_shape_meshes(mesh, active=False):
    # for each shape key on the mesh... (not including the first basis shape)...
    if mesh.data.shape_keys:
        meshes, shapes = [], [s for i, s in enumerate(mesh.data.shape_keys.key_blocks) if i > 0]
        if active:
            shapes = [mesh.active_shape_key]
        for shape in shapes:
            # create and link a copy as an actual mesh...
            m = mesh.copy()
            data = mesh.data.copy()
            m.data = data
            collections = [coll for coll in mesh.users_collection]
            for collection in collections:
                collection.objects.link(m)
            m.name = shape.name
            # get the shape we want to keep... (we should always find it)...
            s = data.shape_keys.key_blocks.get(shape.name)
            # save it's coordinates and clear all shape keys...
            scos = [v.co.copy() for v in s.data]
            m.shape_key_clear()
            # then set it's vertices to the coordinates...
            for i, v in enumerate(m.data.vertices):
                v.co = scos[i]
            meshes.append(m)
        return meshes
    else:
        return []

def get_mirrored_vertices(vertices, precision=4, speed=4):
    # this seems to be the fastest and msot accurate method... (tested several others)...
    tolerance = 10 ** -precision
    # first get our vertices sorted into an x mirror dictionary...
    mirrored, binned = {}, {}
    for v in vertices:
        rounded = round(v.co.x, speed)
        # the bin search will run exponentially faster with more decimal places...
        if rounded in binned:
            # and even more efficiently when isolated to one axis...
            binned[rounded].append(v)
        else:
            binned[rounded] = [v]
    # iterate through verts again...
    for v in vertices:
        # if the mirrored x hash exists in our vert bin...
        rounded = -round(v.co.x, speed)
        if rounded in binned:
            # we can check through all the verts associated with the x hash...
            for i, m in enumerate(binned[rounded]):
                # using the isclose function for the best accuracy...
                x = math.isclose(-v.co.x, m.co.x, abs_tol=tolerance)
                y = math.isclose(v.co.y, m.co.y, abs_tol=tolerance)
                z = math.isclose(v.co.z, m.co.z, abs_tol=tolerance)
                # if xyz are close enough and it's not a self mirror...
                if x and y and z: #and v != m:
                    # add the mirrored indices to the mirror dictionary...
                    mirrored[v.index] = m.index
                    # and pop the mirrored vertex to avoid re-checking... (pop is faster than remove)...
                    binned[rounded].pop(i)
                    break
    return mirrored

def set_mirrored_shapes(meshes, basis="", prefix="", active=True, selected=False, method='BLEND', blend=0.1):
    # shape key data must be written in object mode...
    last_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    if last_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    # iterate through the selected meshes...
    for mesh in meshes:
        # if it has shape keys...
        if mesh.data.shape_keys:
            # get any shapes that should be mirrored...
            shapes, mirrored = [mesh.active_shape_key], set()
            if not active:
                shapes = [s for s in mesh.data.shape_keys.key_blocks if s.name.startswith(prefix)]
            if shapes:
                # get the meshes verts that have mirrored counterparts...
                pairs = get_mirrored_vertices(mesh.data.vertices)
                for shape in shapes:
                    # mirror only the active shape or unmirrored left/right shapes...
                    name, side = utilities.functions.get_mirrored_name(shape.name)
                    if (active or (name and side)) and shape.name not in mirrored:
                        # record the start time and get our basis shape...
                        start = time.time()
                        basis_key = mesh.data.shape_keys.key_blocks.get(basis) or shape.relative_key
                        # if the mirror shape already exists on the object...
                        mirror = mesh.data.shape_keys.key_blocks.get(name)
                        if mirror:
                            # add the mirrored name so we don't re-mirror...
                            mirrored.add(name)
                            # clear its vertex positions...
                            for i, v in enumerate(basis_key.data):
                                # potentially skipping unselected vertices...
                                if mesh.data.vertices[i].select or not selected:
                                    mirror.data[i].co = v.co
                        else:
                            # else add a fresh shape key for it...
                            name = name or shape.name + ".001"
                            mesh.shape_key_add(name=name, from_mix=False)
                            mirror = mesh.data.shape_keys.key_blocks[-1]
                        # if we are only mirroring the active shape key...
                        if active:
                            # when blending have both shapes active...
                            if method == 'BLEND':
                                shape.value, mirror.value = 1.0, 1.0
                            # and only the mirrored shape when flipping...
                            elif method == 'FLIP':
                                shape.value, mirror.value = 0.0, 1.0
                        # if niether shape is locked we can iterate...
                        if not (shape.lock_shape or mirror.lock_shape):
                            # get the cieling, floor and copies of the coordinates... (clamp to epsilon for hard cutoff)...
                            threshold = max(blend, 1e-6)
                            cieling, floor = threshold, -threshold
                            coordinates, failed = [v.co.copy() for v in shape.data], []
                            # iterate on its data coordinates...
                            for i, v in enumerate(mirror.data):
                                # potentially skipping unselected vertices...
                                if mesh.data.vertices[i].select or not selected:
                                    # if we get it's mirror vert and index...
                                    if i in pairs:
                                        m = pairs[i]
                                        # get the mirrored coordinates of the vertex we are mirroring...
                                        mco = Vector((-coordinates[m].x, coordinates[m].y, coordinates[m].z))
                                        # if don't want blending...
                                        if method == 'FLIP':
                                            # simply flip the shape...
                                            v.co = mco
                                        else:
                                            # get the basis and source coordinates and blend by central direction...
                                            bco, sco = basis_key.data[i].co.copy(), shape.data[i].co.copy()
                                            factor = utilities.functions.get_mapped_range(bco.x, floor, cieling, 0.0, 1.0, clamp=True, default=0.0)
                                            alpha = factor if side == 'RIGHT' else 1.0 - factor
                                            # lerp both the mirror and source back toward basis by their respective alphas...
                                            v.co = bco.lerp(mco, alpha)
                                            shape.data[i].co = bco.lerp(sco, 1.0 - alpha)
                                    else:
                                        failed.append(i)
                                # if this is the last vertex to iterate through...
                                if v == mirror.data[-1]:
                                    # report if any verts failed to mirror and how long the process took...
                                    end = time.time()
                                    print("'" + shape.name + "' " + str(len(mirror.data) - len(failed)) + "/" + str(len(mirror.data)) + " vertices mirrored in " + str(round(end - start, 2)) + " seconds...", end='\n', flush=True)
                                else:
                                    # else just report progress... (on the same line)...
                                    print("'" + shape.name + "' " + str((i + 1) - len(failed)) + "/" + str(len(mirror.data)) + " vertices mirrored...", end='\r', flush=True)
    if last_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=last_mode)

def set_blended_shapes(meshes, prefix="", active=True, blend=0.1, into="", alpha=1.0, steps=0):
    # vertex selection data is stale in edit mode, switch to object mode to read it correctly...
    last_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    if last_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for mesh in meshes:
        # if it has shape keys...
        if mesh.data.shape_keys:
            # if we want to operate on all shape keys...
            shapes = [mesh.active_shape_key]
            if not active:
                shapes = [s for s in mesh.data.shape_keys.key_blocks if s.name.startswith(prefix)]
            if shapes:
                # build a map of all edge connected vertices...
                connected = {v.index : [] for v in mesh.data.vertices}
                for edge in mesh.data.edges:
                    connected[edge.vertices[0]].append(edge.vertices[1])
                    connected[edge.vertices[1]].append(edge.vertices[0])
                # get selected vertices... (as a dictionary for fast look up)...
                selected = {v.index : v for v in mesh.data.vertices if v.select}
                # and all unselected vertices immediately adjacent to the selection...
                bordered = [i for i in connected if i not in selected and any(c in selected for c in connected[i])]
                if not bordered:
                    print("'" + mesh.name + "' has no unselected border vertex to blend from, skipping...")
                    continue
                # we also need the vertices of the relative shape... (if any)...
                if into not in mesh.data.shape_keys.key_blocks:
                    print("'" + mesh.name + "' has no shape key named '" + into + "', skipping...")
                    continue
                relative = mesh.data.shape_keys.key_blocks[into]
                # iterate through the shapes...
                for shape in shapes:
                    # blend and track which vertices were actually affected...
                    affected = set()
                    for v in mesh.data.vertices:
                        # if this vertex is selected...
                        if v.index in selected:
                            # get the closest border vertex to it...
                            closest = float('inf')
                            for b in bordered:
                                distance, _ = utilities.functions.get_distance_direction(shape.data[v.index].co, shape.data[b].co)
                                if distance < closest:
                                    closest = distance
                            # and lerp the shape key to the target shape from distance to closest border vertex...
                            factor = utilities.functions.get_mapped_range(closest, 0.0, blend, 0.0, alpha, clamp=True, default=alpha)
                            shape.data[v.index].co = shape.data[v.index].co.lerp(relative.data[v.index].co, factor)
                            # if the vertex is within blending range it may require smoothing...
                            if closest > 0.0 and closest < blend:
                                affected.add(v.index)
                    # smooth only the vertices that were actually blended...
                    for _ in range(steps):
                        for i in affected:
                            neighbors = connected[i]
                            if neighbors:
                                avg = Vector((0.0, 0.0, 0.0))
                                for n in neighbors:
                                    avg += shape.data[n].co
                                shape.data[i].co = avg / len(neighbors)
    if last_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode=last_mode)
