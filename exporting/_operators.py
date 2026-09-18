import bpy
import os
import json

from bpy.props import (BoolProperty, StringProperty, PointerProperty)

from bpy_extras.io_utils import ExportHelper

from .. import utilities
from . import _functions as functions
from . import _interface as interface
from . import _properties as properties

class MMT_OT_Export(bpy.types.Operator, ExportHelper):
    """Exports armatures and meshes as compatible FBX files."""
    bl_idname = "mmt.export"
    bl_label = "Compatible FBX"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".fbx"

    filter_glob: StringProperty(
        default="*.fbx", options={'HIDDEN'}
        )

    only_selected: BoolProperty(
        name="Only Selected", description="Only include selected meshes and armatures.",
        default=True
        )

    background: BoolProperty(
        name="Background Export", description="Run the export against in a background process because so the open file remains untouched (Warning; only set false for debugging).",
        default=True
        )

    settings: PointerProperty(type=properties.MMT_PG_Export)

    def invoke(self, context, event):
        # restore whatever was last used, so settings persist across files/sessions...
        prefs = utilities.functions.get_addon_preferences(context)
        if prefs.export_settings:
            try:
                utilities.functions.set_deserialized_settings(self.settings, json.loads(prefs.export_settings))
            except (ValueError, TypeError):
                pass
        # detect the export assets by name, there are no per-item checkboxes to sync into settings anymore...
        self._statics, self._targets = functions.get_export_assets(self.only_selected)
        self._only_selected = self.only_selected
        return ExportHelper.invoke(self, context, event)

    def check(self, context):
        # only re-scan when only_selected itself changes...
        if self._only_selected == self.only_selected:
            return False
        self._statics, self._targets = functions.get_export_assets(self.only_selected)
        self._only_selected = self.only_selected
        return True

    def draw(self, context):
        interface.draw_export_dialog(self, context)

    def execute(self, context):
        # remember these settings for next time, regardless of whether the export itself succeeds...
        prefs = utilities.functions.get_addon_preferences(context)
        prefs.export_settings = json.dumps(utilities.functions.get_serialized_settings(self.settings))
        # a script/macro call can reach execute() without ever going through invoke()...
        if not hasattr(self, '_statics'):
            self._statics, self._targets = functions.get_export_assets(self.only_selected)
        # background exports run against a disposable file copy, so nothing here needs saving/restoring...
        if self.background:
            success, error = functions.export_filmbox_background(os.path.dirname(self.filepath), self.settings, self._statics, self._targets)
            if not success:
                self.report({'ERROR'}, error)
                return {'CANCELLED'}
            return {'FINISHED'}
        mode, selected, active = utilities.functions.get_current_objects(context)
        try:
            functions.export_filmbox_assets(os.path.dirname(self.filepath), self.settings, self._statics, self._targets)
        except RuntimeError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        finally:
            utilities.functions.set_current_objects(mode, selected, active)
        return {'FINISHED'}

def add_export_operator(self, context):
    self.layout.operator(MMT_OT_Export.bl_idname, text="Mr Mannequins FBX (.fbx)", icon='USER')
