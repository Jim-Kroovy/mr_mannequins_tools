import bpy

from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty)

from .. import utilities
from . import _functions as functions

class MMT_OT_RetargetingActions(bpy.types.Operator):
    """Retargets actions between the active armature and another one, in either direction."""
    bl_idname = "mmt.actions"
    bl_label = "Retarget Actions"
    bl_options = {'REGISTER', 'UNDO'}

    def get_target_items(self, context):
        prefs = utilities.functions.get_addon_preferences(context)
        functions.set_target_items(prefs, context.object, include_oriented=True)
        return prefs.target_items

    target: EnumProperty(
        name="Target", description="Armature to retarget actions with.",
        items=get_target_items, options={'SKIP_SAVE'})

    direction: EnumProperty(
        name="Direction", description="Which way actions retarget between the active armature and the target.",
        items=[('FROM', "From", "Pull actions from the target onto the active armature."), ('TO', "To", "Push actions from the active armature onto the target.")],
        default='FROM', options={'HIDDEN'})

    only_selected: BoolProperty(
        name="Only Selected", description="Only retarget bones that are currently selected, leaving unselected bones untouched.",
        default=False
        )

    keep_original: BoolProperty(
        name="Keep Original", description="Keep the source actions, prefixing the new ones with the receiving armatures name. Disable to remove the source actions instead, renaming the new ones onto their old names.",
        default=True
        )

    step_height: FloatProperty(
        name="Step Height", description="How far a plantigrade foot's heel needs to lift before its parent fully hands the ball's own hinge rotation over to the foot control, rather than carrying it directly.",
        default=0.1, min=0.0
        )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != 'ARMATURE':
            cls.poll_message_set("Requires an active armature")
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
        row.prop(self, 'keep_original')
        row = layout.row()
        row.prop(self, 'step_height')

    def execute(self, context):
        active, target = context.object, bpy.data.objects.get(self.target)
        if not target or target.type != 'ARMATURE' or target == active:
            return {'FINISHED'}
        # the active armature retargets against whichever of its own tiers is the most built-out...
        rig, oriented, original = utilities.functions.get_armature_hierarchy(active)
        active_highest = rig or oriented or original
        source, destination = (target, active_highest) if self.direction == 'FROM' else (active_highest, target)
        last_mode = active.mode
        # retargeting can touch every tier of both hierarchies - hidden ones can't reliably be selected or made active, so unhide them for the duration...
        source_tiers = utilities.functions.get_armature_hierarchy(source)
        destination_tiers = utilities.functions.get_armature_hierarchy(destination)
        hidden = utilities.functions.get_hidden_objects({a for a in (*source_tiers, *destination_tiers) if a})
        utilities.functions.set_objects_unhidden(hidden)
        bpy.ops.object.mode_set(mode='OBJECT')
        # the receivers original name is a stable prefix for kept source actions... (its own name depends on which tier ended up highest)
        _, _, destination_original = utilities.functions.get_armature_hierarchy(destination)
        prefix = (destination_original or destination).name
        stashed = utilities.functions.get_armature_actions(source, method='STASHED')
        active_action = source.animation_data.action if source.animation_data else None
        actions = [active_action] + [a for a in stashed if a != active_action] if active_action else stashed
        results = []
        for action in actions:
            new_action = functions.set_retargeted_action(context, action, source, destination, step_height=self.step_height, only_selected=self.only_selected)
            if not new_action:
                continue
            was_active = action == active_action
            if self.keep_original:
                new_action.name = prefix + "_" + new_action.name
            else:
                name = action.name
                # strip the stash references before removing the action... (deleting it first leaves a dead strip with no action)
                utilities.functions.remove_stashed_action(source, action)
                bpy.data.actions.remove(action)
                new_action.name = name
            results.append((destination, new_action, was_active))
        # only the result of the active source action gets assigned, the rest get stashed... (clear the action if the source had none or it failed)
        active_result = next((result for result in results if result[2]), None)
        for destination, action, was_active in results:
            if not was_active:
                utilities.functions.set_stashed_action(destination, action)
        # the active result becomes the destinations action...
        if active_result:
            destination, new_action, was_active = active_result
            destination.animation_data_create()
            destination.animation_data.action = new_action
            destination.animation_data.action_slot = new_action.slots[0]
        elif destination.animation_data:
            # no active result, so don't leave the old action assigned...
            destination.animation_data.action = None
            if results:
                # no retargeted result stays active - clear the pose too, or the receiver visually stays on whatever frame was last evaluated during retargeting...
                functions.set_pose_reset(destination)
        # retargeting may have left a different object active (eg. spline rigging, or the disposable mapped source) - restore the armature that invoked this operator before returning its mode...
        context.view_layer.objects.active = active
        active.select_set(True)
        bpy.ops.object.mode_set(mode=last_mode)
        # rehide anything that wasn't visible to begin with...
        for obj in hidden:
            obj.hide_set(True)
        return {'FINISHED'}
    
