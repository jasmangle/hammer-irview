
from PySide6.QtWidgets import QApplication

from irv.ui import MainWindow


class IRVApp(QApplication):

  def __init__(self, args):
    super().__init__(args)
    self.main = MainWindow()  # 'global'

    # Load the yaml files provided
    if len(args) > 1:
      self.main.load_yamls(args[1:])
