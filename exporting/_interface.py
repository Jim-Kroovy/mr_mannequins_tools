def draw_filmbox_settings(self, layout, filmbox):
    col = layout.column()
    # native-style aligned label:value rows, with no keyframe decorator dots, matching the built in FBX exporter...
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(filmbox, 'scaling')
    col.prop(filmbox, 'forward')
    col.prop(filmbox, 'upward')
    col.prop(filmbox, 'smoothing')
    col.prop(filmbox, 'colors')
    sub = col.column()
    sub.enabled = filmbox.colors != 'NONE'
    sub.prop(filmbox, 'prioritize')
    col.prop(filmbox, 'edges')
    col.prop(filmbox, 'tangents')
    col.prop(filmbox, 'triangles')
    col.prop(filmbox, 'primary')
    col.prop(filmbox, 'secondary')
    #col.prop(filmbox, 'animations')...
    sub = col.column()
    sub.enabled = filmbox.animations
    sub.prop(filmbox, 'step')
    sub.prop(filmbox, 'simplify')
    #col.prop(filmbox, 'use_mesh_modifiers')...
    col.prop(filmbox, 'use_metadata')
    col.prop(self, 'only_selected')
    col.prop(self, 'background')

def draw_mesh_settings(layout, meshes):
    col = layout.column()
    col.enabled = meshes.export
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(meshes, 'folder')
    col.prop(meshes, 'modifiers')
    col.prop(meshes, 'batch')
    col.prop(meshes, 'suffix')
    col.separator()
    export = col.column(heading="Export")
    export.prop(meshes, 'static')
    export.prop(meshes, 'skeletal')
    export.prop(meshes, 'socket')

def draw_action_settings(layout, action):
    col = layout.column()
    col.enabled = action.export
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(action, 'folder')
    col.prop(action, 'method')
    col.prop(action, 'batch')

def draw_clean_settings(layout, clean):
    col = layout.column()
    col.use_property_split = True
    col.use_property_decorate = False
    col.prop(clean, 'prefix')
    col.prop(clean, 'shapes')
    col.prop(clean, 'groups')
    col.prop(clean, 'materials')

def draw_export_dialog(self, context):
    settings = self.settings
    layout = self.layout
    # meshes...
    header, panel = layout.panel("mmt_export_meshes", default_closed=False)
    header.prop(settings.meshes, 'export', text="")
    header.label(text="Meshes", icon='MESH_DATA')
    if panel:
        draw_mesh_settings(panel, settings.meshes)
    # actions...
    header, panel = layout.panel("mmt_export_action", default_closed=False)
    header.prop(settings.action, 'export', text="")
    header.label(text="Actions", icon='ACTION')
    if panel:
        draw_action_settings(panel, settings.action)
    # mesh data cleanup...
    header, panel = layout.panel("mmt_export_clean", default_closed=True)
    header.label(text="Cleaning", icon='TRASH')
    if panel:
        draw_clean_settings(panel, settings.clean)
    # advanced filmbox settings...
    header, panel = layout.panel("mmt_export_advanced", default_closed=True)
    header.label(text="Advanced", icon='PREFERENCES')
    if panel:
        draw_filmbox_settings(self, panel, settings.filmbox)
