import logging
import sys

from yaml import load, dump

from irv.ui.hierarchical.verilog_module import VerilogModuleHierarchy, VerilogModuleHierarchyScopedModel
from irv.ui.hierarchical.yml_loader import HammerYaml
from irv.ui.widgets.statusbar_mgr import StatusBarLogger
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QFileDialog
from PySide6.QtCore import QFile, QIODevice, QRect, QModelIndex

from pyqtgraph.parametertree import ParameterTree

from irv.ui.widgets.mplcanvas import MplCanvas
from irv.ui.models.hierarchy import DesignHierarchyModel, DesignHierarchyModule

LOGGER = logging.getLogger(__name__)


class MainWindow:
  UI_PATH = 'ui/main.ui'

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
    self.ui.moduleHierarchyTree.setModel(canvas.module.module_model)
    self.ui.moduleHierarchyTree.setSelectionModel(canvas.module.module_model.selection_model)

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
      idx = canvas.module.module_model.indexFromConstraint(constraint)
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
    self.ui.tabs.setCurrentIndex(self.ui.tabs.addTab(canvas, module.name))
    self.ui.moduleHierarchyTree.selectionModel().selectionChanged.connect(self.handleConstraintHierarchyClick)
    self.ui.statusbar.showMessage(f"Module {module.name} loaded.")
    #canvas.render_module(module)

  def load_yamls(self, yamls: list[str]):
    # parse out the stuff
    modules = []
    
    self.ui.statusbar.showMessage(f"Parsing Verilog source files...")
    self.vhierarchy = VerilogModuleHierarchy()
    self.designHierarchyModel = VerilogModuleHierarchyScopedModel(self.vhierarchy)
    self.vhierarchy.register_modules_from_directory('/scratch/angle/ofot-chipyard/vlsi/generated-src/chipyard.harness.TestHarness.MyCoolSoCConfig/gen-collateral',
                                                        self.statusbar_logger)
    

    for path in yamls:
      self.ui.statusbar.showMessage(f"Ready")
      data = {}
      # with open(path, 'r') as f:
      #   data = load(f, Loader=Loader)
      
      # vlsi_hier_inputs = data.get('vlsi.inputs.hierarchical', {})
      # modules = vlsi_hier_inputs.get('manual_modules')
      # toplevel_name = vlsi_hier_inputs.get('top_module')
      # module_insts = []

      yml = HammerYaml(path)
      self.vhierarchy.register_constraints_in_yml(yml, self.statusbar_logger)
      # # Load LEF files into the design hierarchy model
      # self.designHierarchyModel.load_lefs(
      #   data.get('vlsi.technology.extra_libraries', {}))

      # queue = [(modules, None)]
      # while queue:
      #   cur, parent = queue.pop()
      #   module = None

      #   if isinstance(cur, dict):
      #     for name, submodules in cur.items():
      #       module = DesignHierarchyModule(name, parent)
      #       queue.append((submodules, module))
      #   elif isinstance(cur, list):
      #     for el in cur:
      #       queue.append((el, parent))
      #   elif isinstance(cur, str):
      #     module = DesignHierarchyModule(cur, parent)

      #   if module and self.designHierarchyModel.get_module_by_path(module.path):
      #     LOGGER.debug(f"Found duplicate module {module}, skipping...")
      #   elif module:
      #     self.designHierarchyModel.add_module(module, parent)
      #     module_insts.append(module)

      
      # #self.designHierarchyModel.set_toplevel_module(
      # #  self.designHierarchyModel.get_module_by_path(toplevel_name))
      
      # # Load placement constraints
      # vlsi_constraints = vlsi_hier_inputs.get('constraints')
      # self.designHierarchyModel.parse_vlsi_constraints(vlsi_constraints or [])
          
      # Populate the "limited scope" view
      toplevel_name = yml.get_value('vlsi.inputs.top_module')
      if toplevel_name:
        toplevel_module = self.vhierarchy.get_module_by_name(toplevel_name)
        self.vhierarchy.set_top_level_module(toplevel_module)

    self._update_design_hierarchy_model()

