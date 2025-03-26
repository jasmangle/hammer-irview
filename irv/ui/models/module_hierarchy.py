import logging
import typing
from PySide6 import QtCore
from irv.ui.models.placement_constraints import ModuleConstraint
from irv.ui.pluginmgr import IRVBehavior

LOGGER = logging.getLogger(__name__)


class ModuleHierarchyConstraint:

  def __init__(self, constraint):
    self.constraint = constraint

  def appendChild(self, group):
    pass

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


class ModuleHierarchyModel(QtCore.QAbstractItemModel):

  def __init__(self, module):
    """Create and setup a new model"""
    super().__init__()
    self.module = module
    self.selection_model = QtCore.QItemSelectionModel(self)
    
  def indexFromConstraint(self, constraint):
    row = self.module.constraints_indices.get(constraint, 0)
    return self.createIndex(row, 0, constraint)
  
  def index(self, row:int, column:int, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> QtCore.QModelIndex:
    """Returns the index of the item in the model specified by the given row, column and parent index."""
    if not self.hasIndex(row, column, parent):
      return QtCore.QModelIndex()
    if not parent.isValid():
      item = None
    else:
      item = parent.internalPointer()

    child = self.module.placement_constraints_list[row]
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
    if parent.isValid():
      return 0
    else:
      return len(self.module.placement_constraints_list)

  def columnCount(self, parent:typing.Optional[QtCore.QModelIndex]=QtCore.QModelIndex()) -> int:
    """Returns the number of columns for the children of the given parent."""
    return 2

  def data(self, index:QtCore.QModelIndex, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data stored under the given role for the item referred to by the index."""
    if index.isValid() and role == QtCore.Qt.ItemDataRole.DisplayRole:
      return index.internalPointer().data(index.column())
    # elif index.isValid() and role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
    #   return QtCore.Qt.AlignmentFlag.AlignRight
    elif not index.isValid():
      return None

  def headerData(self, section:int, orientation:QtCore.Qt.Orientation, role:typing.Optional[int]=QtCore.Qt.DisplayRole) -> typing.Any:
    """Returns the data for the given role and section in the header with the specified orientation."""
    if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
      if section == 0:
        return 'RTL Path'
      elif section == 1:
        return 'Type'
