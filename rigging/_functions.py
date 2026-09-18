import bpy
import math
import os
import re
import json
import pprint
import keyword

from mathutils import Vector, Euler, Matrix, Quaternion

from .. import utilities

def get_bone_axes(bone, axes):
    # pull straight from the matrix for a bone bone instead...
    if isinstance(bone, bpy.types.Bone):
        x_axis, y_axis, z_axis = bone.matrix_local.col[0].xyz, bone.matrix_local.col[1].xyz, bone.matrix_local.col[2].xyz
    else:
        x_axis, y_axis, z_axis = bone.x_axis, bone.y_axis, bone.z_axis
    # declare a dictionary of the bones cardinal direction vectors...
    cardinal = {
        '+X' : x_axis, '-X' : x_axis * -1,
        '+Y' : y_axis, '-Y' : y_axis * -1,
        '+Z' : z_axis, '-Z' : z_axis * -1,
        }
    # iterate through them to gather what we need...
    result = {}
    for axis in axes:
        result[axis] = cardinal[axis]
    # and return the resulting dictionary...
    return result

def get_roll_axes(bone, head, tail):
    # get the closest axis to the tail direction...
    _, direction = utilities.functions.get_distance_direction(head, tail)
    axes = get_bone_axes(bone, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
    closest, _ = utilities.functions.get_closest_axis(direction, axes)
    # and exclude it from the result... (positive and negative)...
    axes = get_bone_axes(bone, [a for a in ['+X', '-X', '+Y', '-Y', '+Z', '-Z'] if not a.endswith(closest[1])])
    return axes

def get_existing_bone(rig, bone):
    # the parent transform child of always targets the rigging armature...
    con = bone.constraints.get("Parent Transform")
    if con and con.target == rig:
        return con.subtarget
    return ""

def remove_invalid_drivers(armature):
    # simply iterate through and remove all invalid drivers... (nothing to do if there are none at all)...
    if not armature.animation_data:
        return
    drivers = armature.animation_data.drivers
    invalid = [d for d in drivers if not d.is_valid]
    for driver in invalid:
        drivers.remove(driver)

def get_shortest_roll(bone, directions):
    # we can always find a roll smaller than 360 degrees...
    y_axis, start = bone.y_axis, bone.roll
    shortest = math.radians(360.0)
    for direction in directions:
        # shortest is always Y axis so exclude it...
        if direction != y_axis and direction != (y_axis * -1):
            # get the roll for the axis... (using Blenders align)...
            bone.align_roll(direction)
            roll = bone.roll
            # and updating the roll if it's shorter...
            if abs(roll) < abs(shortest):
                shortest = roll
    # return the roll of the bone to what it was...
    bone.roll = start
    # return the smallest angle...
    return shortest

def get_central_position(start, end, heads):
    # get the length and primary direction of the chain...
    length, primary = utilities.functions.get_distance_direction(start, end)
    if length == 0.0 or not heads:
        return 0.5
    # find the head whose projection along the primary axis is closest to the midpoint...
    midpoint = length * 0.5
    central, closest = midpoint, float('inf')
    for head in heads:
        projection = (head - start).dot(primary)
        if abs(projection - midpoint) < closest:
            closest = abs(projection - midpoint)
            central = projection
    # return as a 0-1 position along the chain...
    return central / length

def get_chain_normals(points, fallback=Vector((0.0, 1.0, 0.0)), override=None):
    # get the length and primary direction of the chain...
    start, end = points[0], points[-1]
    length, primary = utilities.functions.get_distance_direction(start, end)
    # a user chosen axis always overrides the detected bend, regardless of whether the chain is straight...
    if override is not None:
        secondary = override.normalized()
    else:
        # get the secondary direction from the dominant bend of the chain bones...
        dominant = Vector((0.0, 0.0, 0.0))
        for point in points[1:-1]:
            projection = (point - start).dot(primary)
            perpendicular = point - (start + (primary * projection))
            if perpendicular.length > dominant.length:
                dominant = perpendicular
        # using the largest perpendicular deviation... (falling back to a given direction if the chain is straight)...
        _, secondary = utilities.functions.get_distance_direction(Vector((0.0, 0.0, 0.0)), dominant)
        if secondary.length == 0.0:
            secondary = fallback.normalized()
    # cross primary and secondary for the third orthogonal axis, signed to point away from the world origin...
    tertiary = primary.cross(secondary)
    if tertiary.dot((start + (primary * (length * 0.5))).normalized()) < 0:
        tertiary = -tertiary
    # also return the length... (it often gets used with this function)...
    return primary, secondary, tertiary, length

def get_chain_curvature(points):
    # sum the angles between chain segments in degrees (straight is zero)...
    total = 0.0
    for index in range(1, len(points) - 1):
        before, after = points[index] - points[index - 1], points[index + 1] - points[index]
        if before.length > 1e-9 and after.length > 1e-9:
            total += math.degrees(before.angle(after))
    return total

def get_suggested_count(points, degrees_per_target=25.0, minimum=3):
    # estimate spline target count from chain curvature (a guide, not a requirement)...
    curvature = get_chain_curvature(points)
    return max(minimum, min(len(points) - 1, math.ceil(curvature / degrees_per_target) + 1))

def get_chain_axis(points, origin, fallback=Vector((0.0, 1.0, 0.0))):
    # if the chain has a genuine bend the fallback axis is never actually used, so there's nothing to detect...
    start, end = points[0], points[-1]
    _, primary = utilities.functions.get_distance_direction(start, end)
    dominant = Vector((0.0, 0.0, 0.0))
    for point in points[1:-1]:
        projection = (point - start).dot(primary)
        perpendicular = point - (start + (primary * projection))
        if perpendicular.length > dominant.length:
            dominant = perpendicular
    if dominant.length > 0.0:
        return 'AUTO'
    # otherwise find the origin X or Z axis closest to tertiary... (Y is the primary chain axis)...
    _, _, tertiary, _ = get_chain_normals(points, fallback=fallback)
    axes = get_bone_axes(origin, ['+X', '-X', '+Z', '-Z'])
    closest, _ = utilities.functions.get_closest_axis(tertiary, axes)
    return closest

def get_axis_override(origin, axis):
    # auto means let the detected bend win as usual, so there's nothing to force...
    if axis == 'AUTO':
        return None
    # otherwise the user has explicitly chosen an axis, so it should always win, bent chain or not...
    return get_bone_axes(origin, ['+X', '-X', '+Z', '-Z'])[axis]

def get_axis_fallback(points, origin, axis, fallback=Vector((0.0, 1.0, 0.0))):
    # resolve a settings axis enum (which may itself be AUTO) into an actual fallback vector...
    if axis == 'AUTO':
        axis = get_chain_axis(points, origin, fallback=fallback)
        # a genuine bend means the fallback is never used anyway, so any vector will do...
        if axis == 'AUTO':
            return fallback
    return get_bone_axes(origin, ['+X', '-X', '+Z', '-Z'])[axis]

def get_pole_angle(start, end, pole):
    pole_angle = 0.0
    # if the chain and pole deltas are both greater than zero...
    chain_delta = end.head - start.head
    pole_delta = pole.head - start.head
    if chain_delta.length > 0.0 and pole_delta.length > 0.0:
        # if the pole normal length is greater than zero...
        pole_normal = chain_delta.cross(pole_delta)
        if pole_normal.length > 0.0:
            # if the pole axis length is greater than zero...
            pole_axis = pole_normal.cross(start.y_axis)
            if pole_axis.length > 0.0:
                # get the signed angle from start bones X axis to pole axis around start bone Y axis...
                pole_angle = math.atan2(start.y_axis.dot(pole_axis.cross(start.x_axis)), start.x_axis.dot(pole_axis))
    # return the pole angle if it could be calculated...
    return pole_angle

def get_tracked_basis(rest, aim, rotation, rest_offset, position):
    # reproduces a live damped track + iterative roll correction purely analytically, returning vectors local rotation basis and its resulting pose matrix...
    def get_tracked_matrix(basis):
        matrix = rest @ basis.to_matrix().to_4x4()
        current = matrix.to_3x3().col[1].normalized()
        swing = current.rotation_difference(aim.normalized())
        return Matrix.LocRotScale(rest.translation, swing @ matrix.to_quaternion(), Vector((1.0, 1.0, 1.0)))
    basis = get_tracked_matrix(Quaternion()).to_quaternion().inverted() @ rotation
    vector_matrix = get_tracked_matrix(basis)
    if ((vector_matrix @ rest_offset).translation - position).length >= 0.001:
        for _ in range(4):
            axis = vector_matrix.to_3x3().col[1].normalized()
            current = (vector_matrix @ rest_offset).translation - vector_matrix.translation
            current -= current.dot(axis) * axis
            desired = position - vector_matrix.translation
            desired -= desired.dot(axis) * axis
            if current.length < 1e-6 or desired.length < 1e-6:
                break
            angle = math.atan2(current.cross(desired).dot(axis), current.dot(desired))
            if abs(angle) < 1e-5:
                break
            basis = basis @ Quaternion((0.0, 1.0, 0.0), angle)
            vector_matrix = get_tracked_matrix(basis)
    return basis, vector_matrix

def get_hierarchy_matrix(pose_bone, get_basis, roots, cache):
    # armature-space matrix built from get_basis (fcurves when baking, live matrix_basis when interactive), recursing up to the root (roots themselves locked at rest)...
    if pose_bone.name in cache:
        return cache[pose_bone.name]
    basis = Matrix.Identity(4) if pose_bone.name in roots else get_basis(pose_bone)
    if pose_bone.parent:
        parent_matrix = get_hierarchy_matrix(pose_bone.parent, get_basis, roots, cache)
        matrix = parent_matrix @ pose_bone.parent.bone.matrix_local.inverted() @ pose_bone.bone.matrix_local @ basis
    else:
        matrix = pose_bone.bone.matrix_local @ basis
    cache[pose_bone.name] = matrix
    return matrix

def get_compensated_local(pose_bone, desired_matrix, get_matrix):
    # bones with a live "Root Transform" child of get root motion re-applied on top of their own basis, so solve backward through it assuming full attachment, then lerp/slerp against the unconstrained solve by influence, matching how blender itself blends a partial child of - only exact at 0 or 1 influence, accepted limitation since animators toggle this, not animate it...
    unconstrained = pose_bone.bone.matrix_local.inverted() @ desired_matrix
    root = pose_bone.constraints.get("Root Transform")
    if root and root.influence > 0.0:
        root_pb = root.target.pose.bones.get(root.subtarget)
        root_matrix = get_matrix(root_pb)
        constrained = pose_bone.bone.matrix_local.inverted() @ (root_matrix @ root.inverse_matrix).inverted() @ desired_matrix
        translation = unconstrained.translation.lerp(constrained.translation, root.influence)
        rotation = unconstrained.to_quaternion().slerp(constrained.to_quaternion(), root.influence)
        local = Matrix.LocRotScale(translation, rotation, Vector((1.0, 1.0, 1.0)))
    else:
        local = unconstrained
    return local

def set_snapped_target(target_pb, ending_matrix, get_matrix):
    # sets target directly onto the ending bones world transform - only valid when target has no parent chain of its own (opposable); plantigrade instead drives target indirectly via get_snapped_parent...
    local = get_compensated_local(target_pb, ending_matrix, get_matrix)
    target_pb.rotation_mode = 'QUATERNION'
    target_pb.location = local.translation
    target_pb.rotation_quaternion = local.to_quaternion()

def set_snapped_vector(vector_pb, get_matrix, ending_matrix, primary, secondary, origin_pb):
    # aims vector at the ending bone with a stable roll, matching the retargeting bakes own inlined version - origin_pb must be vectors real blender-parent (the chains origin bone), not any other chain bone, to carry its rest-relative transform into world space correctly...
    if origin_pb:
        origin_matrix = get_matrix(origin_pb)
        rest = origin_matrix @ origin_pb.bone.matrix_local.inverted() @ vector_pb.bone.matrix_local
    else:
        rest = vector_pb.bone.matrix_local
    aim = ending_matrix.translation - rest.translation
    if aim.length > 1e-6:
        y_axis = primary.normalized()
        z_axis = secondary - secondary.dot(y_axis) * y_axis
        if z_axis.length > 1e-6:
            z_axis.normalize()
            # secondarys handedness only defines the bend plane, not which of [+secondary, -secondary] this bone was built to roll toward - callers resolve that fixed sign once from rest data and pre-apply it, so this just trusts whatever sign it was handed...
            x_axis = y_axis.cross(z_axis)
            rotation = Matrix((x_axis, y_axis, z_axis)).transposed().to_quaternion()
            basis, vector_matrix = get_tracked_basis(rest, aim, rotation, Matrix.Identity(4), rest.translation)
            vector_pb.rotation_mode = 'QUATERNION'
            vector_pb.rotation_quaternion = basis
            return vector_matrix

def set_snapped_pole(pole_pb, position, vector_matrix, get_matrix):
    # pole has a live child of on vector ("Vector Transform") and another on root ("Root Transform"), only ever meaningfully 1 or 0, so solve backward through whichever ones active - vector_matrix is set_snapped_vectors own already-computed result, avoiding a stale read before the next depsgraph update...
    pole_rest = pole_pb.bone.matrix_local
    desired_matrix = Matrix.Translation(position) @ pole_rest.to_3x3().to_4x4()

    vector_influence = pole_pb["Vector Influence"] if "Vector Influence" in pole_pb else 1.0
    root_con = pole_pb.constraints.get("Root Transform")
    if vector_influence > 0.0 and vector_matrix is not None:
        vector_con = pole_pb.constraints.get("Vector Transform")
        local = pole_rest.inverted() @ (vector_matrix @ vector_con.inverse_matrix).inverted() @ desired_matrix
    elif root_con and root_con.influence > 0.0:
        root_pb = root_con.target.pose.bones.get(root_con.subtarget)
        root_matrix = get_matrix(root_pb)
        local = pole_rest.inverted() @ (root_matrix @ root_con.inverse_matrix).inverted() @ desired_matrix
    else:
        local = pole_rest.inverted() @ desired_matrix
    # only ever touch location, same as set_settled_position - setting rotation would force a real compensating rotation onto pole to cancel out whichever constraint is driving it, even though the final constrained result is right...
    pole_pb.location = local.translation

def get_snapped_parent(parent_pb, ball_pb, ending_pb, get_matrix, step_height=0.1):
    # plantigrades foot parent/control: parent snaps to the ball or the ankle/target, control takes the balls own local rotation (X is the one real hinge axis, per the "Copy Rotator/Control Rotation" constraints) - pure computation, no bone writes, returns (control_x, parent_local_matrix)...
    def get_local_x(pose_bone, matrix, parent_pose_bone, parent_matrix):
        rest = parent_pose_bone.bone.matrix_local.inverted() @ pose_bone.bone.matrix_local
        local = (parent_matrix @ rest).inverted() @ matrix
        return local.to_quaternion().to_euler('XYZ').x

    ball_matrix = get_matrix(ball_pb)
    ending_matrix = get_matrix(ending_pb)
    ball_angle = get_local_x(ball_pb, ball_matrix, ending_pb, ending_matrix)

    ball_rest_offset = ball_pb.bone.matrix_local.inverted() @ parent_pb.bone.matrix_local
    target_rest_offset = ending_pb.bone.matrix_local.inverted() @ parent_pb.bone.matrix_local
    as_child_of_ball = ball_matrix @ ball_rest_offset
    as_child_of_target = ending_matrix @ target_rest_offset

    if ball_angle < 0.0:
        control_x = min(math.radians(90.0), -ball_angle)
        local = get_compensated_local(parent_pb, as_child_of_ball, get_matrix)
        # the balls hinge amount is already applied separately through control_x, so leaving it in parents local x too would double it up - lerp it out with how far the heel has risen (ball-to-ankle radius * sin of the hinge angle) instead of a hard pop at the threshold...
        radius = (ending_matrix.translation - ball_matrix.translation).length
        height = radius * math.sin(-ball_angle)
        blend = max(0.0, min(1.0, height / step_height)) if step_height > 1e-6 else 1.0
        euler = local.to_quaternion().to_euler('XYZ')
        euler.x *= (1.0 - blend)
        local = Matrix.LocRotScale(local.translation, euler.to_quaternion(), Vector((1.0, 1.0, 1.0)))
    else:
        control_x = 0.0
        local = get_compensated_local(parent_pb, as_child_of_target, get_matrix)
    return control_x, local

def set_bones_reset(*pose_bones, update=True):
    # reset path-dependent constraints before each snap... (prevents twist compounding across calls)...
    for pose_bone in pose_bones:
        if pose_bone:
            pose_bone.matrix_basis = Matrix.Identity(4)
    if update:
        bpy.context.view_layer.update()

def set_settled_position(pole_pb, position, iterations=4):
    # only touches location, which stays affine through any child of stack - one correction usually lands exactly...
    previous_length = None
    for _ in range(iterations):
        bpy.context.view_layer.update()
        error = position - pole_pb.head
        length = error.length
        if length < 1e-6:
            break
        # a clamping constraint (eg Floor) can pin the measured result so the error never shrinks, so stop the moment progress stalls rather than trusting iterations...
        if previous_length is not None and length >= previous_length - 1e-6:
            break
        pole_pb.location += pole_pb.matrix_basis.to_3x3() @ pole_pb.matrix.to_3x3().inverted() @ error
        previous_length = length

def set_settled_matrix(pose_bone, matrix, iterations=4):
    # same measure-and-correct as set_settled_position, generalized to position and rotation...
    pose_bone.rotation_mode = 'QUATERNION'
    previous_location_length, previous_rotation_angle = None, None
    for _ in range(iterations):
        bpy.context.view_layer.update()
        current = pose_bone.matrix
        location_error = matrix.translation - current.translation
        rotation_error = current.to_quaternion().rotation_difference(matrix.to_quaternion())
        location_length, rotation_angle = location_error.length, rotation_error.angle
        if location_length < 1e-6 and rotation_angle < 1e-6:
            break
        # same non-convergence guard as set_settled_position - a clamping constraint can stall either error term...
        if (previous_location_length is not None and location_length >= previous_location_length - 1e-6
                and rotation_angle >= previous_rotation_angle - 1e-6):
            break
        pose_bone.location += pose_bone.matrix_basis.to_3x3() @ current.to_3x3().inverted() @ location_error
        pose_bone.rotation_quaternion = pose_bone.rotation_quaternion @ current.to_quaternion().inverted() @ matrix.to_quaternion()
        previous_location_length, previous_rotation_angle = location_length, rotation_angle

def get_bone_tail(bone, child, recursive=False, length=0.0):
    # if we have a set child to use...
    if child:
        # tail will be the head of it...
        tail = child.head
    # else if we don't have a set child but do have children...
    elif bone.children:
        # we can use their center to define the tail direction...
        children = bone.children_recursive if recursive else bone.children
        heads = [eb.head for eb in children]
        center = sum(heads, Vector((0.0, 0.0, 0.0))) / len(heads)
        # by getting the closest axis of the chain bone to the child center...
        distance, direction = utilities.functions.get_distance_direction(bone.head, center)
        axis = utilities.functions.get_closest_vector(direction, get_bone_axes(bone, ['+X', '-X', '+Y', '-Y', '+Z', '-Z']).values())
        # and using the distance to that center to get the tail position...
        tail = bone.head + (axis * (length if length > 0.0 else distance if distance > 0.0 else bone.length))
    # else if we don't have a child or children but do have a parent...
    elif bone.parent:
        # so we use whichever axis is closest to the direction from it's parent... (it should always have a parent)...
        distance, direction = utilities.functions.get_distance_direction(bone.parent.head, bone.head)
        axis = utilities.functions.get_closest_vector(direction, get_bone_axes(bone, ['+X', '-X', '+Y', '-Y', '+Z', '-Z']).values())
        tail = bone.head + (axis * (length if length > 0.0 else distance if distance > 0.0 else bone.length))
    return tail

def add_parent_constraints(child, parent, name, subtarget, drive=False):
    # get the parent bone we want to copy from...
    parent_bb = parent.data.bones.get(subtarget)
    # and the child bone we want to copy to...
    child_pb = child.pose.bones.get(name)
    # remove any constraints from the target bone...
    for con in child_pb.constraints:
        child_pb.constraints.remove(con)
    # in local with parent space limit location...
    limit_loc = child_pb.constraints.new('LIMIT_LOCATION')
    limit_loc.name, limit_loc.show_expanded = "Isolate Location", False
    limit_loc.use_min_x, limit_loc.use_min_y, limit_loc.use_min_z = True, True, True
    limit_loc.use_max_x, limit_loc.use_max_y, limit_loc.use_max_z = True, True, True
    limit_loc.owner_space = 'LOCAL_WITH_PARENT'
    # limit rotation...
    limit_rot = child_pb.constraints.new('LIMIT_ROTATION')
    limit_rot.name, limit_rot.show_expanded = "Isolate Rotation", False
    limit_rot.use_limit_x, limit_rot.use_limit_y, limit_rot.use_limit_z = True, True, True
    limit_rot.owner_space = 'LOCAL_WITH_PARENT'
    # and limit scale...
    limit_sca = child_pb.constraints.new('LIMIT_SCALE')
    limit_sca.name, limit_sca.show_expanded = "Isolate Scale", False
    limit_sca.use_min_x, limit_sca.use_min_y, limit_sca.use_min_z = True, True, True
    limit_sca.use_max_x, limit_sca.use_max_y, limit_sca.use_max_z = True, True, True
    limit_sca.min_x, limit_sca.min_y, limit_sca.min_z = 1.0, 1.0, 1.0
    limit_sca.max_x, limit_sca.max_y, limit_sca.max_z = 1.0, 1.0, 1.0
    limit_sca.owner_space = 'LOCAL_WITH_PARENT'
    # to isolate transforms applied to the child bone...
    child_of = child_pb.constraints.new('CHILD_OF')
    child_of.name, child_of.show_expanded = "Parent Transform", False
    child_of.target, child_of.subtarget = parent, subtarget
    child_of.inverse_matrix = parent_bb.matrix_local.inverted()
    # the limits can be driven from the child ofs own influence, so they blend on and off together...
    if drive:
        for limit in (limit_loc, limit_rot, limit_sca):
            drv = limit.driver_add('influence')
            var = drv.driver.variables.new()
            var.name, var.type = 'influence', 'SINGLE_PROP'
            var.targets[0].id = child
            var.targets[0].data_path = 'pose.bones["' + name + '"].constraints["Parent Transform"].influence'
            drv.driver.expression = 'influence'
            # and remove any sneaky curve modifiers...
            for mod in drv.modifiers:
                drv.modifiers.remove(mod)

def set_parent_constraints(child, parent):
    # iterate through the childs pose bones...
    for child_pb in child.pose.bones:
        # getting the parent transform child of...
        child_of = child_pb.constraints.get("Parent Transform")
        if child_of and child_of.target == parent:
            # if we can get a valid parent bone for it...
            parent_bb = parent.data.bones.get(child_of.subtarget)
            if parent_bb:
                # update the child of constraints matrix...
                child_of.inverse_matrix = parent_bb.matrix_local.inverted()
            else:
                # else the bone has been removed and so should all the constraints...
                for con in child_pb.constraints:
                    child_pb.constraints.remove(con)

def add_hook_modifiers(rig, curve, index, prior, post, weight, precision=3):
    # get the influence and inverted influence... (we may need to be reducing from the inverse)...
    influence, inverted = round(weight, precision), round(1 - weight, precision)
    # if the inverse influence is greater than zero...
    if prior and inverted > 0.0:
        # it needs a hook modifier to the previous target...
        name = "Hook " + str(index) + " (" + prior + " - " + str(inverted) + ")"
        hook = curve.modifiers.new(name=name, type='HOOK')
        hook.object, hook.subtarget = rig, prior
        hook.vertex_indices_set([index])
        hook.strength = inverted
    # if the influence is greater than zero...
    if post and influence > 0.0:
        # it needs a hook modifier to the next target...
        name = "Hook " + str(index) + " (" + post + " - " + str(influence) + ")"
        hook = curve.modifiers.new(name=name, type='HOOK')
        hook.object, hook.subtarget = rig, post
        hook.vertex_indices_set([index])
        hook.strength = influence

def add_space_drivers(rig, constraint, bone, space):
    drv = constraint.driver_add(space)
    var = drv.driver.variables.new()
    var.name, var.type = "inherit", 'SINGLE_PROP'
    var.targets[0].id = rig
    var.targets[0].data_path = 'data.bones["' + bone + '"].use_inherit_rotation'
    drv.driver.expression =  "1 if inherit > 0.5 else 3"
    # and remove any sneaky curve modifiers...
    for mod in drv.modifiers:
        drv.modifiers.remove(mod)

def add_kinematic_drivers(rig, name, target):
    settings = [
        'ik_stretch', 'lock_ik_x', 'lock_ik_y', 'lock_ik_z',
        'ik_stiffness_x', 'ik_stiffness_y', 'ik_stiffness_z',
        'use_ik_limit_x', 'ik_min_x', 'ik_max_x',
        'use_ik_limit_y', 'ik_min_y', 'ik_max_y',
        'use_ik_limit_z', 'ik_min_z', 'ik_max_z',
        ]
    rig_pb = rig.pose.bones.get(name)
    for setting in settings:
        drv = rig_pb.driver_add(setting)
        var = drv.driver.variables.new()
        var.name, var.type = setting, 'SINGLE_PROP'
        var.targets[0].id = rig
        var.targets[0].data_path = 'pose.bones["' + target + '"].' + setting
        drv.driver.expression =  setting
        # and remove any sneaky curve modifiers...
        for mod in drv.modifiers:
            drv.modifiers.remove(mod)

def add_spline_drivers(rig, name, forward, targets, mappings, weights):
    axes = {'X' : 'ROT_X', 'Y' : 'ROT_Y', 'Z' : 'ROT_Z'}
    # get the pose bones and make sure the driven bone is using euler rotation...
    rig_pb, forward_pb = rig.pose.bones.get(name), rig.pose.bones.get(forward)
    rig_pb.rotation_mode = 'XYZ'
    # drop zero-weight targets, keeps the expression length tied to nearby influences rather than total count...
    influences = [(target_index, target, mapping, weight) for target_index, (target, mapping, weight) in enumerate(zip(targets, mappings, weights)) if weight > 0.0]
    # influence custom prop per target, full ordinal word since it's user facing (unlike the driver variable names below)...
    labels = []
    for target_index, target, mapping, weight in influences:
        target_pb = rig.pose.bones.get(target)
        target_pb.rotation_mode = 'XYZ'
        label = utilities.functions.get_ordinal_index(target_index + 1)
        prop = label + " Influence"
        forward_pb[prop] = weight
        forward_pb.id_properties_ui(prop).update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, default=weight, subtype='FACTOR')
        labels.append(label)
    # use short driver variables within blenders 255 character limit (skip python keywords)...
    letters_by_target, cursor = [], 0
    for _ in influences:
        while True:
            letters = utilities.functions.get_letter_index(cursor)
            cursor += 1
            if not keyword.iskeyword(letters + "r") and not keyword.iskeyword(letters + "i"):
                break
        letters_by_target.append(letters)
    # each destination channel sums every nearby targets own mapped rotation, weighted by it's own influence property...
    for dest_index in range(3):
        drv = rig_pb.driver_add('rotation_euler', dest_index)
        terms = []
        for influence_index, (target_index, target, mapping, weight) in enumerate(influences):
            axis, sign = mapping[dest_index]
            letters = letters_by_target[influence_index]
            rot_name, inf_name = letters + "r", letters + "i"
            # add a rotation variable for this targets own mapped axis...
            rot_var = drv.driver.variables.new()
            rot_var.name, rot_var.type = rot_name, 'TRANSFORMS'
            rot_var.targets[0].id = rig
            rot_var.targets[0].bone_target = target
            rot_var.targets[0].transform_type = axes[axis]
            rot_var.targets[0].rotation_mode = 'AUTO'
            rot_var.targets[0].transform_space = 'LOCAL_SPACE'
            # and an influence variable for this targets own custom property...
            inf_var = drv.driver.variables.new()
            inf_var.name, inf_var.type = inf_name, 'SINGLE_PROP'
            inf_var.targets[0].id = rig
            inf_var.targets[0].data_path = 'pose.bones["' + forward + '"]["' + labels[influence_index] + ' Influence"]'
            # no parens needed, * already binds tighter than +/-...
            terms.append(("-" if sign == -1 else "+") + rot_name + "*" + inf_name)
        expression = "".join(terms)
        if expression.startswith("+"):
            expression = expression[1:]
        drv.driver.expression = expression if terms else "0"
        # and remove any sneaky curve modifiers...
        for mod in drv.modifiers:
            drv.modifiers.remove(mod)

