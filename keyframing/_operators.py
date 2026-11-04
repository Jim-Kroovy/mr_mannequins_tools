import bpy
import math

from bpy.props import StringProperty, EnumProperty, FloatProperty, PointerProperty, BoolProperty

from . import _functions as functions
from . import _properties as properties

def set_playing_animation(context):
    # plays the timeline once something's been generated, but never toggles it off if it's already playing... (and quietly skips without a screen)...
    screen = getattr(context, 'screen', None)
    if screen and not screen.is_animation_playing and bpy.ops.screen.animation_play.poll():
        try:
            bpy.ops.screen.animation_play()
        except RuntimeError:
            pass

def get_selected_transfer(context):
    # the active bone is the target and the first other selected bone is the source, blank if either isn't on the active armature...
    obj, active = context.object, context.active_pose_bone
    target = active.name if active and active.id_data == obj else ""
    source = next((b.name for b in (context.selected_pose_bones or []) if b.id_data == obj and b != active), "")
    return source, target

def get_selected_actions(obj):
    # every action on the selected nla tracks, in nla order and only once each... (strip selection is ignored, stashes come out selected anyway)...
    tracks = obj.animation_data.nla_tracks if obj and obj.animation_data else []
    return list(dict.fromkeys(s.action for t in tracks if t.select for s in t.strips if s.action))

def get_forced_stash(operator):
    # redirected actions have to be stashed when they came from the nla or there's more than one, only one of them can be left active...
    return operator.from_tracks or sum(len(e.directions) for e in operator.settings.actions) > 1

class MMT_OT_KeyframingTransfer(bpy.types.Operator):
    """Transfers the source bones travel along a world direction onto the target bone (eg. root motion) in every listed action, keying location only"""
    bl_idname = "mmt.transfer_motion"
    bl_label = "Transfer Root Motion"
    bl_options = {'REGISTER', 'UNDO'}

    source_bone: StringProperty(
        name="Source", description="The bone whose directional travel gets moved onto the target. (eg. the pelvis)",
        default=""
        )

    target_bone: StringProperty(
        name="Target", description="The bone that receives the directional travel. (eg. the root)",
        default=""
        )

    # never filled in from last time, so a straight menu click always starts with nothing listed...
    settings: PointerProperty(type=properties.MMT_PG_KeyframingTransfer, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        obj = context.object
        return bool(obj and obj.type == 'ARMATURE' and obj.mode == 'POSE')

    def draw(self, context):
        layout = self.layout
        armature, settings = context.object, self.settings
        row = layout.row()
        row.prop_search(self, 'source_bone', armature.data, 'bones')
        row = layout.row()
        row.prop_search(self, 'target_bone', armature.data, 'bones')
        # each action gets its own box with its direction underneath...
        for entry in settings.transfers:
            box = layout.box()
            row = box.row(align=True)
            row.prop_search(entry, 'action', bpy.data, 'actions', text="")
            row = box.row(align=True)
            row.prop(entry, 'direction', text="Direction")

    def invoke(self, context, event):
        # always overwritten so last times bones and actions can't leak in from another armature or selection...
        self.source_bone, self.target_bone = get_selected_transfer(context)
        obj = context.object
        action = obj.animation_data.action if obj.animation_data else None
        # the active action gets listed on its own, otherwise everything on the selected nla tracks, otherwise a blank row to pick one...
        actions = [action] if action else get_selected_actions(obj)
        settings = self.settings
        settings.transfers.clear()
        for listed in actions or [None]:
            entry = settings.transfers.add()
            entry.action = listed.name if listed else ""
        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):
        armature, settings = context.object, self.settings
        # plain copies of the named entries, blank rows just get skipped... (transferring never touches the operators own data)...
        entries = tuple((bpy.data.actions.get(e.action), tuple(e.direction)) for e in settings.transfers if e.action)
        # redo re-runs this on every edit, so anything unfinished or invalid quietly does nothing until it's all valid... (no pop ups, and the redo panel sticks around)...
        if entries and all(a for a, _ in entries) and self.source_bone and self.target_bone:
            try:
                transfers = functions.set_transferred_actions(armature, self.source_bone, self.target_bone, entries)
            except ValueError:
                transfers = []
            if transfers:
                self.report({'INFO'}, "Transferred motion from '" + self.source_bone + "' to '" + self.target_bone + "' in " + str(len(transfers)) + " action(s) over "
                    + str(sum(f for _, f in transfers)) + " frames: " + ", ".join(n for n, _ in transfers))
        return {'FINISHED'}

