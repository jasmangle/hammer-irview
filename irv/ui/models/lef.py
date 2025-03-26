import logging
import typing
from PySide6 import QtCore
from irv.ui.models.placement_constraints import ModuleConstraint
from irv.ui.pluginmgr import IRVBehavior

LOGGER = logging.getLogger(__name__)


class LefDefUtils:

  def __init__(self, file_path):
    """
    Loads all necessary data from a LEF file
    """