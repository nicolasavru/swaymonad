#!/usr/bin/env python3
import argparse
import functools
import logging
import sys
import traceback
import time
from typing import Callable
try:
  from typing import Concatenate, ParamSpec
except ImportError:
  from typing_extensions import Concatenate, ParamSpec

import i3ipc

import swaymonad.common as common
import swaymonad.cycle_windows as cycle_windows
import swaymonad.layout as layout
import swaymonad.n_col as n_col
import swaymonad.nop_layout as nop_layout
import swaymonad.promote_window as promote_window
import swaymonad.transformations as transformations

argparser = argparse.ArgumentParser(description='An xmonad-like auto-tiler for sway.')
argparser.add_argument('--default-layout', default="tall",
                       help="Layout to use for workspaces where the layout has not been manually set."
                       "Valid options are 'tall', '3_col', and 'nop'.")
argparser.add_argument('--verbose', "-v", action="count", help="Enable debug logging.")
argparser.add_argument('--log-file', help="Log file path, defaults to stderr.")
argparser.add_argument('--delay', default=0.0, type=float,
                       help=("Sleep for n seconds before sending every command to sway, "
                             "allowing a human to observe intermediate state,"))
args = argparser.parse_args()


P = ParamSpec("P")
Command = Callable[Concatenate[i3ipc.Connection, i3ipc.Event, P], None]


COMMANDS: dict[str, Command] = {
  "promote_window": promote_window.promote_window,
  "reflectx": layout.reflectx_dispatcher,
  "reflecty": layout.reflecty_dispatcher,
  "transpose": layout.transpose_dispatcher,
  "focus_next_window": cycle_windows.focus_next_window,
  "focus_prev_window": cycle_windows.focus_prev_window,
  "swap_with_next_window": cycle_windows.swap_with_next_window,
  "swap_with_prev_window": cycle_windows.swap_with_prev_window,
  "set_layout": layout.set_layout,
  "increment_masters": layout.increment_masters_dispatcher,
  "decrement_masters": layout.decrement_masters_dispatcher,
  "move": layout.move_dispatcher,
  "fullscreen": layout.fullscreen_dispatcher,
}


def parse_command(event: i3ipc.Event) -> list[str]:
  logging.debug(f"Parsing command: {event.binding.command}")
  split_command = event.binding.command.split()
  return ([]
          if not split_command or split_command[0] != 'nop'
          else split_command[1:])


def command_dispatcher(i3: i3ipc.Connection, event: i3ipc.Event):
  logging.debug(f"Receved command event: {event.ipc_data}")

  command = parse_command(event)
  logging.debug(f"Parsed command: {command}")
  if not command:
    return

  try:
    i3.enable_command_buffering()
    COMMANDS.get(command[0], lambda i3, event, *args: None)(i3, event, *command[1:])
    i3.disable_command_buffering()
  except Exception as ex:
    traceback.print_exc()


layout.LAYOUTS.update({
  "tall": functools.partial(n_col.NCol, n_columns=2),
  "3_col": functools.partial(n_col.NCol, n_columns=3),
  "nop": nop_layout.Nop,
})


class Connection(i3ipc.Connection):

  def __init__(self, *args, **kwargs) -> None:
    super().__init__(*args, **kwargs)
    self.buffering_commands = False
    self.command_buffer: list[str] = []

  def command(self, payload: str) -> list[i3ipc.CommandReply]:
    if self.buffering_commands:
      logging.debug(f"Buffering command: {payload}", stacklevel=2)
      self.command_buffer.append(payload)
      return []

    logging.debug(f"Executing command: {payload}", stacklevel=2)
    time.sleep(args.delay)
    return super().command(payload)

  def enable_command_buffering(self) -> None:
    self.buffering_commands = True

  def disable_command_buffering(self) -> list[i3ipc.CommandReply]:
    self.buffering_commands = False

    if not self.command_buffer:
      return []

    command = ";".join(self.command_buffer)
    self.command_buffer = []
    return self.command(command)

  def get_tree(self) -> i3ipc.Con:
    # TODO: handle returned errors
    self.disable_command_buffering()
    tree = super().get_tree()
    self.enable_command_buffering()
    return tree

  def get_workspaces(self) -> list[i3ipc.replies.WorkspaceReply]:
    # TODO: handle returned errors
    self.disable_command_buffering()
    workspaces = super().get_workspaces()
    self.enable_command_buffering()
    return workspaces

def main():
  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                      filename=args.log_file,
                      format='%(asctime)s, %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s')

  layout.DEFAULT_LAYOUT = args.default_layout

  i3 = Connection()

  i3.on(i3ipc.Event.BINDING, command_dispatcher)

  i3.on(i3ipc.Event.WINDOW_NEW, layout.layout_dispatcher)
  i3.on(i3ipc.Event.WINDOW_CLOSE, layout.layout_dispatcher)
  i3.on(i3ipc.Event.WINDOW_MOVE, layout.layout_dispatcher)

  i3.main()

if __name__ == "__main__":
  main()
