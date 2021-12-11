import collections.abc
import enum

import i3ipc

import common


class Transformation(common.AutoName):
  REFLECTX = enum.auto()
  REFLECTY = enum.auto()
  TRANSPOSE = enum.auto()


def reflect_container(
    i3: i3ipc.Connection,
    container: i3ipc.Con,
    split_filter: collections.abc.Set[str] = frozenset({"splith", "splitv"})) -> None:
  if container.layout in split_filter:
    common.reverse_nodes(i3, container)

  for node in container.nodes:
    reflect_container(i3, node, split_filter)


def reflectx_direction(direction: str) -> str:
  if direction == "right":
    return "left"
  elif direction == "left":
    return "right"
  elif direction in ("up", "down"):
    return direction
  else:
    raise ValueError(f"Invalid direction: {direction!r}")


def reflectx_command_transformation(command: str) -> str:
  if (split_command := command.split())[0] == "move":
    return f"move {reflectx_direction(split_command[1])}"
  else:
    return command


def reflecty_direction(direction: str) -> str:
  if direction == "up":
    return "down"
  elif direction == "down":
    return "up"
  elif direction in ("left", "right"):
    return direction
  else:
    raise ValueError(f"Invalid direction: {direction!r}")


def reflecty_command_transformation(command: str) -> str:
  if (split_command := command.split())[0] == "move":
    return f"move {reflecty_direction(split_command[1])}"
  else:
    return command


def transpose_container(i3: i3ipc.Connection, container: i3ipc.Con) -> None:
  focused_container = common.get_focused_window(i3)
  if container.type == "workspace" and container.nodes:
    container.nodes[0].command("layout toggle split")
    # These moves only change container splits and don't actually move any
    # windows, so they don't trigger move events and we don't need to increment
    # the move counter.
    if container.layout == "splith":
      container.nodes[0].command("move up")
    elif container.layout == "splitv":
      container.nodes[0].command("move left")

    common.reverse_nodes(i3, container, starting_idx=1)

  elif container.nodes:
    container.nodes[0].command("layout toggle split")

  for node in container.nodes:
    transpose_container(i3, node)

  focused_container.command("focus")


def transpose_direction(direction: str) -> str:
  if direction == "right":
    return "down"
  elif direction == "down":
    return "left"
  elif direction == "left":
    return "up"
  elif direction == "up":
    return "right"
  else:
    raise ValueError(f"Invalid direction: {direction!r}")


def transpose_split(split: str) -> str:
  if split == "splitv":
    return "splith"
  elif split == "split v":
    return "split h"
  elif split == "split vertical":
    return "split horizontal"
  elif split == "splith":
    return "splitv"
  elif split == "split h":
    return "split v"
  elif split == "split horizontal":
    return "split vertical"
  else:
    return split


def transpose_command_transformation(command: str) -> str:
  split_command = command.split()
  if split_command[0] == "move":
    return f"move {transpose_direction(split_command[1])}"
  elif split_command[0].startswith("split"):
    return transpose_split(command)
  else:
    return command