def add_rotation_constraints(rig, name, copy, limit, transform, drive=False):
    rig_pb = rig.pose.bones.get(name)
    if copy:
        copy_rot = rig_pb.constraints.new('COPY_ROTATION')
        copy_rot.target, copy_rot.subtarget = rig, copy['subtarget']
        copy_rot.use_x, copy_rot.use_y, copy_rot.use_z = copy['use']
        copy_rot.invert_x, copy_rot.invert_y, copy_rot.invert_z = copy['invert']
        copy_rot.target_space, copy_rot.owner_space = copy['space']
        copy_rot.mix_mode, copy_rot.influence = copy['mode'], copy['influence'] if 'influence' in copy else 1.0
        axes = ""
        if copy['use'][0]:
            axes = axes + "X"
        if copy['use'][1]:
            axes = axes + "Y"
        if copy['use'][2]:
            axes = axes + "Z"
        end = " Rotation" if axes else "Rotation"
        copy_rot.name = copy['name'] if 'name' in copy else "Copy " + axes + end
        # target and owner spaces can driven from rotation inheritance... (for FK bones)...
        if drive:
            add_space_drivers(rig, copy_rot, name, 'target_space')
            add_space_drivers(rig, copy_rot, name, 'owner_space')
    if limit:
        limit_rot = rig_pb.constraints.new('LIMIT_ROTATION')
        limit_rot.use_limit_x, limit_rot.use_limit_y, limit_rot.use_limit_z = limit['use']
        limit_rot.min_x, limit_rot.min_y, limit_rot.min_z = (math.radians(m) for m in limit['min'])
        limit_rot.max_x, limit_rot.max_y, limit_rot.max_z = (math.radians(m) for m in limit['max'])
        limit_rot.owner_space = limit['space']
    if transform:
        trans_rot = rig_pb.constraints.new('TRANSFORM')
        trans_rot.target, trans_rot.subtarget = rig, transform['subtarget']
        trans_rot.map_from, trans_rot.map_to = 'ROTATION', 'ROTATION'
        rotation = [math.radians(-360), math.radians(360)]
        inverted = [math.radians(360), math.radians(-360)]
        if transform['use'][0]:
            trans_rot.from_min_x_rot, trans_rot.from_max_x_rot = rotation
            trans_rot.to_min_x_rot, trans_rot.to_max_x_rot = inverted if transform['invert'][0] else rotation
        if transform['use'][1]:
            trans_rot.from_min_y_rot, trans_rot.from_max_y_rot = rotation
            trans_rot.to_min_y_rot, trans_rot.to_max_y_rot = inverted if transform['invert'][1] else rotation
        if transform['use'][2]:
            trans_rot.from_min_z_rot, trans_rot.from_max_z_rot = rotation
            trans_rot.to_min_z_rot, trans_rot.to_max_z_rot = inverted if transform['invert'][2] else rotation
        trans_rot.target_space, trans_rot.owner_space = transform['space']
        trans_rot.mix_mode_rot, trans_rot.influence = transform['mode'], transform['influence'] if 'influence' in transform else 1.0
        # target and owner spaces can driven from rotation inheritance... (for FK bones)...
        if drive:
            add_space_drivers(rig, trans_rot, name, 'target_space')
            add_space_drivers(rig, trans_rot, name, 'owner_space')

