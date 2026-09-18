import bpy

from bpy.props import (EnumProperty, BoolProperty, FloatProperty, IntProperty, PointerProperty)

from .. import utilities
from .. import retargeting

class MMT_PG_ImportFBX(bpy.types.PropertyGroup):

    scaling: FloatProperty(
        name="Scale", description="Scale all data.",
        default=1.0, min=0.001, max=1000.0
        )

    forward: EnumProperty(
        name="Forward", description="Forward axis.",
        items=[
            ('X', "X Forward", "", '', 0), ('Y', "Y Forward", "", '', 1), ('Z', "Z Forward", "", '', 2),
            ('-X', "-X Forward", "", '', 3), ('-Y', "-Y Forward", "", '', 4), ('-Z', "-Z Forward", "", '', 5),
            ], default=3
        )

    upward: EnumProperty(
        name="Up", description="Up axis.",
        items=[
            ('X', "X Up", "", '', 0), ('Y', "Y Up", "", '', 1), ('Z', "Z Up", "", '', 2),
            ('-X', "-X Up", "", '', 3), ('-Y', "-Y Up", "", '', 4), ('-Z', "-Z Up", "", '', 5),
            ], default=1
        )

    manual_orientation: BoolProperty(
        name="Manual Orientation", description="Specify orientation and scale, instead of using embedded data in the FBX file.",
        default=False
        )

    use_custom_normals: BoolProperty(
        name="Custom Normals", description="Import custom normals, if available (otherwise Blender computes them).",
        default=True
        )

    use_image_search: BoolProperty(
        name="Image Search", description="Search subdirectories for any associated images (WARNING: may be slow).",
        default=True
        )

    use_alpha_decals: BoolProperty(
        name="Alpha Decals", description="Treat materials with alpha as decals (no shadow casting).",
        default=False
        )

    decal_offset: FloatProperty(
        name="Decal Offset", description="Displace geometry of alpha meshes.",
        default=0.0, min=0.0, max=1.0
        )

    anim_offset: FloatProperty(
        name="Animation Offset", description="Offset to apply to animation during import, in frames.",
        default=1.0
        )

    ignore_leaf_bones: BoolProperty(
        name="Ignore Leaf Bones", description="Ignore the last bone at the end of each chain (used to mark the length of the previous bone).",
        default=False
        )

    force_connect_children: BoolProperty(
        name="Force Connect Children", description="Force connection of children bones to their parent, even if their computed head/tail is not aligned (technically, it works only if the distance between both is small).",
        default=False
        )

    automatic_bone_orientation: BoolProperty(
        name="Automatic Bone Orientation", description="Try to align the major bone axis with the bone children.",
        default=False
        )

    primary: EnumProperty(
        name="Primary Bone Axis", description="Primary bone axis.",
        items=[
            ('X', "X Axis", "", '', 0), ('Y', "Y Axis", "", '', 1), ('Z', "Z Axis", "", '', 2),
            ('-X', "-X Axis", "", '', 3), ('-Y', "-Y Axis", "", '', 4), ('-Z', "-Z Axis", "", '', 5),
            ], default=1
        )

    secondary: EnumProperty(
        name="Secondary Bone Axis", description="Secondary bone axis.",
        items=[
            ('X', "X Axis", "", '', 0), ('Y', "Y Axis", "", '', 1), ('Z', "Z Axis", "", '', 2),
            ('-X', "-X Axis", "", '', 3), ('-Y', "-Y Axis", "", '', 4), ('-Z', "-Z Axis", "", '', 5),
            ], default=0
        )

    use_prepost_rot: BoolProperty(
        name="Use Pre/Post Rotation", description="Use pre/post rotation from FBX transform (you may have to disable it for some armatures, when it causes them to be twisted).",
        default=True
        )

class MMT_PG_Orientation(bpy.types.PropertyGroup):

    orient: BoolProperty(
        name="Orient Armature", description="Create an oriented armature for any armatures that get imported.",
        default=False
        )

    root_length: FloatProperty(
        name="Root Length", description="Length to give the root bone added to imported armatures, 0 to disable adding one.",
        default=0.10, min=0.0, max=1000.0
        )

    max_length: FloatProperty(
        name="Max Length", description="Clamp oriented armature bones down to this length if they would otherwise be longer. 0 to disable.",
        default=0.1, min=0.0
        )

    original_shape: EnumProperty(
        name="Original Shape", description="Custom shape for the original armatures bones.",
        items=utilities.functions.get_shape_items)

    oriented_shape: EnumProperty(
        name="Oriented Shape", description="Custom shape for the oriented armatures bones.",
        items=utilities.functions.get_shape_items)

def get_target_items(self, context):
    # same dynamic armature-only enum the retargeting operator uses, but with no "self" to exclude since context.object has no relationship to what's about to be imported...
    prefs = utilities.functions.get_addon_preferences(bpy.context)
    retargeting.functions.set_target_items(prefs, None)
    return prefs.target_items

class MMT_PG_Retargeting(bpy.types.PropertyGroup):

    target: EnumProperty(
        name="Target", description="Optional existing armature to retarget imported meshes and actions onto.",
        items=get_target_items
        )

    meshes: BoolProperty(
        name="Meshes", description="Retarget imported meshes onto the target armature.",
        default=True
        )

    actions: BoolProperty(
        name="Actions", description="Retarget imported actions onto the target or oriented armature.",
        default=True
        )

    step_height: FloatProperty(
        name="Step Height", description="How far a plantigrade foot's heel needs to lift before its parent fully hands the ball's own hinge rotation over to the foot control.",
        default=0.1, min=0.0
        )

class MMT_PG_Cleaning(bpy.types.PropertyGroup):

    decimate: EnumProperty(
        name="Decimate Keyframes", description="Reduce each imported actions keyframes via blenders own curve-fitting decimate. This can be slow - expect several seconds per action on a dense, fully baked mocap take.",
        items=[
            ('NONE', "None", "Don't decimate keyframes. (Faster, but less editable)."),
            ('PRE', "Before", "Decimate before scaling and retargeting. (Slow but more editable)."),
            ('POST', "After", "Decimate after scaling and retargeting (Slower but more editable and more accurate)."),
            ], default='NONE'
        )

    margin: FloatProperty(
        name="Error Margin", description="How much the decimated curve is allowed to deviate from the original.",
        default=0.01, min=0.0
        )

    spacing: IntProperty(
        name="Key Thinning", description="Minimum space keys can have when thinning. (0 to disable).",
        default=4, min=0
        )

class MMT_PG_Import(bpy.types.PropertyGroup):

    filmbox: PointerProperty(type=MMT_PG_ImportFBX, name="Filmbox")

    orientation: PointerProperty(type=MMT_PG_Orientation, name="Orientation")

    retargeting: PointerProperty(type=MMT_PG_Retargeting, name="Retargeting")

    cleaning: PointerProperty(type=MMT_PG_Cleaning, name="Cleaning")
