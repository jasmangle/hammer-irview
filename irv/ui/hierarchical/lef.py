import logging
from pathlib import Path

from lefdef import C_LefReader, _lef

LOGGER = logging.getLogger(__name__)


class IRVMacro:

  def __init__(self, lef_macro: _lef.C_Lef_Macro):
    self.macro = lef_macro
    self.geometry_by_layer: dict[str, _lef.C_Lef_Rect] = {}

    for rect_idx in range(self.macro.c_obs.c_num_rects):
      rect = self.macro.c_obs.c_rects[rect_idx]
      self.geometry_by_layer[rect.c_layer] = rect

  def get_rect_for_layer(self, layer_name: str) -> _lef.C_Lef_Rect | None:
    return self.geometry_by_layer.get(layer_name)


class MacroLibrary:

  def __init__(self):
    """
    Initializes a new Macro library for holding LEF file data.

    This technically *can* work with DEF files too...
    """
    self.macros: dict[_lef.C_lefMacro | Path] = {}
    self._reader = C_LefReader()

  def add_lazy_by_path(self, name, path: Path):
    self.macros[name] = path

  def add_by_path(self, path: Path):
    """
    Adds a new LEF file based on its file path, reading in the contents and
    analyzing its parameters.

    Args:
        path (Path): Path to the LEF file to read.
    """
    path = Path(path)
    lef = self._reader.read(str(path.resolve()))

    ## IT IS REALLY EASY TO SEGFAULT HERE WHEN USING CADENCE LEFDEF ##
    ## MAKE SURE TO CHECK LENGTHS OF ARRAYS!!! ##

    # If the LEF file contains multiple macros, register each.
    for macro_idx in range(lef.c_num_macros):
      macro = lef.c_macros[macro_idx]
      self.macros[macro.c_name.decode()] = IRVMacro(macro)

    # Macros can technically render the pins as well, but not for MVP (plz).

    pass

  def get_macro(self, name: str) -> IRVMacro | None:
    inst = self.macros.get(name)
    if isinstance(inst, Path):
      self.add_by_path(inst)
    return self.macros.get(name)