def add_scale_constraints(rig, name, copy, limit):
    rig_pb = rig.pose.bones.get(name)
    if copy:
        copy_sca = rig_pb.constraints.new('COPY_SCALE')
        copy_sca.target, copy_sca.subtarget = rig, copy['subtarget']
        copy_sca.use_x, copy_sca.use_y, copy_sca.use_z = copy['use']
        copy_sca.power, copy_sca.use_make_uniform = copy['power'], copy['uniform']
        copy_sca.use_offset, copy_sca.use_add = copy['offset'], copy['additive']
        copy_sca.target_space, copy_sca.owner_space = copy['space']
        axes = ""
        if copy['use'][0]:
            axes = axes + "X"
        if copy['use'][1]:
            axes = axes + "Y"
        if copy['use'][2]:
            axes = axes + "Z"
        end = " Scale" if axes else "Scale"
        copy_sca.name = copy['name'] if 'name' in copy else "Copy " + axes + end
    if limit:
        limit_sca = rig_pb.constraints.new('LIMIT_SCALE')
        limit_sca.use_min_x, limit_sca.use_min_y, limit_sca.use_min_z = limit['use']
        limit_sca.use_max_x, limit_sca.use_max_y, limit_sca.use_max_z = limit['use']
        limit_sca.min_x, limit_sca.min_y, limit_sca.min_z = limit['min']
        limit_sca.max_x, limit_sca.max_y, limit_sca.max_z = limit['max']
        limit_sca.owner_space = limit['space']
        if 'name' in limit:
            limit_sca.name = limit['name']

