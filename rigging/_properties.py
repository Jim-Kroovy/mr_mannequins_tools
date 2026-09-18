import bpy

from bpy.props import (EnumProperty, BoolProperty, StringProperty, CollectionProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty)

from .. import utilities
from . import _functions as functions

class MMT_PG_Affix(bpy.types.PropertyGroup):

    affix: StringProperty(
        name="Affix", description="Bone name affix to use.",
        default="", update=functions.update_module_settings
        )

    unique: BoolProperty(
        name="Unique", description="The affix must be unique.",
        default=True, options={'HIDDEN'}
        )

    required: BoolProperty(
        name="Required", description="The affix is required.",
        default=True, options={'HIDDEN'}
        )

class MMT_PG_Color(bpy.types.PropertyGroup):

    def get_palette_items(self, context):
        # all colors except custom... (honestly because i'm lazy, maybe in the future)...
        palette, items = bpy.types.BoneColor.bl_rna.properties['palette'], []
        for i, e in enumerate(palette.enum_items):
            icon, number = "", e.identifier[len("THEME"):]
            if e.identifier.startswith('THEME'):
                icon = "COLORSET_" + number + "_VEC"
            item = (e.identifier, e.name, e.description, icon, i)
            items.append(item)
        return items

    palette: EnumProperty(
        name="Theme", description="Color palette to use.",
        items=get_palette_items, default=0, update=functions.update_module_settings, options=set()
        )

class MMT_PG_Shape(bpy.types.PropertyGroup):

    show: EnumProperty(
        name="Show", description="Show translation, rotation or scale settings.",
        items=[
            ('SHAPE', "Shape", "", 'OBJECT_DATA', 0),
            ('TRANSLATION', "Translation", "", 'CON_LOCLIKE', 1),
            ('ROTATION', "Rotation", "", 'CON_ROTLIKE', 2),
            ('SCALE', "Scale", "", 'CON_SIZELIKE', 3)
            ], default=0, options=set()
        )

    mesh: EnumProperty(
        name="Mesh", description="Custom shape to use.",
        items=utilities.functions.get_shape_items, default=0, update=functions.update_module_settings, options=set()
        )

    translation: FloatVectorProperty(
        name="Translation", description="Adjust the position of the custom shape.",
        default=(0.0, 0.0, 0.0), subtype='XYZ', update=functions.update_module_settings, options=set()
        )

    rotation: FloatVectorProperty(
        name="Rotation", description="Adjust the rotation of the custom shape.",
        default=(0.0, 0.0, 0.0), subtype='EULER', update=functions.update_module_settings, options=set()
        )

    space: StringProperty(
        name="Space", description="Which set of directions the custom shapes forward and upward settings are keyed into. "
        "BONE, WORLD or CHAIN.",
        default='CHAIN'
        )

    forward: StringProperty(
        name="Forward", description="Which direction the custom shapes Y axis should point along. "
        "+X, -X, +Y, -Y, +Z or -Z, keyed into whichever direction space this shape uses.",
        default='+X'
        )

    upward: StringProperty(
        name="Upward", description="Which direction the custom shapes Z axis should point along. "
        "+X, -X, +Y, -Y, +Z or -Z, keyed into whichever direction space this shape uses.",
        default='+Z'
        )

    scale: FloatVectorProperty(
        name="Scale", description="Adjust the rotation of the custom shape.",
        default=(1.0, 1.0, 1.0), subtype='XYZ', update=functions.update_module_settings, options=set()
        )

class MMT_PG_Axes(bpy.types.PropertyGroup):

    x: BoolProperty(
        name="X", description="Use X axis.",
        default=True, update=functions.update_module_settings, options=set()
        )

    y: BoolProperty(
        name="Y", description="Use Y axis.",
        default=True, update=functions.update_module_settings, options=set()
        )

    z: BoolProperty(
        name="Z", description="Use Z axis.",
        default=True, update=functions.update_module_settings, options=set()
        )

