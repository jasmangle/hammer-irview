
from threading import Thread
from PySide6.QtWidgets import QApplication

from irview.irv.mainwindow import MainWindow


class IRVApp(QApplication):

  def __init__(self, driver):
    super().__init__([])
    self.main = MainWindow()  # 'global'

    # Load the yaml files provided
    if driver:
      Thread(target=self.main.load_hammer_data, args=(driver,)).start()
      # self.main.load_yamls(args[1:])
