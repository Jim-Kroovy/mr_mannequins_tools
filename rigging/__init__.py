import bpy

from bpy.utils import (register_class, unregister_class)
from bpy.props import (PointerProperty)

from . import _functions as functions
from . import _operators as operators
from . import _interface as interface
from . import _properties as properties
from ..utilities._properties import MMT_PG_UtilitiesArmature
from ..orientation._properties import MMT_PG_OrientationSettings
from bpy.props import CollectionProperty

_keymaps = []

def register():
    MMT_PG_UtilitiesArmature.__annotations__['rigging'] = CollectionProperty(type=properties.MMT_PG_RiggingModule)
    MMT_PG_UtilitiesArmature.__annotations__['orientation'] = PointerProperty(type=MMT_PG_OrientationSettings)
    # general properties...
    register_class(properties.MMT_PG_RiggingAffix)
    register_class(properties.MMT_PG_RiggingColor)
    register_class(properties.MMT_PG_RiggingShape)
    register_class(properties.MMT_PG_RiggingAxes)
    register_class(properties.MMT_PG_RiggingSettings)
    register_class(properties.MMT_PG_RiggingModule)
    register_class(MMT_PG_UtilitiesArmature)
    # rigging modules list... (much like bone collections, lives on the armature data itself)...
    register_class(interface.MMT_UL_RiggingModules)
    register_class(interface.MMT_PT_RiggingModules)
    register_class(interface.MMT_PT_RiggingControls)
    register_class(operators.MMT_OT_RiggingAddModule)
    register_class(operators.MMT_MT_RiggingAdd)
    register_class(operators.MMT_MT_RiggingModuleOptions)
    register_class(operators.MMT_OT_RiggingRemoveModule)
    register_class(operators.MMT_OT_RiggingMoveModule)
    register_class(operators.MMT_OT_RiggingSnap)
    bpy.types.Armature.mmt = PointerProperty(type=MMT_PG_UtilitiesArmature)
    bpy.types.VIEW3D_MT_pose.append(operators.add_rigging_operator)
    keymaps = bpy.context.window_manager.keyconfigs.addon.keymaps
    # no keyconfig in background, so only add the hotkey if there is one...
    if keymaps:
        keymap = keymaps.new(name='Pose', space_type='EMPTY', region_type='WINDOW')
        keymap_item = keymap.keymap_items.new('wm.call_menu', 'A', 'PRESS', shift=True, head=True)
        keymap_item.properties.name = operators.MMT_MT_RiggingAdd.bl_idname
        _keymaps.append((keymap, keymap_item))
    # child of matrix refresh...
    register_class(operators.MMT_OT_RiggingRefresh)
    register_class(operators.MMT_OT_RiggingRebuild)
    register_class(operators.MMT_OT_RiggingCopy)
    bpy.types.VIEW3D_MT_pose_apply.append(operators.add_refresh_operator)
    # custom shapes...
    register_class(operators.MMT_OT_RiggingShapes)
    bpy.types.VIEW3D_MT_object.append(operators.add_shape_operator)

def unregister():
    # custom shapes...
    bpy.types.VIEW3D_MT_object.remove(operators.add_shape_operator)
    unregister_class(operators.MMT_OT_RiggingShapes)
    # child of matrix refresh...
    bpy.types.VIEW3D_MT_pose_apply.remove(operators.add_refresh_operator)
    unregister_class(operators.MMT_OT_RiggingCopy)
    unregister_class(operators.MMT_OT_RiggingRebuild)
    unregister_class(operators.MMT_OT_RiggingRefresh)
    # rigging modules list...
    del bpy.types.Armature.mmt
    bpy.types.VIEW3D_MT_pose.remove(operators.add_rigging_operator)
    for keymap, keymap_item in _keymaps:
        keymap.keymap_items.remove(keymap_item)
    _keymaps.clear()
    unregister_class(operators.MMT_OT_RiggingSnap)
    unregister_class(operators.MMT_OT_RiggingMoveModule)
    unregister_class(operators.MMT_OT_RiggingRemoveModule)
    unregister_class(operators.MMT_MT_RiggingModuleOptions)
    unregister_class(operators.MMT_OT_RiggingAddModule)
    unregister_class(operators.MMT_MT_RiggingAdd)
    unregister_class(interface.MMT_PT_RiggingControls)
    unregister_class(interface.MMT_PT_RiggingModules)
    unregister_class(interface.MMT_UL_RiggingModules)
    # general properties...
    unregister_class(properties.MMT_PG_RiggingAffix)
    unregister_class(properties.MMT_PG_RiggingColor)
    unregister_class(properties.MMT_PG_RiggingShape)
    unregister_class(properties.MMT_PG_RiggingSettings)
    unregister_class(properties.MMT_PG_RiggingAxes)
    unregister_class(MMT_PG_UtilitiesArmature)
    unregister_class(properties.MMT_PG_RiggingModule)
