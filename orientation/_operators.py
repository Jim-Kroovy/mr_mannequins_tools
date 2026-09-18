import bpy

from bpy.props import StringProperty, EnumProperty, FloatProperty, BoolProperty

from .. import utilities

from .. import skinning

from .. import rigging

from . import _functions as functions

class MMT_OT_Oriented(bpy.types.Operator):
    """Makes a Blender compatible armature by orienting bones using shortest rolls by matching names. (adds any new bones from the original)"""
    bl_idname = "mmt.oriented"
    bl_label = "Set Oriented Armature"
    bl_options = {'REGISTER', 'UNDO'}

    max_length: FloatProperty(
        name="Max Length", description="Clamp oriented armature bones down to this length if they would otherwise be longer. (0.0 to unclamp length)",
        default=0.1, min=0.0
        )

    actions: BoolProperty(
        name="Retarget Actions", description="Retarget the originals active action and stashed actions onto the oriented armature.",
        default=True
        )

    original_shape: EnumProperty(
        name="Original Shape", description="Custom shape for the original armatures bones.",
        items=utilities.functions.get_shape_items)

    oriented_shape: EnumProperty(
        name="Oriented Shape", description="Custom shape for the oriented armatures bones.",
        items=utilities.functions.get_shape_items)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'max_length')
        row = layout.row()
        row.prop(self, 'actions')
        row = layout.row()
        row.prop(self, 'original_shape')
        row = layout.row()
        row.prop(self, 'oriented_shape')

    def execute(self, context):
        original = context.object
        _, oriented, existing = utilities.functions.get_armature_hierarchy(original)
        # add missing original bones to the existing oriented armature...
        if oriented and existing:
            names = [n for n in utilities.functions.get_bone_order(existing, {b.name for b in existing.data.bones}) if n not in oriented.data.bones]
            if names:
                mode, selected, active = utilities.functions.get_current_objects(context)
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.select_all(action='DESELECT')
                oriented.select_set(True)
                existing.select_set(True)
                bpy.context.view_layer.objects.active = existing
                bpy.ops.object.mode_set(mode='EDIT')
                for name in names:
                    functions.add_oriented_bone(oriented, existing, name, self.max_length if self.max_length > 0.0 else None)
                utilities.functions.set_current_objects(mode, selected, active)
            # existing pairs still need shape changes... (the operator doubles as their shape assignment)...
            names = [bone.name for bone in existing.data.bones if bone.name in oriented.data.bones]
            functions.set_shaped_bones(existing, oriented, names, self.original_shape, self.oriented_shape)
            return {'FINISHED'}
        # not compatible yet - check for a pre-existing rigging armature to hand off to the new oriented below...
        rig = next((c for c in original.children if c.get('Armature Type') == "Rigging"), None)
        max_length = self.max_length if self.max_length > 0.0 else None
        oriented, original = functions.add_oriented_armature(original, max_length, self.original_shape, self.oriented_shape, self.actions)
        if rig:
            functions.clear_parent_constraints(original)
            functions.set_rigging_reparented(rig, oriented)
        return {'FINISHED'}

def add_oriented_operator(self, context):
    self.layout.separator()
    self.layout.operator(MMT_OT_Oriented.bl_idname, icon='GROUP_BONE')

