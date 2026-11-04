import bpy

from bpy.props import StringProperty, FloatVectorProperty, FloatProperty, BoolProperty, IntProperty, CollectionProperty, EnumProperty

from . import _functions as functions

def update_split_count(self, context):
    # resizes the split list to exactly the count without changing entries already authored... (only once the dialog has filled it in)...
    if not self.resizing and self.source_name:
        self.resizing = True
        try:
            functions.set_split_count(self)
        finally:
            self.resizing = False

def update_swing_count(self, context):
    # resizes the swing list to exactly the count... (new default entries on the end, or trimmed off the end)...
    if not self.resizing:
        self.resizing = True
        while len(self.swings) < self.swing_count:
            self.swings.add()
        while len(self.swings) > self.swing_count:
            self.swings.remove(len(self.swings) - 1)
        self.resizing = False

def update_direction_count(self, context):
    # resizes this actions directions to exactly its count, keeping the ones already authored... (an empty list is blender filling it in from a script, so it's left for the script to fill)...
    if self.directions:
        functions.set_redirect_directions(self)

def update_redirect_action(self, context):
    # picking an action names any of its directions that are still blank after it, never one that was typed in...
    for direction in self.directions:
        if not direction.action_name:
            direction.action_name = self.action

class MMT_PG_KeyframingRedirectDirection(bpy.types.PropertyGroup):

    axis: EnumProperty(
        name="Axis", description="The world space axis to rotate the motion around.",
        items=[
            ('X', "X", "", '', 0),
            ('Y', "Y", "", '', 1),
            ('Z', "Z", "", '', 2),
            ], default='Z'
        )

    angle: FloatProperty(
        name="Angle", description="How far to rotate the motion around the axis.",
        subtype='ANGLE', default=0.0
        )

    action_name: StringProperty(
        name="New Action", description="The name of this new redirected action. (a taken name gets a .001 style suffix)",
        default=""
        )

class MMT_PG_KeyframingRedirectAction(bpy.types.PropertyGroup):

    # operators can't hold data-block pointers, so the action is found by name...
    action: StringProperty(
        name="Action", description="The action to redirect.",
        default="", update=update_redirect_action
        )

    direction_count: IntProperty(
        name="Directions", description="How many redirected actions to make from this action, one per direction.",
        default=1, min=1, max=64, update=update_direction_count
        )

    directions: CollectionProperty(type=MMT_PG_KeyframingRedirectDirection)

class MMT_PG_KeyframingRedirect(bpy.types.PropertyGroup):

    # filled in from the active action or the selected nla tracks when the dialog opens...
    actions: CollectionProperty(type=MMT_PG_KeyframingRedirectAction)

class MMT_PG_KeyframingTransferEntry(bpy.types.PropertyGroup):

    # operators can't hold data-block pointers, so the action is found by name...
    action: StringProperty(
        name="Action", description="The action to transfer motion in.",
        default=""
        )

    direction: FloatVectorProperty(
        name="Direction", description="The world space direction of travel to transfer for this action.",
        size=3, subtype='XYZ', default=(0.0, 1.0, 0.0)
        )

class MMT_PG_KeyframingTransfer(bpy.types.PropertyGroup):

    # filled in from the active action or the selected nla tracks when the dialog opens...
    transfers: CollectionProperty(type=MMT_PG_KeyframingTransferEntry)

class MMT_PG_KeyframingLocomotionSwing(bpy.types.PropertyGroup):

    bone: StringProperty(
        name="Bone", description="The bone to swing.",
        default=""
        )

    pivot: StringProperty(
        name="Pivot", description="The bone to swing around, the swing follows it as it moves.",
        default=""
        )

    minimum: FloatVectorProperty(
        name="Min", description="The world space X, Y and Z angles the swing starts and ends each oscillation at.",
        size=3, subtype='EULER', default=(0.0, 0.0, 0.0)
        )

    maximum: FloatVectorProperty(
        name="Max", description="The world space X, Y and Z angles the swing reaches halfway through each oscillation.",
        size=3, subtype='EULER', default=(0.0, 0.0, 0.0)
        )

    frequency: IntProperty(
        name="Frequency", description="How many complete swings happen per locomotion loop.",
        default=1, min=1
        )