class MMT_PG_Rigging(bpy.types.PropertyGroup):

    offset: FloatProperty(
        name="Offset", description="The distance to offset the pole target bone by (negative inverts direction).",
        default=0.3, update=functions.update_module_settings, options=set()
        )

    position: FloatProperty(
        name="Position", description="The position along the chain to place the pole target.",
        default=0.5, min=0.0, max=1.0, update=functions.update_module_settings, options=set()
        )

    mirror: BoolProperty(name="Mirror Rigging", description="Attempt to mirror rigging using bone names.",
        default=False, update=functions.update_module_settings, options=set()
        )

    shared: BoolProperty(name="Edit Shared", description="Allow this module to edit bones (in edit mode) and restyle them (color/shape) even when they're shared with another module (eg. a chained origin/ending). Defaults to off if another module already claims the bone.",
        default=True, update=functions.update_module_settings, options=set()
        )

    count: IntProperty(
        name="Count", description="The amount of targets spread between start and end (cannot be less than two or greater than the chain length).",
        default=3, min=2, update=functions.update_module_settings, options=set()
        )

    influences: IntProperty(
        name="Influences", description="How many nearby targets blend together to drive each bones twist (cannot be more than 38 - the most a single twist drivers expression can fit).",
        default=2, min=1, max=38, update=functions.update_module_settings, options=set()
        )

    floor: BoolProperty(name="Floor Target", description="Add an IK floor target.",
        default=False, update=functions.update_module_settings, options=set()
        )

    inverse: BoolProperty(name="Inverse", description="Reverses the direction the generated influences spread across the chain.",
        default=False, update=functions.update_module_settings, options=set()
        )

    axis: EnumProperty(
        name="Axis", description="Axis for orienting straight bone chains. Y is excluded, that's always the primary chain axis.",
        items=[
            ('AUTO', "Auto", "Automatically detect the closest axis of the origin or first chain bone.", '', 0),
            ('+X', "+X", "", '', 1), ('-X', "-X", "", '', 2),
            ('+Z', "+Z", "", '', 3), ('-Z', "-Z", "", '', 4),
            ], default=0, update=functions.update_module_settings, options=set()
        )
    
    axes: CollectionProperty(type=MMT_PG_Axes)

    suffices: CollectionProperty(type=MMT_PG_Affix)

    prefices: CollectionProperty(type=MMT_PG_Affix)

    colors: CollectionProperty(type=MMT_PG_Color)

    shapes: CollectionProperty(type=MMT_PG_Shape)

class MMT_PG_Module(bpy.types.PropertyGroup):

    # internal guard, stops settings changes made while a rebuild is already in progress re-triggering it...
    updating: BoolProperty(
        name="Updating", description="Internal.",
        default=False, options={'HIDDEN', 'SKIP_SAVE'}
        )

    rigging: EnumProperty(
        name="Rigging", description="The type of rigging module.",
        items=[
            # first, so a freshly added items own enum default reliably resolves to it...
            ('NONE', "Select a module... ", "", 0),
            ('ROOT', "Root Controls", "Root motion rigging", 1),
            ('SPLINE', "Spline Chain", "Spline chain rigging", 2),
            ('OPPOSABLE', "Opposable Arm", "Opposable arm rigging", 3),
            ('PLANTIGRADE', "Plantigrade Leg", "Plantigrade leg rigging.", 4),
            ('DIGITIGRADE', 'Digitigrade Leg', "Digitigrade leg rigging.", 5),
            ('SCALAR', "Scalar Chain", "Scalar chain rigging", 6),
            ('CURL', "Curl Chain", "Curl chain rigging", 7),
            ('TWIST', "Twist Chain", "Twist chain rigging", 8),
            # always last - the fallback for when nothing else fits, new rigging types go above this one...
            ('CUSTOM', "Custom Bones", "Plain bones with no chain logic, added from selection", 9),
            ], default='NONE',
        update=functions.update_module_rigging, options=set()
        )

    module: StringProperty(
        name="Module", description="The unique identifier of the module",
        default=""
        )

    settings: PointerProperty(type=MMT_PG_Rigging)

    mirrored: PointerProperty(type=MMT_PG_Rigging)

    mirrored_name: StringProperty(name="Mirrored", description="Internal counterpart module name.", default="",
        options={'HIDDEN'})

    is_mirrored: BoolProperty(name="Mirrored Counterpart", description="Internal derived-mirror marker.", default=False,
        options={'HIDDEN'})
    
