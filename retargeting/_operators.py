import bpy

from bpy.props import (BoolProperty, EnumProperty, FloatProperty, IntProperty)

from .. import utilities
from . import _functions as functions

class MMT_OT_Retarget(bpy.types.Operator):
    """Retargets armatures, meshes and actions."""
    bl_idname = "mmt.retarget"
    bl_label = "Retarget"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode", description="Whether to retarget the active armature or actions from another armature.",
        items=[('ARMATURE', "Armature", ""), ('ACTIONS', "Actions", "")], default='ARMATURE')

    def get_target_items(self, context):
        prefs = utilities.functions.get_addon_preferences(context)
        functions.set_target_items(prefs, context.object)
        return prefs.target_items

    target: EnumProperty(
        name="Armature", description="Armature to use as the retarget pose or action source.",
        items=get_target_items)

    only_selected: BoolProperty(
        name="Only Selected", description="Only retarget bones that are currently selected, leaving unselected bones untouched.",
        default=False
        )

    max_length: FloatProperty(
        name="Max Length", description="Clamp retargeted armature bones down to this length after positioning them. 0 to disable.",
        default=0.0, min=0.0
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
        if self.mode == 'ARMATURE':
            row = layout.row()
            row.prop(self, 'max_length')
            # resolve the whole armature hierarchy to find the rig...
            rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
            if rig:
                layout.label(text="The existing rigging armature and its modules will be rebuilt for the new pose.", icon='INFO')
        else:
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
        if self.mode == 'ARMATURE':
            max_length = self.max_length if self.max_length > 0.0 else None
            functions.set_retargeted_rigging(original, target, max_length, only_selected=self.only_selected)
        else:
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

def add_armature_operator(self, context):
    self.layout.separator()
    op = self.layout.operator(MMT_OT_Retarget.bl_idname, text="Retarget Armature To", icon='ARMATURE_DATA')
    op.mode = 'ARMATURE'

def add_actions_operator(self, context):
    op = self.layout.operator(MMT_OT_Retarget.bl_idname, text="Retarget Actions From", icon='ACTION')
    op.mode = 'ACTIONS'

class MMT_OT_SetBelow(bpy.types.Operator):
    """Copies the active bones retargeting settings down onto every bone beneath it in the hierarchy."""
    bl_idname = "mmt.set_below"
    bl_label = "Copy To Children"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(obj and obj.type == 'ARMATURE' and obj.mode == 'POSE' and context.active_pose_bone)

    def execute(self, context):
        active = context.active_pose_bone
        for descendant in functions.get_descendant_bones(active):
            descendant.mmt.rotation = active.mmt.rotation
            descendant.mmt.translation = active.mmt.translation
            descendant.mmt.mirror = active.mmt.mirror
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


