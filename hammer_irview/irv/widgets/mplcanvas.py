from collections import defaultdict
import matplotlib

from hammer_irview.irv.widgets.mplzoompan import ZoomPan

matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

class MplCanvas(FigureCanvasQTAgg):

  def __init__(self, plugin_mgr, module, parent=None):
    self.module = module
    self.selected = None
    self.constraint_to_artists = defaultdict(list)
    self.artist_to_constraint = defaultdict(list)
    self.render_hierarchy = False
    self.needs_rerender = False
    self.setup_mpl()
    super().__init__(self.fig)

  def setup_mpl(self):
    self.fig = Figure(figsize=(1, 1), dpi=100)

    # Remove padding, add grid, and fix aspect to be constant (no stretch)
    self.axes = self.fig.add_axes([0, 0, 1, 1])
    # self.axes.grid(False, linewidth=0.3)
    self.axes.grid(True, linewidth=0.3)
    self.axes.set_aspect('equal')
    self.axes.axis('equal')
    self.axes.autoscale(enable=None, axis="x")
    self.axes.autoscale(enable=None, axis="y")
    self.axes.axvline(x=0, c="dimgray", label="x=0")
    self.axes.axhline(y=0, c="dimgray", label="y=0")

    # Zoom/pan functionality
    self.zoompan = ZoomPan()
    self.zoompan.pan_factory(self.axes)
    self.zoompan.zoom_factory(self.axes)
  
  def zoom_to_fit(self):
    x, y = self.module.top_constraint.x, self.module.top_constraint.y
    width, height = self.module.top_constraint.width, self.module.top_constraint.height
    horiz_pad = width / 10
    vert_pad = height / 10
    self.axes.set_ylim([y - vert_pad, y + height + vert_pad])
    self.axes.set_xlim([x - horiz_pad, x + width + horiz_pad])
    self.draw()
    
  def render_module(self):
    # Render module placement constraints
    self.constraint_to_artists.clear()
    for a in self.artist_to_constraint.keys():
      a.remove()
    self.artist_to_constraint.clear()
    for constraint in self.module.constraints.values():
      artists = constraint.render(self.axes, (0, 0), under_hierarchy=False,
                                  render_hierarchy=self.render_hierarchy)
      self.constraint_to_artists[constraint] = artists
      for artist in artists:
        self.artist_to_constraint[artist] = constraint
    self.needs_rerender = False
    self.draw()

  def select_constraint(self, constraint):
    # TODO: Handle selection color change
    self.selected = constraint

  def handle_resize(self):
    for constraint in self.module.constraints.values():
      constraint.draw_resize(self.axes)

# Adds support for descend edit:
#   queue = [(artists, constraint)]
#   while queue:
#     artist, constraint = queue.pop()
#     if isinstance(artist, list):
#       queue.extend(artist)
#     elif isinstance(artist, dict):
#       # Assume constraint to artists mapping direction
#       for constraint, artist in artists:
#         self.artist_to_constraint[artist].extend(constraints)
#         for constraint in constraints:
#           self.constraint_to_artists[constraint].append(artist)
#     else:
#       self.constraint_to_artists[constraint] = artists
#       self.artist_to_constraint[artist] = constraint
# self.needs_rerender = False