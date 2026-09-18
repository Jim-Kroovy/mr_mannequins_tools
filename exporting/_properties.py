import bpy

from bpy.props import (EnumProperty, BoolProperty, StringProperty, FloatProperty, PointerProperty)

class MMT_PG_ExportFBX(bpy.types.PropertyGroup):

    scaling: FloatProperty(
        name="Scale", description="Scale all data.",
        default=1.0, min=0.001, max=1000.0
        )

    forward: EnumProperty(
        name="Forward", description="Forward axis.",
        items=[
            ('X', "X Forward", "", '', 0), ('Y', "Y Forward", "", '', 1), ('Z', "Z Forward", "", '', 2),
            ('-X', "-X Forward", "", '', 3), ('-Y', "-Y Forward", "", '', 4), ('-Z', "-Z Forward", "", '', 5),
            ], default=5
        )

    upward: EnumProperty(
        name="Up", description="Up axis.",
        items=[
            ('X', "X Up", "", '', 0), ('Y', "Y Up", "", '', 1), ('Z', "Z Up", "", '', 2),
            ('-X', "-X Up", "", '', 3), ('-Y', "-Y Up", "", '', 4), ('-Z', "-Z Up", "", '', 5),
            ], default=1
        )

    smoothing: EnumProperty(
        name="Smoothing", description="Export smoothing information.",
        items=[
            ('OFF', "Normals Only", "Export only normals instead of writing edge or face smoothing data.", '', 0),
            ('FACE', "Face", "Write face smoothing.", '', 1),
            ('EDGE', "Edge", "Write edge smoothing.", '', 2),
            ], default=1
        )

    colors: EnumProperty(
        name="Vertex Colors", description="Export vertex color attributes.",
        items=[
            ('NONE', "None", "Do not export color attributes.", '', 0),
            ('SRGB', "sRGB", "Export colors in sRGB color space.", '', 1),
            ('LINEAR', "Linear", "Export colors in linear color space.", '', 2),
            ], default=1
        )

    prioritize: BoolProperty(
        name="Prioritize Active Color", description="Make sure the active color will be exported first (unless 'None' is chosen for Vertex Colors).",
        default=False
        )

    edges: BoolProperty(
        name="Loose Edges", description="Export loose edges (as two-vertices polygons).",
        default=False
        )

    tangents: BoolProperty(
        name="Tangent Space", description="Add binormal and tangent vectors, together with normal they form the tangent space (will only work correctly with tris/quads only meshes).",
        default=False
        )

    triangles: BoolProperty(
        name="Triangulate Faces", description="Convert all faces to triangles.",
        default=False
        )

    primary: EnumProperty(
        name="Primary Bone Axis", description="Primary bone axis.",
        items=[
            ('X', "X Axis", "", '', 0), ('Y', "Y Axis", "", '', 1), ('Z', "Z Axis", "", '', 2),
            ('-X', "-X Axis", "", '', 3), ('-Y', "-Y Axis", "", '', 4), ('-Z', "-Z Axis", "", '', 5),
            ], default=1
        )

    secondary: EnumProperty(
        name="Secondary Bone Axis", description="Secondary bone axis.",
        items=[
            ('X', "X Axis", "", '', 0), ('Y', "Y Axis", "", '', 1), ('Z', "Z Axis", "", '', 2),
            ('-X', "-X Axis", "", '', 3), ('-Y', "-Y Axis", "", '', 4), ('-Z', "-Z Axis", "", '', 5),
            ], default=0
        )

    animations: BoolProperty(
        name="Animation", description="Export baked keyframe animation.",
        default=True
        )

    step: FloatProperty(
        name="Sampling Rate", description="How often to evaluate animated values (in frames).",
        default=1.0, min=0.01, max=100.0
        )

    simplify: FloatProperty(
        name="Simplify", description="How much to simplify baked values (0.0 to disable, the higher the more simplified).",
        default=0.0, min=0.0, max=100.0
        )

    use_mesh_modifiers: BoolProperty(
        name="Apply Modifiers", description="Apply modifiers before export (destructive, kills shape keys). Hidden when Armature Intuitive Meshes is installed.",
        default=False
        )

    use_metadata: BoolProperty(
        name="Metadata", description="Export metadata (creator, ...).",
        default=True
        )

class MMT_PG_Clean(bpy.types.PropertyGroup):
 
    prefix: StringProperty(
        name="Prefix", description="Only clean data that starts with this prefix.",
        default=""
        )

    shapes: BoolProperty(
        name="Shape Keys", description="Remove shape keys that start with the prefix.",
        default=False
        )

    groups: BoolProperty(
        name="Vertex Groups", description="Remove vertex groups that start with the prefix.",
        default=False
        )

    materials: BoolProperty(
        name="Materials", description="Remove material slots that start with the prefix.",
        default=False
        )

class MMT_PG_Meshes(bpy.types.PropertyGroup):

    export: BoolProperty(
        name="Export", description="Export meshes.",
        default=True
        )

    folder: StringProperty(
        name="Folder", description="The folder in the export directory to export meshes to.",
        default="")

    modifiers: BoolProperty(
        name="Apply Modifiers", description="Apply modifiers non-destructively before export (supports shape keys).",
        default=True
        )

    batch: BoolProperty(
        name="Batch Export", description="Batch export meshes to individual files (socket meshes always batch export)",
        default=True
        )

    suffix: BoolProperty(
        name="Socket Suffices", description="Add socket bone name as a suffix to the exported file (only for socket meshes).",
        default=True
        )
    
    static: BoolProperty(
        name="Static Meshes", description="Export static meshes.",
        default=True
        )

    skeletal: BoolProperty(
        name="Skeletal Meshes", description="Export skeletal meshes.",
        default=True
        )

    socket: BoolProperty(
        name="Socket Meshes", description="Export socket meshes.",
        default=True
        )

class MMT_PG_Action(bpy.types.PropertyGroup):

    export: BoolProperty(
        name="Export", description="Export actions.",
        default=True
        )

    folder: StringProperty(
        name="Folder", description="The folder in the export directory to export these actions to.",
        default="")
    
    method: EnumProperty(
        name="Method", description="The actions that are assigned to armatures.",
        items=[
            ('ACTIVE', "Only Active", "Export only the active action on armatures.", '', 0),
            ('STASHED', "Only Stashed", "Export only the stashed actions on armatures.", '', 1),
            ('ALL', "All Actions", "Export all actions that the armature can use.", '', 2),
            ], default=0
        )
    
    batch: BoolProperty(
        name="Batch Export", description="Batch export baked actions to individual files, otherwise merge them into one file as separate FBX animation stacks.",
        default=True
        )

class MMT_PG_Export(bpy.types.PropertyGroup):

    filmbox: PointerProperty(type=MMT_PG_ExportFBX, name="Filmbox")

    meshes: PointerProperty(type=MMT_PG_Meshes, name="Meshes")

    action: PointerProperty(type=MMT_PG_Action, name="Action")

    clean: PointerProperty(type=MMT_PG_Clean, name="Clean")
