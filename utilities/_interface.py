def draw_apply_settings(self):
    layout = self.layout
    row = layout.row()
    row.prop(self, 'modifiers')
    row = layout.row()
    row.prop(self, 'parent')
    row = layout.row()
    row.prop(self, 'location')
    row = layout.row()
    row.prop(self, 'rotation')
    row = layout.row()
    row.prop(self, 'scale')
    row = layout.row()
    row.prop(self, 'original')

def draw_clean_settings(self):
    layout = self.layout
    row = layout.row()
    row.prop(self, 'prefix')
    row = layout.row()
    row.prop(self, 'shapes')
    row = layout.row()
    row.prop(self, 'groups')
    row = layout.row()
    row.prop(self, 'materials')
