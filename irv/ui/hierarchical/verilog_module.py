"""
Contains all Verilog-adjacent information modeling classes.
"""
from collections import OrderedDict, defaultdict
import os
import logging
from pathlib import Path
import re
import typing

from PySide6 import QtCore, QtWidgets

from irv.ui.hierarchical.lef import IRVMacro, MacroLibrary
from irv.ui.hierarchical.placement_constraints import ModuleConstraint, ModuleHierarchical, ModuleTopLevel, PlacementConstraintManager
from irv.ui.hierarchical.yml_loader import HammerYaml

LOGGER = logging.getLogger(__name__)


class VerilogModule:
  """
  Module to hold a grouping of Verilog instance relationships for a particular
  module. This should be referenced by a VerilogModuleInstance, which contains
  the actual instantiation of this module.
  """

  def __init__(self, name: str, file: Path):
    self.name = name
    self.file = file
    self.instances = {}

    self.top_constraint = None
    self.children = []

    self.constraints = OrderedDict()
    self.constraints_list = []
    self.constraints_indices = {}

    self.view_model = VerilogModuleConstraintsModel(self)

  def add_constraint(self, constraint: ModuleConstraint):
    constraint.module = self
    self.constraints[constraint.path] = constraint
    self.constraints_indices[constraint] = len(self.constraints_list)
    self.constraints_list.append(constraint)
    if isinstance(constraint, ModuleTopLevel):
      self.top_constraint = constraint
    if isinstance(constraint, ModuleHierarchical):
      self.children.append(constraint)

  def __str__(self):
    return f'<{self.name} from {self.file}>'
  
  def __repr__(self):
    return f'<{self.name} from {self.file}>'


class VerilogModuleInstance:
  """
  Contains details regarding a specific VerilogModule instance.
  """

  def __init__(self, name: str, module: VerilogModule):
    self.name = name
    self.module = module


