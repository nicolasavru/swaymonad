import abc
import collections.abc
import logging
import traceback
from typing import Optional, Protocol

import i3ipc

import common
import transformations


class Layout(abc.ABC):
  i3: i3ipc.Connection
  workspace_id: int
  n_masters: int
  active_transformations: set[transformations.Transformation]

  @abc.abstractmethod
  def layout(self, i3: i3ipc.Connection, event: Optional[i3ipc.Event]) -> None:
    pass

  def __init__(self,
               workspace_id: int,
               n_masters: int = 1,
               transforms: collections.abc.Set[transformations.Transformation] = frozenset()):
    self.workspace_id = workspace_id
    self.n_masters = n_masters
    self.active_transformations = set(transforms)
    self.old_workspace: i3ipc.Con = None

  def __repr__(self) -> str:
    return f"{type(self).__name__}({self.workspace_id}, {self.n_masters})"

  def increment_masters(self) -> int:
    self.n_masters += 1
    logging.debug(f"Incremented n_masters for workspace {self.workspace_id} to {self.n_masters}.")
    return self.n_masters

  def decrement_masters(self) -> int:
    self.n_masters = max(self.n_masters - 1, 1)
    logging.debug(f"Decremented n_masters for workspace {self.workspace_id} to {self.n_masters}.")
    return self.n_masters

  def move(self, i3: i3ipc.Connection, direction: str) -> None:
    focused_window = common.get_focused_window(i3)
    i3.command(f"focus {direction}")
    new_window = common.get_focused_window(i3)
    focused_window.command(f"swap container with con_id {new_window.id}")
    focused_window.command("focus")

  def workspace(self, i3: i3ipc.Connection) -> i3ipc.Con:
    return i3.get_tree().find_by_id(self.workspace_id)

  def transform_command(self, command: str) -> str:
    if transformations.Transformation.TRANSPOSE in self.active_transformations:
      command = transformations.transpose_command_transformation(command)

    if transformations.Transformation.REFLECTX in self.active_transformations:
      command = transformations.reflectx_command_transformation(command)

    if transformations.Transformation.REFLECTY in self.active_transformations:
      command = transformations.reflecty_command_transformation(command)

    return command

  def refetch_container(self, i3: i3ipc.Connection) -> None:
    self.old_workspace = common.refetch_container(i3, self.old_workspace)


class LayoutConstructionProtocol(Protocol):
  def __call__(self,
               workspace_id: int,
               n_masters: int = ...,
               transforms: collections.abc.Set[transformations.Transformation] = ...) -> Layout: ...


LAYOUTS: dict[str, LayoutConstructionProtocol] = {}

WORKSPACE_LAYOUTS: dict[str, Layout] = {}

DEFAULT_LAYOUT = "tall"


def get_layout(workspace: i3ipc.Con) -> Layout:
  if workspace.id not in WORKSPACE_LAYOUTS:
    WORKSPACE_LAYOUTS[workspace.id] = LAYOUTS[DEFAULT_LAYOUT](workspace_id=workspace.id)
    logging.debug(
      f"Workspace {workspace.id} has no layout, setting default {WORKSPACE_LAYOUTS[workspace.id]}.")
  workspace_layout = WORKSPACE_LAYOUTS[workspace.id]
  logging.debug(f"Retreived workspace layout {workspace_layout} for workspace {workspace.id}.")
  return workspace_layout


def set_layout(i3: i3ipc.Connection,
               event: i3ipc.Event,
               layout: str) -> None:
  workspace = common.get_focused_workspace(i3)
  current_layout = get_layout(workspace)
  WORKSPACE_LAYOUTS[workspace.id] = LAYOUTS[layout](
    workspace_id=workspace.id,
    n_masters=current_layout.n_masters,
    transforms=current_layout.active_transformations)
  logging.debug(f"Changing layout of workspace {workspace.id} from {current_layout} to {layout} .")
  i3.command("mode default")

  workspace_layout = get_layout(workspace)
  workspace_layout.layout(i3, event)


def layout_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  try:
    logging.debug(f"Received layout event: {event.ipc_data}")
    workspace = (common.get_workspace_of_event(i3, event) or
                 common.get_focused_workspace(i3))
    if workspace is None:
      logging.debug("Event had no associated workspace and there is no focused workpace. Returning.")
      return

    logging.debug(f"Applying to workspace {workspace.id}.")
    layout = get_layout(workspace)
    i3.enable_command_buffering()
    layout.layout(i3, event)
    i3.disable_command_buffering()
  except Exception as ex:
    traceback.print_exc()


