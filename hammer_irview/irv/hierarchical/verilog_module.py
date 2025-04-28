"""
Contains all Verilog-adjacent information modeling classes.
"""
from collections import OrderedDict, defaultdict
from decimal import Decimal
import logging
from pathlib import Path
import re
import typing

from PySide6 import QtCore, QtWidgets, QtGui

from hammer.hammer.tech.stackup import Metal, RoutingDirection, Stackup
from hammer.hammer.vlsi.driver import HammerDriver
from hammer_irview.irv.hierarchical.lef import IRVMacro, MacroLibrary
from hammer_irview.irv.hierarchical.placement_constraints import IRVAlignCheck, ModuleConstraint, ModuleHierarchical, ModuleTopLevel, PlacementConstraintManager
from hammer_irview.irv.models.verilog_module import VerilogModuleConstraintsModel

LOGGER = logging.getLogger(__name__)


class TechMetalLayer:

  def __init__(self, metal: Metal):
    self.metal = metal
    self.dir = metal.direction
    self.name = metal.name
  
  def check_alignment(self, x: Decimal, y: Decimal, width: Decimal, height: Decimal):
    x = Decimal(str(x))
    y = Decimal(str(y))
    width = Decimal(str(width))
    height = Decimal(str(height))
    bb_xmax = x + width
    bb_ymax = y + height
    if self.dir == RoutingDirection.Horizontal:
      return x % self.metal.grid_unit == 0.0 and bb_xmax % self.metal.grid_unit == 0.0
    elif self.dir == RoutingDirection.Vertical:
      return y % self.metal.grid_unit == 0.0 and bb_ymax % self.metal.grid_unit == 0.0

  @staticmethod
  def create_from_stackups(stackups: list[Stackup]):
    layers = {}
    for stackup in stackups:
      for metal in stackup.metals:
        layers[metal.name] = TechMetalLayer(metal)
    return layers
  
  def __str__(self):
    return self.name


class VerilogModule:
  """
  Module to hold a grouping of Verilog instance relationships for a particular
  module. This should be referenced by a VerilogModuleInstance, which contains
  the actual instantiation of this module.
  """

  def __init__(self, name: str, file: Path):
    self.name = name
    self.file = file
    self.instances = {}

    self.top_constraint = None
    self.children = []

    self.constraints = OrderedDict()
    self.constraints_list = []
    self.constraints_indices = {}

    self.view_model = VerilogModuleConstraintsModel(self)

  def add_constraint(self, constraint: ModuleConstraint):
    constraint.module = self
    self.constraints[constraint.path] = constraint
    self.constraints_indices[constraint] = len(self.constraints_list)
    self.constraints_list.append(constraint)
    if isinstance(constraint, ModuleTopLevel):
      self.top_constraint = constraint
    if isinstance(constraint, ModuleHierarchical):
      self.children.append(constraint)

  def __str__(self):
    return f'<{self.name} from {self.file}>'
  
  def __repr__(self):
    return f'<{self.name} from {self.file}>'


class VerilogModuleInstance:
  """
  Contains details regarding a specific VerilogModule instance.
  """

  def __init__(self, name: str, module: VerilogModule):
    self.name = name
    self.module = module


