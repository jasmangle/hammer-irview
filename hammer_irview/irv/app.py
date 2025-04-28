import signal
from threading import Thread
from PySide6.QtWidgets import QApplication

from hammer.hammer.vlsi.driver import HammerDriver
from hammer_irview.irv.mainwindow import MainWindow


class IRVApp(QApplication):

  def __init__(self, driver: HammerDriver):
    super().__init__([])
    self.main = MainWindow()  # 'global'

    def handle_sigint(signum, frame):
      driver.log.info("SIGINT received. Exiting gracefully...")
      QApplication.quit()

    # Load the yaml files provided
    if driver:
      signal.signal(signal.SIGINT, handle_sigint)
      Thread(target=self.main.load_hammer_data, args=(driver,)).start()
      # self.main.load_yamls(args[1:])
