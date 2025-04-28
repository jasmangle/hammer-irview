import enum
from typing import *
from decimal import Decimal

from matplotlib.axes import Axes
from matplotlib.patches import Circle, Rectangle
from matplotlib.transforms import Bbox, TransformedBbox
from pyqtgraph.parametertree import Parameter
from PySide6.QtCore import SIGNAL

if TYPE_CHECKING:
  from hammer_irview.irv.hierarchical.verilog_module import *
  
from hammer_irview.irv.pluginmgr import IRVBehavior

from hammer_irview.irv.hierarchical.lef import IRVMacro


class IRVAlignCheck(enum.Enum):
  ALIGNED = 0
  UNKNOWN = 1
  MISALIGNED = 2


class ModuleConstraint:
  """
  Modelable placement constraint object.
  """

  # pyname = Mapping for class variable.

  def __init__(self, yml: dict, hierarchy: 'VerilogModuleHierarchy'):
    
    self.add_param_dict(dict(name='Constraint', type='group', child_params=[
      dict(name='Path', getter='path', type='str'),
      dict(name='Type', getter='type', type='str'),
      dict(name='Position', type='group', child_params=[
        dict(name='x', type='float', getter='x'),
        dict(name='y', type='float', getter='y'),
      ]),
      dict(name='Dimensions', type='group', child_params=[
        dict(name='Width', type='float', getter='width'),
        dict(name='Height', type='float', getter='height'),
        dict(name='Layers', type='checklist', getter=self.get_param_layers, limits=hierarchy.layers.values()),
      ]),
      dict(name='Margins', type='group', child_params=[
        dict(name='Left', type='float', getter=self.get_param_margins),
        dict(name='Right', type='float', getter=self.get_param_margins),
        dict(name='Top', type='float', getter=self.get_param_margins),
        dict(name='Bottom', type='float', getter=self.get_param_margins),
      ]),
    ]), end=False)
    
    module_name = yml.get('path').split('/', 1)[0]
    self.hierarchy = hierarchy

    self.misaligned_layers = None
    self.misaligned_log = 'Alignment was not checked for this constraint.'

    self.module = hierarchy.get_module_by_name(module_name)
    self.path = yml.get('path')
    self.type = yml.get('type')
    self.x = yml.get('x', 0)
    self.y = yml.get('y', 0)
    self.width = yml.get('width')
    self.height = yml.get('height')
    self.margins = yml.get('margins')
    self.defined = True
    self.yml = yml
    self.geometry = []
    self.text_artist = None

    self.params = Parameter.create(name='root', type='group')
    remaining = [(p, self.params) for p in self.constraint_params]
    while remaining:
      param_dict, parent = remaining.pop(0)
      param = Parameter.create(**param_dict)
      
      if param_dict['type'] == 'group':
        for child in param_dict['child_params']:
          remaining.append((child, param))
        del param_dict['child_params']

      if 'getter' in param_dict:
        getter = param_dict['getter']
        value = ''
        if isinstance(getter, str):
          value = yml.get(getter) or 0
          setattr(self, getter, value)
        elif callable(getter):
          value = getter(yml, param_dict['name'])
        
        param.setDefault(value)
        param.setToDefault()
        
      param.sigStateChanged.connect(self.param_state_changed)
      parent.addChild(param)

  def rotate_coordinates(self, origin: Tuple[Decimal, Decimal], size: Tuple[Decimal, Decimal], orientation: str) -> Tuple[Decimal, Decimal]:
    x,y = origin
    width,height = size
    if orientation == 'r0':
      return (x,y)
    elif orientation == 'r90':
      return (x+height,y)
    elif orientation == 'r180':
      return (x+width,y+height)
    elif orientation == 'r270':
      return (x,y+width)
    elif orientation == 'mx':
      return (x,y+height)
    elif orientation == 'my':
      return (x+width,y)
    elif orientation == 'mx90':
      return (x,y)
    elif orientation == 'my90':
      return (x+height,y+width)
    else:
      self.logger.error(f"Invalid orientation {orientation}")
      return (x,y)

  def refresh_alignment(self):
    cmul_log = []
    self.misaligned_layers = []
    
    self.hierarchy.driver.log.info(f'--- Refreshing alignment check for module constraint "{self.path}" (Parent Module: "{self.module.name}") ---')
    for layer in self.hierarchy.layers.values():
      aligned = layer.check_alignment(self.x, self.y, self.width, self.height)

      align_log = f'Metal {layer.name} ({layer.dir}, grid unit: {layer.metal.grid_unit}): Alignment {"PASS" if aligned else "FAIL"} x: {self.x}, y: {self.y}, width: {self.width}, height: {self.height}'
      cmul_log.append(align_log)
      self.hierarchy.driver.log.info('\t' + align_log)

      if not aligned:
        self.misaligned_layers.append(layer)
        
    self.misaligned_log = '\n'.join(cmul_log)

  @property
  def is_grid_aligned(self) -> IRVAlignCheck:
    """
    Returns the status of grid alignment for the entire module.

    Returns:
        IRVAlignCheck: Status of the module's overall alignment.
    """
    if self.misaligned_layers is None:
      self.refresh_alignment()

      # Still undefined?
      if self.misaligned_layers is None:
        return IRVAlignCheck.UNKNOWN
    
    if len(self.misaligned_layers) > 0:
      return IRVAlignCheck.MISALIGNED
    else:
      return IRVAlignCheck.ALIGNED

  def get_param_margins(self, yml, name):
    return yml.get('margins', {}).get(name.lower(), 0)
  
  def get_param_layers(self, yml, name):
    layer_strs = yml.get('layers', [])
    return [self.hierarchy.layers[layer_str] for layer_str in layer_strs]
  
  def add_param_dict(self, param_dict, end=True):
    if hasattr(self, 'constraint_params') and end:
      self.constraint_params.append(param_dict)
    elif hasattr(self, 'constraint_params') and not end:
      self.constraint_params.insert(0, param_dict)
    else:
      self.constraint_params = [param_dict]
    
  def param_state_changed(self, param, change, info):
    pass
    #print('state changed')

  def populate_params(self, tree):
    tree.setParameters(self.params, False)

  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    """
    Renders the constraint onto the provided Matplotlib axes object.
    """
    return []
  
  def get_display_text(self):
    return self.path

  def update_text_artist(self, axes: Axes, parent_geom):
    txt = self.get_display_text()

    # Text placement
    if not hasattr(parent_geom, 'get_xy'):
      return
    rx, ry = parent_geom.get_xy()
    rxt = rx + parent_geom.get_width()
    ryt = ry + parent_geom.get_height()
    # cx = rx + parent_geom.get_width()/2.0
    # cy = ry + parent_geom.get_height()/2.0
    cx = rx
    cy = ry

    if not self.text_artist:
      self.text_artist = axes.annotate(txt, (rxt, cy), 
        color='black', fontsize=6, ha='right', va='bottom') # weight='bold'

    bbox = TransformedBbox(Bbox([[rx,ry],[rxt,ryt]]), axes.transData)
    self.text_artist.set_clip_box(bbox)
    # Bounding box

    # Text scaling
    # r = parent_geom.get_window_extent()
    # t = self.text_artist.get_window_extent()
    # scale = min(r.height / t.height, r.width / t.width)
    # self.text_artist.set_size(self.text_artist.get_size() * scale)

  
  def draw_resize(self, axes: Axes):
    if self.geometry:
      shape = self.geometry[0]
      self.update_text_artist(axes, shape)
      
  
  def select_event(self, selected):
    pass

  # ----- QAbstractItemModel Methods ----- # 
  def appendChild(self, group):
    pass

  def data(self, column):
    if column == 0:
      return self.path
    else:
      return self.type

  def childrenCount(self):
    return 0

  def hasChildren(self):
    return False

  def row(self):
    return 0


