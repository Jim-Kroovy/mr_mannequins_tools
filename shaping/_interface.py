def draw_mirror_settings(self, context):
    layout = self.layout
    row = layout.row()
    row.prop(self, 'method')
    row = layout.row()
    shape_keys = context.active_object.data.shape_keys
    row.prop_search(self, 'basis', shape_keys, 'key_blocks')
    row.enabled = self.method == 'BLEND'
    row = layout.row()
    row.prop(self, 'prefix')
    row.enabled = not self.active
    row = layout.row()
    row.prop(self, 'blend')
    row.enabled = self.method == 'BLEND'
    row = layout.row()
    row.prop(self, 'active')
    row.prop(self, 'selected')

def draw_blend_settings(self, context):
    layout = self.layout
    row = layout.row()
    shape_keys = context.active_object.data.shape_keys
    row.prop_search(self, 'into', shape_keys, 'key_blocks')
    row = layout.row()
    row.prop(self, 'prefix')
    row.enabled = not self.active
    row = layout.row()
    row.prop(self, 'blend')
    row = layout.row()
    row.prop(self, 'alpha')
    row = layout.row()
    row.prop(self, 'steps')
    row = layout.row()
    row.prop(self, 'active')
