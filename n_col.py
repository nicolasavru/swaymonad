import math
import logging
import sys
import time
import traceback
from typing import Callable, Optional

import i3ipc

import common
import cycle_windows
import layout
import move_counter
import transformations


def balance_cols(i3: i3ipc.Connection,
                 col1: i3ipc.Con, col1_expected: int,
                 col2: i3ipc.Con) -> bool:
  logging.debug(f"Balancing columns of container {col1.id} and {col2.id}. "
               f"Column 1 has {len(col1.nodes)} nodes (expected {col1_expected}) "
               f"and column 2 has {len(col2.nodes)}")
  caused_mutation = False

  if len(col1.nodes) < col1_expected and col2.nodes:
    logging.debug(f"Moving container {col2.nodes[0].id} left.")
    common.move_container(col2.nodes[0], col1)
    col1.nodes.append(col2.nodes.pop(0))
    caused_mutation = True

  elif len(col1.nodes) > col1_expected and len(col1.nodes) > 1:
    logging.debug(f"Moving container {col1.nodes[-1].id} right.")
    common.add_node_to_front(i3, col2, col1.nodes[-1])
    col2.nodes.insert(0, col1.nodes.pop(-1))
    caused_mutation = True

  return caused_mutation


class NCol(layout.Layout):

  def __init__(self, n_columns: int, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.n_columns = n_columns

  def __repr__(self) -> str:
    return f"{type(self).__name__}({self.workspace_id}, {self.n_columns}, {self.n_masters})"

  def reflow(self, i3: i3ipc.Connection, workspace: i3ipc.Con) -> bool:
    if len(workspace.leaves()) == 1:
      return False

    for node in workspace.nodes:
      common.ensure_split(node, self.transform_command("splitv"))

    workspace = common.refetch_container(i3, workspace)

    leaves = workspace.leaves()
    masters = leaves[:self.n_masters]
    slaves = leaves[self.n_masters:]

    n_slaves = len(slaves)
    slaves_per_col = math.ceil(n_slaves / (self.n_columns - 1))
    logging.debug(f"Reflowing {len(leaves)} leaves into {self.n_masters} masters "
                  f"and {n_slaves} slaves with {slaves_per_col} slaves per column.")

    nodes = workspace.nodes[
      ::(-1 if
         ((transformations.Transformation.REFLECTX in self.active_transformations and
           workspace.layout == "splith") or
          (transformations.Transformation.REFLECTY in self.active_transformations and
           workspace.layout == "splitv"))
         else 1)
    ]

    caused_mutation = False

    for i, cur_col in enumerate(nodes):
      logging.debug(f"Examining column {i} (container {cur_col.id}), which has {len(cur_col.nodes)} nodes.")
      if i == len(nodes) - 1 and i > 0:  # last pane
        # If the cur or prev column is the master, don't move anything into it here.
        if i > 1:
          prev_col = nodes[i-1]
          caused_mutation |= balance_cols(i3, prev_col, slaves_per_col, cur_col)

        if len(cur_col.nodes) > 1:
          if len(nodes) < self.n_columns:
            logging.debug(f"Found {len(nodes)} columns, but expected {self.n_columns}; "
                          f"moving container {cur_col.nodes[-1]} right.")
            move_counter.increment()
            # Move changes focus to the container being moved, so refocused what
            # we focued before the move.
            focused = workspace.find_focused()
            cur_col.nodes[-1].command(self.transform_command("move right"))
            if focused:
              focused.command("focus")
            caused_mutation = True
            workspace = common.refetch_container(i3, workspace)

          elif len(nodes) > self.n_columns:
            logging.debug(f"Found {len(nodes)} columns, but expected {self.n_columns}; "
                          f"moving container {cur_col.nodes[0].id} left.")
            move_counter.increment()
            focused = workspace.find_focused()
            cur_col.nodes[0].command(self.transform_command("move left"))
            if focused:
              focused.command("focus")
            caused_mutation = True
            workspace = common.refetch_container(i3, workspace)

      elif i == 0:  # master pane
        if len(cur_col.nodes) > self.n_masters and len(nodes) == 1:
          logging.debug(f"Found a single column with {len(cur_col.nodes)} containers (the master pane), "
                        f"but expected {self.n_masters} containers; "
                        f"moving container {cur_col.nodes[-1].id} right.")
          move_counter.increment()
          focused = workspace.find_focused()
          cur_col.nodes[0].command(self.transform_command("move left"))
          if focused:
            focused.command("focus")
          caused_mutation = True
          workspace = common.refetch_container(i3, workspace)

        if len(nodes) > 1:
          next_col = nodes[i+1]
          caused_mutation |= balance_cols(i3, cur_col, self.n_masters, next_col)

      else:
        next_col = nodes[i+1]
        caused_mutation |= balance_cols(i3, cur_col, slaves_per_col, next_col)

    return caused_mutation

  def layout(self, i3: i3ipc.Connection, event: Optional[i3ipc.Event]) -> None:
    workspace = self.workspace(i3)
    if not self.old_workspace:
      self.old_workspace = workspace

    if not workspace:  # the workspace no longer exists
      logging.debug(f"Workspace no longer exists, not running layout.")
      return
    logging.debug(f"Running layout for workspace {workspace.id}.")

    should_reflow = event is None
    post_hooks: list[Callable[[], None]] = []

    # Have new windows displace the current window instead of being opened below them.
    if event and event.change == "new":
      # Dialog windows are created as normal windows and then made to float
      # (https://github.com/swaywm/sway/commit/c9be0145576433e71f8b7732f7ff5ddee0d36076),
      # so by the time we get there, recheck if we actually have a new leaf.
      # Yes, this is a race, and it may be necessary to add a sleep here, but
      # this seems to work fine now and sway really should win the race (as we
      # want it to) as that's all happening internally in C, not after IPC
      # back-and-forth in Python.
      workspace = common.refetch_container(i3, workspace)
      old_leaf_ids = {leaf.id for leaf in self.old_workspace.leaves()}
      leaf_ids = {leaf.id for leaf in workspace.leaves()}
      if old_leaf_ids != leaf_ids:
        cycle_windows.swap_with_prev_window(
          i3, event, window=workspace.find_by_id(event.container.id))
        should_reflow = True

      # Similarly, fullscreen windows are created as normal windows and them
      # changed to be fullscreen.
      if (con := workspace.find_by_id(event.container.id)) and con.fullscreen_mode == 1:
        logging.debug(f"New container {con.id} was fullscreen. Setting to fullscreen again.")
        post_hooks.append(lambda: con.command("focus"))
        post_hooks.append(lambda: con.command("fullscreen"))

    elif event and event.change == "close":
      # Focus the "next" window instead of the last-focused window in the other
      # column. Unless the window is floating, in which case let sway focus the
      # last focused window in the workspace.
      old_leaf_ids = {leaf.id for leaf in self.old_workspace.leaves()}
      leaf_ids = {leaf.id for leaf in workspace.leaves()}

      if (old_leaf_ids != leaf_ids and
          workspace.id == common.get_focused_workspace(i3).id and
          (closed_container := self.old_workspace.find_by_id(event.container.id)) and
          not common.is_floating(closed_container)):
        should_reflow = True

        logging.debug(f"Looking at container {closed_container.id}: {closed_container.__dict__}")
        window_was_fullscreen = closed_container.fullscreen_mode == 1
        next_window = closed_container
        for _ in range(len(old_leaf_ids)):
          next_window = cycle_windows.find_next_window(next_window)
          if next_window and next_window.id in leaf_ids:
            next_window.command("focus")
            if window_was_fullscreen:
              logging.debug(f"Closed container {closed_container.id} was fullscreen. "
                            "Setting next container to fullscreen.")
              post_hooks.append(lambda: next_window.command("fullscreen"))
            break

    elif event and event.change == "move":
      if move_counter.value:
        logging.debug(f"Move counter was non-zero ({move_counter.value}), ignoring move event.")
        move_counter.decrement()
        return
      else:
        should_reflow = True

        # split commands bring focus to the workspace of the window they are run
        # on, and they may be run as part of the reflow layer, so refocus the
        # current workspace at the end.
        focused_workspace = common.get_focused_workspace(i3)
        post_hooks.append(lambda: i3.command(f"workspace {focused_workspace.name}"))

        window_of_event = workspace.find_by_id(event.container.id)
        cycle_windows.swap_with_prev_window(
          i3, event, window=window_of_event, focus_after_swap=False)
        layout.relayout_old_workspace(i3, workspace)

    ever_reflowed = should_reflow
    while should_reflow:
      workspace = common.refetch_container(i3, workspace)
      should_reflow = self.reflow(i3, workspace)

    # Move the mouse nicely to the middle of the focused window instead of it
    # continuing to sit in its old position or on a window boundary.
    if (ever_reflowed and
        workspace.id == common.get_focused_workspace(i3).id and
        (focused := workspace.find_focused())):
      logging.debug(f"Refocusing container {focused.id}.")
      cycle_windows.refocus_window(i3, focused)

    for hook in post_hooks:
      hook()

    self.old_workspace = common.refetch_container(i3, workspace)
    #logging.debug(f"Storing workspace:\n{common.tree_str(self.old_workspace)}")
