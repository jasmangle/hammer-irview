"""
HAMMER IRView

A graphical intermediate representation viewer for chip floorplanning.

Created by Jasmine Angle - angle@berkeley.edu
"""

import sys
import logging
from irv import IRVApp

import matplotlib

LOGGER = logging.getLogger(__name__)


def invoke_irv(args):
  # Launches Qt event loop
  logging.basicConfig(encoding='utf-8', level=logging.DEBUG,
                      format='\033[93m%(asctime)s - %(levelname)s - %(message)s\033[0m')
  
  matplotlib.use('Agg')
  app = IRVApp(args)
  sys.exit(app.exec())

if __name__ == '__main__':
  invoke_irv(sys.argv)