class ModuleTopLevel(ModuleConstraint):
  """
  Parses the toplevel bbox yaml element into a modelable constraint object.
  """
  TOP_COLOR_BORDER = 'silver'
  TOP_COLOR_FILL = 'whitesmoke'

  HIER_COLOR_BORDER = 'lightcoral'
  HIER_COLOR_FILL = 'mistyrose'

  def __init__(self, yml, hierarchy):
    super().__init__(yml, hierarchy)

    # if module and module.name == self.path:
    #   module.toplevel = self

  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    coords = (relative_offset[0] + self.x, relative_offset[1] + self.y)

    if under_hierarchy:
      self.geometry = [Rectangle(coords, self.width, self.height,
                                edgecolor=self.HIER_COLOR_BORDER,
                                facecolor=self.HIER_COLOR_FILL)]
    else:
      self.geometry = [Rectangle(coords, self.width, self.height,
                                edgecolor=self.TOP_COLOR_BORDER,
                                facecolor=self.TOP_COLOR_FILL)]
    
    for geom in self.geometry:
      geom.set_picker(True)
      axes.add_artist(geom)
    return self.geometry


class ModuleHierarchical(ModuleConstraint):
  """
  Parses the submodule bbox yaml element into a modelable constraint object.

  Note that the TopLevel paths are defined using the `hierarchical` constraints.

  """
  TOP_COLOR_BORDER = 'silver'
  TOP_COLOR_FILL = 'whitesmoke'

  HIER_COLOR_BORDER = 'lightcoral'
  HIER_COLOR_FILL = 'mistyrose'

  def __init__(self, yml, hierarchy):
    constraint_params = dict(name='Hierarchical', type='group', child_params=[
      dict(name='Master', getter='master', type='str'),
    ])
    self.add_param_dict(constraint_params)
    super().__init__(yml, hierarchy)

    self.defined = False

    # Get the reference to the master module that this constraint depends on
    self.master_module = hierarchy.get_module_by_name(self.master)
    


  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    coords = (relative_offset[0] + self.x, relative_offset[1] + self.y)

    if not under_hierarchy:
      self.geometry = [Rectangle(coords, self.width, self.height,
                                edgecolor=self.HIER_COLOR_BORDER,
                                facecolor=self.HIER_COLOR_FILL)]
    else:
      self.geometry = [Rectangle(coords, self.width, self.height,
                                edgecolor=self.TOP_COLOR_BORDER,
                                facecolor=self.TOP_COLOR_FILL)]
    
    for geom in self.geometry:
      geom.set_picker(True)
      axes.add_artist(geom)
    all_artists = self.geometry

    if render_hierarchy:
      for constraint in self.master_module.placement_constraints.values():
        subartists = constraint.render(axes, coords,
                                       under_hierarchy=True,
                                       render_hierarchy=render_hierarchy)
        all_artists.extend(subartists)

    return all_artists