class VerilogModuleHierarchy:
  """
  
  """

  RE_MODULE_DEFINITION = r'module\s+(\w+)\s*(#\s*\([^)]*\)\s*)?\s*\([^)]*\)\s*;([\s\S]*?)endmodule'
  """
  Pattern to find a Verilog module definition within a file.
  """

  RE_MODULE_INSTANTIATION = r'(\w+)\s+(\w+)\s*\('
  """
  Pattern to find Verilog module instantiations within a module's body.
  """

  RE_BLOCK_COMMENT = r'/\*.*?\*/'
  """
  Pattern to find a Verilog block comment.
  """

  RE_LINE_COMMENT = r'//.*'
  """
  Pattern to find a Verilog single-line comment.
  """


  def __init__(self):

    # Modules of the form: {name: VerilogModule, ...}
    self.modules = OrderedDict()
    self.macro_library = MacroLibrary()
    self.scoped_hierarchy = OrderedDict()
    self.top_level = None
    self.unknown_macros = defaultdict(set)

  def iter_files_in_path(self, directory: Path):
    """
    Generator for retriving all .SV files recursively from a particular
    directory.

    Args:
        directory (Path): Path to search within.
    """
    for p in directory.glob('**/*.[sv][v]'):
      yield p

  def strip_comments(self, content: str):
    """
    Removes all comments (block or single-line) from a Verilog file.

    Args:
        file_content (str): Content of a Verilog file.
    """
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*', '', content)
    return content
  
  def set_top_level_module(self, module):
    self.top_level = module
    ## TODO: Ideally, signal that the view needs to change from the root.

  def parse_verilog_file(self, file: Path) -> list[tuple[VerilogModule, str]]:
    """
    Parses all modules from a Verilog file.

    Args:
        file (Path): Path to the Verilog file to parse.

    Returns:
        list[tuple[VerilogModule, str]]: List of tuples containing
          (VerilogModule object, module body)
    """
    verilog_modules = []
    with open(file, 'r') as verilog_file:
      content = verilog_file.read()

      # Remove comments
      content = self.strip_comments(content)

      # Find all module definitions
      modules = re.findall(self.RE_MODULE_DEFINITION, content, re.MULTILINE)

      # `modules` is a list of tuples with the following information:
      # - [0]: Module Name; [2]: Module Body
      for module_data in modules:
        module_name, _, module_body = module_data
        module = VerilogModule(module_name, file)
        verilog_modules.append((module, module_body))
        LOGGER.debug(f"Found module '{module}'")
    return verilog_modules

  def parse_module_instances(self, module: tuple[VerilogModule, str]):
    """
    Gets all instances for a specific Verilog module and assign them to the
    respective VerilogModule, logging those that haven't been loaded (i.e.,
    LEFs)

    Args:
        module (tuple[VerilogModule, str]): Module+body tuple to parse.
    """
    vmodule, module_body = module
    insts = re.findall(self.RE_MODULE_INSTANTIATION, module_body)

    print(insts)
    for instance in insts:
      inst_module_name, inst_name = instance
      inst_obj = vmodule.instances.get(inst_name)
      
      if not inst_obj:
        inst_obj = VerilogModuleInstance(inst_name, inst_module_name)
        vmodule.instances[inst_name] = inst_obj

      if isinstance(inst_obj.module, VerilogModule):
        # Was resolved before, should update to make sure nothing changed.
        inst_obj.module = self.modules.get(
          inst_obj.module.name, inst_obj.module.name)
      elif isinstance(inst_obj.module, IRVMacro):
        continue
      elif isinstance(inst_obj.module, str):
        # Not resolved yet, attempt to resolve.
        inst_obj.module = self.macro_library.get_macro(inst_obj.module) \
          or self.modules.get(inst_obj.module, inst_obj.module)
        
        # Remove from unknown macros (if it exists)
        if inst_obj in self.unknown_macros[inst_name]:
          self.unknown_macros[inst_name].remove(inst_obj)

      if isinstance(inst_obj.module, str):
        # If after the earlier steps it is still unresolved, log for later.
        self.unknown_macros[inst_name].add(inst_obj)

    # full_instance_path = '/'.join([parent_path, inst_name]) if parent_path else inst_name

  def register_modules_from_directory(self, directory: Path, statusbar: typing.Union[QtWidgets.QStatusBar, None]):
    """
    Registers all .sv files as IRView VerilogModule objects for the current
    VerilogModuleHierarchy.

    Args:
        directory (Path): Path to .sv files.
        statusbar (QStatusBar): Status bar to update with progress.
    """
    directory = Path(directory)
    modules_found = []

    # Parse modules as a flat structure
    for vfile in self.iter_files_in_path(directory):
      statusbar.showMessage(f"Parsing '{vfile}'")
      # Update our registry with the found verilog files.
      modules = self.parse_verilog_file(vfile)
      for module in modules:
        vmodule_obj, module_body = module
        self.modules[vmodule_obj.name] = vmodule_obj
        modules_found.append(module)


    # All modules loaded from all files. Parse instance hierarchy
    for module_tpl in modules_found:
      vmodule_obj, module_body = module_tpl
      statusbar.showMessage(f"Reading instances for module '{vmodule_obj.name}'")
      self.parse_module_instances(module_tpl)

  def register_macros_from_yml(self, yml: HammerYaml):
    """
    Registers LEF macros based on the provided HAMMER YML file.

    Args:
        yml_file (HammerYaml): HammerYaml pre-parsed YAML object.
        statusbar (QtWidgets.QStatusBar | None): Status bar for GUI updates.
    """
    all_paths = []

    # Open technology libraries
    tech_libs = yml.get_value('vlsi.technology.extra_libraries') or []
    
    for lib in tech_libs:
      lib = lib.get('library')
      lib_lef_path = lib.get('lef_file')
      if lib_lef_path:
        all_paths.append(Path(lib_lef_path))

    # Now, let's load the extras.
    extra_lefs = yml.get_value('irview.extra_lefs') or []
    for lef in extra_lefs:
      # lef contains the path to the lef that we wish to load.
      all_paths.append(Path(lef))

    for path in all_paths:
      self.macro_library.add_by_path(path)

  def register_constraints_in_yml(self, yml: HammerYaml, statusbar: QtWidgets.QStatusBar | None):
    """
    Registers all constraints from a provided HAMMER YML file.

    Args:
        yml_file (HammerYaml): HammerYaml pre-parsed YAML object.
    """
    
    constraints = yml.get_value('vlsi.inputs.placement_constraints')
    num_constraints = len(constraints)
    for i, constraint in enumerate(constraints):
      statusbar.showMessage(f'[{yml.yml_file}] Deserializing placement constraint {i+1} of {num_constraints}')
      constraint_obj = PlacementConstraintManager.deserialize(constraint, self)
      constraint_obj.module.add_constraint(constraint_obj)
    # if 

    # if constraint_obj.module.add_constr


  def get_module_by_name(self, name: str) -> typing.Union[VerilogModule, None]:
    """
    Retrieves a VerilogModule object from its name.

    Args:
        name (str): Name of the module to retrieve

    Returns:
        Union[VerilogModule, None]: The associated VerilogModule, or None if it
            doesn't exist.
    """
    return self.modules.get(name)
  
