import bpy

from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty)

from .. import utilities
from . import _functions as functions

class MMT_OT_Retarget(bpy.types.Operator):
    """Retargets actions from another armature onto the active one."""
    bl_idname = "mmt.retarget"
    bl_label = "Retarget"
    bl_options = {'REGISTER', 'UNDO'}

    def get_target_items(self, context):
        prefs = utilities.functions.get_addon_preferences(context)
        functions.set_target_items(prefs, context.object)
        return prefs.target_items

    target: EnumProperty(
        name="Armature", description="Armature to use as the action source.",
        items=get_target_items)

    only_selected: BoolProperty(
        name="Only Selected", description="Only retarget bones that are currently selected, leaving unselected bones untouched.",
        default=False
        )

    action_method: EnumProperty(
        name="Actions", description="Which actions on the source armature to retarget.",
        items=[
            ('ACTIVE', "Only Active", "Retarget only the action currently assigned to the armature.", '', 0),
            ('STASHED', "Only Stashed", "Retarget only actions on muted NLA tracks.", '', 1),
            ('ALL', "All Actions", "Retarget every action that uses the armature's bones.", '', 2),
            ], default='ACTIVE')

    step_height: FloatProperty(
        name="Step Height", description="How far a plantigrade foot's heel needs to lift before its parent fully hands the ball's own hinge rotation over to the foot control, rather than carrying it directly.",
        default=0.1, min=0.0
        )

    @classmethod
    def poll(cls, context):
        if not utilities.functions.get_oriented_available(context):
            cls.poll_message_set("Requires an Oriented armature")
            return False
        return True

    def invoke(self, context, event):
        # always starts with no target to ensure selection...
        self.target = 'NONE'
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'target')
        row = layout.row()
        row.prop(self, 'only_selected')
        row = layout.row()
        row.prop(self, 'action_method')
        row = layout.row()
        row.prop(self, 'step_height')

    def execute(self, context):
        original, target = context.object, bpy.data.objects.get(self.target)
        if not target or target.type != 'ARMATURE' or target == original:
            return {'FINISHED'}
        last_mode = original.mode
        bpy.ops.object.mode_set(mode='OBJECT')
        # Actions are taken from the selected armature and retargeted onto the active one.
        actions = utilities.functions.get_armature_actions(target, method=self.action_method)
        results = []
        for action in actions:
            # The active armature (or its rig) receives the retargeted action.
            rig, _, _ = utilities.functions.get_armature_hierarchy(original)
            destination = rig if rig else original
            new_action = functions.set_retargeted_action(context, action, target, original, step_height=self.step_height, only_selected=self.only_selected)
            if new_action:
                results.append((destination, new_action))
        # keep the first result active and stash the remainder... (batch actions remain independently usable)...
        if results:
            destination, new_action = results[0]
            destination.animation_data_create()
            destination.animation_data.action = new_action
            destination.animation_data.action_slot = new_action.slots[0]
            for destination, action in results[1:]:
                utilities.functions.set_stashed_action(destination, action)
        bpy.ops.object.mode_set(mode=last_mode)
        return {'FINISHED'}

