from typing import Optional

import i3ipc

import common


def find_biggest_window(container: i3ipc.Con) -> Optional[i3ipc.Con]:
  return max(container.leaves(),
             key=lambda leaf: leaf.rect.width * leaf.rect.height,
             default=None)


def promote_window(i3: i3ipc.Connection, event: i3ipc.Event) -> None:
  del event
  workspace = common.get_focused_workspace(i3)
  focused_window = common.get_focused_window(i3)
  master = find_biggest_window(workspace)
  if not master:
    return
  focused_window.command(f"swap container with con_id {master.id}")
  focused_window.command("focus")
  if focused_window.fullscreen_mode == 1:
    focused_window.command("fullscreen")