class ModuleObstruction(ModuleConstraint):
  """
  Parses the submodule bbox yaml element into a modelable constraint object.

  Note that the TopLevel paths are defined using the `hierarchical` constraints.

  """
  COLOR_BORDER = 'darkseagreen'
  COLOR_FILL = 'honeydew'

  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    coords = (relative_offset[0] + self.x, relative_offset[1] + self.y)

    self.geometry = [Rectangle(coords, self.width, self.height,
                              edgecolor=self.COLOR_BORDER,
                              facecolor=self.COLOR_FILL)]
    
    for geom in self.geometry:
      geom.set_picker(True)
      axes.add_artist(geom)
    return self.geometry

class ModuleOverlap(ModuleConstraint):
  """
  Parses the submodule bbox yaml element into a modelable constraint object.

  Note that the TopLevel paths are defined using the `hierarchical` constraints.

  """
  COLOR_BORDER = 'lightskyblue'
  COLOR_FILL = 'aliceblue'

  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    coords = (relative_offset[0] + self.x, relative_offset[1] + self.y)

    self.geometry = [Rectangle(coords, self.width, self.height,
                              edgecolor=self.COLOR_BORDER,
                              facecolor=self.COLOR_FILL)]
    
    for geom in self.geometry:
      geom.set_picker(True)
      axes.add_artist(geom)
    return self.geometry

class ModuleHardMacro(ModuleConstraint):
  """
  Parses the hardmacro bbox yaml element into a modelable constraint object.
  """
  COLOR_BORDER = 'rebeccapurple'
  COLOR_FILL = 'mediumpurple'

  def __init__(self, yml, hierarchy):
    constraint_params = dict(name='Macro', type='group', child_params=[
      dict(name='LEF File', getter='path', type='str'),
    ])
    self.add_param_dict(constraint_params)
    super().__init__(yml, hierarchy)

    self.defined = False

    # Get the reference to the LEF macro that this constraint depends on
    self.master_module = hierarchy.get_module_by_path(self.path)
    if isinstance(self.master_module, str):
      self.master_module = hierarchy.macro_library.get_macro(self.master_module)

    if not self.master_module:
      print(f'Hard Macro placement constraint for {self.path} is not associated with a defined Verilog instance!')
    else:
      self.width = self.master_module.macro.c_size_x
      self.height = self.master_module.macro.c_size_y
    print('Placement Constraint Master: ', self.master_module)

  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    coords = (relative_offset[0] + self.x, relative_offset[1] + self.y)
    width = 0
    height = 0
    self.geometry.clear()

    if self.width and self.height:
      width = self.width
      height = self.height

    if isinstance(self.master_module, IRVMacro):
      width = self.master_module.macro.c_size_x
      height = self.master_module.macro.c_size_y

    if width and height:
      self.geometry.append(Rectangle(coords, width, height,
                                edgecolor=self.COLOR_BORDER,
                                facecolor=self.COLOR_FILL))

    # Propagate via LEF
    self.geometry.append(Circle(coords, 3,
                              edgecolor=self.COLOR_BORDER,
                              facecolor=self.COLOR_FILL))
      
    for geom in self.geometry:
      geom.set_picker(True)
      axes.add_artist(geom)
    return self.geometry


class PlacementConstraintManager:

  PLACEMENT_CONSTRAINT_TYPES = {
    'hierarchical': ModuleHierarchical,
    'toplevel': ModuleTopLevel,
    'obstruction': ModuleObstruction,
    'hardmacro': ModuleHardMacro,
    'overlap': ModuleOverlap,
  }

  @staticmethod
  def register_placement_constraint_type(name, cls):
    PlacementConstraintManager.PLACEMENT_CONSTRAINT_TYPES[name] = cls

  @staticmethod
  def deserialize(yml: dict, hierarchy: 'VerilogModuleHierarchy'
                  ) -> ModuleConstraint:
    """
    Deserializes an YAML placement constraint.

    Args:
        constraint (dict): Serialized placement constraint
        hierarchy (VerilogModuleHierarchy): Module hierarchy for module lookups
    """
    yml_type = yml.get('type')
    cls = PlacementConstraintManager.PLACEMENT_CONSTRAINT_TYPES.get(yml_type)
    return cls(yml, hierarchy)
    

IRVBehavior.PLACEMENT_CONSTRAINT_TYPES.update({
  'hierarchical': ModuleHierarchical,
  'toplevel': ModuleTopLevel,
  'obstruction': ModuleObstruction,
  'hardmacro': ModuleHardMacro,
  'overlap': ModuleOverlap,
})
