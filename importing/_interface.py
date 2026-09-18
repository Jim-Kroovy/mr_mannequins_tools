def draw_orientation_settings(layout, orientation):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(orientation, 'orient')
    col.prop(orientation, 'root_length')
    sub = col.column()
    sub.enabled = orientation.orient
    sub.prop(orientation, 'max_length')
    sub.prop(orientation, 'original_shape')
    sub.prop(orientation, 'oriented_shape')

def draw_retargeting_settings(layout, retargeting):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(retargeting, 'target')
    col.separator()
    retarget = col.column(heading="Retarget")
    retarget.enabled = retargeting.target != 'NONE'
    retarget.prop(retargeting, 'meshes')
    retarget.prop(retargeting, 'actions')
    step = col.column()
    # step height only matters for the plantigrade foot-parent bake, which needs a real target rig...
    step.enabled = retargeting.actions and retargeting.target != 'NONE'
    step.prop(retargeting, 'step_height')

def draw_cleaning_settings(layout, cleaning):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(cleaning, 'decimate')
    sub = col.column()
    sub.enabled = cleaning.decimate != 'NONE'
    sub.prop(cleaning, 'margin')
    # thinning runs independently of decimate, so its spacing control always stays interactive...
    col.prop(cleaning, 'spacing')

def draw_filmbox_settings(layout, filmbox):
    col = layout.column()
    # native-style aligned label:value rows, with no keyframe decorator dots, matching the built in FBX importer...
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(filmbox, 'manual_orientation')
    sub = col.column()
    sub.enabled = filmbox.manual_orientation
    sub.prop(filmbox, 'scaling')
    sub.prop(filmbox, 'forward')
    sub.prop(filmbox, 'upward')
    col.prop(filmbox, 'use_custom_normals')
    col.prop(filmbox, 'use_image_search')
    col.prop(filmbox, 'use_alpha_decals')
    sub = col.column()
    sub.enabled = filmbox.use_alpha_decals
    sub.prop(filmbox, 'decal_offset')
    col.prop(filmbox, 'anim_offset')
    col.prop(filmbox, 'ignore_leaf_bones')
    col.prop(filmbox, 'force_connect_children')
    col.prop(filmbox, 'automatic_bone_orientation')
    sub = col.column()
    sub.enabled = not filmbox.automatic_bone_orientation
    sub.prop(filmbox, 'primary')
    sub.prop(filmbox, 'secondary')
    col.prop(filmbox, 'use_prepost_rot')

def draw_import_dialog(self, context):
    settings = self.settings
    layout = self.layout
    # orientation...
    header, panel = layout.panel("mmt_import_orientation", default_closed=False)
    header.label(text="Orientation", icon='ARMATURE_DATA')
    if panel:
        draw_orientation_settings(panel, settings.orientation)
    # retargeting...
    header, panel = layout.panel("mmt_import_retargeting", default_closed=False)
    header.label(text="Retargeting", icon='CON_ARMATURE')
    if panel:
        draw_retargeting_settings(panel, settings.retargeting)
    # cleaning...
    header, panel = layout.panel("mmt_import_cleaning", default_closed=False)
    header.label(text="Cleaning", icon='SHARPCURVE')
    if panel:
        draw_cleaning_settings(panel, settings.cleaning)
    # advanced filmbox settings...
    header, panel = layout.panel("mmt_import_advanced", default_closed=True)
    header.label(text="Advanced", icon='PREFERENCES')
    if panel:
        draw_filmbox_settings(panel, settings.filmbox)
