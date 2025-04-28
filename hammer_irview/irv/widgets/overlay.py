import logging
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from hammer_irview.irv.pluginmgr import IRVBehavior

log = logging.getLogger(__name__)

class OverlayWidget(QtWidgets.QWidget):
  """
  Container-like widget which allows the user to overlay another widget on top of it. Switching on/off the overlay
  widget is done by setting the overlayHidden property.
  
  Credit: https://github.com/Woutah/pyside6-utils/blob/main/pyside6_utils/widgets/overlay_widget.py
  """


  def __init__(self, parent: QtWidgets.QWidget | None) -> None:
    super().__init__(parent)

    self._display_overlay = False
    self._overlay_widget = None
    self._overlay_widget_container: QtWidgets.QWidget = QtWidgets.QWidget(self)
    self._overlay_widget_container.setParent(self)
    self._overlay_widget_container.setWindowFlags(Qt.WindowType.Widget | Qt.WindowType.FramelessWindowHint)
    self._overlay_widget_container.setAutoFillBackground(True)
    self._overlay_widget_container.setContentsMargins(0, 0, 0, 0)
    self._overlay_widget_container.raise_()

    if self.parent:
      self.resizeToParent()

    self._cur_background_color = None
    self.set_overlay_mouse_block(True)
    self.set_background_color(QtGui.QColor(200, 200, 200, 150))


  def set_overlay_mouse_block(self, block: bool) -> None:
    """Sets whether the overlay widget should block mouse events from reaching the underlying widget."""
    self._overlay_widget_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not block)

  def get_overlay_mouse_block(self) -> bool:
    """Returns whether the overlay widget blocks mouse events from reaching the underlying widget."""
    return self._overlay_widget_container.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

  def showEvent(self, event: QtGui.QShowEvent) -> None:
    """On show, raise the overlay widget to make sure it is on top."""
    self._overlay_widget_container.raise_() #Make sure the overlay widget is on top
    return super().showEvent(event)


  def set_overlay_widget(self, overlay_widget: QtWidgets.QWidget) -> None:
    """
    Sets the overlay widget to display on top of this widget.
    """
    self._overlay_widget = overlay_widget
    self._overlay_widget_container.setLayout(QtWidgets.QVBoxLayout()) #Reset the layout to remove any previous
    self._overlay_widget_container.layout().addWidget(overlay_widget)
    self._overlay_widget_container.resize(self.size())
    self._overlay_widget_container.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._overlay_widget_container.raise_()

  def resizeToParent(self):
    if self.parent:
      self.resize(self.parent().size())

  def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
    """
    #On resize, update the overlay widget size
    """
    super().resizeEvent(event)
    self._overlay_widget_container.resize(self.size())

  def set_overlay_hidden(self, hidden: bool) -> None:
    """
    Sets the overlay widget to be hidden or visible.
    """
    self._overlay_widget_container.setHidden(hidden)

  def get_overlay_hidden(self) -> bool:
    """
    Returns whether the overlay widget is hidden or visible.
    """
    return self._overlay_widget_container.isHidden()

  def set_background_color(self, color: QtGui.QColor) -> None:
    """
    Sets the background color of the overlay widget.
    """
    self._cur_background_color = color
    style = QtWidgets.QApplication.style()
    palette = style.standardPalette()
    palette.setColor(QtGui.QPalette.ColorRole.Window, color) #Background color
    self._overlay_widget_container.setPalette(palette)
  def get_background_color(self) -> QtGui.QColor | None:
    """
    Returns the background color of the overlay widget.
    """
    return self._cur_background_color

  overlayHidden = QtCore.Property(bool, get_overlay_hidden, set_overlay_hidden)
  overlayBlocksMouse = QtCore.Property(bool, get_overlay_mouse_block, set_overlay_mouse_block)
  overlayBackgroundColor = QtCore.Property(QtGui.QColor, get_background_color, set_background_color)


class LoadingWidget(OverlayWidget):

  def __init__(self, text, parent):
    super().__init__(parent)

    #Create overlay and create button to hide it
    overlay = QtWidgets.QWidget(None)

    sizePolicy = QtWidgets.QSizePolicy(
      QtWidgets.QSizePolicy.Policy.Expanding,
      QtWidgets.QSizePolicy.Policy.Fixed)
    sizePolicy.setHorizontalStretch(0)
    sizePolicy.setVerticalStretch(0)
    sizePolicy.setHeightForWidth(overlay.sizePolicy().hasHeightForWidth())
    
    #overlay.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
    #overlay.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
    #overlay.setLineWidth(3)
    #overlay.setFixedSize(154, 68)
    overlay.setLayout(QtWidgets.QHBoxLayout())
    overlay.setCursor(Qt.CursorShape.WaitCursor)
    overlay.setStyleSheet("border-radius: 5px; background-color: rgba(255, 255, 255 , 1);")
    
    movie = QtGui.QMovie(str(IRVBehavior.UI_PATH / 'hammer.gif'))
    self.gif_label = QtWidgets.QLabel()
    self.gif_label.setMinimumSize(QtCore.QSize(50, 50))
    self.gif_label.setMaximumSize(QtCore.QSize(50, 50))
    self.gif_label.setScaledContents(True)

    self.gif_label.setMovie(movie)
    movie.start()
    overlay.layout().addWidget(self.gif_label)

    self.txt_label = QtWidgets.QLabel(text)
    self.txt_label.setWordWrap(True)
    overlay.layout().addWidget(self.txt_label)
    # btn = QtWidgets.QPushButton("Hide overlay")
    # btn.clicked.connect(lambda: widget.set_overlay_hidden(True))
    # overlay.layout().addWidget(btn)
    self.set_overlay_widget(overlay)

  @property
  def text(self):
    return self.txt_label.text

  @text.setter
  def text_set(self, value):
    self.txt_label.setText(value)