class MMT_PG_KeyframingLocomotion(bpy.types.PropertyGroup):

    action_name: StringProperty(
        name="Action Name", description="The name for the newly generated action.",
        default=""
        )

    root_bone: StringProperty(
        name="Root", description="The root bone, it travels along the direction when root motion is on.",
        default=""
        )

    pelvis_bone: StringProperty(
        name="Pelvis", description="The pelvis bone that bobs up and down with each step.",
        default=""
        )

    root_motion: BoolProperty(
        name="Root Motion", description="Move the root (and everything with it) along the direction, otherwise the gait stays in place.",
        default=False
        )

    direction: FloatVectorProperty(
        name="Direction", description="The world space direction of travel. (only its horizontal part is used)",
        size=3, subtype='XYZ', default=(0.0, 1.0, 0.0)
        )

    speed: FloatProperty(
        name="Speed", description="How fast to travel, in world units per second.",
        default=1.0, min=0.001
        )

    step_height: FloatProperty(
        name="Step Height", description="How high each foot lifts at the peak of its swing.",
        subtype='DISTANCE', default=0.2, min=0.0
        )

    step_length: FloatProperty(
        name="Step Length", description="How far the character travels with each full cycle of steps.",
        subtype='DISTANCE', default=1.0, min=0.001
        )

    pelvic_bob: FloatProperty(
        name="Pelvic Bob", description="How far the pelvis dips, twice per cycle.",
        subtype='DISTANCE', default=0.05, min=0.0
        )

    pelvis_offset: FloatVectorProperty(
        name="Pelvis Offset", description="A constant world space offset applied to the pelvis position. (negative Z crouches the character)",
        size=3, subtype='XYZ', default=(0.0, 0.0, 0.0)
        )

    pelvis_pitch_offset: FloatProperty(
        name="Pitch X", description="A constant pitch of the pelvis around the world X axis.",
        subtype='ANGLE', default=0.0
        )

    pelvis_yaw_offset: FloatProperty(
        name="Yaw Z", description="A constant yaw of the pelvis around the world Z axis.",
        subtype='ANGLE', default=0.0
        )

    pelvis_roll_offset: FloatProperty(
        name="Roll Y", description="A constant roll of the pelvis around the world Y axis.",
        subtype='ANGLE', default=0.0
        )

    pelvic_pitch: FloatProperty(
        name="Pitch X", description="How far the pelvis pitches around the world X axis at the bottom of each dip.",
        subtype='ANGLE', default=0.0
        )

    pelvic_yaw: FloatProperty(
        name="Yaw Z", description="How far the pelvis yaws around the world Z axis at the bottom of each dip.",
        subtype='ANGLE', default=0.0
        )

    pelvic_roll: FloatProperty(
        name="Roll Y", description="How far the pelvis rolls around the world Y axis at the bottom of each dip.",
        subtype='ANGLE', default=0.0
        )

    loop_count: IntProperty(
        name="Loops", description="How many full cycles to generate.",
        default=1, min=1
        )

    swing_count: IntProperty(
        name="Swing Count", description="How many extra bones to swing around a pivot bone.",
        default=0, min=0, max=32, update=update_swing_count
        )

    swings: CollectionProperty(type=MMT_PG_KeyframingLocomotionSwing)

    # guards the swing count update while it resizes the swings...
    resizing: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

class MMT_PG_KeyframingLoopingBone(bpy.types.PropertyGroup):

    bone: StringProperty(
        name="Bone", description="The selected bone this entry loops.",
        default=""
        )

    minimum_location: FloatVectorProperty(
        name="Min Location", description="The world space X, Y and Z offset the loop starts and ends each oscillation at.",
        size=3, subtype='TRANSLATION', default=(0.0, 0.0, 0.0)
        )

    maximum_location: FloatVectorProperty(
        name="Max Location", description="The world space X, Y and Z offset the loop reaches halfway through each oscillation.",
        size=3, subtype='TRANSLATION', default=(0.0, 0.0, 0.0)
        )

    minimum_rotation: FloatVectorProperty(
        name="Min Rotation", description="The world space X, Y and Z angles the loop starts and ends each oscillation at.",
        size=3, subtype='EULER', default=(0.0, 0.0, 0.0)
        )

    maximum_rotation: FloatVectorProperty(
        name="Max Rotation", description="The world space X, Y and Z angles the loop reaches halfway through each oscillation.",
        size=3, subtype='EULER', default=(0.0, 0.0, 0.0)
        )

    minimum_scale: FloatVectorProperty(
        name="Min Scale", description="The local X, Y and Z scale factors the loop starts and ends each oscillation at. (multiplies the actions own scale, 1.0 changes nothing)",
        size=3, subtype='XYZ', default=(1.0, 1.0, 1.0), min=0.001
        )

    maximum_scale: FloatVectorProperty(
        name="Max Scale", description="The local X, Y and Z scale factors the loop reaches halfway through each oscillation. (multiplies the actions own scale, 1.0 changes nothing)",
        size=3, subtype='XYZ', default=(1.0, 1.0, 1.0), min=0.001
        )

    cycle_offset: FloatProperty(
        name="Cycle Offset", description="Shifts this bones oscillation along by a fraction of one oscillation.",
        subtype='FACTOR', default=0.0, min=0.0, max=1.0
        )

class MMT_PG_KeyframingLooping(bpy.types.PropertyGroup):

    speed: FloatProperty(
        name="Speed", description="How many base loops happen per second.",
        default=1.0, min=0.001
        )

    frequency: IntProperty(
        name="Frequency", description="How many complete oscillations happen per base loop.",
        default=1, min=1
        )

    loop_count: IntProperty(
        name="Loops", description="How many base loops to generate.",
        default=1, min=1
        )

    bones: CollectionProperty(type=MMT_PG_KeyframingLoopingBone)

class MMT_PG_KeyframingSplitEntry(bpy.types.PropertyGroup):

    name: StringProperty(
        name="Name", description="The name for this new action.",
        default=""
        )

    start: IntProperty(
        name="Start", description="The first frame of this new action. (included)",
        default=1
        )

    end: IntProperty(
        name="End", description="The last frame of this new action. (included)",
        default=1
        )

class MMT_PG_KeyframingSplit(bpy.types.PropertyGroup):

    split_count: IntProperty(
        name="Count", description="How many new actions to split the active action into. (nothing gets split at zero)",
        default=0, min=0, max=64, update=update_split_count
        )

    keep_original: BoolProperty(
        name="Keep Original", description="Keep the original action as it is, otherwise it gets removed once every split has been made.",
        default=True
        )

    splits: CollectionProperty(type=MMT_PG_KeyframingSplitEntry)

    # the action (and keyed range) the splits were last filled in for...
    source_name: StringProperty(default="", options={'HIDDEN', 'SKIP_SAVE'})
    source_start: IntProperty(default=0, options={'HIDDEN', 'SKIP_SAVE'})
    source_end: IntProperty(default=0, options={'HIDDEN', 'SKIP_SAVE'})

    # guards the split count update while it resizes the splits...
    resizing: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})
