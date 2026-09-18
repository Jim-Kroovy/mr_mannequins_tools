import bpy
import json

from bpy.props import (EnumProperty, BoolProperty)

from .. import utilities
from . import _functions as functions

class MMT_OT_Shapes(bpy.types.Operator):
    """Saves/loads a custom shapes (saving is stored from mesh evaluations and only supports sharp edges)."""
    bl_idname = "mmt.shapes"
    bl_label = "Custom Shapes"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode", description="What are we doing to a custom shapes.",
        items=[('SAVE', "Save", ""), ('LOAD', "Load", "")], default='SAVE')

    shape: EnumProperty(
        name="Shape", description="The custom shape to load.",
        items=utilities.functions.get_shape_items)
    
    active: BoolProperty(
        name="Only Active", description="Only save the active mesh as a custom shape.",
        default=True)
    
    def draw(self, context):
        layout = self.layout
        row = layout.row()
        if self.mode == 'SAVE':
            row.prop(self, 'active')
        elif self.mode == 'LOAD':
            row.prop(self, 'shape')

    def execute(self, context):
        if self.mode == 'SAVE':
            selected = context.selected_objects
            shapes = [m for m in selected if m.type == 'MESH']
            functions.save_custom_shapes(shapes)
        elif self.mode == 'LOAD' and self.shape != 'NONE':
            shape = utilities.functions.get_shape_mesh(self.shape)
            if context.object:
                collections = [coll for coll in context.object.users_collection]
            else:
                collections = [context.scene.collection]
            for collection in collections:
                # nobody needs more than one of a given custom shape in their file, just reuse whats already there...
                if collection not in shape.users_collection:
                    collection.objects.link(shape)
        return {'FINISHED'}

def add_shape_operator(self, context):
    op = self.layout.operator(MMT_OT_Shapes.bl_idname, text="Save Custom Shape", icon='EXPORT')
    op.mode = 'SAVE'
    op = self.layout.operator(MMT_OT_Shapes.bl_idname, text="Load Custom Shape", icon='IMPORT')
    op.mode = 'LOAD'

class MMT_OT_Refresh(bpy.types.Operator):
    """Refreshes child of constraints on oriented and original armatures."""
    bl_idname = "mmt.refresh"
    bl_label = "Refresh Binding Constraints"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # get the oriented and original armature...
        rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
        # if this was called on an oriented or original armature...
        if oriented and original:
            # update the original armatures child of constraints...
            functions.set_parent_constraints(original, oriented)
        # if this was called on an oriented or rigging armature...
        if oriented and rig:
            # update the oriented armatures child of constraints...
            functions.set_parent_constraints(oriented, rig)
        return {'FINISHED'}
    
def add_refresh_operator(self, context):
    op = self.layout.operator(MMT_OT_Refresh.bl_idname, icon='FILE_REFRESH')

class MMT_OT_Rebuild(bpy.types.Operator):
    """Rebuilds all rigging modules from their current settings."""
    bl_idname = "mmt.rebuild"
    bl_label = "Rebuild Rigging"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rig, oriented, _ = utilities.functions.get_armature_hierarchy(context.object)
        if oriented and rig:
            functions.set_refreshed_rigging(context, oriented, rig)
        return {'FINISHED'}