class MMT_OT_KeyframingRedirect(bpy.types.Operator):
    """Rotates the active root bones animation (and every independent control) around a world axis through the world origin, any other selected bones get rotated back around the root to counter it"""
    bl_idname = "mmt.redirect_motion"
    bl_label = "Redirect Root Motion"
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(
        name="Axis", description="The world space axis to rotate the motion around.",
        items=[
            ('X', "X", "", '', 0),
            ('Y', "Y", "", '', 1),
            ('Z', "Z", "", '', 2),
            ], default='Z'
        )

    angle: FloatProperty(
        name="Angle", description="How far to rotate the motion around the axis. (nothing gets redirected at zero)",
        subtype='ANGLE', default=0.0, options={'SKIP_SAVE'}
        )

    action_name: StringProperty(
        name="New Action", description="The name of the new redirected action. (a taken name gets a .001 style suffix)",
        default="", options={'SKIP_SAVE'}
        )

    keep_original: BoolProperty(
        name="Keep Original", description="Keep the original action as it is, otherwise it gets removed once the redirected action has been made.",
        default=True, options={'SKIP_SAVE'}
        )

    stash_action: BoolProperty(
        name="Stash Action", description="Stash the redirected action in the NLA, named after the redirected action.",
        default=True, options={'SKIP_SAVE'}
        )

    # never filled in from last time, the dialog lists the actions (and their directions) fresh every time... (scripts without it use the single axis, angle and name above)...
    settings: PointerProperty(type=properties.MMT_PG_KeyframingRedirect, options={'SKIP_SAVE'})

    # whether the dialog got its actions from the selected nla tracks, those always get stashed...
    from_tracks: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        obj, pose_bone = context.object, context.active_pose_bone
        return bool(obj and obj.type == 'ARMATURE' and obj.mode == 'POSE' and pose_bone and pose_bone.id_data == obj)

    def draw(self, context):
        layout = self.layout
        # each action gets its own box, with its directions count and one row per direction...
        for entry in self.settings.actions:
            box = layout.box()
            row = box.row(align=True)
            row.prop_search(entry, 'action', bpy.data, 'actions', text="")
            row.prop(entry, 'direction_count')
            for direction in entry.directions:
                row = box.row(align=True)
                row.prop(direction, 'axis', expand=True)
                row.prop(direction, 'angle')
                row.prop(direction, 'action_name', text="")
        row = layout.row()
        row.prop(self, 'keep_original')
        # stashing greys out when it can't be turned off...
        sub = row.row()
        sub.enabled = not get_forced_stash(self)
        sub.prop(self, 'stash_action')

    def check(self, context):
        # more than one new action (or actions from the nla) can't go unstashed, so it gets ticked back on... (always redraws so the checkbox greys in and out with the count)...
        if get_forced_stash(self):
            self.stash_action = True
        return True

    def invoke(self, context, event):
        obj = context.object
        action = obj.animation_data.action if obj.animation_data else None
        # the active action gets listed on its own, otherwise everything on the selected nla tracks, otherwise a blank row to pick one... (each with one direction)...
        actions = [action] if action else get_selected_actions(obj)
        self.from_tracks = bool(actions) and not action
        if self.from_tracks:
            self.stash_action = True
        settings = self.settings
        settings.actions.clear()
        for listed in actions or [None]:
            entry = settings.actions.add()
            entry.action = listed.name if listed else ""
            functions.set_redirect_directions(entry)
        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):
        armature, root, settings = context.object, context.active_pose_bone, self.settings
        # the rest of the selection gets countered, read fresh every time so redo uses the selection it was run on...
        targets = [b.name for b in (context.selected_pose_bones or []) if b.id_data == armature and b != root]
        if settings.actions:
            # plain copies of the listed actions and their directions, redirecting never touches the operators own data...
            entries = tuple((e.action, bpy.data.actions.get(e.action) if e.action else None, tuple((d.axis, d.angle, d.action_name) for d in e.directions)) for e in settings.actions)
            missing = next((str(i) + " ('" + n + "')" for i, (n, a, _) in enumerate(entries, 1) if n and not a), None)
            # a script has to list exactly as many directions as it says it has, nothing gets guessed or trimmed...
            mismatch = next(("Entry " + str(i) + " ('" + e.action + "') lists " + str(len(e.directions)) + " direction(s) but Directions is " + str(e.direction_count)
                for i, e in enumerate(settings.actions, 1) if e.action and e.direction_count != len(e.directions)), None)
            # nothing picked yet quietly finishes, and nothing gets redirected until an angle is set...
            if any(name for name, _, _ in entries):
                # every entry has to be a real action...
                if missing:
                    self.report({'ERROR'}, "Entry " + missing + " isn't an action")
                    return {'CANCELLED'}
                elif mismatch:
                    # and the entries have to match each other...
                    self.report({'ERROR'}, mismatch)
                    return {'CANCELLED'}
                elif all(abs(d[1]) < 1e-6 for _, _, directions in entries for d in directions):
                    self.report({'INFO'}, "Set an angle to redirect motion")
                else:
                    # the dialog isn't the only way in (redo, scripts), so stashing gets forced here too...
                    if get_forced_stash(self):
                        self.stash_action = True
                    try:
                        results = functions.set_redirected_actions(armature, root.name, tuple((a, d) for _, a, d in entries), self.keep_original, self.stash_action, targets)
                    except ValueError as error:
                        self.report({'ERROR'}, str(error))
                        return {'CANCELLED'}
                    names = [o[0] for _, outputs in results for o in outputs]
                    chains, controls = results[0][1][0][3:5]
                    self.report({'INFO'}, "Redirected " + str(len(results)) + " action(s) into " + str(len(names)) + " new action(s): " + ", ".join(names)
                        + (", countered " + str(chains) + " chain(s) and " + str(controls) + " control(s)" if targets else "") + (", stashed" if self.stash_action else "") + ("" if self.keep_original else ", originals removed"))
        elif abs(self.angle) >= 1e-6:
            # scripts that don't list any actions still redirect the active one with the single axis, angle and name...
            try:
                name, bones, frames, chains, controls = functions.set_redirected_action(armature, root.name, self.axis, self.angle, self.action_name, self.keep_original, self.stash_action, targets)
            except ValueError as error:
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}
            self.report({'INFO'}, "Redirected motion of '" + root.name + "' and " + str(bones - 1) + " other control(s) over " + str(frames) + " frames into '" + name + "'"
                + (", countered " + str(chains) + " chain(s) and " + str(controls) + " control(s)" if targets else "") + (", stashed" if self.stash_action else "") + ("" if self.keep_original else ", original removed"))
        else:
            # nothing changes but it still finishes, so the redo panel sticks around to pick an angle...
            self.report({'INFO'}, "Set an angle in the redo panel to redirect motion")
        return {'FINISHED'}

