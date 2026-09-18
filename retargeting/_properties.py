import bpy

from bpy.props import (EnumProperty, BoolProperty)

from . import _functions as functions

class MMT_PG_Bone(bpy.types.PropertyGroup):

    # internal guard, stops a mirrored update re-triggering its own mirrored update back onto us...
    updating: BoolProperty(
        name="Updating", description="Internal.",
        default=False, options={'HIDDEN', 'SKIP_SAVE'}
        )

    rotation: EnumProperty(
        name="Rotation", description="How this bones rotation retargets onto a different skeleton.",
        items=[
            ('ANIMATION', "Animation", "Use the rotation straight from the animation, unmodified."),
            ('RELATIVE', "Animation Relative", "Apply the retarget as a fixed rotational difference from the source rest pose, keeping the animations own motion intact."),
            ('SKELETON', "Skeleton", "Always use the target skeletons own rest pose rotation, ignoring the animation entirely."),
            ], default='RELATIVE', update=functions.update_bone_retargeting
        )

    translation: EnumProperty(
        name="Translation", description="How this bones translation retargets onto a different skeleton, mirrors Unreal Engines own per-bone retargeting modes.",
        items=[
            ('ANIMATION', "Animation", "Use the translation straight from the animation, unmodified."),
            ('SKELETON', "Skeleton", "Always use the target skeletons own rest pose translation, ignoring the animation entirely."),
            ('SCALED', "Animation Scaled", "Keep the animated translation, rescaled by the ratio between the source and target rest pose bone lengths."),
            ('RELATIVE', "Animation Relative", "Apply the retarget as an additive difference from the source rest pose, keeping the animations own motion intact."),
            ('ORIENT', "Orient and Scale", "Rotate and rescale the animated translation from the source bones rest direction onto the targets, for bones whose rest pose orientation differs between skeletons."),
            ], default='ANIMATION', update=functions.update_bone_retargeting
        )

    mirror: BoolProperty(
        name="Mirror Settings", description="Copy this bones retargeting settings onto its mirrored left/right counterpart bone, if one exists.",
        default=True, update=functions.update_bone_retargeting
        )