class MMT_OT_Copy(bpy.types.Operator):
    """Copies/pastes every rigging module's type and settings via the addon preferences, so they can be rebuilt onto another armature."""
    bl_idname = "mmt.copy"
    bl_label = "Copy Rigging"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode", description="Whether we're copying rigging from this armature or pasting it onto this armature.",
        items=[('COPY', "Copy", ""), ('PASTE', "Paste", "")], default='COPY', options={'HIDDEN'})

    def execute(self, context):
        if self.mode == 'PASTE':
            return self.paste(context)
        return self.copy(context)

    def copy(self, context):
        rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
        cached = [(item.rigging, utilities.functions.get_serialized_settings(item.settings))
            for item in rig.data.mmt.rigging if item.rigging != 'NONE' and functions.is_primary_module(item)] if rig else []
        if not cached:
            self.report({'WARNING'}, "No rigging modules to copy.")
            return {'CANCELLED'}
        prefs = utilities.functions.get_addon_preferences(context)
        prefs.rigging_clipboard = json.dumps(cached)
        self.report({'INFO'}, "Copied " + str(len(cached)) + " rigging module" + ("" if len(cached) == 1 else "s") + ".")
        return {'FINISHED'}

    def paste(self, context):
        prefs = utilities.functions.get_addon_preferences(context)
        try:
            cached = json.loads(prefs.rigging_clipboard) if prefs.rigging_clipboard else []
        except (ValueError, TypeError):
            cached = []
        if not cached:
            self.report({'WARNING'}, "The rigging clipboard is empty.")
            return {'CANCELLED'}
        rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
        oriented = oriented or original
        if not oriented:
            self.report({'WARNING'}, "No armature to paste rigging onto.")
            return {'CANCELLED'}
        if not rig:
            rig = functions.add_rigging_armature(oriented)
        failed = []
        for rigging_type, settings_data in cached:
            item = rig.data.mmt.rigging.add()
            rig.data.mmt.module = len(rig.data.mmt.rigging) - 1
            if not functions.set_module_restored(context, item, rigging_type, settings_data):
                index = rig.data.mmt.module
                rig.data.mmt.rigging.remove(index)
                rig.data.mmt.module = min(index, len(rig.data.mmt.rigging) - 1)
                failed.append(rigging_type)
        # tears the rig back down if every module failed to find its bones (eg. pasted onto an unrelated armature)...
        functions.remove_empty_armature(oriented, rig)
        if failed:
            self.report({'WARNING'}, "Couldn't paste (missing bones): " + ", ".join(failed))
        return {'FINISHED'}

class MMT_MT_ModuleOptions(bpy.types.Menu):
    bl_idname = "MMT_MT_module_options"
    bl_label = "Rigging Module Options"

    def draw(self, context):
        self.layout.operator(MMT_OT_Rebuild.bl_idname, icon='FILE_REFRESH', text="Rebuild Rigging")
        self.layout.separator()
        op = self.layout.operator(MMT_OT_Copy.bl_idname, icon='COPYDOWN', text="Copy Rigging")
        op.mode = 'COPY'
        op = self.layout.operator(MMT_OT_Copy.bl_idname, icon='PASTEDOWN', text="Paste Rigging")
        op.mode = 'PASTE'

