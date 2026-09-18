import bpy

from .. import utilities
from . import _functions as functions
from . import _operators as operators

class MMT_MT_Templates(bpy.types.Menu):
    bl_idname = "MMT_MT_Templates"
    bl_label = "Template"

    def draw(self, context):
        layout = self.layout
        prefs = utilities.functions.get_addon_preferences(context)
        functions.set_template_items(prefs)
        for identifier, name, description, icon, index in prefs.template_items:
            if identifier == 'NONE':
                layout.label(text=name, icon=icon)
                continue
            op = layout.operator(operators.MMT_OT_Template.bl_idname, text=name)#, icon=icon)
            op.template = identifier

def add_templates_menu(self, context):
    self.layout.separator()
    self.layout.menu(MMT_MT_Templates.bl_idname, icon='USER')
