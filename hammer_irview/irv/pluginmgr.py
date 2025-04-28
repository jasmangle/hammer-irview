import logging
from importlib import resources

from lefdef import C_LefReader

LOGGER = logging.getLogger(__name__)

class IRVBehavior:

  UI_PATH = resources.path('hammer_irview', 'ui')

  LEF_READER = C_LefReader()

  @staticmethod
  def parse_placement_constraints(model, module, data):
    """
    Parses placement constraints into a hierarchy module object.

    Returns a list of argument tuples for PLACEMENT_CONSTRAINT_TYPES
    that could not be initialized immediately.
    """
    if not module:
      return

    incomplete_constraints = []
    for constraint in data:
      incomplete_constraint = IRVBehavior.retry_placement_constraint(model, module, constraint)
      if incomplete_constraint:
        incomplete_constraints.append(incomplete_constraint)
      # constraint_type = constraint.get('type')
      # if constraint_type not in IRVBehavior.PLACEMENT_CONSTRAINT_TYPES:
      #   LOGGER.warning(f"No placement constraint handler associated with type '{constraint_type}'")
      #   continue

      # constraint_obj = IRVBehavior.PLACEMENT_CONSTRAINT_TYPES[constraint_type](
      #   module, constraint, model)
      # if constraint_obj.path in module.placement_constraints:
      #   # TODO: special handling here for rendering update
      #   pass

      # if constraint_obj.defined:
      #   module.placement_constraints[constraint_obj.path] = constraint_obj
      # else:
      #   incomplete_constraints.append((model, constraint, module))
    return incomplete_constraints
  
  @staticmethod
  def retry_placement_constraint(model, module, constraint):
    """
    Called for a second pass when a hierarchical block hasn't been initialized yet.
    """
    constraint_type = constraint.get('type')
    if constraint_type not in IRVBehavior.PLACEMENT_CONSTRAINT_TYPES:
      LOGGER.warning(f"No placement constraint handler associated with type '{constraint_type}'.")
      return

    constraint_obj = IRVBehavior.PLACEMENT_CONSTRAINT_TYPES[constraint_type](
      module, constraint, model)
    if constraint_obj.defined:
      module.add_placement_constraint(constraint_obj)
      module.placement_constraints[constraint_obj.path] = constraint_obj
    else:
      return ('vlsi.inputs.placement_constraints', model, module, constraint)


  # Dictionary of key/tuple pairs in the following format:
  # key = VLSI Constraint Key
  # tuple[func, func] = First represents initial constraint parsing, second represents subsequent passthrough.
  VLSI_CONSTRAINT_HANDLERS = {
    'vlsi.inputs.placement_constraints': (parse_placement_constraints, retry_placement_constraint)
  }

  PLACEMENT_CONSTRAINT_TYPES = {}

  LEF_LOADERS = {}
