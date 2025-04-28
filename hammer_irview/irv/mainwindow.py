import logging
import sys
from importlib import resources

from hammer.hammer.vlsi.driver import HammerDriver
from hammer_irview.irv.hierarchical.verilog_module import VerilogModuleHierarchy
from hammer_irview.irv.models.verilog_module import VerilogModuleHierarchyScopedModel
from hammer_irview.irv.widgets.overlay import LoadingWidget
from hammer_irview.irv.widgets.statusbar_mgr import StatusBarLogger
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QFileDialog, QHeaderView
from PySide6.QtCore import QFile, QFileInfo, QIODevice, QModelIndex

from pyqtgraph.parametertree import ParameterTree

from hammer_irview.irv.widgets.mplcanvas import MplCanvas
from hammer_irview.irv.pluginmgr import IRVBehavior

LOGGER = logging.getLogger(__name__)


class MainWindow:
  UI_PATH = IRVBehavior.UI_PATH / 'main.ui'

  def _load_ui(self, path, parent):
    # Initialize uic for included UI file path
    ui_file = QFile(path)
    if not ui_file.open(QIODevice.ReadOnly):
        file_info = QFileInfo(ui_file)
        LOGGER.error(f"UIC: Cannot open UI file at '{path}' ({file_info.absoluteFilePath()}): {ui_file.errorString()}")
        sys.exit(-1)
    loader = QUiLoader()
    self.ui = loader.load(ui_file, parent)
    ui_file.close()
    if not self.ui:
        LOGGER.error(f"UIC: No window loaded from '{path}': {loader.errorString()}")
        sys.exit(-1)

    self.statusbar_logger = StatusBarLogger(self.ui.statusbar)

    # Initialize ParameterTree
    # size_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
    self.paramtree = ParameterTree(None, True)
    self.paramtree.header().setSectionResizeMode(QHeaderView.Interactive)
    self.ui.dockProperties.setWidget(self.paramtree)

    # Loading modal
    self.loader_modal = LoadingWidget('Please wait...', self.ui)

    # Event handling
    self.ui.resizeEvent = self.handleResize
    self.ui.designHierarchyTree.doubleClicked.connect(self.handleDesignHierarchyDoubleClick)
    self.ui.actionOpenSram.triggered.connect(self.handleActionLoadSramCompiler)
    self.ui.actionViewZoomToFit.triggered.connect(self.action_zoom_to_fit)
    self.ui.actionRenderHierarchical.triggered.connect(self.handleActionRenderHierarchical)
    self.ui.tabs.currentChanged.connect(self.handleChangeTab)
    self.ui.tabs.tabCloseRequested.connect(self.handleCloseTab)

    #self.designHierarchyModel = DesignHierarchyModel()
    #self._update_design_hierarchy_model()

  def action_zoom_to_fit(self):
    print('zoom to fit init called')
    self.ui.tabs.currentWidget().zoom_to_fit()

  def _update_design_hierarchy_model(self):
    self.ui.designHierarchyTree.setModel(self.designHierarchyModel)

  def __init__(self, parent=None):
    self._load_ui(self.UI_PATH, parent)
    self.ui.show()

  def handleResize(self):
    self.ui.tabs.currentWidget().draw()

  def handleDesignHierarchyDoubleClick(self, item: QModelIndex):
    module = item.internalPointer()
    if module:
      self.open_module(module)

  def handleChangeTab(self):
    canvas = self.ui.tabs.currentWidget()

    view_model = None
    if canvas:
      view_model = canvas.module.view_model
      canvas.render_module()
      self.select_artist(canvas, canvas.selected)
      self.ui.actionRenderHierarchical.checked = canvas.render_hierarchy
      self.ui.moduleHierarchyTree.setSelectionModel(view_model.selection_model)

    self.ui.moduleHierarchyTree.setModel(view_model)

  def handleCloseTab(self, index):
    self.ui.tabs.removeTab(index)


  def handleActionRenderHierarchical(self):
    canvas = self.ui.tabs.currentWidget()
    if canvas:
      canvas.render_hierarchy = self.ui.actionRenderHierarchical.isChecked()
      canvas.render_module()

  def handleActionLoadSramCompiler(self):
    # First load seq_mems.json, then load sram_generator-output.json
    self.dialog = QFileDialog(self.ui)

    self.dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    self.dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
    self.dialog.setWindowTitle('Open mems.conf...')
    self.dialog.open()

    if not self.dialog.selectedFiles:
      return
    
    # Have mems.conf, can get mapping of module -> sram characteristics
    path_conf = self.dialog.selectedFiles()
    with open(path_conf, 'r') as conf:
      for line in conf:
        line = line.strip()
        line_elems = ' '.split(line)
        # Example: name cc_dir_ext depth ## width ## ports ### mask_gran ##

  def handleMplZoom(self, event):
    event.canvas.handle_resize()

  def handleMplClick(self, event):
    artist = event.artist
    if artist and event.mouseevent.button == 1:
      constraint = event.canvas.artist_to_constraint[artist]
      print(constraint)
      self.select_artist(event.canvas, constraint)

  def handleConstraintHierarchyClick(self, item: QModelIndex):
    indexes = item.indexes()
    if indexes:
      constraint = indexes[0].internalPointer()
      self.select_artist(self.ui.tabs.currentWidget(), constraint)

  def select_artist(self, canvas, constraint):
    if constraint:
      canvas.select_constraint(constraint)
      idx = canvas.module.view_model.get_constraint_index(constraint)
      constraint.populate_params(self.paramtree)
      self.ui.moduleHierarchyTree.setCurrentIndex(idx)

  def mouse_hover_statusbar_update(self, event):
    if event.xdata and event.ydata:
      self.ui.statusbar.showMessage(f"Cursor Pos: ({round(event.xdata, 4)}, {round(event.ydata, 4)})")
    else:
      self.ui.statusbar.clearMessage()

  def open_module(self, module):
    self.ui.statusbar.showMessage(f"Rendering module {module.name}...")
    # Check if tab isn't already open. If it is, change tab context.
    for tab_idx in range(self.ui.tabs.count()):
      if self.ui.tabs.widget(tab_idx).module == module:
        self.ui.tabs.setCurrentIndex(tab_idx)
        self.ui.statusbar.showMessage(f"Changed editor context to {module.name}.")
        return
      
    # Open new tab
    canvas = MplCanvas(None, module)
    canvas.zoom_to_fit()
    canvas.mpl_connect('motion_notify_event', self.mouse_hover_statusbar_update)
    canvas.mpl_connect('pick_event', self.handleMplClick)
    canvas.mpl_connect('resize_event', self.handleMplZoom)
    self.ui.tabs.setCurrentIndex(self.ui.tabs.addTab(canvas, module.name))
    self.ui.moduleHierarchyTree.selectionModel().selectionChanged.connect(self.handleConstraintHierarchyClick)
    self.ui.statusbar.showMessage(f"Module {module.name} loaded.")
    #canvas.render_module(module)

  def load_hammer_data(self, driver: HammerDriver):
    # parse out the stuff
    self.loader_modal.show()
    self.vhierarchy = VerilogModuleHierarchy()
    self.vhierarchy.register_irv_settings(driver)

    self.ui.statusbar.showMessage(f'Loading HAMMER libraries...')

    self.vhierarchy.register_hammer_tech_libraries(driver, self.ui.statusbar)
    self.vhierarchy.register_hammer_extra_libraries(driver, self.ui.statusbar)

    self.ui.statusbar.showMessage(f"Parsing Verilog hierarchy...")
    self.designHierarchyModel = VerilogModuleHierarchyScopedModel(self.vhierarchy)
    self.vhierarchy.register_modules_from_driver(driver, self.statusbar_logger)
    self.vhierarchy.register_constraints_in_driver(driver, self.statusbar_logger)

    toplevel_name = driver.project_config.get('vlsi.inputs.top_module')
    if toplevel_name:
      toplevel_module = self.vhierarchy.get_module_by_name(toplevel_name)
      self.vhierarchy.set_top_level_module(toplevel_module)

    self._update_design_hierarchy_model()
    self.loader_modal.hide()

    self.ui.statusbar.showMessage(f'Ready.')

