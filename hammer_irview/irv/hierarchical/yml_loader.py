"""
Convenience class for handling YML parsing.
"""
from collections import OrderedDict
import os
import logging
from pathlib import Path
import re
from typing import *

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

LOGGER = logging.getLogger(__name__)



class HammerYaml:

  def __init__(self, path: Path):
    self.yml_file = Path(path)

    if not self.yml_file.is_file():
      LOGGER.warning(f'YML file path "{self.yml_file}" does not exist.')
      return
    
    data = {}
    with open(self.yml_file, 'r') as f:
      data = load(f, Loader=Loader)
    self.flatten_data(data)

  def set_value(self, key: str, value: Any):
    """
    Sets a value for a provided dot-delimited key.

    Args:
        key (str): Dot-delimited key (i.e., `vlsi.inputs`)
        value (Any): Value to assign for the specified key.
    """
    key_parts = key.split('.')

    current_dict = self.data
    for part_idx, part in enumerate(key_parts):
      if part_idx < len(key_parts) - 1:
        if part not in current_dict:
          current_dict[part] = {}
        current_dict = current_dict[part]
      else:
        current_dict[part] = value

  def get_value(self, key):
    """
    Gets a value from a provided dot-delimited key.

    Args:
        key (str): Dot-delimited key (i.e., `vlsi.inputs`)
    """
    key_parts = key.split('.')

    current_dict = self.data
    for part_idx, part in enumerate(key_parts):
      if part_idx < len(key_parts) - 1:
        if part not in current_dict:
          current_dict[part] = {}
        current_dict = current_dict[part]
      else:
        return current_dict.get(part)


  def flatten_data(self, data: Union[dict, list]):
    """
    Normalizes an imported YAML file into a nested dot-delimited dict object
    format.

    Args:
        data (Union[dict, list]): Deserialized root YAML data
    """
    self.data = {}

    queue = [(data, '')]
    while queue:
      cur, parent_key = queue.pop()

      if isinstance(cur, dict):
        for name, value in cur.items():
          path_str = f'{parent_key}.{name}' if parent_key else name
          queue.append((value, path_str))
      else:
        self.set_value(parent_key, cur)

