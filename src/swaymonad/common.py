import enum
import logging
import math
from typing import Optional

import i3ipc

import move_counter


def get_workspaces(i3: i3ipc.Connection) -> list[i3ipc.Con]:
  return [i3.get_tree().find_by_id(reply.ipc_data["id"]).workspace()
          for reply in i3.get_workspaces()]


def get_focused_workspace(i3: i3ipc.Connection) -> i3ipc.Con:
  for reply in i3.get_workspaces():
    if reply.focused:
      return i3.get_tree().find_by_id(reply.ipc_data["id"]).workspace()
  raise Exception("No workspaces were focused. This should never happen")


def get_focused_window(i3: i3ipc.Connection) -> i3ipc.Con:
  # Should never return None because we start with the focused workspace.
  return get_focused_workspace(i3).find_focused()


def get_window_of_event(i3: i3ipc.Connection, event: i3ipc.Event) -> Optional[i3ipc.Con]:
  return i3.get_tree().find_by_id(event.container.id)


def get_workspace_of_window(window: Optional[i3ipc.Con]) -> Optional[i3ipc.Con]:
  return window.workspace() if window is not None else None


def get_workspace_of_event(i3: i3ipc.Connection, event: i3ipc.Event) -> Optional[i3ipc.Con]:
  return get_workspace_of_window(get_window_of_event(i3, event))


def refetch_container(i3: i3ipc.Connection, container: i3ipc.Con) -> i3ipc.Con:
  return i3.get_tree().find_by_id(container.id)


def tree_str(container: i3ipc.Con, indent: str = "") -> str:
  out = f"{indent} {container.id} {container.layout}\n"
  for node in container.nodes:
    out += tree_str(node, indent + "  ")
  return out


def move_container(con1: i3ipc.Con, con2: i3ipc.Con) -> None:
  move_counter.increment()
  con2.command("mark __swaymonad__mark");
  con1.command("move window to mark __swaymonad__mark")
  con2.command("unmark __swaymonad__mark");


def reverse_nodes(i3: i3ipc.Connection, container: i3ipc.Con, starting_idx: int = 0) -> None:
  logging.debug(f"Reversing nodes in container {container.id} from index {starting_idx} onward.")
  for i, node in enumerate(container.nodes[starting_idx:math.ceil(len(container.nodes)/2)]):
    target_node_id = container.nodes[-i-1].id
    logging.debug(f"Swapping node {i} (container id {node.id}) with "
                  f"node {len(container.nodes) - i - 1} (container id {target_node_id})")
    if node.id != target_node_id:
      node.command(f"swap container with con_id {target_node_id}")


def insert_node_at_index(i3: i3ipc.Connection,
                         container: i3ipc.Con,
                         node: i3ipc.Con,
                         index: int) -> None:
  logging.debug(f"Inserting node {node.id} into container {container.id} at index {index}.")
  move_container(node, container)
  # We haven't refreshed our view of container, so it still only contains the
  # old nodes and does not include the new node at the end.
  for old_node in container.nodes[::-1]:
    node.command(f"swap container with con_id {old_node.id}")


def add_node_to_front(i3: i3ipc.Connection, container: i3ipc.Con, node: i3ipc.Con) -> None:
  insert_node_at_index(i3, container, node, 0)


def ensure_split(container: i3ipc.Con, split: str) -> list[i3ipc.replies.CommandReply]:
  if container.layout != split:
    return container.command(split)
  else:
    return []


def is_floating(container: i3ipc.Con) -> bool:
  # TODO: replace first clause with container.is_floating() when the next
  # version of i3ipc-python is released.
  return container.floating in ['user_on', 'auto_on'] or container.type == "floating_con"


# https://docs.python.org/3/library/enum.html#using-automatic-values
class AutoName(enum.Enum):
  value: str
  # https://github.com/python/mypy/issues/7591
  @staticmethod
  def _generate_next_value_(name: str, start: int, count: int, last_values: list[str]) -> str:
    return name
