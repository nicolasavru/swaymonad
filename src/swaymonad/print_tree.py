#!/usr/bin/env python3
import i3ipc

import common


i3 = i3ipc.Connection()
print(common.tree_str(common.get_focused_workspace(i3)))