class MMT_OT_RetargetPose(bpy.types.Operator):
    """Sets or applies a retarget pose. Set poses the active armature into a targets bone directions only, without touching names, meshes or actions, so it can be cleaned up by hand. Apply then bakes that pose onto the meshes and rest pose, carrying stashed actions along - reusing whichever target Set was last run with."""
    bl_idname = "mmt.retarget_pose"
    bl_label = "Retarget Pose"
    bl_options = {'REGISTER', 'UNDO'}

    def get_target_items(self, context):
        prefs = utilities.functions.get_addon_preferences(context)
        functions.set_target_items(prefs, context.object)
        return prefs.target_items

    target: EnumProperty(
        name="Armature", description="Armature to pose (or retarget) the active armature against.",
        items=get_target_items)

    mode: EnumProperty(
        name="Mode", description="Whether we're setting a new retarget pose, or applying the one already set.",
        items=[('SET', "Set", ""), ('APPLY', "Apply", "")], default='SET', options={'HIDDEN'})

    only_selected: BoolProperty(
        name="Only Selected", description="Only pose bones that are currently selected, leaving unselected bones untouched.",
        default=False
        )

    max_length: FloatProperty(
        name="Max Length", description="Clamp retargeted armature bones down to this length after positioning them. 0 to disable.",
        default=0.0, min=0.0
        )

    rename: BoolProperty(
        name="Rename Bones", description="Rename bones onto the targets own naming wherever a bone mapping resolves one, so this armature fully matches the target - names, orientations and retargeting settings alike. Disable to keep this armatures own names, eg. to reuse them in a different pose.",
        default=True
        )

    @classmethod
    def poll(cls, context):
        if not utilities.functions.get_oriented_available(context):
            cls.poll_message_set("Requires an Oriented armature")
            return False
        return True

    def invoke(self, context, event):
        if self.mode == 'SET':
            # setting a fresh pose always resets target to force a pick - applying reuses whatever target was last set, so it isn't picked twice...
            self.target = 'NONE'
        return self.execute(context)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'target')
        if self.mode == 'SET':
            row = layout.row()
            row.prop(self, 'only_selected')
        else:
            row = layout.row()
            row.prop(self, 'max_length')
            row = layout.row()
            row.prop(self, 'rename')

    def execute(self, context):
        armature, target = context.object, bpy.data.objects.get(self.target)
        if not target or target.type != 'ARMATURE' or target == armature:
            return {'FINISHED'}
        bpy.ops.object.mode_set(mode='OBJECT')
        # isolate the active armature before touching pose mode again - a leftover multi-selection would otherwise drag unrelated armatures into pose mode alongside it...
        bpy.ops.object.select_all(action='DESELECT')
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        if self.mode == 'SET':
            functions.set_armature_posed(armature, target, only_selected=self.only_selected)
            bpy.ops.object.mode_set(mode='POSE')
        else:
            max_length = self.max_length if self.max_length > 0.0 else None
            oriented, original = functions.set_retargeted_armature(armature, target, max_length, rename=self.rename)
            bpy.context.view_layer.objects.active = oriented
        return {'FINISHED'}

def add_retarget_pose_operator(self, context):
    self.layout.separator()
    op = self.layout.operator(MMT_OT_RetargetPose.bl_idname, text="Set Retarget Pose", icon='ARMATURE_DATA')
    op.mode = 'SET'

def add_armature_operator(self, context):
    op = self.layout.operator(MMT_OT_RetargetPose.bl_idname, text="Apply Retarget Pose", icon='ARMATURE_DATA')
    op.mode = 'APPLY'

def add_actions_operator(self, context):
    self.layout.operator(MMT_OT_Retarget.bl_idname, text="Retarget Actions From", icon='ACTION')

class MMT_OT_AddMapping(bpy.types.Operator):
    """Adds a blank alternate name to the active bones retargeting mapping."""
    bl_idname = "mmt.add_mapping"
    bl_label = "Add Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if not context.active_pose_bone:
            cls.poll_message_set("Requires an active pose bone")
            return False
        if not utilities.functions.get_oriented_available(context):
            cls.poll_message_set("Requires an Oriented armature")
            return False
        return True

    def execute(self, context):
        pose_bone = context.active_pose_bone
        pose_bone.mmt.mapping.add()
        functions.set_cascaded_retargeting(context.object, pose_bone.name)
        return {'FINISHED'}

class MMT_OT_RemoveMapping(bpy.types.Operator):
    """Removes an alternate name from the active bones retargeting mapping."""
    bl_idname = "mmt.remove_mapping"
    bl_label = "Remove Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        if not context.active_pose_bone:
            cls.poll_message_set("Requires an active pose bone")
            return False
        if not utilities.functions.get_oriented_available(context):
            cls.poll_message_set("Requires an Oriented armature")
            return False
        return True

    def execute(self, context):
        pose_bone = context.active_pose_bone
        pose_bone.mmt.mapping.remove(self.index)
        functions.set_cascaded_retargeting(context.object, pose_bone.name)
        return {'FINISHED'}

class MMT_OT_FCurve(bpy.types.Operator):
    """Reduces the selected f-curves to the fewest keyframes that still fit their original shape within a margin of error, via blenders own curve-fitting decimate - optionally followed by a pass thinning out any keys still clustered too close together."""
    bl_idname = "mmt.fcurve"
    bl_label = "Decimate Keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    margin: FloatProperty(
        name="Error Margin", description="How much the decimated curve is allowed to deviate from the original.",
        default=0.01, min=0.0
        )

    spacing: IntProperty(
        name="Thin Spacing", description="Minimum space keys can have when thinning, 0 to disable thinning entirely.",
        default=4, min=0
        )

    def execute(self, context):
        with functions.get_graph_override(context) as area:
            if area:
                functions.set_decimated_fcurves(context, self.margin)
                if self.spacing > 0:
                    functions.set_thinned_fcurves(context, self.spacing)
        return {'FINISHED'}

def add_fcurve_operator(self, context):
    self.layout.separator()
    self.layout.operator(MMT_OT_FCurve.bl_idname, icon='SHARPCURVE')