def add_location_constraints(rig, name, copy, limit, drive=False):
    rig_pb = rig.pose.bones.get(name)
    if copy:
        copy_loc = rig_pb.constraints.new('COPY_LOCATION')
        copy_loc.target, copy_loc.subtarget = rig, copy['subtarget']
        copy_loc.use_x, copy_loc.use_y, copy_loc.use_z = copy['use']
        copy_loc.invert_x, copy_loc.invert_y, copy_loc.invert_z = copy['invert']
        copy_loc.use_offset = copy['offset']
        copy_loc.target_space, copy_loc.owner_space = copy['space']
        copy_loc.influence = copy['influence'] if 'influence' in copy else 1.0
        axes = ""
        if copy['use'][0]:
            axes = axes + "X"
        if copy['use'][1]:
            axes = axes + "Y"
        if copy['use'][2]:
            axes = axes + "Z"
        end = " Location" if axes else "Location"
        copy_loc.name = copy['name'] if 'name' in copy else "Copy " + axes + end
        # target and owner spaces can driven from rotation inheritance... (for FK bones)...
        if drive:
            add_space_drivers(rig, copy_loc, name, 'target_space')
            add_space_drivers(rig, copy_loc, name, 'owner_space')
    if limit:
        limit_loc = rig_pb.constraints.new('LIMIT_LOCATION')
        limit_loc.use_min_x, limit_loc.use_min_y, limit_loc.use_min_z = limit['use']
        limit_loc.use_max_x, limit_loc.use_max_y, limit_loc.use_max_z = limit['use']
        limit_loc.min_x, limit_loc.min_y, limit_loc.min_z = limit['min']
        limit_loc.max_x, limit_loc.max_y, limit_loc.max_z = limit['max']
        limit_loc.owner_space = limit['space']
    return copy_loc if copy else None

def add_kinematic_constraints(rig, name, ik):
    rig_pb = rig.pose.bones.get(name)
    if ik:
        # create the IK constraint... (target should always exist)...
        ik_con = rig_pb.constraints.new('IK')
        ik_con.target, ik_con.subtarget = rig, ik['target']
        ik_con.chain_count, ik_con.use_stretch = ik['length'], ik['stretch']
        if 'name' in ik:
            ik_con.name = ik['name']
        # if we have a pole bone...
        pole_eb = rig.data.edit_bones.get(ik['pole'])
        if pole_eb:
            # also get the start and target bones...
            start_eb = rig.data.edit_bones[name]
            for _ in range(0, ik['length'] - 1):
                start_eb = start_eb.parent
            target_eb = rig.data.edit_bones.get(ik['target'])
            # in order to calculate the pole angle...
            angle = get_pole_angle(start_eb, target_eb, pole_eb)
            ik_con.pole_target, ik_con.pole_subtarget, ik_con.pole_angle = rig, ik['pole'], angle

def add_rigging_bone(rig, name, parent, head, tail, rolls, rotation=True, scale='FULL'):
    rig_eb = rig.data.edit_bones.get(name)
    if not rig_eb:
        rig_eb = rig.data.edit_bones.new(name)
    rig_eb.head, rig_eb.tail = head, tail
    rig_eb.roll = get_shortest_roll(rig_eb, rolls)
    rig_eb.parent = rig.data.edit_bones.get(parent)
    rig_eb.use_inherit_rotation, rig_eb.inherit_scale = rotation, scale
    return rig_eb

