import os
import json

import bpy

from bpy.props import (StringProperty, CollectionProperty, PointerProperty)

from bpy_extras.io_utils import ImportHelper

from .. import utilities
from . import _functions as functions
from . import _interface as interface
from . import _properties as properties

class MMT_OT_Import(bpy.types.Operator, ImportHelper):
    """Imports compatible FBX files."""
    bl_idname = "mmt.import"
    bl_label = "Mr Mannequins FBX"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".fbx"

    filter_glob: StringProperty(
        default="*.fbx", options={'HIDDEN'}
        )

    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})

    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})

    settings: PointerProperty(type=properties.MMT_PG_Import)

    def invoke(self, context, event):
        # restore whatever was last used, so settings persist across files/sessions...
        prefs = utilities.functions.get_addon_preferences(context)
        if prefs.import_settings:
            try:
                utilities.functions.set_deserialized_settings(self.settings, json.loads(prefs.import_settings))
            except (ValueError, TypeError):
                pass
        return ImportHelper.invoke(self, context, event)

    def draw(self, context):
        interface.draw_import_dialog(self, context)

    def execute(self, context):
        # remember these settings for next time, regardless of whether the import itself succeeds...
        prefs = utilities.functions.get_addon_preferences(context)
        prefs.import_settings = json.dumps(utilities.functions.get_serialized_settings(self.settings))
        filepaths = [os.path.join(self.directory, f.name) for f in self.files] if self.files else [self.filepath]
        # only the mode needs restoring - the imported statics/skeletons are meant to end up selected/active, same as any other importer...
        mode, selected, active = utilities.functions.get_current_objects(context)
        # target is a dynamic enum rebuilt from bpy.data.objects, so it has to resolve here, before importing adds a new armature of its own - reading it any later re-runs the same callback against a list that new armature just joined, silently landing on whatever sorts into its old index instead...
        target = bpy.data.objects.get(self.settings.retargeting.target)
        try:
            statics, skeletons, removals = functions.get_imported_assets(context, filepaths, self.settings)
            functions.set_imported_assets(context, self.settings, statics, skeletons, removals, target)
        except RuntimeError as error:
            self.report({'ERROR'}, str(error))
            utilities.functions.set_current_objects(mode, selected, active)
            return {'CANCELLED'}
        # mode_set always needs an active object regardless of target mode, and pose mode specifically only applies back if an armature actually ended up active (eg. a statics-only import wouldn't have one)...
        current = context.view_layer.objects.active
        if current and (mode != 'POSE' or current.type == 'ARMATURE'):
            bpy.ops.object.mode_set(mode=mode)
        return {'FINISHED'}

def add_import_operator(self, context):
    self.layout.operator(MMT_OT_Import.bl_idname, text="Mr Mannequins FBX (.fbx)", icon='USER')
