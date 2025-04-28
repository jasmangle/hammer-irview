"""
Qt View Models for common data display formats.
"""


import logging
import typing

from PySide6 import QtCore, QtGui

from hammer.hammer.tech.stackup import RoutingDirection
from hammer_irview.irv.hierarchical.placement_constraints import IRVAlignCheck, ModuleConstraint, ModuleHierarchical

from typing import TYPE_CHECKING

from hammer_irview.irv.pluginmgr import IRVBehavior

if TYPE_CHECKING:
  from hammer_irview.irv.hierarchical.verilog_module import VerilogModuleHierarchy, VerilogModule

LOGGER = logging.getLogger(__name__)


class VerilogModuleHierarchyScopedModel(QtCore.QAbstractItemModel):

  # Internal Pointer managed as VerilogModule objects.

  def __init__(self, hierarchy: 'VerilogModuleHierarchy'):
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
    return 1

  def data(self, index:QtCore.QModelIndex, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data stored under the given role for the item referred to by the index."""
    if index.isValid() and role == QtCore.Qt.DisplayRole:
      return index.internalPointer().name
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
    self.icon_aligned = QtGui.QIcon(str(IRVBehavior.UI_PATH / 'icon-aligned.jpg'))
    self.icon_misaligned = QtGui.QIcon(str(IRVBehavior.UI_PATH / 'icon-misaligned.jpg'))

    for constraint in self.module.constraints_list:
      constraint.refresh_alignment()


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
    if not index.isValid():
      return 'No Data (This is a bug)'
    
    constraint: ModuleConstraint = index.internalPointer()
    if role == QtCore.Qt.ItemDataRole.DisplayRole:
      if index.column() == 0:
        return constraint.path
      else:
        return constraint.type
    elif role == QtCore.Qt.ItemDataRole.DecorationRole and index.column() == 0:
      if self.module.top_constraint == constraint:
        return None
      match constraint.is_grid_aligned:
        case IRVAlignCheck.ALIGNED:
          return self.icon_aligned
        case IRVAlignCheck.MISALIGNED:
          return self.icon_misaligned
        case IRVAlignCheck.UNKNOWN:
          return None
    elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
      header = ''
      match constraint.is_grid_aligned:
        case IRVAlignCheck.ALIGNED:
          header = 'Grid alignment check passed.'
        case IRVAlignCheck.MISALIGNED:
          header = 'Grid alignment check failed.'
        case IRVAlignCheck.UNKNOWN:
          header = 'Grid alignment was not checked for this constraint.'
      
      # Show stackup details
      return f'{header}\n{constraint.misaligned_log}'

  def headerData(self, section:int, orientation:QtCore.Qt.Orientation, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data for the given role and section in the header with the specified orientation."""
    if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
      if section == 0:
        return 'Relative RTL Path'
      elif section == 1:
        return 'Type'
