import logging
from typing import Optional

value: int = 0


def increment():
  global value
  value += 1
  logging.debug(f"Incremented move_counter to {value}.")


def decrement():
  global value
  value = max(value - 1, 0)
  logging.debug(f"Decremented move_counter to {value}.")