def add_shared_bone(oriented, rig, prefix, name, key, search=True, length=None):
    # if we have an origin bone...
    shared = prefix + name
    shared_pb = oriented.pose.bones.get(name)
    if shared_pb:
        # if the shared bone is already rigged...
        if get_existing_bone(rig, shared_pb):
            # update the name... (never trust users with naming)...
            shared = get_existing_bone(rig, shared_pb)
        # if the shared bone does not yet exist in the armature...
        shared_eb = rig.data.edit_bones.get(shared)
        if not shared_eb:
            # we can add and constrain it...
            oriented_eb = oriented.data.edit_bones.get(name)
            shared_eb = rig.data.edit_bones.new(shared)
            # if this is a root bone...
            if key == 'root':
                # root bones should always align to armature space... (it's mostly preferential but this is the most logical)...
                shared_eb.head, shared_eb.tail, shared_eb.roll = oriented_eb.head, oriented_eb.head + (Vector((0.0, 1.0, 0.0)) * oriented_eb.length), 0.0
            else:
                shared_eb.head, shared_eb.tail, shared_eb.roll = oriented_eb.head, oriented_eb.tail, oriented_eb.roll
                # an explicit length overrides the natural tail distance, keeping the same direction...
                if length is not None:
                    shared_eb.tail = shared_eb.head + (oriented_eb.y_axis * length)
            # update from edit mode and add the child of constraints to the oriented bone...
            rig.update_from_editmode()
            add_parent_constraints(oriented, rig, name, shared)
        # if we want to update parenting for new and existing bones...
        if search:
            set_bone_hierarchy(oriented, rig, name, shared)
    # return the name to update the names dictionary...
    return shared

def set_bone_hierarchy(oriented, rig, name, shared):
    # adopts any already rigged children as our own, then adopts a rigged parent if we don't already have one...
    shared_pb, shared_eb = oriented.pose.bones.get(name), rig.data.edit_bones.get(shared)
    # then check down through the hierarchy...
    children = [c for c in shared_pb.children]
    while children:
        # if the child is already rigged...
        child_pb = children.pop()
        if get_existing_bone(rig, child_pb):
            # it should use the shared bone...
            child = get_existing_bone(rig, child_pb)
            child_eb = rig.data.edit_bones.get(child)
            child_eb.parent = shared_eb
        else:
            # else append it's children to be checked...
            children = children + [c for c in child_pb.children]
    # then check up through the hierarchy to find the next rigged parent...
    parent_pb = shared_pb.parent
    while parent_pb and not shared_eb.parent:
        # if we find one use it...
        if parent_pb and get_existing_bone(rig, parent_pb):
            parent = get_existing_bone(rig, parent_pb)
            parent_eb = rig.data.edit_bones.get(parent)
            shared_eb.parent = parent_eb
        else:
            # else go to the next parent...
            parent_pb = parent_pb.parent

def get_shared_default(rig, name):
    # false only when an existing rigging modules bone collection already claims this bone - the first module to touch a shared bone keeps edit/styling rights over it by default...
    # reads membership off the bone itself, not the collections own bones list - the latter reads empty while the armature is in edit mode...
    bone = rig.data.bones.get(name) if rig else None
    if not bone:
        return True
    rigging_types = {"Opposable", "Plantigrade", "Digitigrade", "Spline", "Scalar", "Curl", "Twist", "Root", "Custom"}
    return not any(c.get('Group Type') in rigging_types for c in bone.collections)

def get_is_root(rig, name):
    # chains can never edit/claim a bone that already belongs to an actual Root Controls module, regardless of their own shared setting...
    bone = rig.data.bones.get(name) if rig else None
    if not bone:
        return False
    return any(c.get('Group Type') == "Root" for c in bone.collections)

def set_bone_color(rig, name, color):
    rig_bb = rig.data.bones.get(name)
    if rig_bb:
        rig_bb.color.palette = color.palette

def save_custom_shapes(shapes):
    directory = utilities.functions.get_shapes_directory()
    # if the directory exists and is writable...
    if os.path.isdir(directory) and os.access(directory, os.W_OK):
        # iterate over shapes...
        for shape in shapes:
            # get the name replacing any non alpha numeric characters and leading/trailing underscores... (lower case)...
            filename = re.sub(r'[^0-9a-zA-Z]+', '_', shape.name).strip('_').lower()
            # put my leading/trailing underscores and the .py extension back into the name...
            filename = filename.lower() + ".py"
            filepath = os.path.join(directory, filename)
            # get the shape data properties we want to save... (we already know the name)...
            data = {'name' : shape.name, 'vertices' : [], 'edges' : [], 'faces' : [], 'sharps' : []}
            # get the mesh evaluated... (so any/all modifiers are applied)...
            depsgraph = bpy.context.evaluated_depsgraph_get()
            evaluated = shape.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            # get the face vertex indices for the faces list...
            for face in mesh.polygons:
                data['faces'].append([i for i in face.vertices])
            # get the edge vertex indices for the edges list...
            for edge in mesh.edges:
                data['edges'].append([i for i in edge.vertices])
            # get the vertex coordinates for the vertex list...
            for vert in mesh.vertices:
                data['vertices'].append((vert.co.x, vert.co.y, vert.co.z))
            # get the sharp edges... (defaulting to false if there aren't any)...
            sharps = mesh.attributes.get('sharp_edge')
            data['sharps'] = [s.value for s in sharps.data] if sharps else [False for e in data['edges']]
            # good practice to clear the evaluation...
            evaluated.to_mesh_clear()
            # write the python file...
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("shape = ")
                pprint.pprint(data, stream=f, width=256, compact=True)
                f.write("\n")

def get_shape_rotation(rig, name, shape, directions, invert, first=None):
    rig_bb = rig.data.bones[name]
    axes = get_bone_axes(rig_bb, ['+X', '-X', '+Y', '-Y', '+Z', '-Z'])
    # if the space is bone space we don't need to get the closest...
    if shape.space == 'BONE':
        forward, upward = axes[shape.forward], axes[shape.upward]
    elif first:
        # forward is always whichever of our own axes points closest towards the first chain bone...
        first_bb = rig.data.bones[first]
        _, direction = utilities.functions.get_distance_direction(rig_bb.matrix_local.translation, first_bb.matrix_local.translation)
        label, forward = utilities.functions.get_closest_axis(direction, axes)
        # then upward is whichever of our remaining axes best matches the desired upward direction...
        remaining = {l : v for l, v in axes.items() if l[-1] != label[-1]}
        _, upward = utilities.functions.get_closest_axis(directions[shape.upward], remaining)
    else:
        # else prioritise upward, matching whichever of our own axes fits it best, then pick forward from whats left...
        label, upward = utilities.functions.get_closest_axis(directions[shape.upward], axes)
        remaining = {l : v for l, v in axes.items() if l[-1] != label[-1]}
        _, forward = utilities.functions.get_closest_axis(directions[shape.forward], remaining)
    # if we want to invert upwards...
    if invert:
        upward = -upward
    # forward and upward axes are always perpendicular, cross them to complete a right handed frame for the shapes X axis...
    y_axis, z_axis = forward.normalized(), upward.normalized()
    x_axis = y_axis.cross(z_axis)
    # this is the shapes target orientation in the same (armature local) space the bone axes are in...
    world = Matrix((x_axis, y_axis, z_axis)).transposed()
    # bring it back relative to the bones own rest orientation, since that's the space...
    bone = rig_bb.matrix_local.to_3x3().normalized()
    local = bone.inverted() @ world
    return local

def set_bone_shape(rig, name, shape, axes, rigging, offset=0.3, base=0.3, first=None):
    if shape.mesh != 'NONE':
        # the bone must exist before calling this function...
        rig_pb = rig.pose.bones.get(name)
        # get and set the shape mesh... (loading if needed)...
        mesh = utilities.functions.get_shape_mesh(shape.mesh)
        rig_pb.custom_shape = mesh
        invert, scale, translation = False, shape.scale.copy(), shape.translation.copy()
        # scale translation to the bones length...
        translation = translation * rig_pb.length
        # if the spline chain has a negative offset.....
        if rigging == 'SPLINE' and offset < 0.0:
                # invert it's default upward directions...
                invert = True
        # the curl chains offset is done purely on the shapes...
        if rigging == 'CURL':
            if shape.name != 'origin' and offset < 0.0:
                invert = True
            if shape.name in {'forward', 'target'}:
                scale = scale * (1 + abs(offset))
        # some bones should use different spaces...
        directions = {}
        if shape.space == 'WORLD':
            directions = {
                '+X' : Vector((1.0, 0.0, 0.0)), '-X' : Vector((-1.0, 0.0, 0.0)),
                '+Y' : Vector((0.0, 1.0, 0.0)), '-Y' : Vector((0.0, -1.0, 0.0)),
                '+Z' : Vector((0.0, 0.0, 1.0)), '-Z' : Vector((0.0, 0.0, -1.0))}
        elif shape.space == 'CHAIN':
            directions = {
                '+X' : axes[0], '-X' : -axes[0],
                '+Y' : axes[1], '-Y' : -axes[1],
                '+Z' : axes[2], '-Z' : -axes[2]}
        # get the default shape rotation and compose it with the editable rotation...
        default = get_shape_rotation(rig, name, shape, directions, invert, first)
        edited = Euler(Vector(shape.rotation), 'XYZ').to_matrix()
        rotation = (default @ edited).to_euler('XYZ')

        # if this is a pole we want to keep it the same size regardless of offset...
        if shape.name == 'pole':
            scale = scale * (abs(base) / max(abs(offset), 1e-6))
        
        rig_pb.custom_shape_translation = translation
        rig_pb.custom_shape_rotation_euler = rotation
        rig_pb.custom_shape_scale_xyz = scale
        # if we have primary and tertiary axes...
        if axes:
            cardinals = {
                '+X' : Vector((1.0, 0.0, 0.0)), '-X' : Vector((-1.0, 0.0, 0.0)),
                '+Y' : Vector((0.0, 1.0, 0.0)), '-Y' : Vector((0.0, -1.0, 0.0)),
                '+Z' : Vector((0.0, 0.0, 1.0)), '-Z' : Vector((0.0, 0.0, -1.0))}
            # check chain axes against cardinal directions for mirroring... (tertiary, primary, then secondary)...
            closest, _ = utilities.functions.get_closest_axis(axes[0], cardinals)
            if not closest == '-X':
                closest, _ = utilities.functions.get_closest_axis(axes[1], cardinals)
            if not closest == '-X':
                closest, _ = utilities.functions.get_closest_axis(axes[2], cardinals)
            if closest == '-X':
                angles = Vector(shape.rotation)
                edited = Euler(Vector((angles.x, -angles.y, -angles.z)), 'XYZ').to_matrix()
                rotation = (default @ edited).to_euler('XYZ')
                rig_pb.custom_shape_rotation_euler = rotation
                rig_pb.custom_shape_scale_xyz = Vector((-scale.x, scale.y, scale.z))
                rig_pb.custom_shape_translation = Vector((-translation.x, translation.y, translation.z))

