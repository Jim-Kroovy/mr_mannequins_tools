import bpy

from .. import utilities
from . import _functions

rigging_types = {'TWIST', 'OPPOSABLE', 'PLANTIGRADE', 'DIGITIGRADE', 'SCALAR', 'SPLINE', 'CURL', 'ROOT'}

def draw_module_controls(layout, rig, rigging, module):
    # deferred imports avoid a circular import...
    if rigging == 'TWIST':
        from .modules import twist
        twist.draw_twist_controls(layout, rig, module)
    elif rigging == 'OPPOSABLE':
        from .modules import opposable
        opposable.draw_opposable_controls(layout, rig, module)
    elif rigging == 'PLANTIGRADE':
        from .modules import plantigrade
        plantigrade.draw_plantigrade_controls(layout, rig, module)
    elif rigging == 'DIGITIGRADE':
        from .modules import digitigrade
        digitigrade.draw_digitigrade_controls(layout, rig, module)
    elif rigging == 'SCALAR':
        from .modules import scalar
        scalar.draw_scalar_controls(layout, rig, module)
    elif rigging == 'SPLINE':
        from .modules import spline
        spline.draw_spline_controls(layout, rig, module)
    elif rigging == 'CURL':
        from .modules import curl
        curl.draw_curl_controls(layout, rig, module)
    elif rigging == 'ROOT':
        from .modules import root
        root.draw_root_controls(layout, rig, module)

class MMT_UL_Modules(bpy.types.UIList):
    bl_idname = "MMT_UL_Modules"

    icons = {
        'TWIST' : 'CON_LOCKTRACK', 'CURL' : 'CON_ROTLIKE', 'SPLINE' : 'CURVE_BEZCURVE',
        'SCALAR' : 'CON_SIZELIKE', 'OPPOSABLE' : 'CON_KINEMATIC',
        'PLANTIGRADE' : 'CON_KINEMATIC', 'DIGITIGRADE' : 'CON_KINEMATIC',
        'ROOT' : 'CON_CHILDOF', 'CUSTOM' : 'BONE_DATA',
        }

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row()
        row.label(text=item.module, icon=self.icons.get(item.rigging, 'ARMATURE_DATA'))

def draw_module_settings(layout, oriented, module):
    # deferred imports avoid a circular import...
    if module.rigging == 'TWIST':
        from .modules import twist
        twist.draw_twist_settings(layout, oriented, module)
    elif module.rigging == 'OPPOSABLE':
        from .modules import opposable
        opposable.draw_opposable_settings(layout, oriented, module)
    elif module.rigging == 'PLANTIGRADE':
        from .modules import plantigrade
        plantigrade.draw_plantigrade_settings(layout, oriented, module)
    elif module.rigging == 'DIGITIGRADE':
        from .modules import digitigrade
        digitigrade.draw_digitigrade_settings(layout, oriented, module)
    elif module.rigging == 'SCALAR':
        from .modules import scalar
        scalar.draw_scalar_settings(layout, oriented, module)
    elif module.rigging == 'SPLINE':
        from .modules import spline
        spline.draw_spline_settings(layout, oriented, module)
    elif module.rigging == 'CURL':
        from .modules import curl
        curl.draw_curl_settings(layout, oriented, module)
    elif module.rigging == 'ROOT':
        from .modules import root
        root.draw_root_settings(layout, oriented, module)
    elif module.rigging == 'CUSTOM':
        from .modules import custom
        custom.draw_custom_settings(layout, oriented, module)

class MMT_PT_Modules(bpy.types.Panel):
    bl_idname = "MMT_PT_Modules"
    bl_label = "Rigging Modules"
    bl_order = 1
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj:
            return False
        rig, oriented, original = utilities.functions.get_armature_hierarchy(obj)
        oriented = oriented or original
        if not oriented or obj not in (oriented, original, rig):
            return False
        return obj.select_get()

    def draw(self, context):
        layout = self.layout
        posed = context.object.mode == 'POSE'
        rig, oriented, original = utilities.functions.get_armature_hierarchy(context.object)
        oriented = oriented or original
        # no rigging armature yet means no modules added, list stays empty... (kept in sync by add/remove)...
        data = rig.data if rig else oriented.data
        row = layout.row()
        row.template_list("MMT_UL_Modules", "", data.mmt, "rigging", data.mmt, "module")
        col = row.column(align=True)
        # editing the list only makes sense in pose mode, everywhere else it's read only...
        col.enabled = posed
        add = col.operator("mmt.add", icon='ADD', text="")
        add.rigging_type = 'NONE'
        col.operator("mmt.remove", icon='REMOVE', text="")
        col.separator()
        col.operator("mmt.move", icon='TRIA_UP', text="").direction = 'UP'
        col.operator("mmt.move", icon='TRIA_DOWN', text="").direction = 'DOWN'
        col.separator()
        col.menu("MMT_MT_module_options", icon='DOWNARROW_HLT', text="")
        # settings and controls both need pose bones to work on, so only show them in pose mode...
        if posed and 0 <= data.mmt.module < len(data.mmt.rigging):
            item = data.mmt.rigging[data.mmt.module]
            # the rigging type picker always shows, everything else depends on a type being picked...
            row = layout.row()
            row.use_property_split = True
            row.prop(item, 'rigging')
            reference = item
            if item.rigging == 'NONE':
                # keep the panel stable while an empty module awaits its rigging type...
                reference = next((data.mmt.rigging[i] for i in range(data.mmt.module - 1, -1, -1)
                    if data.mmt.rigging[i].rigging != 'NONE'), None)
            if reference and reference.rigging != 'NONE':
                # collapsible like blenders own sub-panels (eg. custom shape under viewport display)...
                header, panel = layout.panel("mmt_module_settings", default_closed=False)
                header.label(text="Settings" if reference == item else "Settings (previous module)")
                if panel:
                    panel.enabled = reference == item
                    draw_module_settings(panel, oriented, reference)
                # naming, colors and shapes are generic across every module, so they don't need dispatching...
                prefices = [p for p in reference.settings.prefices]
                header, panel = layout.panel("mmt_settings_naming", default_closed=True)
                header.label(text="Naming")
                if panel:
                    panel.enabled = reference == item
                    show_operator_naming(panel, reference, _functions.get_naming_validity(prefices))
                header, panel = layout.panel("mmt_settings_colors", default_closed=True)
                header.label(text="Colors")
                if panel:
                    show_operator_colors(panel, item)
                header, panel = layout.panel("mmt_settings_shapes", default_closed=True)
                header.label(text="Shapes")
                if panel:
                    show_operator_shapes(panel, item)
            if item.rigging in rigging_types:
                header, panel = layout.panel("mmt_module_controls", default_closed=True)
                header.label(text="Controls")
                if panel:
                    draw_module_controls(panel, rig, item.rigging, item.module)