class MMT_OT_Orient(bpy.types.Operator):
    """Orients bone tails and rolls to align axes in the input space."""
    bl_idname = "mmt.orient"
    bl_label = "Set Bone Orientation"
    bl_options = {'REGISTER', 'UNDO'}

    space: EnumProperty(
        name="Space", description="The desired space to orient the bone in.",
        items=[
            ('AUTO', "Auto", "", '', 0),
            ('LOCAL', "Local", "", '', 1),
            ('TARGET', "Target", "", '', 2),
            ('ARMATURE', "Armature", "", '', 3),
            ], default=0
        )

    primary: EnumProperty(
        name="Primary", description="The desired tail direction of the bone.",
        items=[
            ('+X', "+X", "", '', 0), ('-X', "-X", "", '', 1),
            ('+Y', "+Y", "", '', 2), ('-Y', "-Y", "", '', 3),
            ('+Z', "+Z", "", '', 4), ('-Z', "-Z", "", '', 5),
            ], default=2
        )

    secondary: EnumProperty(
        name="Secondary", description="The desired roll direction of the bone.",
        items=[
            ('+X', "+X", "", '', 0), ('-X', "-X", "", '', 1),
            ('+Y', "+Y", "", '', 2), ('-Y', "-Y", "", '', 3),
            ('+Z', "+Z", "", '', 4), ('-Z', "-Z", "", '', 5),
            ], default=4
        )

    target: StringProperty(
        name='Target Bone', description="The bone to define space from.",
        default=""
        )

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'space')
        row = layout.row()
        row.enabled = (self.space == 'TARGET')
        row.prop_search(self, 'target', context.object.data, 'bones')
        row = layout.row()
        row.enabled = (self.space != 'AUTO')
        row.prop(self, 'primary')
        row = layout.row()
        row.enabled = (self.space != 'AUTO')
        row.alert = self.secondary.endswith(self.primary[1])
        row.prop(self, 'secondary')

    def execute(self, context):
        armature = context.object
        # roll direction must not be the same axis as the tail direction...
        if self.secondary.endswith(self.primary[1]):
            return {'FINISHED'}
        # target bone must exist... (if it's to be used)...
        elif self.space == 'TARGET' and self.target not in armature.data.bones:
            return {'FINISHED'}
        # get our current objects and mode... (works from either pose or edit mode)...
        mode, selected, active = utilities.functions.get_current_objects(context)
        # oriented/original are only needed for automatic orientation reference and refreshing constraints after...
        _, oriented, original = utilities.functions.get_armature_hierarchy(armature)
        hierarchy = original if original else oriented
        # meshes live on the original armature if we have one, otherwise directly on the armature we're orienting...
        meshes_armature = original if original else armature
        # get the selected bone names before touching visibility, selection or mode...
        if mode == 'EDIT':
            selection = [eb.name for eb in context.selected_bones if eb.id_data == armature.data]
        else:
            selection = [pb.name for pb in context.selected_pose_bones if pb.id_data == armature]
        # only the bones actually being reoriented need their mesh children unsocketed around it...
        statics = [m for m in meshes_armature.children if m.type == 'MESH' and m.parent_type == 'BONE' and m.parent_bone in selection]

        # make sure everything we're about to touch is unhidden, so it can be selected/entered into edit mode...
        needed = set(statics)
        if self.space == 'AUTO' and hierarchy:
            needed.add(hierarchy)
        hidden = utilities.functions.get_hidden_objects(needed)
        utilities.functions.set_objects_unhidden(hidden)

        # select the hierarchy armature too, if it's not already, so multi-object edit mode picks it up...
        if self.space == 'AUTO' and hierarchy != armature and not hierarchy.select_get():
            bpy.ops.object.mode_set(mode='OBJECT')
            hierarchy.select_set(True)
            bpy.ops.object.mode_set(mode=mode)
        # convert any static attached meshes to skeletal before orientation... (to avoid transform issues)...
        if statics:
            skinning.functions.set_unsocketed_meshes(statics)
        # go into edit mode and orient the selected bones... (already there if invoked from edit mode)...
        if mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        for name in selection:
            functions.set_bone_orientation(armature, name, orient=self, hierarchy=hierarchy)
        # drop to object mode... (a safe neutral state, set_current_objects below returns us to pose/edit as needed)...
        bpy.ops.object.mode_set(mode='OBJECT')
        # if this was called on an oriented or original armature...
        if oriented and original:
            # update the original armatures export child of constraints...
            rigging.functions.set_parent_constraints(original, oriented)
        # convert any static mesh attachments back into static meshes...
        if statics:
            skinning.functions.set_socketed_meshes(statics)
        # reset our current objects and mode...
        utilities.functions.set_current_objects(mode, selected, active)
        # then rehide anything that wasn't visible to begin with...
        for obj in hidden:
            obj.hide_set(True)
        return {'FINISHED'}

def add_orient_operator(self, context):
    row = self.layout.row()
    row.operator(MMT_OT_Orient.bl_idname, icon='ORIENTATION_GIMBAL')




