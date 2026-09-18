import bpy

from bpy.utils import (register_class, unregister_class)
from bpy.props import (PointerProperty)

from . import _functions as functions
from . import _operators as operators
from . import _interface as interface
from . import _properties as properties
from ..utilities._properties import MMT_PG_Armature
from ..orientation._properties import MMT_PG_Orientation
from bpy.props import CollectionProperty

_keymaps = []

def register():
    MMT_PG_Armature.__annotations__['rigging'] = CollectionProperty(type=properties.MMT_PG_Module)
    MMT_PG_Armature.__annotations__['orientation'] = PointerProperty(type=MMT_PG_Orientation)
    # general properties...
    register_class(properties.MMT_PG_Affix)
    register_class(properties.MMT_PG_Color)
    register_class(properties.MMT_PG_Shape)
    register_class(properties.MMT_PG_Axes)
    register_class(properties.MMT_PG_Rigging)
    register_class(properties.MMT_PG_Module)
    register_class(MMT_PG_Armature)
    # rigging modules list... (much like bone collections, lives on the armature data itself)...
    register_class(interface.MMT_UL_Modules)
    register_class(interface.MMT_PT_Modules)
    register_class(interface.MMT_PT_Controls)
    register_class(operators.MMT_OT_Add)
    register_class(operators.MMT_MT_AddRigging)
    register_class(operators.MMT_MT_ModuleOptions)
    register_class(operators.MMT_OT_Remove)
    register_class(operators.MMT_OT_Move)
    register_class(operators.MMT_OT_Snap)
    bpy.types.Armature.mmt = PointerProperty(type=MMT_PG_Armature)
    bpy.types.VIEW3D_MT_pose.append(operators.add_rigging_operator)
    keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
    if keymaps:
        keymap = keymaps.new(name='Pose', space_type='EMPTY', region_type='WINDOW')
        keymap_item = keymap.keymap_items.new('wm.call_menu', 'A', 'PRESS', shift=True, head=True)
        keymap_item.properties.name = operators.MMT_MT_AddRigging.bl_idname
        _keymaps.append((keymap, keymap_item))
    # child of matrix refresh...
    register_class(operators.MMT_OT_Refresh)
    register_class(operators.MMT_OT_Rebuild)
    register_class(operators.MMT_OT_Copy)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_refresh_operator)
    # custom shapes...
    register_class(operators.MMT_OT_Shapes)
    bpy.types.VIEW3D_MT_object.append(operators.add_shape_operator)

def unregister():
    # custom shapes...
    bpy.types.VIEW3D_MT_object.remove(operators.add_shape_operator)
    unregister_class(operators.MMT_OT_Shapes)
    # child of matrix refresh...
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_refresh_operator)
    unregister_class(operators.MMT_OT_Copy)
    unregister_class(operators.MMT_OT_Rebuild)
    unregister_class(operators.MMT_OT_Refresh)
    # rigging modules list...
    del bpy.types.Armature.mmt
    bpy.types.VIEW3D_MT_pose.remove(operators.add_rigging_operator)
    for keymap, keymap_item in _keymaps:
        keymap.keymap_items.remove(keymap_item)
    _keymaps.clear()
    unregister_class(operators.MMT_OT_Snap)
    unregister_class(operators.MMT_OT_Move)
    unregister_class(operators.MMT_OT_Remove)
    unregister_class(operators.MMT_MT_ModuleOptions)
    unregister_class(operators.MMT_OT_Add)
    unregister_class(operators.MMT_MT_AddRigging)
    unregister_class(interface.MMT_PT_Controls)
    unregister_class(interface.MMT_PT_Modules)
    unregister_class(interface.MMT_UL_Modules)
    # general properties...
    unregister_class(properties.MMT_PG_Affix)
    unregister_class(properties.MMT_PG_Color)
    unregister_class(properties.MMT_PG_Shape)
    unregister_class(properties.MMT_PG_Rigging)
    unregister_class(properties.MMT_PG_Axes)
    unregister_class(MMT_PG_Armature)
    unregister_class(properties.MMT_PG_Module)
