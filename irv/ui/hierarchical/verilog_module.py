"""
Contains all Verilog-adjacent information modeling classes.
"""
from collections import OrderedDict
import os
import logging
from pathlib import Path
import re
import typing

from PySide6 import QtCore

LOGGER = logging.getLogger(__name__)


# class PbRObject:
#   """
#   Pass-by-Reference wrapper object for 
#   """
#   def __init__(self,s=""):
#     self.s=s
#   def __add__(self,s):
#     self.s+=s
#     return self
#   def __str__(self):
#     return self.s


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

  def iter_files_in_path(directory: Path):
    """
    Generator for retriving all .SV files recursively from a particular
    directory.

    Args:
        directory (Path): Path to search within.
    """
    for p in directory.glob('**/*.sv'):
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
        LOGGER.info(f"Found module '{module}'")
    return verilog_modules

  def parse_module_instances(self, module: tuple[VerilogModule, str],
                             parent_path: str
                             ) -> dict[str, VerilogModuleInstance]:
    """
    Gets all instances for a specific Verilog module.

    Args:
        module (tuple[VerilogModule, str]): Module+body tuple to parse.
        parent_path: Path for the hierarchical parent of this module.

    Returns:
        dict[str, VerilogModuleInstance]: Map of VerilogModuleInstance
          objects.
    """
    vmodule, module_body = module
    instances = re.findall(self.RE_MODULE_INSTANTIATION, module_body)
    LOGGER.info(f'Found {len(instances)} instances in module {vmodule.name}')

    instances = {}
    for instance in instances:
      inst_module_name, inst_name = instance
      # full_instance_path = '/'.join([parent_path, inst_name]) if parent_path else inst_name
      instances[inst_name] = inst_module_name

    return instances

  def register_modules_from_directory(self, directory: Path):
    """
    Registers all .sv files as IRView VerilogModule objects for the current
    VerilogModuleHierarchy.

    Args:
        directory (Path): Path to .sv files.
    """
    modules_found = []

    # Parse modules as a flat structure
    for vfile in self.iter_files_in_path(directory):
      # Update our registry with the found verilog files.
      modules = self.parse_verilog_file(vfile)
      for module in modules:
        vmodule_obj, module_body = module
        self.modules[vmodule_obj.name] = vmodule_obj
        modules_found.append(module)

    
    # All modules loaded from all files. Parse instance hierarchy
    for module_tpl in modules_found:
      vmodule_obj, module_body = module_tpl
      vmodule_obj.instances.update(self.parse_module_instances(module_tpl))
      

class VerilogModuleHierarchyModel():

  def __init__(self, hierarchy):
    self.hierarchy = hierarchy

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
      if index.column() == 0:
        return index.internalPointer().
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