

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QHBoxLayout
from PySide6.QtGui import QMovie
from PySide6.QtCore import Qt, QTimer
from PySide6.QtSvgWidgets import QSvgWidget


class LoadingDialog(QDialog):
    
  def __init__(self, text, parent=None):
    super().__init__(None)
    self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
    self.setModal(True)
    self.setAttribute(Qt.WA_TranslucentBackground)

    # Layout
    layout = QHBoxLayout(self)
    layout.setAlignment(Qt.AlignCenter)

    # Loading GIF
    # self.svg_label = QSvgRenderer(self)
    self.svg_label = QSvgWidget(self)
    # self.svg_label.setAlign(Qt.AlignCenter)
    # self.svg_label(True)
    self.svg_label.load('hammer_irview/ui/loading.svg')
    #self.movie = QMovie("loading.gif")  # Replace with your GIF file path
    #self.gif_label.setMovie(self.movie)
    
    #self.movie.start()

    self.text_label = QLabel(text, self)
    self.text_label.setAlignment(Qt.AlignCenter)
    self.text_label.setStyleSheet("color: black; font-size: 16px;")

    # Add widgets to layout
    layout.addWidget(self.svg_label, 0, Qt.AlignCenter)
    layout.addWidget(self.text_label, 0, Qt.AlignCenter)

    # Set dialog size and background
    self.setFixedSize(300, 200)
    self.setStyleSheet("background-color: rgba(0, 0, 0, 150); border-radius: 10px;")

    QTimer.singleShot(
      0,
      lambda: self.move(
        self.mapToGlobal(parent.rect().center() - self.rect().center())
      ),
    )