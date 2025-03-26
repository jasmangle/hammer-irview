from matplotlib.axes import Axes
from matplotlib.patches import Circle, Rectangle
from pyqtgraph.parametertree import Parameter
from PySide6.QtCore import SIGNAL


class ModuleConstraint:
  """
  Modelable placement constraint object.
  """

  # pyname = Mapping for class variable.
  

  def __init__(self, module, yml: dict, model):
    
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
      ]),
      dict(name='Margins', type='group', child_params=[
        dict(name='Left', type='float', getter=self.get_param_margins),
        dict(name='Right', type='float', getter=self.get_param_margins),
        dict(name='Top', type='float', getter=self.get_param_margins),
        dict(name='Bottom', type='float', getter=self.get_param_margins),
      ]),
    ]), end=False)
    
    self.module = module
    self.path = yml.get('path')
    self.type = yml.get('type')
    self.x = yml.get('x', 0)
    self.y = yml.get('y', 0)
    self.width = yml.get('width')
    self.height = yml.get('height')
    self.margins = yml.get('margins')
    self.defined = True
    self.yml = yml

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

  def get_param_margins(self, yml, name):
    return yml.get('margins', {}).get(name.lower(), 0)
  
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

  def __init__(self, module, yml, model):
    super().__init__(module, yml, model)

    if module and module.name == self.path:
      module.toplevel = self

  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    coords = (relative_offset[0] + self.x, relative_offset[1] + self.y)

    if under_hierarchy:
      self.geometry = Rectangle(coords, self.width, self.height,
                                edgecolor=self.HIER_COLOR_BORDER,
                                facecolor=self.HIER_COLOR_FILL)
    else:
      self.geometry = Rectangle(coords, self.width, self.height,
                                edgecolor=self.TOP_COLOR_BORDER,
                                facecolor=self.TOP_COLOR_FILL)
    
    self.geometry.set_picker(True)
    axes.add_artist(self.geometry)
    return [self.geometry]


class ModuleHierarchical(ModuleConstraint):
  """
  Parses the submodule bbox yaml element into a modelable constraint object.

  Note that the TopLevel paths are defined using the `hierarchical` constraints.

  """
  TOP_COLOR_BORDER = 'silver'
  TOP_COLOR_FILL = 'whitesmoke'

  HIER_COLOR_BORDER = 'lightcoral'
  HIER_COLOR_FILL = 'mistyrose'

  def __init__(self, module, yml, model):
    constraint_params = dict(name='Hierarchical', type='group', child_params=[
      dict(name='Master', getter='master', type='str'),
    ])
    self.add_param_dict(constraint_params)
    super().__init__(module, yml, model)

    self.defined = False
    # Get the reference to the external module that this constraint depends on
    self.attempt_init(module, yml, model)

  def attempt_init(self, module, yml, model):
    # Retry until referenced hierarchy module is defined.
    self.master_module = model.get_module_by_name(self.master) \
      or model.get_lef_by_instance_name(self.master)
    if self.master_module:
      self.defined = True
      return


  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    coords = (relative_offset[0] + self.x, relative_offset[1] + self.y)

    if not under_hierarchy:
      self.geometry = Rectangle(coords, self.width, self.height,
                                edgecolor=self.HIER_COLOR_BORDER,
                                facecolor=self.HIER_COLOR_FILL)
    else:
      self.geometry = Rectangle(coords, self.width, self.height,
                                edgecolor=self.TOP_COLOR_BORDER,
                                facecolor=self.TOP_COLOR_FILL)
    
    self.geometry.set_picker(True)
    axes.add_artist(self.geometry)
    all_artists = [self.geometry]

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

    self.geometry = Rectangle(coords, self.width, self.height,
                              edgecolor=self.COLOR_BORDER,
                              facecolor=self.COLOR_FILL)
    self.geometry.set_picker(True)
    axes.add_artist(self.geometry)
    return [self.geometry]

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

    self.geometry = Rectangle(coords, self.width, self.height,
                              edgecolor=self.COLOR_BORDER,
                              facecolor=self.COLOR_FILL)
    self.geometry.set_picker(True)
    axes.add_artist(self.geometry)
    return [self.geometry]

class ModuleHardMacro(ModuleConstraint):
  """
  Parses the hardmacro bbox yaml element into a modelable constraint object.
  """
  COLOR_BORDER = 'rebeccapurple'
  COLOR_FILL = 'mediumpurple'

  def render(self, axes: Axes, relative_offset: tuple[int, int],
             under_hierarchy: bool, render_hierarchy: bool):
    coords = (relative_offset[0] + self.x, relative_offset[1] + self.y)

    if self.width and self.height:
      self.geometry = Rectangle(coords, self.width, self.height,
                                edgecolor=self.COLOR_BORDER,
                                facecolor=self.COLOR_FILL)
    else:
      # Propagate via LEF
      self.geometry = Circle(coords, 3,
                                edgecolor=self.COLOR_BORDER,
                                facecolor=self.COLOR_FILL)
    self.geometry.set_picker(True)
    axes.add_artist(self.geometry)
    return [self.geometry]