class MMT_OT_KeyframingLocomotion(bpy.types.Operator):
    """Keys a looping procedural walk into a new action, the selected foot targets step in phase around the active one while the pelvis bobs (and optionally the root travels)"""
    bl_idname = "mmt.generate_locomotion"
    bl_label = "Generate Locomotion"
    bl_options = {'REGISTER', 'UNDO'}

    settings: PointerProperty(type=properties.MMT_PG_KeyframingLocomotion)

    @classmethod
    def poll(cls, context):
        obj, pose_bone = context.object, context.active_pose_bone
        return bool(obj and obj.type == 'ARMATURE' and obj.mode == 'POSE' and pose_bone and pose_bone.id_data == obj and pose_bone.select
            and len([b for b in obj.pose.bones if b.select]) >= 2)

    def draw(self, context):
        layout = self.layout
        armature, settings = context.object, self.settings
        row = layout.row()
        row.prop(settings, 'action_name')
        row = layout.row()
        row.prop_search(settings, 'root_bone', armature.data, 'bones')
        row = layout.row()
        row.prop_search(settings, 'pelvis_bone', armature.data, 'bones')
        row = layout.row()
        row.prop(settings, 'root_motion')
        row = layout.row()
        row.prop(settings, 'direction')
        for name in ('speed', 'step_height', 'step_length', 'pelvic_bob', 'pelvis_offset'):
            row = layout.row()
            row.prop(settings, name)
        # both rotation groups are pitch, yaw and roll around fixed world X, Z and Y...
        for label, group in (("Pelvis Rotation Offset", "pelvis_%s_offset"), ("Pelvic Rotation Bob", "pelvic_%s")):
            layout.label(text=label)
            row = layout.row(align=True)
            for axis in ('pitch', 'yaw', 'roll'):
                row.prop(settings, group % axis)
        row = layout.row()
        row.prop(settings, 'loop_count')
        row = layout.row()
        row.prop(settings, 'swing_count')
        # every swing gets its own little box...
        for index, swing in enumerate(settings.swings):
            box = layout.box()
            box.label(text="Swing " + str(index + 1))
            box.prop_search(swing, 'bone', armature.data, 'bones')
            box.prop_search(swing, 'pivot', armature.data, 'bones')
            box.prop(swing, 'minimum')
            box.prop(swing, 'maximum')
            box.prop(swing, 'frequency')

    def invoke(self, context, event):
        # suggest the old automatic name, but never over the top of one already entered...
        if not self.settings.action_name.strip():
            self.settings.action_name = context.object.name + "_Locomotion"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        armature, active, settings = context.object, context.active_pose_bone, self.settings
        targets = [b.name for b in armature.pose.bones if b.select]
        # plain copies of the swing entries, generation never touches the operators own data...
        swings = tuple((s.bone, s.pivot, tuple(s.minimum), tuple(s.maximum), s.frequency) for s in settings.swings)
        try:
            action, frames, cycle_frames, realized, keyed = functions.set_generated_locomotion(armature, settings.root_bone, settings.pelvis_bone, targets, active.name,
                settings.root_motion, settings.direction, settings.speed, settings.step_height, settings.step_length, settings.pelvic_bob, settings.loop_count, pelvis_offset=settings.pelvis_offset,
                pelvis_rotation_offset=(settings.pelvis_pitch_offset, settings.pelvis_yaw_offset, settings.pelvis_roll_offset), pelvic_rotation=(settings.pelvic_pitch, settings.pelvic_yaw, settings.pelvic_roll),
                swings=swings, action_name=settings.action_name)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        message = "Generated '" + action.name + "' over " + str(frames) + " frames (" + str(cycle_frames) + " per cycle, " + str(keyed) + " bones keyed)"
        # frame rounding can nudge the speed, so say so when it's noticeable...
        if abs(realized - settings.speed) > settings.speed * 0.01:
            message += ", actual speed " + str(round(realized, 3)) + " units/s"
        self.report({'INFO'}, message)
        set_playing_animation(context)
        return {'FINISHED'}