class VerilogModuleHierarchyScopedModel(QtCore.QAbstractItemModel):

  # Internal Pointer managed as VerilogModule objects.

  def __init__(self, hierarchy: VerilogModuleHierarchy):
    super().__init__()
    self.hierarchy = hierarchy
    self.selection_model = QtCore.QItemSelectionModel(self)

  def index(self, row:int, column:int, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> QtCore.QModelIndex:
    """Returns the index of the item in the model specified by the given row, column and parent index."""
    if not self.hasIndex(row, column, parent):
      return QtCore.QModelIndex()
    if not parent.isValid():
      child = self.hierarchy.top_level
    else:
      parent_module = parent.internalPointer()
      child = parent_module.children[row]

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

    parent = None
    if parent == None:
      return QtCore.QModelIndex()
    else:
      return self.createIndex(parent.row(), 0, parent)

  def rowCount(self, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> int:
    """Returns the number of rows under the given parent. When the parent is valid it means that is returning the number of children of parent."""
    if parent.row() > 0:
      return 0
    if parent.isValid():
      parent_module = parent.internalPointer()
      return len(parent_module.children)
    else:
      return 1 if self.hierarchy.top_level else 0
    

  def columnCount(self, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> int:
    """Returns the number of columns for the children of the given parent."""
    return 2

  def data(self, index:QtCore.QModelIndex, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data stored under the given role for the item referred to by the index."""
    if index.isValid() and role == QtCore.Qt.DisplayRole:
      if index.column() == 0:
        return index.internalPointer().name
      else:
        return index.internalPointer().file
    elif not index.isValid():
      return "No Data (This is a bug)"

  def headerData(self, column:int, orientation:QtCore.Qt.Orientation, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data for the given role and section in the header with the specified orientation."""
    if column == 0 and orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
      if self.hierarchy.top_level:
        return f"Top Level: {self.hierarchy.top_level.name}"
      else:
        return "No Design Loaded"
      

class VerilogModuleConstraintsModel(QtCore.QAbstractItemModel):

  # Internal Pointer managed as ModuleConstraint objects.

  def __init__(self, module: 'VerilogModule'):
    super().__init__()
    self.module = module
    self.selection_model = QtCore.QItemSelectionModel(self)
    self.descend_edit = False

  ### --- Custom --- ###

  def get_constraint_index(self, constraint):
    # TODO: May need to implement `parent` for hierarchical constraints...
    module = constraint.module
    row = module.constraints_indices.get(constraint, 0)

    # Get parent of constraint
    

    return self.createIndex(row, 0, constraint)
  
  ### --- QAbstractItemModel --- ###

  def index(self, row:int, column:int, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> QtCore.QModelIndex:
    """Returns the index of the item in the model specified by the given row, column and parent index."""
    if not self.hasIndex(row, column, parent):
      return QtCore.QModelIndex()
    if not parent.isValid():
      constraint = self.module.constraints_list[row]
    else:
      parent_constraint = parent.internalPointer()
      constraint = parent_constraint.module.constraints_list[row]

    if constraint:
        return self.createIndex(row, column, constraint)
    return QtCore.QModelIndex()
  
  def parent(self, child:QtCore.QModelIndex) -> QtCore.QModelIndex:
    """Returns the parent of the model item with the given index. If the item has no parent, an invalid QModelIndex is returned."""
    if not child.isValid():
      return QtCore.QModelIndex()
    item = child.internalPointer()
    if not item:
      return QtCore.QModelIndex()

    parent = None
    if parent == None:
      return QtCore.QModelIndex()
    else:
      return self.createIndex(parent.row(), 0, parent)

  def rowCount(self, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> int:
    """Returns the number of rows under the given parent. When the parent is valid it means that is returning the number of children of parent."""
    if parent.row() > 0:
      return 0
    if parent.isValid():
      constraint = parent.internalPointer()
      if isinstance(constraint, ModuleHierarchical):
        return len(constraint.module.constraints_list)
      else:
        return 0
    else:
      return len(self.module.constraints_list)
    
  # def hasChildren(self, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> bool:
  #   if parent.isValid():
  #     return bool(parent.internalPointer().module.constraints)
  #   return bool(self.module.constraints)
  

  def columnCount(self, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> int:
    """Returns the number of columns for the children of the given parent."""
    return 2

  def data(self, index:QtCore.QModelIndex, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data stored under the given role for the item referred to by the index."""
    if index.isValid() and role == QtCore.Qt.DisplayRole:
      if index.column() == 0:
        return index.internalPointer().path
      else:
        return index.internalPointer().type
    elif not index.isValid():
      return "No Data (This is a bug)"

  def headerData(self, section:int, orientation:QtCore.Qt.Orientation, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data for the given role and section in the header with the specified orientation."""
    if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
      if section == 0:
        return 'Relative RTL Path'
      elif section == 1:
        return 'Type'
