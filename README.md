# swaymonad

An auto-tiler for sway that implements Xmonad-like layouts.

It may be compatible with i3 once https://github.com/i3/i3/issues/3808 is
closed, but this is not tested.

Inspired by Bruno Garcia's blog posts
[1](https://aduros.com/blog/hacking-i3-automatic-layout/),
[2](https://aduros.com/blog/hacking-i3-window-promoting/) and
[Swaysome](https://gitlab.com/hyask/swaysome).

## Dependencies

- Python >= 3.9
- [typing_extensions](https://github.com/python/typing/tree/master/typing_extensions) if Python < 3.10
- [i3ipc-python](https://github.com/altdesktop/i3ipc-python)

## Layouts

- NCol

  Maintains n columns, with one column being the master column. When n=2, this
  is equivalent to Xmonad's Tall layout. When n=3, this is equivalent to
  Xmonad's ThreeColumn layout. Higher ns are supported, but don't currently have
  bindings.

  Supports incrementing and decrementing the number of master windows.

- Nop

  Disables auto-tiling for the workspace, allowing managing containers in normal
  Sway fashion.

- Transformations

  These transformations can be applied to layouts and can be combined:

  - ReflectX - reflect the workspace horizontally.
  - ReflectY - reflect the workspace vertically.
  - Transpose - convert each column into a row. Equivalent to XMonad's Mirror.

## Usage

Add something like the following to your sway config file:

```
exec_always "pkill -f 'python3? .+/swaymonad.py';  ~/.config/sway/swaymonad/swaymonad.py"

bindsym $mod+Return nop promote_window

bindsym $mod+j nop focus_next_window
bindsym $mod+k nop focus_prev_window

bindsym $mod+Shift+Left nop move left
bindsym $mod+Shift+Down nop move down
bindsym $mod+Shift+Up nop move up
bindsym $mod+Shift+Right nop move right

bindsym $mod+Shift+j nop swap_with_next_window
bindsym $mod+Shift+k nop swap_with_prev_window

bindsym $mod+x nop reflectx
bindsym $mod+y nop reflecty
bindsym $mod+t nop transpose

bindsym $mod+f nop fullscreen

bindsym $mod+Comma nop increment_masters
bindsym $mod+Period nop decrement_masters

mode "layout" {
  bindsym t nop set_layout tall
  bindsym 3 nop set_layout 3_col
  bindsym n nop set_layout nop

  # Return to default mode
  bindsym Return mode "default"
  bindsym Escape mode "default"
}
bindsym $mod+l mode "layout"

mouse_warping container
focus_wrapping no
```

## Installation

### NixOS

#### NixOS installation with Flakes

Just import flake and use defaultPackage. `swaymonad` binary will be available in PATH

```nix
{
  # ........
  inputs.swaymonad = {
    url = "github:nicolasavru/swaymonad";
    inputs.nixpkgs.follows = "nixpkgs"; # not mandatory but recommended
  };
  # ........

  outputs = { self, nixpkgs, swaymonad }: {
      # ........
      modules = [
        ({ self, ... }: {
          environment.systemPackages = with pkgs; [
            # ........
            swaymonad.defaultPackage.x86_64-linux
            # ........
          ];
        })
      ];
    };
  };
}
```
