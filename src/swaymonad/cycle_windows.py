import logging
from typing import Any, Optional

import i3ipc

import common


def find_offset_window(current_container: i3ipc.Con,
                       offset: int) -> Optional[i3ipc.Con]:
  logging.debug(f"Finding window at offset {offset} relative to container {current_container.id}.")
  leaves = current_container.workspace().leaves()
  leaf_ids = [leaf.id for leaf in leaves]
  logging.debug(f"Container's workspace has leaves {leaf_ids}.")

  try:
    current_leaf_index = leaf_ids.index(current_container.id)
  except ValueError:
    # The current container is floating.
    return None

  return leaves[(current_leaf_index + offset) % len(leaves)]


def find_next_window(current_container: i3ipc.Con) -> Optional[i3ipc.Con]:
  return find_offset_window(current_container, 1)


def find_prev_window(current_container: i3ipc.Con) -> Optional[i3ipc.Con]:
  return find_offset_window(current_container, -1)


def focus_window(i3: i3ipc.Connection,
                 offset: int,
                 window: Optional[i3ipc.Con] = None) -> None:
  focused_window = window or common.get_focused_window(i3)
  if not focused_window:
    return

  if new_window := find_offset_window(focused_window, offset):
    new_window.command("focus")
    if focused_window.fullscreen_mode == 1:
      new_window.command("fullscreen")


def focus_next_window(i3: i3ipc.Connection,
                      event: Any,
                      window: Optional[i3ipc.Con] = None) -> None:
  del event
  focus_window(i3, 1, window)


def focus_prev_window(i3: i3ipc.Connection,
                      event: Any,
                      window: Optional[i3ipc.Con] = None) -> None:
  del event
  focus_window(i3, -1, window)


def refocus_window(i3: i3ipc.Connection, window: i3ipc.Con) -> None:
  # window.command("focus") can leave the cursor on the border of a window,
  # while this will move the cursor to the center of the window.
  focus_next_window(i3, None, window)
  window.command("focus")
  if window.fullscreen_mode == 1:
    window.command("fullscreen")


def swap_with_window(i3: i3ipc.Connection,
                     offset: int,
                     window: Optional[i3ipc.Con] = None,
                     focus_after_swap: bool = True) -> None:
  focused_window = window or common.get_focused_window(i3)
  if not focused_window:
    return

  if new_window := find_offset_window(focused_window, offset):
    focused_window.command(f"swap container with con_id {new_window.id}")
    if focus_after_swap:
      focused_window.command("focus")
      if focused_window.fullscreen_mode == 1:
        new_window.command("fullscreen")


def swap_with_next_window(i3: i3ipc.Connection,
                          event: i3ipc.Event,
                          window: Optional[i3ipc.Con] = None,
                          focus_after_swap: bool = True) -> None:
  del event
  swap_with_window(i3, 1, window, focus_after_swap)


def swap_with_prev_window(i3: i3ipc.Connection,
                          event: i3ipc.Event,
                          window: Optional[i3ipc.Con] = None,
                          focus_after_swap: bool = True) -> None:
  del event
  swap_with_window(i3, -1, window, focus_after_swap)