class MMT_OT_KeyframingOscillation(bpy.types.Operator):
    """Layers looping world space location and rotation offsets (and local scale factors) onto the selected bones of the active action, in place"""
    bl_idname = "mmt.generate_loops"
    bl_label = "Add Oscillatory Motion"
    bl_options = {'REGISTER', 'UNDO'}

    settings: PointerProperty(type=properties.MMT_PG_KeyframingLooping)

    @classmethod
    def poll(cls, context):
        obj = context.object
        action = obj.animation_data.action if obj and obj.animation_data else None
        return bool(obj and obj.type == 'ARMATURE' and obj.mode == 'POSE' and action and not action.library and getattr(action, 'is_editable', True)
            and any(b.select for b in obj.pose.bones))

    def draw(self, context):
        layout = self.layout
        settings = self.settings
        for name in ('speed', 'frequency', 'loop_count'):
            row = layout.row()
            row.prop(settings, name)
        # every selected bone gets its own little box...
        for entry in settings.bones:
            box = layout.box()
            box.label(text=entry.bone)
            # one aligned row per vector, so blender can't stack the components vertically...
            for label, name in (("Min Location", 'minimum_location'), ("Max Location", 'maximum_location'), ("Min Rotation", 'minimum_rotation'), ("Max Rotation", 'maximum_rotation'), ("Min Scale", 'minimum_scale'), ("Max Scale", 'maximum_scale')):
                row = box.row(align=True)
                row.label(text=label)
                for index, axis in enumerate("XYZ"):
                    row.prop(entry, name, index=index, text=axis)
            row = box.row()
            row.prop(entry, 'cycle_offset')

    def invoke(self, context, event):
        functions.set_looping_bones(self.settings, [b.name for b in context.object.pose.bones if b.select])
        return context.window_manager.invoke_props_dialog(self, width=650)

    def execute(self, context):
        armature, settings = context.object, self.settings
        # plain copies of the entries, generation never touches the operators own data...
        entries = tuple((e.bone, tuple(e.minimum_location), tuple(e.maximum_location), tuple(e.minimum_rotation), tuple(e.maximum_rotation), e.cycle_offset, tuple(e.minimum_scale), tuple(e.maximum_scale)) for e in settings.bones)
        try:
            frames, cycle_frames, realized, keyed, cyclic = functions.set_looped_motion(armature, entries, settings.speed, settings.frequency, settings.loop_count)
        except ValueError as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        message = "Looped " + str(keyed) + " bone(s) over " + str(frames) + " frames (" + str(cycle_frames) + " per base loop)"
        # frame rounding can nudge the speed, so say so when it's noticeable...
        if abs(realized - settings.speed) > settings.speed * 0.01:
            message += ", actual speed " + str(round(realized, 3)) + " loops/s"
        self.report({'INFO'}, message)
        if not cyclic:
            self.report({'WARNING'}, "The action's own motion doesn't match at the first and last frame, so it won't loop cleanly (the looping offsets themselves do)")
        set_playing_animation(context)
        return {'FINISHED'}