def get_active_module(rig, bone_name):
    # whichever module owns this bone, if any...
    for item in rig.data.mmt.rigging:
        collection = rig.data.collections_all.get(item.module)
        if collection and collection.bones.get(bone_name):
            return item
    return None

def get_bone_collection(rig, group, bone=""):
    # using flags to search instead of names... (for renaming)...
    collection = None
    # for all bone collections...
    for coll in rig.data.collections_all:
        # if the collection has the group type flag and it's the one we are looking for...
        if coll.get('Group Type') and coll.get('Group Type') == group:
            # if there is no bone input... (unique collections)...
            if not bone:
                collection = coll
            # else if there is the collection must have the bone... (ambiguous collections)...
            elif coll.bones.get(bone):
                collection = coll
    return collection

def copy_retargeting_settings(rig, added):
    # carry retargeting settings over onto the rigs forward bones from whichever armature they were created from - a
    # plain name match is enough to find them, no need to know the underlying forward-prefix mapping here...
    _, oriented, original = utilities.functions.get_armature_hierarchy(rig)
    oriented = oriented or original
    if not oriented:
        return
    for name in added:
        oriented_pb, rig_pb = oriented.pose.bones.get(name), rig.pose.bones.get(name)
        if oriented_pb and rig_pb:
            rig_pb.mmt.updating = True
            rig_pb.mmt.rotation = oriented_pb.mmt.rotation
            rig_pb.mmt.translation = oriented_pb.mmt.translation
            rig_pb.mmt.mirror = oriented_pb.mmt.mirror
            rig_pb.mmt.updating = False

def set_bone_groups(rig, name, groups, module):
    # if the modules collection doesn't exist create it...
    rig_pb = rig.data.bones.get(name)
    if not rig_pb:
        # tolerate unsynchronized edit bones... (the pose bone remains available in object mode)...
        return
    modules = get_bone_collection(rig, "Modules")
    if not modules:
        modules = rig.data.collections.new("Modules")
        modules['Group Type'] = "Modules"
        modules.is_visible = False
    # if the general collection doesn't exist create it under the modules...
    general = get_bone_collection(rig, "General")
    if not general:
        general = rig.data.collections.new("General", parent=modules)
        general['Group Type'] = "General"
    # if the limited collection doesn't exist create it under the modules...
    limited = get_bone_collection(rig, "Limited")
    if not limited:
        limited = rig.data.collections.new("Limited", parent=modules)
        limited['Group Type'] = "Limited"
    # if we input a module collection... (adding general bones does not require one)...
    if module:
        # create it if it doesn't already exist...
        rigging = rig.data.collections_all.get(module)
        if not rigging:
            rigging = rig.data.collections.new(module, parent=modules)
            rigging['Group Type'] = module.split(" ")[0]  # caller resyncs once its whole build is done, not here...
        # and assign the bone to it...
        rigging.assign(rig_pb)
    # for each group the bone is assigned to...
    for group in groups:
        # create it's category if it doesn't exist... (general and limited always exist)...
        category = get_bone_collection(rig, group.capitalize())
        if not category:
            category = rig.data.collections.new(group.capitalize())
            category['Group Type'] = group.capitalize()
        # assign it to its group...
        category.assign(rig_pb)
    # make sure the modules group is at the bottom of the list... (if it's not been parented somewhere)...
    if rig.data.collections.get(modules.name):
        index = rig.data.collections.find(modules.name)
        rig.data.collections.move(index, len(rig.data.collections) - 1)

def add_mirrored_module(rig, rigging, name, settings):
    # the mirrored copy never goes through mmt.add, so update its own list entry in place rather than duplicating it...
    index = next((i for i, m in enumerate(rig.data.mmt.rigging) if m.module == name), -1)
    if index >= 0:
        item = rig.data.mmt.rigging[index]
    else:
        item = rig.data.mmt.rigging.add()
    item.updating = True
    item.module, item.rigging, item.is_mirrored = name, rigging, True
    set_default_settings(item.settings, get_settings_snapshot(settings))
    item.updating = False

def set_module_moved(rig, direction):
    # bone collection order was never used for anything else, so just reorder the list directly...
    index = rig.data.mmt.module
    if not (0 <= index < len(rig.data.mmt.rigging)):
        return
    target = index + (-1 if direction == 'UP' else 1)
    if target < 0 or target >= len(rig.data.mmt.rigging):
        return
    rig.data.mmt.rigging.move(index, target)
    rig.data.mmt.module = target

def get_space_cache(rig):
    # blender can quietly reset a surviving transforms drivers own space when edit bones elsewhere get deleted...
    cache = {}
    if not rig.animation_data:
        return cache
    for fcurve in rig.animation_data.drivers:
        for var_index, var in enumerate(fcurve.driver.variables):
            if var.type == 'TRANSFORMS':
                for target_index, target in enumerate(var.targets):
                    cache[(fcurve.data_path, fcurve.array_index, var_index, target_index)] = target.transform_space
    return cache

def set_space_cache(rig, cache):
    # put back any transform spaces blender reset behind our back while we were editing bones...
    if not rig.animation_data:
        return
    for fcurve in rig.animation_data.drivers:
        for var_index, var in enumerate(fcurve.driver.variables):
            if var.type == 'TRANSFORMS':
                for target_index, target in enumerate(var.targets):
                    key = (fcurve.data_path, fcurve.array_index, var_index, target_index)
                    if key in cache and target.transform_space != cache[key]:
                        target.transform_space = cache[key]

