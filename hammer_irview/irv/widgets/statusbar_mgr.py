"""
QStatusBar -> Logging interface
"""

import logging

from PySide6.QtWidgets import QStatusBar


LOGGER = logging.getLogger(__name__)

class StatusBarLogger:

  def __init__(self, statusbar: QStatusBar):
    self.logger = LOGGER
    self.statusbar = statusbar

  def showMessage(self, msg: str):
    self.logger.info(msg)
    self.statusbar.showMessage(msg)