class VerilogModuleHierarchy:
  """
  
  """

  RE_MODULE_DEFINITION = r'module\s+(\w+)\s*(#\s*\([^)]*\)\s*)?\s*\([^)]*\)\s*;([\s\S]*?)endmodule'
  """
  Pattern to find a Verilog module definition within a file.
  """

  RE_MODULE_INSTANTIATION = r'(\w+)\s+(\w+)\s*\('
  """
  Pattern to find Verilog module instantiations within a module's body.
  """

  RE_BLOCK_COMMENT = r'/\*.*?\*/'
  """
  Pattern to find a Verilog block comment.
  """

  RE_LINE_COMMENT = r'//.*'
  """
  Pattern to find a Verilog single-line comment.
  """


  def __init__(self):

    # Modules of the form: {name: VerilogModule, ...}
    self.driver = None
    self.modules = OrderedDict()
    self.macro_library = MacroLibrary()
    self.scoped_hierarchy = OrderedDict()
    self.top_level = None
    self.unknown_macros = defaultdict(set)

  def iter_files_in_path(self, directory: Path):
    """
    Generator for retriving all .SV files recursively from a particular
    directory.

    Args:
        directory (Path): Path to search within.
    """
    for p in directory.glob('**/*.[sv][v]'):
      yield p

  def strip_comments(self, content: str):
    """
    Removes all comments (block or single-line) from a Verilog file.

    Args:
        file_content (str): Content of a Verilog file.
    """
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    content = re.sub(r'//.*', '', content)
    return content
  
  def set_top_level_module(self, module):
    self.top_level = module
    ## TODO: Ideally, signal that the view needs to change from the root.

  def parse_verilog_file(self, file: Path) -> list[tuple[VerilogModule, str]]:
    """
    Parses all modules from a Verilog file.

    Args:
        file (Path): Path to the Verilog file to parse.

    Returns:
        list[tuple[VerilogModule, str]]: List of tuples containing
          (VerilogModule object, module body)
    """
    verilog_modules = []
    with open(file, 'r') as verilog_file:
      content = verilog_file.read()

      # Remove comments
      content = self.strip_comments(content)

      # Find all module definitions
      modules = re.findall(self.RE_MODULE_DEFINITION, content, re.MULTILINE)

      # `modules` is a list of tuples with the following information:
      # - [0]: Module Name; [2]: Module Body
      for module_data in modules:
        module_name, _, module_body = module_data
        module = VerilogModule(module_name, file)
        verilog_modules.append((module, module_body))
        LOGGER.debug(f"Found module '{module}'")
    return verilog_modules

  def parse_module_instances(self, module: tuple[VerilogModule, str]):
    """
    Gets all instances for a specific Verilog module and assign them to the
    respective VerilogModule, logging those that haven't been loaded (i.e.,
    LEFs)

    Args:
        module (tuple[VerilogModule, str]): Module+body tuple to parse.
    """
    vmodule, module_body = module
    insts = re.findall(self.RE_MODULE_INSTANTIATION, module_body)

    for instance in insts:
      inst_module_name, inst_name = instance
      inst_obj = vmodule.instances.get(inst_name)
      
      if not inst_obj:
        inst_obj = VerilogModuleInstance(inst_name, inst_module_name)
        vmodule.instances[inst_name] = inst_obj

      if isinstance(inst_obj.module, VerilogModule):
        # Was resolved before, should update to make sure nothing changed.
        inst_obj.module = self.modules.get(
          inst_obj.module.name, inst_obj.module.name)
      elif isinstance(inst_obj.module, IRVMacro):
        continue
      elif isinstance(inst_obj.module, str):
        # Not resolved yet, attempt to resolve.
        inst_obj.module = self.macro_library.get_macro(inst_obj.module) \
          or self.modules.get(inst_obj.module, inst_obj.module)
        
        # Remove from unknown macros (if it exists)
        if inst_obj in self.unknown_macros[inst_name]:
          self.unknown_macros[inst_name].remove(inst_obj)

      if isinstance(inst_obj.module, str):
        # If after the earlier steps it is still unresolved, log for later.
        self.unknown_macros[inst_name].add(inst_obj)

    # full_instance_path = '/'.join([parent_path, inst_name]) if parent_path else inst_name

  def register_irv_settings(self, driver: HammerDriver):
    """
    Registers all IRV-namespaced settings relevant to verilog module parsing.
    This also pulls in 

    Args:
        driver (HammerDriver): Associated Hammer driver
    """
    pass
    #driver.database.get_config('irv.')

  def register_modules_from_driver(self, driver: HammerDriver,
                                      statusbar: QtWidgets.QStatusBar | None):
    """
    Registers all .sv files as IRView VerilogModule objects for the current
    VerilogModuleHierarchy based on `synthesis.inputs.input_files`.

    Args:
        driver (HammerDriver): Associated Hammer driver
        statusbar (QStatusBar): Status bar to update with progress.
    """
    self.driver = driver
    modules_found = []

    files = driver.project_config.get('synthesis.inputs.input_files', [])
    num_files = len(files)

    # Parse modules as a flat structure
    for i, vfile in enumerate(files):
      vfile = Path(vfile)
      statusbar.showMessage(f"Parsing synthesis module {i+1} of {num_files}: {vfile}")
      # Update our registry with the found verilog files.
      modules = self.parse_verilog_file(vfile)
      for module in modules:
        vmodule_obj, module_body = module
        self.modules[vmodule_obj.name] = vmodule_obj
        modules_found.append(module)

    # All modules loaded from all files. Parse instance hierarchy
    for module_tpl in modules_found:
      vmodule_obj, module_body = module_tpl
      statusbar.showMessage(f"Reading instances for module '{vmodule_obj.name}'")
      self.parse_module_instances(module_tpl)

  def register_modules_from_directory(self, directory: Path,
                                      statusbar: QtWidgets.QStatusBar | None):
    """
    Registers all .sv files as IRView VerilogModule objects for the current
    VerilogModuleHierarchy.

    Args:
        directory (Path): Path to .sv files.
        statusbar (QStatusBar): Status bar to update with progress.
    """
    directory = Path(directory)
    modules_found = []

    # Parse modules as a flat structure
    for vfile in self.iter_files_in_path(directory):
      statusbar.showMessage(f"Parsing '{vfile}'")
      # Update our registry with the found verilog files.
      modules = self.parse_verilog_file(vfile)
      for module in modules:
        vmodule_obj, module_body = module
        self.modules[vmodule_obj.name] = vmodule_obj
        modules_found.append(module)


    # All modules loaded from all files. Parse instance hierarchy
    for module_tpl in modules_found:
      vmodule_obj, module_body = module_tpl
      statusbar.showMessage(f"Reading instances for module '{vmodule_obj.name}'")
      self.parse_module_instances(module_tpl)


  def register_hammer_extra_libraries(self, driver: HammerDriver, statusbar):
    libs = driver.project_config.get('vlsi.technology.extra_libraries', [])
    num_libs = len(libs)
    for i, lib in enumerate(libs):
      lib = lib.get('library', {})
      lef_path = lib.get('lef_file', None)
      if lef_path:
        lef_path = Path(driver.obj_dir, lef_path)
        statusbar.showMessage(f'Loading extra library {i+1} of {num_libs}: {lef_path}')
        self.macro_library.add_by_path(lef_path)

  def register_hammer_tech_libraries(self, driver: HammerDriver, statusbar):
    num_libs = len(driver.tech.tech_defined_libraries)
    for i, lib in enumerate(driver.tech.tech_defined_libraries):
      statusbar.showMessage(f'Lazily loading technology library {i+1} of {num_libs}: {lib.name}')
      if lib.lef_file:
        self.macro_library.add_lazy_by_path(lib.name, lib.lef_file)
  
  def register_constraints_in_driver(self, driver: HammerDriver, statusbar: QtWidgets.QStatusBar | None):
    """
    Registers all constraints from a provided HAMMER YML file.

    Args:
        driver (HammerDriver): Hammer driver.
    """

    statusbar.showMessage(f'Converting stackup metal definitions for technology "{driver.tech.name}"')
    self.layers = TechMetalLayer.create_from_stackups(driver.tech.config.stackups)

    
    constraints = driver.project_config.get('vlsi.inputs.placement_constraints', [])
    num_constraints = len(constraints)
    for i, constraint in enumerate(constraints):
      statusbar.showMessage(f'Deserializing placement constraint {i+1} of {num_constraints}')
      constraint_obj = PlacementConstraintManager.deserialize(constraint, self)
      constraint_obj.module.add_constraint(constraint_obj)
    # if 

    # if constraint_obj.module.add_constr


  def get_module_by_name(self, name: str) -> typing.Union[VerilogModule, None]:
    """
    Retrieves a VerilogModule object from its name.

    Args:
        name (str): Name of the module to retrieve

    Returns:
        Union[VerilogModule, None]: The associated VerilogModule, or None if it
            doesn't exist.
    """
    return self.modules.get(name)
  
  def get_module_by_path(self, path):
    segments = path.split('/')
    current = self.get_module_by_name(segments[0])
    for segment in segments[1:]:
      if isinstance(current, VerilogModule):
        inst = current.instances.get(segment)
        if isinstance(inst, VerilogModuleInstance):
          current = inst.module
        else:
          current = inst
      elif isinstance(current, IRVMacro) or isinstance(current, str):
        return current
      else:
        return None
    return current

