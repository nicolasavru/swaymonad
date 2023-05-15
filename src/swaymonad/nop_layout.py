from typing import Optional

import i3ipc

import layout


class Nop(layout.Layout):

  def move(self, i3: i3ipc.Connection, direction: str) -> None:
    i3.command(f"move {direction}")

  def layout(self, i3: i3ipc.Connection, event: Optional[i3ipc.Event]) -> None:
    workspace = self.workspace(i3)

    if event and event.change == "move":
      layout.relayout_old_workspace(i3, workspace)

    if focued := workspace.find_focused():
      focued.command("focus")