def add_action_operator(self, context):
    self.layout.separator()
    op = self.layout.operator(MMT_OT_RetargetingActions.bl_idname, text="Retarget Actions To", icon='ACTION')
    op.direction = 'TO'
    op = self.layout.operator(MMT_OT_RetargetingActions.bl_idname, text="Retarget Actions From", icon='ACTION')
    op.direction = 'FROM'

class MMT_OT_RetargetingPose(bpy.types.Operator):
    """Sets or applies a retarget pose. Set poses the active armature into a targets bone directions only, without touching names, meshes or actions, so it can be cleaned up by hand. Apply then bakes that pose onto the meshes and rest pose, carrying stashed actions along - reusing whichever target Set was last run with."""
    bl_idname = "mmt.pose"
    bl_label = "Retarget Pose"
    bl_options = {'REGISTER', 'UNDO'}

    def get_target_items(self, context):
        prefs = utilities.functions.get_addon_preferences(context)
        functions.set_target_items(prefs, context.object, prefer_rig=False)
        return prefs.target_items

    target: EnumProperty(
        name="Target", description="Armature to pose (or retarget) the active armature against.",
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

    enforce_hierarchy: BoolProperty(
        name="Enforce Hierarchy", description="Pad any chain the target has more bones in than this armature does, so both skeletons keep the same joint count - injected bones are positioned proportionally to this armatures own real bone gap, but oriented like their own target counterpart, and the transported animation is split evenly across them rather than left concentrated on the one bone that used to carry all of it.",
        default=True
        )

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.type != 'ARMATURE':
            cls.poll_message_set("Requires an active armature")
            return False
        if obj.get('Armature Type') == 'Rigging':
            cls.poll_message_set("Requires an Original or Oriented armature, not Rigging")
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
        # only set mode gets the selection option...
        if self.mode == 'SET':
            row = layout.row()
            row.prop(self, 'only_selected')
        else:
            row = layout.row()
            row.prop(self, 'max_length')
            row = layout.row()
            row.prop(self, 'rename')
            row = layout.row()
            row.prop(self, 'enforce_hierarchy')

    def execute(self, context):
        armature, target = context.object, bpy.data.objects.get(self.target)
        if not target or target.type != 'ARMATURE':
            return {'FINISHED'}
        # the target picker can resolve as high as rig now, but posing only ever works against oriented/original...
        _, oriented, original = utilities.functions.get_armature_hierarchy(target)
        target = oriented or original
        if not target or target == armature:
            return {'FINISHED'}
        name, selected, last_mode = armature.name, [o.name for o in context.selected_objects], armature.mode
        bpy.ops.object.mode_set(mode='OBJECT')
        # isolate the active armature before touching pose mode again - a leftover multi-selection would otherwise drag unrelated armatures into pose mode alongside it...
        bpy.ops.object.select_all(action='DESELECT')
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        # pose the armature and stay in pose mode...
        if self.mode == 'SET':
            functions.set_armature_posed(armature, target, only_selected=self.only_selected)
            bpy.ops.object.mode_set(mode='POSE')
        else:
            max_length = self.max_length if self.max_length > 0.0 else None
            try:
                oriented, original = functions.set_retargeted_armature(armature, target, max_length, rename=self.rename, enforce_hierarchy=self.enforce_hierarchy)
            except Exception:
                functions.set_selection_restored(name, selected, last_mode)
                raise
            # no oriented comes back if there wasn't one to rebuild - just applied the posed original itself...
            if oriented or original:
                bpy.context.view_layer.objects.active = oriented or original
            else:
                # neither means it backed out before touching anything...
                functions.set_selection_restored(name, selected, last_mode)
        return {'FINISHED'}

def add_pose_operator(self, context):
    self.layout.separator()
    op = self.layout.operator(MMT_OT_RetargetingPose.bl_idname, text="Set Retarget Pose", icon='ARMATURE_DATA')
    op.mode = 'SET'
    op = self.layout.operator(MMT_OT_RetargetingPose.bl_idname, text="Apply Retarget Pose", icon='ARMATURE_DATA')
    op.mode = 'APPLY'


class MMT_OT_RetargetingAddMapping(bpy.types.Operator):
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

class MMT_OT_RetargetingRemoveMapping(bpy.types.Operator):
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

class MMT_OT_RetargetingKeyframes(bpy.types.Operator):
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
            # needs a graph editor for either of these...
            if area:
                functions.set_decimated_fcurves(context, self.margin)
                if self.spacing > 0:
                    functions.set_thinned_fcurves(context, self.spacing)
        return {'FINISHED'}

def add_fcurve_operator(self, context):
    self.layout.separator()
    self.layout.operator(MMT_OT_RetargetingKeyframes.bl_idname, icon='SHARPCURVE')