def remove_rigging_module(oriented, rig, module, remove_entry=True):
    # find the bones that belong only to this module... (a shared bone survives if another module still has it)...
    collection = rig.data.collections_all.get(module)
    if not collection:
        # remove orphaned entries left behind by failed or interrupted builds...
        if remove_entry:
            index = next((i for i, item in enumerate(rig.data.mmt.rigging) if item.module == module), -1)
            if index >= 0:
                rig.data.mmt.rigging.remove(index)
                rig.data.mmt.module = min(index, len(rig.data.mmt.rigging) - 1)
                remove_empty_armature(oriented, rig)
        return
    # cache surviving drivers own transform spaces before we start deleting bones elsewhere...
    spaces = get_space_cache(rig)
    module_names = {b.name for b in collection.bones}
    rigging_types = {"Opposable", "Plantigrade", "Digitigrade", "Spline", "Scalar", "Curl", "Twist", "Root", "Custom"}
    used_elsewhere = {b.name for c in rig.data.collections_all
        if c != collection and c.get('Group Type') in rigging_types for b in c.bones}
    remove = [n for n in module_names if n not in used_elsewhere]
    # remove any spline curves attached to the bones we're about to remove first... (to avoid console spam)...
    for name in remove:
        pose_bone = rig.pose.bones.get(name)
        if not pose_bone:
            continue
        for constraint in list(pose_bone.constraints):
            if constraint.type == 'SPLINE_IK' and constraint.target:
                curve, curve_data = constraint.target, constraint.target.data
                bpy.data.objects.remove(curve, do_unlink=True)
                if curve_data and curve_data.users == 0:
                    bpy.data.curves.remove(curve_data)
    # strip any drivers living on the bones we're about to remove first... (to avoid console spam)...
    if rig.animation_data:
        prefixes = tuple('pose.bones["' + n + '"]' for n in remove)
        for fcurve in list(rig.animation_data.drivers):
            if fcurve.data_path.startswith(prefixes):
                rig.animation_data.drivers.remove(fcurve)
    # and remove the oriented armatures parent transform child ofs targeting these bones first too... (to avoid console spam)...
    for child_pb in oriented.pose.bones:
        child_of = child_pb.constraints.get("Parent Transform")
        if child_of and child_of.target == rig and child_of.subtarget in remove:
            for con in list(child_pb.constraints):
                child_pb.constraints.remove(con)
    # a shared ending bone can survive with a leftover constraint another module aimed at what we're deleting...
    for pose_bone in rig.pose.bones:
        if pose_bone.name in remove:
            continue
        for con in list(pose_bone.constraints):
            if getattr(con, 'target', None) == rig and getattr(con, 'subtarget', '') in remove:
                pose_bone.constraints.remove(con)
    # save our current mode... (if there is no contextual object then we must be in object mode)...
    last_mode = bpy.context.object.mode if bpy.context.object else 'OBJECT'
    selected = [o for o in bpy.context.selected_objects] if bpy.context.object else []
    # rig is commonly hidden while animating elsewhere, unhide it so it can be selected/entered...
    hidden = utilities.functions.get_hidden_objects({rig})
    utilities.functions.set_objects_unhidden(hidden)
    # ensure we have nothing else selected and take the rigging armature into edit mode...
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    # remove the modules own bones...
    for name in remove:
        edit_bone = rig.data.edit_bones.get(name)
        if edit_bone:
            rig.data.edit_bones.remove(edit_bone)
    # clean up any invalid drivers...
    remove_invalid_drivers(rig)
    bpy.ops.object.mode_set(mode='OBJECT')
    # the collection is no longer needed, whatever's left in it (general bones) still belongs elsewhere...
    rig.data.collections.remove(collection)
    # drop this modules own list entry directly - no need to rescan every other module too, they're untouched...
    if remove_entry:
        index = next((i for i, m in enumerate(rig.data.mmt.rigging) if m.module == module), -1)
        if index >= 0:
            rig.data.mmt.rigging.remove(index)
            rig.data.mmt.module = min(index, len(rig.data.mmt.rigging) - 1)
    # clear any constraints from the bones being driven on the oriented armature...
    set_parent_constraints(oriented, rig)
    
    # go back into object mode to reselect anything we deselected...
    for ob in selected:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = rig
    # then return our mode to whatever it was, and rehide anything that wasn't visible to begin with...
    bpy.ops.object.mode_set(mode=last_mode)
    for obj in hidden:
        obj.hide_set(True)
    # and put back any transform spaces blender reset while we were deleting bones...
    set_space_cache(rig, spaces)
    if remove_entry:
        remove_empty_armature(oriented, rig)

def remove_empty_armature(oriented, rig):
    if rig.data.mmt.rigging:
        return
    # remove the empty rig and return to the oriented armature...
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    data = rig.data
    bpy.data.objects.remove(rig, do_unlink=True)
    if not data.users:
        bpy.data.armatures.remove(data)
    oriented.hide_set(False)
    oriented.select_set(True)
    bpy.context.view_layer.objects.active = oriented
    bpy.ops.object.mode_set(mode='POSE')

def add_rigging_armature(oriented):
    # add one armature that will serve as the new animation driver...
    data = bpy.data.armatures.new(oriented.name + "_Rigging")
    rig = bpy.data.objects.new(oriented.name + "_Rigging", data)
    collections = [coll for coll in oriented.users_collection]
    for collection in collections:
        collection.objects.link(rig)
    # keep the scene-level rig above the oriented and original armatures without changing their transforms...
    rig.matrix_world = oriented.matrix_world
    oriented_world = oriented.matrix_world.copy()
    oriented.parent = rig
    oriented.matrix_world = oriented_world
    rig.show_in_front, rig.data.relation_line_position = True, 'HEAD'
    rig.data.axes_position = oriented.data.axes_position
    # and flag them with custom properties...
    oriented['Armature Type'], rig['Armature Type'] = "Oriented", "Rigging"
    return rig

def set_default_settings(settings, defaults):
    # iterate through the default settings dictionary...
    for setting, defaults in defaults.items():
        # if the item is a pointer... (origin, end, root)...
        if settings.bl_rna.properties[setting].type == 'POINTER':
            # it's stored as a dictionary...
            item = getattr(settings, setting)
            for prop, value in defaults.items():
                setattr(item, prop, value)
        # if the item is a collection... (chain, naming, colors, shapes)...
        elif settings.bl_rna.properties[setting].type == 'COLLECTION':
            # it's stored as an array of dictionaries... (always cleared for now)...
            items = getattr(settings, setting)
            items.clear()
            for default in defaults:
                item = items.add()
                for prop, value in default.items():
                    # rotations are stored in degree angles...
                    if prop == 'rotation':
                        # and need converting to radians...
                        value = tuple(math.radians(a) for a in value)
                    setattr(item, prop, value)
        else:
            # else it's stored as a single property...
            setattr(settings, setting, defaults)

def set_auto_mirror(settings, selection, origin):
    # enable mirroring if every selected chain bone has a flipped counterpart...
    mirrored = [utilities.functions.get_mirrored_name(pb.name)[0] for pb in selection]
    armature = selection[0].id_data if selection else None
    settings.mirror = bool(armature and
        all(name and name in armature.data.bones for name in mirrored))

def add_chain_names(settings, count, ending=False):
    # add blank required suffixes, so an incomplete selection can still be finished off in the UI...
    existing = len(settings.suffices)
    for index in range(existing, count + (1 if ending else 0)):
        suffix = settings.suffices.add()
        suffix.name = 'ending' if ending and index == count else utilities.functions.get_ordinal_index(index + 1).lower()
        suffix.affix, suffix.unique, suffix.required = '', True, True

def set_mirrored_settings(settings, mirrored):
    pointers = ['origin', 'ending', 'root']
    collections = ['suffices']
    # iterate through the settings properties...
    for setting in settings.bl_rna.properties:
        # if the item is a pointer... (origin, end, root)...
        identifier = setting.identifier
        if settings.bl_rna.properties[identifier].type == 'POINTER' and identifier != 'rna_type':
            item = getattr(settings, identifier)
            mirror = getattr(mirrored, identifier)
            # copy all of its not read only values into the mirrored item...
            for prop in item.bl_rna.properties:
                if not prop.is_readonly:
                    value = getattr(item, prop.identifier)
                    setattr(mirror, prop.identifier, value)
                    # only try to mirror if it's the affix of a suffix pointer... (empty if not found)...
                    if identifier in pointers and prop.identifier == 'affix':
                        name, _ = utilities.functions.get_mirrored_name(value)
                        setattr(mirror, prop.identifier, name)
        # if the item is a collection... (chain, naming, colors, shapes)...
        elif settings.bl_rna.properties[identifier].type == 'COLLECTION':
            # iterate through its items adding the mirror entries... (always cleared for now)...
            items = getattr(settings, identifier)
            mirrors = getattr(mirrored, identifier)
            mirrors.clear()
            for item in items:
                mirror = mirrors.add()
                # copy all of its not read only values into the mirrored item...
                for prop in item.bl_rna.properties:
                    if not prop.is_readonly:
                        value = getattr(item, prop.identifier)
                        setattr(mirror, prop.identifier, value)
                        # only try to mirror if it's the affix of a suffix item... (same name both sides if not found)...
                        if identifier in collections and prop.identifier == 'affix':
                            name, _ = utilities.functions.get_mirrored_name(value)
                            setattr(mirror, prop.identifier, name or value)
        # settings that are not readonly...
        if not setting.is_readonly:
            value = getattr(settings, identifier)
            # a chosen tertiary axis needs flipping to stay mirrored... (AUTO and the Z roll axis are unaffected)...
            if identifier == 'axis' and value in {'+X', '-X'}:
                value = '-X' if value == '+X' else '+X'
            # just get copied over otherwise... (might need to mirror some of these in the future)...
            setattr(mirrored, identifier, value)

def get_settings_snapshot(settings):
    # the inverse of set_default_settings, captures current values into a plain dict shaped like get_X_defaults()...
    snapshot = {}
    for prop in settings.bl_rna.properties:
        identifier = prop.identifier
        if identifier == 'rna_type':
            continue
        # if the item is a pointer... (origin, end, root)...
        if prop.type == 'POINTER':
            item = getattr(settings, identifier)
            snapshot[identifier] = {p.identifier : get_snapshot_value(getattr(item, p.identifier)) for p in item.bl_rna.properties if not p.is_readonly}
        # if the item is a collection... (chain, naming, colors, shapes)...
        elif prop.type == 'COLLECTION':
            entries = []
            for item in getattr(settings, identifier):
                entry = {p.identifier : get_snapshot_value(getattr(item, p.identifier)) for p in item.bl_rna.properties if not p.is_readonly}
                # rotations are stored in radians, set_default_settings expects degrees...
                if 'rotation' in entry:
                    entry['rotation'] = tuple(math.degrees(a) for a in entry['rotation'])
                entries.append(entry)
            snapshot[identifier] = entries
        elif not prop.is_readonly:
            snapshot[identifier] = get_snapshot_value(getattr(settings, identifier))
    return snapshot

def get_snapshot_value(value):
    # arrays and vectors need converting to plain tuples so they survive being stashed in a dictionary...
    if hasattr(value, '__len__') and not isinstance(value, str):
        return tuple(value)
    return value

def get_saved_defaults(rigging):
    # the last naming/colors/shapes settings used for this rigging type, across any rig or file...
    prefs = utilities.functions.get_addon_preferences(bpy.context)
    entry = prefs.defaults.get(rigging)
    if not entry or not entry.json:
        return None
    try:
        return json.loads(entry.json)
    except ValueError:
        return None