class MMT_OT_KeyframingSplit(bpy.types.Operator):
    """Splits the active action into new actions by frame range, each one stashed on the armature"""
    bl_idname = "mmt.split_action"
    bl_label = "Split Active Action"
    bl_options = {'REGISTER', 'UNDO'}

    # never filled in from last time, so a straight menu click always starts at zero...
    settings: PointerProperty(type=properties.MMT_PG_KeyframingSplit, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        obj = context.object
        action = obj.animation_data.action if obj and obj.animation_data else None
        return bool(obj and obj.type == 'ARMATURE' and obj.mode in ('OBJECT', 'POSE') and action and not action.library and getattr(action, 'is_editable', True))

    def draw(self, context):
        layout = self.layout
        settings = self.settings
        row = layout.row()
        row.prop(settings, 'split_count')
        row.prop(settings, 'keep_original')
        # one compact row per split...
        row = layout.row()
        row.label(text="Name")
        row.label(text="Start")
        row.label(text="End")
        for entry in settings.splits:
            row = layout.row(align=True)
            row.prop(entry, 'name', text="")
            row.prop(entry, 'start', text="")
            row.prop(entry, 'end', text="")

    def invoke(self, context, event):
        action = context.object.animation_data.action
        # nothing to split without keys...
        if not functions.get_keyed_range(action):
            self.report({'ERROR'}, "'" + action.name + "' has no keyframes to split")
            return {'CANCELLED'}
        # always starts from nothing, the count gets picked in the dialog...
        settings = self.settings
        settings.split_count = 0
        settings.splits.clear()
        functions.set_split_entries(settings, action)
        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):
        armature, settings = context.object, self.settings
        action = armature.animation_data.action
        if functions.get_keyed_range(action):
            # a straight menu click still needs to know the action, rows that are already there (scripted or edited in redo) are kept...
            if not settings.splits:
                functions.set_split_entries(settings, action)
            if settings.split_count:
                # plain copies of the entries, splitting never touches the operators own data...
                entries = tuple((e.name, e.start, e.end) for e in settings.splits)
                try:
                    splits = functions.set_split_action(armature, entries, settings.keep_original)
                except ValueError as error:
                    self.report({'ERROR'}, str(error))
                    return {'CANCELLED'}
                message = "Split into " + str(len(splits)) + " action(s): " + ", ".join(n + " (" + str(s) + " to " + str(e) + ")" for n, s, e in splits)
                self.report({'INFO'}, message + ("" if settings.keep_original else ", original removed"))
            else:
                # nothing changes but it still finishes, so the redo panel sticks around to pick a count...
                self.report({'INFO'}, "Set a count in the redo panel to split '" + action.name + "'")
            return {'FINISHED'}
        self.report({'ERROR'}, "'" + action.name + "' has no keyframes to split")
        return {'CANCELLED'}

def add_keyframing_operators(self, context):
    self.layout.separator()
    # every entry opens its dialog, filled in from whatever's selected when it gets clicked... (the menus own context would just execute them)...
    layout = self.layout.column()
    layout.operator_context = 'INVOKE_DEFAULT'
    layout.operator(MMT_OT_KeyframingSplit.bl_idname)
    layout.operator(MMT_OT_KeyframingTransfer.bl_idname)
    layout.operator(MMT_OT_KeyframingRedirect.bl_idname)
    layout.operator(MMT_OT_KeyframingOscillation.bl_idname)
