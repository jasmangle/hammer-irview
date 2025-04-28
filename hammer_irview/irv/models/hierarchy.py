

from collections import OrderedDict, defaultdict
import logging
import typing
from typing_extensions import Self
from PySide6 import QtCore

from hammer_irview.irv.models.module_hierarchy import ModuleHierarchyModel
from hammer_irview.irv.models.placement_constraints import ModuleConstraint
from hammer_irview.irv.pluginmgr import IRVBehavior

LOGGER = logging.getLogger(__name__)

class DesignHierarchyModule:

  def __init__(self, name, parent: Self,
               placement_constraints: dict[str, ModuleConstraint] = None):
    self.name = name

    self.parent = parent
    if self.parent:
      self.path = parent.path + '/' + self.name
    else:
      self.path = self.name

    if placement_constraints:
      self.placement_constraints = placement_constraints
    else:
      self.placement_constraints = OrderedDict()
    self.placement_constraints_list = []
    self.constraints_indices = {}

    self.toplevel = None
    self.module_model = ModuleHierarchyModel(self)

  def add_placement_constraint(self, constraint):
    self.placement_constraints[constraint.path] = constraint
    self.constraints_indices[constraint] = len(self.placement_constraints_list)
    self.placement_constraints_list.append(constraint)

  def appendChild(self, group):
    pass
    #self.children.append(SI(group, self))

  def data(self, column):
    if self.placement_constraints:
      return f'{self.name}'
    else:
      return f'{self.name} (No Layout)'

  def child(self, row):
    return self.children[row]

  def childrenCount(self):
    return 0

  def hasChildren(self):
    if len(self.children) > 0 :
      return True
    return False

  def row(self):
    if self.parent:
      return self.parent.children.index(self)
    return 0

  def columnCount(self):
    return 1


class DesignHierarchyModel(QtCore.QAbstractItemModel):

  def __init__(self):
    """Create and setup a new model"""
    super().__init__()

    # Dummy header element
    self.root = DesignHierarchyModule("Module", None)
    self.modules = defaultdict(list)

    # Bidirectional mapping of modules/module names
    self.modules_by_path = {}
    self.modules_by_name = {}

    # Reference to a toplevel constraint
    self.toplevel = None

    # Map of {macro name: lefdef LEF Instance}
    self.lefs = {}
  
  #### Module External Helpers ####

  def add_module(self, module, parent=None):
    self.modules[parent].append(module)
    self.modules_by_path[module.path] = module
    self.modules_by_name[module.name] = module

  def get_module_by_name(self, name):
    return self.modules_by_name.get(name)

  def get_module_by_path(self, path: str, parent=None):
    if parent:
      path = parent.path + '/' + path
    return self.modules_by_path.get(path)
  
  def set_toplevel_module(self, module):
    if module not in self.modules:
      self.add_module(module, None)
    self.toplevel = module

  #### Loading and Parsing Helpers ####

  def load_lefs(self, extra_libs: list[dict]):
    """
    Extracts LEF files from the vlsi.technology.extra_libraries section of a
    YAML file.

    :param extra_libs: Scoped vlsi.technology.extra_libraries contents.
    """
    for lib in extra_libs:
      if 'library' not in lib:
        LOGGER.warning(f"Extraneous library found in extra_libraries: {lib}")
        continue

      library = lib['library']
      file_path = library.get('lef_file')
      if not file_path:
        LOGGER.warning(f"Library found without LEF definition: {library}")
        continue

      lef = IRVBehavior.LEF_READER.read(file_path)
      


  def parse_vlsi_constraints(self, constraints):
    """
    Reads constraints from the `constraints` key of `vlsi.inputs.hierarchical`.
    """
    for constraint_module in constraints:
      for module_name, settings_list in constraint_module.items():
        module = self.get_module_by_name(module_name)
        if not module:
          LOGGER.warning(f"Unrecognized module '{module_name}' found in VLSI constraints, skipping...")
          continue
        
        # Incompletes always of the form
        # (VLSI key, *args)
        incompletes = []
        for setting_dict in settings_list:
          for setting in setting_dict.keys():
            if setting in IRVBehavior.VLSI_CONSTRAINT_HANDLERS:
              cur_incomplete = IRVBehavior.VLSI_CONSTRAINT_HANDLERS[setting][0](
                self, module, setting_dict[setting])
              incompletes.extend(cur_incomplete)
        
        # Do we still have any undefined constraints? If so, do more passes:
        start_incompletes = len(incompletes)
        still_incomplete = []
        while len(still_incomplete) != start_incompletes:
          still_incomplete.clear()
          for inc in incompletes:
            cur_incomplete = IRVBehavior.VLSI_CONSTRAINT_HANDLERS[inc[0]][1](*inc[1:])
            if cur_incomplete:
              still_incomplete.append(cur_incomplete)
          incompletes = still_incomplete.copy()
        
        if start_incompletes > 0 and len(still_incomplete) == start_incompletes:
          # Did a pass and nothing was resolved, there is a circular dependency.
          LOGGER.error('Circular dependency or unresolvable parameter detected for the following constraints:')
          for inc in still_incomplete:
            LOGGER.error(f'\t*\t{inc}')
          
  
  def index(self, row:int, column:int, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> QtCore.QModelIndex:
    """Returns the index of the item in the model specified by the given row, column and parent index."""
    if not self.hasIndex(row, column, parent):
      return QtCore.QModelIndex()
    if not parent.isValid():
      item = None
    else:
      item = parent.internalPointer()

    child = self.modules[item][row]
    if child:
        return self.createIndex(row, column, child)
    return QtCore.QModelIndex()
  
  def parent(self, child:QtCore.QModelIndex) -> QtCore.QModelIndex:
    """Returns the parent of the model item with the given index. If the item has no parent, an invalid QModelIndex is returned."""
    if not child.isValid():
      return QtCore.QModelIndex()
    item = child.internalPointer()
    if not item:
      return QtCore.QModelIndex()

    parent = item.parent
    if parent == None:
      return QtCore.QModelIndex()
    else:
      return self.createIndex(parent.row(), 0, parent)

  def rowCount(self, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> int:
    """Returns the number of rows under the given parent. When the parent is valid it means that is returning the number of children of parent."""
    if parent.row() > 0:
      return 0
    if parent.isValid():
      item = parent.internalPointer()
    else:
      item = None
    return len(self.modules[item])

  def columnCount(self, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> int:
    """Returns the number of columns for the children of the given parent."""
    if parent.isValid():
      return parent.internalPointer().columnCount()
    else:
      return self.root.columnCount()

  def data(self, index:QtCore.QModelIndex, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data stored under the given role for the item referred to by the index."""
    if index.isValid() and role == QtCore.Qt.DisplayRole:
      return index.internalPointer().data(index.column())
    elif not index.isValid():
      return "No Data (This is a bug)"

  def headerData(self, section:int, orientation:QtCore.Qt.Orientation, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data for the given role and section in the header with the specified orientation."""
    if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
      if self.toplevel:
        return f"Top Level: {self.toplevel.name}"
      else:
        return "No Design Loaded"