def increment_masters_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  workspace = common.get_focused_workspace(i3)
  if workspace is None:
    logging.debug("Event had no associated workspace and there is no focused workpace. Returning.")
    return

  logging.debug(f"Applying to workspace {workspace.id}.")
  layout = get_layout(workspace)
  layout.increment_masters()
  layout.layout(i3, None)


def decrement_masters_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  workspace = common.get_focused_workspace(i3)
  if workspace is None:
    logging.debug("Event had no associated workspace and there is no focused workpace. Returning.")
    return

  logging.debug(f"Applying to workspace {workspace.id}.")
  layout = get_layout(workspace)
  layout.decrement_masters()
  layout.layout(i3, None)


def move_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event, direction: str) -> None:
  workspace = common.get_focused_workspace(i3)
  if workspace is None:
    logging.debug("Event had no associated workspace and there is no focused workpace. Returning.")
    return

  logging.debug(f"Applying to workspace {workspace.id}.")
  layout = get_layout(workspace)
  layout.move(i3, direction)


def transformation_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event,
                              transformation: transformations.Transformation) -> None:
  workspace = common.get_focused_workspace(i3)
  if workspace is None:
    logging.debug("Event had no associated workspace and there is no focused workpace. Returning.")
    return

  logging.debug(f"Applying to workspace {workspace.id}.")
  layout = get_layout(workspace)
  if transformation in layout.active_transformations:
    logging.debug(f"Removing transformation {transformation} from workspace {workspace.id}.")
    layout.active_transformations.remove(transformation)
  else:
    logging.debug(f"Adding transformation {transformation} to workspace {workspace.id}.")
    layout.active_transformations.add(transformation)
  logging.debug(f"Workspace {workspace.id} now has transformations {layout.active_transformations}.")
  globals()[transformation.value.lower()](i3, event)
  layout.layout(i3, None)


def transpose_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  transformation_dispatcher(i3, event, transformations.Transformation.TRANSPOSE)


def reflectx_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  transformation_dispatcher(i3, event, transformations.Transformation.REFLECTX)


def reflecty_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  transformation_dispatcher(i3, event, transformations.Transformation.REFLECTY)


# def collapse_splits(workspace: i3ipc.Con) -> None:
#   if len(workspace.nodes) == 1 and len(workspace.nodes[0].nodes) == 1:
#     child = workspace.nodes[0].nodes[0]
#     child.command("split none")


def relayout_old_workspace(i3: i3ipc.Connection, new_workspace: i3ipc.Con) -> None:
  old_workspace = common.get_focused_workspace(i3)
  logging.debug(f"Detected container move from workspace {old_workspace.id} to {new_workspace.id}.")

  # Necessary for move left/right between outputs.
  if old_workspace.id == new_workspace.id:
    i3.command("workspace back_and_forth")
    old_workspace = common.get_focused_workspace(i3)
    i3.command("workspace back_and_forth")
    logging.debug(f"Old and new workspaces were identical, actual old workspace is {old_workspace.id}.")

  old_workspace_layout = get_layout(old_workspace)
  old_workspace_layout.layout(i3, None)


def transpose(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  workspace = common.get_focused_workspace(i3)
  layout = get_layout(workspace)
  orig_transformations = layout.active_transformations
  if transformations.Transformation.REFLECTX in orig_transformations:
    reflectx(i3, event)
  if transformations.Transformation.REFLECTY in orig_transformations:
    reflecty(i3, event)

  transformations.transpose_container(i3, common.get_focused_workspace(i3))

  if transformations.Transformation.REFLECTX in orig_transformations:
    reflectx(i3, event)
  if transformations.Transformation.REFLECTY in orig_transformations:
    reflecty(i3, event)


def reflectx(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  transformations.reflect_container(i3, common.get_focused_workspace(i3), {"splith"})


def reflecty(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  transformations.reflect_container(i3, common.get_focused_workspace(i3), {"splitv"})


def fullscreen_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  workspace = common.get_focused_workspace(i3)
  if workspace is None:
    logging.debug("Event had no associated workspace and there is no focused workpace. Returning.")
    return

  logging.debug(f"Applying to workspace {workspace.id}.")
  i3.command("fullscreen")
  layout = get_layout(workspace)
  layout.refetch_container(i3)
