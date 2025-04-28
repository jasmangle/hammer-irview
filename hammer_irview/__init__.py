"""
HAMMER IRView

A graphical intermediate representation viewer for chip floorplanning.

Created by Jasmine Angle - angle@berkeley.edu
"""

import sys
import logging
from hammer_irview.irv import IRVApp

import matplotlib

from hammer.vlsi import HammerDriver

LOGGER = logging.getLogger(__name__)


def invoke_irv(args):
  # Launches Qt event loop
  logging.basicConfig(encoding='utf-8', level=logging.INFO,
                      format="[{pathname:>20s}:{lineno:<4}]  {levelname:<7s}   {message}", style='{')
  
  matplotlib.use('Agg')
  app = IRVApp(args)
  sys.exit(app.exec())

def invoke_irv_hammer(driver: HammerDriver, errors):
  # Launches everything from a Hammer context.
  #logging.basicConfig(encoding='utf-8', level=logging.INFO,
  #                    format="[{pathname:>20s}:{lineno:<4}]  {levelname:<7s}   {message}", style='{')
  
  matplotlib.use('Agg')
  app = IRVApp(driver)
  sys.exit(app.exec())


class IRViewDriverMixin:

  def run_main_parsed(self, args):
    print(args)
    action = str(args['action'])
    if action == 'irv':
      driver, errors = self.args_to_driver(args)
      invoke_irv_hammer(driver, errors)

    return super().run_main_parsed(args)

if __name__ == '__main__':
  invoke_irv(sys.argv)