def set_saved_defaults(rigging, snapshot):
    # save reusable naming, display and numeric settings... (selections and mirrors remain per-instance)...
    defaults = {category : snapshot[category] for category in ('prefices', 'colors', 'shapes')}
    defaults['settings'] = {name: snapshot[name] for name in ('offset', 'position', 'count', 'influences', 'floor', 'inverse', 'axis', 'axes') if name in snapshot}
    prefs = utilities.functions.get_addon_preferences(bpy.context)
    entry = prefs.defaults.get(rigging)
    if not entry:
        entry = prefs.defaults.add()
        entry.name = rigging
    entry.json = json.dumps(defaults)

def merge_saved_defaults(settings, saved):
    # overlays saved values onto freshly loaded defaults by matching role name, never replacing collections outright...
    if not saved:
        return
    for category in ('prefices', 'colors', 'shapes'):
        entries = {entry['name'] : entry for entry in saved.get(category, [])}
        for item in getattr(settings, category):
            entry = entries.get(item.name)
            if not entry:
                continue
            for prop, value in entry.items():
                if prop == 'name':
                    continue
                # rotations are saved in degrees, same convention set_default_settings expects...
                if prop == 'rotation':
                    value = tuple(math.radians(a) for a in value)
                setattr(item, prop, value)
    for name, value in saved.get('settings', {}).items():
        if name == 'axes' and isinstance(value, list):
            for item, saved_item in zip(settings.axes, value):
                for prop, item_value in saved_item.items():
                    if hasattr(item, prop):
                        setattr(item, prop, item_value)
            continue
        if hasattr(settings, name):
            setattr(settings, name, value)

def update_module_rigging(self, context):
    # a fresh type pick populates settings from selection then builds it, exactly like the old operators invoke did...
    if self.updating:
        return
    rig, oriented, _ = utilities.functions.get_armature_hierarchy(context.object)
    if not oriented or not rig:
        return
    if self.rigging == 'NONE':
        # switching back to none just tears down whatever rigging was already there...
        if self.module:
            remove_rigging_module(oriented, rig, self.module)
        return
    # a non-empty module here means this item is already built, not a fresh pick from the enum...
    if self.module:
        return
    self.updating, rigging, added = True, self.rigging, None
    module_file = get_module_file(rigging)
    if module_file:
        invoke = getattr(module_file, 'invoke_' + rigging.lower() + '_module')
        execute = getattr(module_file, 'execute_' + rigging.lower() + '_module')
        success = invoke(context, self)
        pending = get_settings_snapshot(self.settings) if success else None
        added = execute(context, self) if success else None
        if added is not None:
            set_saved_defaults(rigging, pending)
            copy_retargeting_settings(rig, added)
    if added is not None:
        self.updating = False
        return
    self.rigging, self.updating = 'NONE', False

def get_module_file(rigging):
    # deferred imports avoid a circular import...
    if rigging == 'TWIST':
        from .modules import twist as module_file
    elif rigging == 'OPPOSABLE':
        from .modules import opposable as module_file
    elif rigging == 'PLANTIGRADE':
        from .modules import plantigrade as module_file
    elif rigging == 'DIGITIGRADE':
        from .modules import digitigrade as module_file
    elif rigging == 'SCALAR':
        from .modules import scalar as module_file
    elif rigging == 'SPLINE':
        from .modules import spline as module_file
    elif rigging == 'CURL':
        from .modules import curl as module_file
    elif rigging == 'ROOT':
        from .modules import root as module_file
    elif rigging == 'CUSTOM':
        from .modules import custom as module_file
    else:
        module_file = None
    return module_file

def set_module_restored(context, item, rigging, settings_data):
    # rebuilds a module straight from previously cached settings, bypassing the selection based invoke defaults entirely...
    item.updating = True
    try:
        item.rigging, item.is_mirrored = rigging, False
        utilities.functions.set_deserialized_settings(item.settings, settings_data)
        module_file = get_module_file(rigging)
        if not module_file:
            return False
        # keep restore transactional so mirrored settings callbacks cannot rebuild incomplete modules...
        execute = getattr(module_file, 'execute_' + rigging.lower() + '_module')
        added = execute(context, item)
        if added is not None:
            rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
            if rig:
                copy_retargeting_settings(rig, added)
        return added is not None
    finally:
        item.updating = False

def set_refreshed_rigging(context, oriented, rig):
    # rebuild every primary rigging module from its current settings, caching plain data first... (removing blender collection entries invalidates their property groups)...
    cached = [(item.module, item.rigging, utilities.functions.get_serialized_settings(item.settings))
        for item in rig.data.mmt.rigging if item.rigging != 'NONE' and is_primary_module(item)]
    # remember the full original list order so it can be restored after rebuilding, since add_mirrored_module re-appends a rebuilt primarys mirror at the tail instead of beside it, and dependent modules (eg spline taking root as its own origin) need to rebuild in that same order too...
    original_order = [item.module for item in rig.data.mmt.rigging if item.rigging != 'NONE']
    # remove_entry=False here - removing list entries one at a time as we go would empty rig.data.mmt.rigging partway through and delete the whole rig object out from under us, so clear the list ourselves in one batch once everything is gone...
    for module_name, _, _ in reversed(cached):
        item = next((candidate for candidate in rig.data.mmt.rigging if candidate.module == module_name), None)
        if not item:
            continue
        counterpart = next((candidate for candidate in rig.data.mmt.rigging
            if candidate.module == item.mirrored_name), None)
        if counterpart:
            remove_rigging_module(oriented, rig, counterpart.module, remove_entry=False)
        remove_rigging_module(oriented, rig, item.module, remove_entry=False)
    rig.data.mmt.rigging.clear()
    for _, rigging, settings in cached:
        item = rig.data.mmt.rigging.add()
        rig.data.mmt.module = len(rig.data.mmt.rigging) - 1
        set_module_restored(context, item, rigging, settings)
    # restore the original order, moving whatever now sits at each remembered names position into that slot, front to back...
    for desired_index, module_name in enumerate(original_order):
        current_index = next((i for i, item in enumerate(rig.data.mmt.rigging) if item.module == module_name), -1)
        if current_index >= 0 and current_index != desired_index:
            rig.data.mmt.rigging.move(current_index, desired_index)

def update_module_settings(self, context):
    # settings groups can end up orphaned mid-update (eg. during undo/redo), only react while still owned by an armature...
    try:
        owner = self.id_data
    except ReferenceError:
        return
    if not isinstance(owner, bpy.types.Armature):
        return
    rig, oriented, _ = utilities.functions.get_armature_hierarchy(context.object)
    if not rig or rig.data != owner:
        return
    index = rig.data.mmt.module
    if not (0 <= index < len(rig.data.mmt.rigging)):
        return
    item = rig.data.mmt.rigging[index]
    if item.updating or item.rigging == 'NONE' or not item.module:
        return
    rigging = item.rigging
    item.updating = True
    counterpart = next((m for m in rig.data.mmt.rigging if m.module == item.mirrored_name), None) if item.mirrored_name else None
    if item.mirrored_name and not counterpart:
        # discard stale mirror links left behind by failed or partial rebuilds...
        item.mirrored_name = ""
    if counterpart and not item.settings.mirror:
        remove_rigging_module(oriented, rig, counterpart.module, remove_entry=False)
        item.mirrored_name = ""
    elif counterpart:
        counterpart.updating = True
        set_mirrored_settings(item.settings, counterpart.settings)
        remove_rigging_module(oriented, rig, counterpart.module, remove_entry=False)
        item.mirrored_name = ""
    # either half can become the source for its rebuilt mirror counterpart...
    item.is_mirrored = False
    # bones/constraints/drivers only - the list entry stays put so blenders own drag binding never swaps mid-drag...
    remove_rigging_module(oriented, rig, item.module, remove_entry=False)
    added = None
    module_file = get_module_file(rigging)
    if module_file:
        execute = getattr(module_file, 'execute_' + rigging.lower() + '_module')
        added = execute(context, item)
        if added is not None:
            set_saved_defaults(rigging, get_settings_snapshot(item.settings))
            copy_retargeting_settings(rig, added)
    item.updating = False
    if counterpart:
        counterpart.updating = False

def link_mirrored_modules(rig, item, mirrored_name):
    item.is_mirrored = False
    item.mirrored_name = mirrored_name
    mirrored = next((m for m in rig.data.mmt.rigging if m.module == mirrored_name), None)
    if mirrored:
        mirrored.mirrored_name = item.module

def is_primary_module(item):
    # the one settings source of a mirrored pair...
    return not item.is_mirrored

def get_naming_validity(items):
    validity, existing = {a.name : True for a in items}, []
    # for each property we want to check...
    for item in items:
        # if the affix is not empty...
        if item.affix:
            # if the affix must be unique and cannot exist...
            if item.unique and item.affix in existing:
                validity[item.name] = False
        # else if the affix is empty it might be required...
        elif item.required:
            validity[item.name] = False
        # apppend the checked affix to existing...
        existing.append(item.affix)
    # return the validity to be checked elsewhere...
    return validity

def get_rigging_validity(oriented, rig, items, conflicts, module_name=""):
    # source bones can be shared but must exist on the oriented armature before a module builds them...
    return {item.name: bool(oriented.data.bones.get(item.affix)) if item.affix else not item.required
        for item in items}