class MMT_PT_Controls(bpy.types.Panel):
    bl_idname = "MMT_PT_Controls"
    bl_label = "Controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Animation"

    @classmethod
    def poll(cls, context):
        obj = context.object
        if not obj or obj.mode != 'POSE' or obj.get('Armature Type') != "Rigging":
            return False
        return len(obj.data.mmt.rigging) > 0

    def draw(self, context):
        layout = self.layout
        rig = context.object
        active = context.active_pose_bone
        if not active:
            layout.label(text="No active bone.", icon='INFO')
            return
        # find whichever module instance the active bone actually belongs to...
        module = _functions.get_active_module(rig, active.bone.name)
        if not module:
            layout.label(text="Active bone isn't part of a rigging module.", icon='INFO')
            return
        layout.label(text=module.module, icon='ARMATURE_DATA')
        draw_module_controls(layout, rig, module.rigging, module.module)

def show_operator_settings(layout, module, oriented, settings, validity):
    # showing settings may need to be restricted per module... (iterate on required identifiers)...
    settings = [identifier for identifier in settings if identifier != 'mirror'] + (['mirror'] if 'mirror' in settings else [])
    for identifier in settings:
        # if the item is a pointer... (origin, end, root)...
        if module.settings.bl_rna.properties[identifier].type == 'POINTER':
            # we display as a property search on the armatures bones...
            item = getattr(module.settings, identifier)
            # alerting if there is a volidity conflict...
            invalid = (item.name in validity and not validity[item.name])
            row = layout.row()
            row.use_property_split = True
            row.alert = (invalid)
            icon = 'ERROR' if invalid else 'BONE_DATA'
            row.prop_search(item, 'affix', oriented.data, 'bones', text=item.name.capitalize(), icon=icon)
        # if the item is a collection... (chain, naming, colors, shapes)...
        elif module.settings.bl_rna.properties[identifier].type == 'COLLECTION':
            items = getattr(module.settings, identifier)
            has_axes = len(module.settings.axes) > 0
            for item in items:
                # alerting if there is a volidity conflict...
                invalid = (item.name in validity and not validity[item.name])
                icon = 'ERROR' if invalid else 'BONE_DATA'
                row = layout.row(align=True)
                row.use_property_split = True
                row.alert = (invalid)
                row.prop_search(item, 'affix', oriented.data, 'bones', text=item.name.capitalize(), icon=icon)
                if has_axes:
                    axes = module.settings.axes.get(item.name)
                    toggles = row.row(align=True)
                    toggles.ui_units_x = 3.5
                    if axes:
                        toggles.prop(axes, 'x', text="X", toggle=True)
                        toggles.prop(axes, 'y', text="Y", toggle=True)
                        toggles.prop(axes, 'z', text="Z", toggle=True)
        # else it's going to be a top level standard setting...
        else:
            # each setting gets its own row... (mirror stays at the bottom for every module)...
            row = layout.row()
            row.use_property_split = True
            row.prop(module.settings, identifier)

def show_operator_naming(layout, module, validity):
    # showing naming is a bit simpler... (dynamic collection)...
    for prefix in module.settings.prefices:
        invalid = (prefix.name in validity and not validity[prefix.name])
        row = layout.row()
        row.use_property_split = True
        row.alert = (invalid)
        row.prop(prefix, 'affix', text=prefix.name.capitalize())

def show_operator_colors(layout, module):
    # showing colors is even simpler... (dynamic collection without validity)...
    for color in module.settings.colors:
        row = layout.row()
        row.use_property_split = True
        row.prop(color, 'palette', text=color.name.capitalize())

def show_operator_shapes(layout, module):
    # show shapes needs to squeeze more data into a small space...
    for shape in module.settings.shapes:
        row = layout.row(align=True)
        row.use_property_split = True
        if shape.show == 'SHAPE':
            row.prop(shape, 'mesh', text=shape.name.capitalize())
        elif shape.show == 'TRANSLATION':
            row.prop(shape, 'translation', index=0, text=shape.name.capitalize())
            row.prop(shape, 'translation', index=1, text="")
            row.prop(shape, 'translation', index=2, text="")
        elif shape.show == 'ROTATION':
            row.prop(shape, 'rotation', index=0, text=shape.name.capitalize())
            row.prop(shape, 'rotation', index=1, text="")
            row.prop(shape, 'rotation', index=2, text="")
        elif shape.show == 'SCALE':
            row.prop(shape, 'scale', index=0, text=shape.name.capitalize())
            row.prop(shape, 'scale', index=1, text="")
            row.prop(shape, 'scale', index=2, text="")
        row.prop(shape, 'show', text="", icon_only=True)


