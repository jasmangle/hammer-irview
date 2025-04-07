import logging
import sys

from yaml import load, dump

from hammer.hammer.vlsi.driver import HammerDriver
from irview.irv.ui.hierarchical.verilog_module import VerilogModuleHierarchy, VerilogModuleHierarchyScopedModel
from irview.irv.ui.hierarchical.yml_loader import HammerYaml
from irview.irv.ui.widgets.loading_modal import LoadingDialog
from irview.irv.ui.widgets.overlay import LoadingWidget
from irview.irv.ui.widgets.statusbar_mgr import StatusBarLogger
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QFileDialog
from PySide6.QtCore import QFile, QIODevice, QRect, QModelIndex

from pyqtgraph.parametertree import ParameterTree

from irview.irv.ui.widgets.mplcanvas import MplCanvas
from irview.irv.ui.models.hierarchy import DesignHierarchyModel, DesignHierarchyModule

LOGGER = logging.getLogger(__name__)


class MainWindow:
  UI_PATH = 'irview/ui/main.ui'

  def _load_ui(self, path, parent):
    # Initialize uic for included UI file path
    ui_file = QFile(path)
    if not ui_file.open(QIODevice.ReadOnly):
        LOGGER.error(f"UIC: Cannot open UI file at '{path}': {ui_file.errorString()}")
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
    self.ui.dockProperties.setWidget(self.paramtree)

    # Loading modal
    self.loader_modal = LoadingWidget('Please wait...', self.ui)

    # Event handling
    self.ui.resizeEvent = self.handleResize
    self.ui.designHierarchyTree.doubleClicked.connect(self.handleDesignHierarchyDoubleClick)
    self.ui.actionOpenSram.triggered.connect(self.handleActionLoadSramCompiler)
    self.ui.actionRenderHierarchical.triggered.connect(self.handleActionRenderHierarchical)
    self.ui.tabs.currentChanged.connect(self.handleChangeTab)

    #self.designHierarchyModel = DesignHierarchyModel()
    #self._update_design_hierarchy_model()

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
    self.ui.actionRenderHierarchical.checked = canvas.render_hierarchy
    canvas.render_module()
    self.select_artist(canvas, canvas.selected)
    self.ui.moduleHierarchyTree.setModel(canvas.module.view_model)
    self.ui.moduleHierarchyTree.setSelectionModel(canvas.module.view_model.selection_model)

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
      canvas.selected = constraint
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
        return
      
    # Open new tab
    canvas = MplCanvas(None, module)
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

    self.ui.statusbar.showMessage(f'Loading HAMMER libraries...')

    self.vhierarchy.register_hammer_tech_libraries(driver, self.ui.statusbar)
    self.vhierarchy.register_hammer_extra_libraries(driver, self.ui.statusbar)
    # parsed_yamls = []
    # module_dirs = []
    # for path in yamls:
    #   parsed_yaml = HammerYaml(path)
    #   parsed_yamls.append(parsed_yaml)
      
    #   #parsed_yaml.get_value('irview.')
    print(self.vhierarchy.macro_library.macros)

    
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