class MMT_OT_Add(bpy.types.Operator):
    """Adds an empty rigging module, pick its type in the Settings dropdown to build it."""
    bl_idname = "mmt.add"
    bl_label = "Add Rigging Module"
    bl_options = {'REGISTER', 'UNDO'}

    rigging_type: EnumProperty(
        name="Rigging", description="The rigging module type to add.",
        items=[
            ('NONE', "Empty Module", "Add a module without selecting its type."),
            ('ROOT', "Root Controls", "Add root motion rigging."),
            ('SPLINE', "Spline Chain", "Add spline chain rigging."),
            ('OPPOSABLE', "Opposable Arm", "Add opposable arm rigging."),
            ('PLANTIGRADE', "Plantigrade Leg", "Add plantigrade leg rigging."),
            ('DIGITIGRADE', "Digitigrade Leg", "Add digitigrade leg rigging."),
            ('SCALAR', "Scalar Chain", "Add scalar chain rigging."),
            ('CURL', "Curl Chain", "Add curl chain rigging."),
            ('TWIST', "Twist Chain", "Add twist chain rigging."),
            ('CUSTOM', "Custom Bones", "Add custom bones from selection."),
            ], default='NONE', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.mode != 'POSE':
            return False
        _, oriented, original = utilities.functions.get_armature_hierarchy(obj)
        oriented = oriented or original
        if not oriented:
            return False
        return obj.select_get()

    def execute(self, context):
        rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
        oriented = oriented or original
        # if we do not have a rigging armature...
        if not rig:
            # add one that will serve as the new target...
            rig = functions.add_rigging_armature(oriented)
        item = rig.data.mmt.rigging.add()
        rig.data.mmt.module = len(rig.data.mmt.rigging) - 1
        if self.rigging_type != 'NONE':
            item.rigging = self.rigging_type
        return {'FINISHED'}

class MMT_MT_AddRigging(bpy.types.Menu):
    bl_idname = "MMT_MT_add_rigging"
    bl_label = "Add Rigging"

    @classmethod
    def poll(cls, context):
        if not context.object or context.object.mode != 'POSE':
            return False
        _, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
        oriented = oriented or original
        return bool(oriented and context.object.select_get())

    def draw(self, context):
        items = (
            ('ROOT', 'Root Controls', 'CON_CHILDOF'),
            ('SPLINE', 'Spline Chain', 'CURVE_BEZCURVE'),
            ('OPPOSABLE', 'Opposable Arm', 'CON_KINEMATIC'),
            ('PLANTIGRADE', 'Plantigrade Leg', 'CON_KINEMATIC'),
            ('DIGITIGRADE', 'Digitigrade Leg', 'CON_KINEMATIC'),
            ('SCALAR', 'Scalar Chain', 'CON_SIZELIKE'),
            ('CURL', 'Curl Chain', 'CON_ROTLIKE'),
            ('TWIST', 'Twist Chain', 'CON_LOCKTRACK'),
            ('CUSTOM', 'Custom Bones', 'CONSTRAINT_BONE'))
        for identifier, label, icon in items:
            op = self.layout.operator(MMT_OT_Add.bl_idname, text=label, icon=icon)
            op.rigging_type = identifier

def add_rigging_operator(self, context):
    self.layout.menu(MMT_MT_AddRigging.bl_idname, text="Add Rigging", icon='ADD')

class MMT_OT_Remove(bpy.types.Operator):
    """Removes a rigging module, deleting the bones and constraints it created (shared origin/ending bones are kept)."""
    bl_idname = "mmt.remove"
    bl_label = "Remove Rigging Module"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.mode != 'POSE':
            return False
        rig, oriented, _ = utilities.functions.get_armature_hierarchy(obj)
        if not oriented or obj not in (oriented, rig):
            return False
        if not obj.select_get():
            return False
        if not rig:
            return False
        return 0 <= rig.data.mmt.module < len(rig.data.mmt.rigging)

    def execute(self, context):
        rig, oriented, _ = utilities.functions.get_armature_hierarchy(context.object)
        index = rig.data.mmt.module
        item = rig.data.mmt.rigging[index]
        if item.module:
            # a built module gets torn down properly, which also resyncs the list...
            functions.remove_rigging_module(oriented, rig, item.module)
        else:
            # an empty, never-built placeholder has no bone collection to tear down, just drop it...
            rig.data.mmt.rigging.remove(index)
            rig.data.mmt.module = min(index, len(rig.data.mmt.rigging) - 1)
            functions.remove_empty_armature(oriented, rig)
        return {'FINISHED'}

class MMT_OT_Move(bpy.types.Operator):
    """Moves the selected rigging module up or down in the list."""
    bl_idname = "mmt.move"
    bl_label = "Move Rigging Module"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="Direction", description="Which way to move the selected module.",
        items=[('UP', "Up", ""), ('DOWN', "Down", "")], default='UP')

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.mode != 'POSE':
            return False
        rig, oriented, _ = utilities.functions.get_armature_hierarchy(obj)
        if not oriented or obj not in (oriented, rig):
            return False
        if not obj.select_get():
            return False
        if not rig:
            return False
        return 0 <= rig.data.mmt.module < len(rig.data.mmt.rigging)

    def execute(self, context):
        rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
        functions.set_module_moved(rig, self.direction)
        return {'FINISHED'}

class MMT_OT_Snap(bpy.types.Operator):
    """Snaps the active modules kinematic controls onto its current forward pose, so switching to ik doesn't pop."""
    bl_idname = "mmt.snap"
    bl_label = "Snap IK to FK"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.mode != 'POSE':
            return False
        rig, oriented, _ = utilities.functions.get_armature_hierarchy(obj)
        if not oriented or obj not in (oriented, rig):
            return False
        if not obj.select_get():
            return False
        if not rig:
            return False
        active = context.active_pose_bone
        if active and functions.get_active_module(rig, active.bone.name):
            return True
        return 0 <= rig.data.mmt.module < len(rig.data.mmt.rigging)

    def execute(self, context):
        rig, _, _ = utilities.functions.get_armature_hierarchy(context.object)
        # prefer the active bones module... (fall back to the properties list when nothing relevant is selected)...
        active = context.active_pose_bone
        item = functions.get_active_module(rig, active.bone.name) if active else None
        if not item:
            item = rig.data.mmt.rigging[rig.data.mmt.module]
        module_file = functions.get_module_file(item.rigging)
        snap = getattr(module_file, 'set_snapped_kinematics', None) if module_file else None
        if not snap:
            self.report({'WARNING'}, "Snapping isn't supported for this rigging type yet.")
            return {'FINISHED'}
        if not snap(context, item):
            self.report({'WARNING'}, "Could not snap - the module may not be fully built.")
        return {'FINISHED'}


