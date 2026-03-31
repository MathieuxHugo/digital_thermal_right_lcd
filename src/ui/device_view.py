"""
device_view.py
==============
Builds the device LED layout on a grid canvas from the ``ui_layout``
section of the device configuration JSON.  No device-specific Python code
lives here — adding or editing a device only requires a JSON change.

``ui_layout`` format
--------------------
::

    "ui_layout": {
      "grid_width":  N,              // canvas width in grid units
      "grid_height": M,              // canvas height in grid units
      "color_modes": ["metrics"],    // palettes the user can edit (optional)
      "placements": [

        // 7-segment digit display
        {
          "type": "digit",
          "group": "cpu_temp",       // must match a group name in the device config
          "x": 0, "y": 1,           // top-left corner in grid units
          "overflow_leds": 0,        // vertical overflow LEDs prepended left
          "led_offset": 0            // index within the group's LED list where digits start
        },

        // Text label  (maps to one LED or one LED within a group)
        {
          "type": "label",
          "group": "cpu_celsius",
          "text": "°C",
          "led_index": null,         // null → group's first LED; int → group[led_index]
          "x": 6, "y": 1
        },

        // Strip of plain rectangular LED canvases
        {
          "type": "leds",
          "group": "middle_led",
          "orientation": "horizontal",  // "horizontal" | "vertical"
          "led_width":  23,             // canvas size per LED (pixels)
          "led_height":  8,
          "led_indices": null,          // null → all group LEDs; list → subset by index
          "x": 0, "y": 5
        }
      ]
    }

Sizing rules (used when authoring device configs)
-------------------------------------------------
* **digit**  group with ``count`` digits  →  width = count × 2 grid units,
  height = 4 grid units (+ 1 extra width unit when ``overflow_leds > 0``)
* **label**  →  width = len(text) grid units, height = 1 grid unit

These rules guide authoring; they are *not* enforced at runtime.

Validation (enforced at runtime via :func:`validate_ui_layout`)
---------------------------------------------------------------
* No two placements may overlap.
* The union of all placed groups' LED indices must cover every index that
  appears in the device's display modes.
"""

import tkinter as tk
import numpy as np

from .theme import SEGMENT_POSITIONS

# Pixels per grid unit.  A single digit display occupies 2 × 4 grid units
# = (2·UNIT_PX) × (4·UNIT_PX) pixels.
UNIT_PX: int = 25


class DeviceView:
    """
    Renders the device LED layout on a ``tk.Canvas`` using placements from
    the device configuration's ``ui_layout`` section.

    Parameters
    ----------
    parent:
        Frame that will contain the canvas.
    device_config:
        :class:`~device_configurations.DeviceConfig` whose ``config_dict``
        contains a ``ui_layout`` key.
    leds_ui:
        Numpy object array indexed by absolute LED index.  Populated with
        widget references as the canvas is built.
    on_led_click:
        Callback ``(group_name: str, led_index: int | None)`` fired when
        the user clicks an LED widget.
    """

    def __init__(self, parent, device_config, leds_ui: np.ndarray, on_led_click):
        self._dc           = device_config
        self._leds_indexes = device_config.leds_indexes
        self._leds_ui      = leds_ui
        self._on_click     = on_led_click

        ui = device_config.config_dict.get("ui_layout", {})
        gw = ui.get("grid_width",  10)
        gh = ui.get("grid_height",  5)

        self._canvas = tk.Canvas(
            parent,
            width=gw * UNIT_PX,
            height=gh * UNIT_PX,
            bg="black",
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)

        for p in ui.get("placements", []):
            self._place(p)

    # ------------------------------------------------------------------
    # Placement dispatcher
    # ------------------------------------------------------------------

    def _place(self, p: dict) -> None:
        ptype = p.get("type")
        px = p.get("x", 0) * UNIT_PX
        py = p.get("y", 0) * UNIT_PX
        group = p.get("group")

        if ptype == "digit":
            widget = self._digit_widget(p, group)
        elif ptype == "label":
            widget = self._label_widget(p, group)
        elif ptype == "leds":
            widget = self._leds_widget(p, group)
        else:
            return

        if widget is not None:
            self._canvas.create_window(px, py, window=widget, anchor="nw")

    # ------------------------------------------------------------------
    # Digit (7-segment) widget
    # ------------------------------------------------------------------

    def _digit_widget(self, p: dict, group: str) -> tk.Frame:
        overflow  = p.get("overflow_leds", 0)
        offset    = p.get("led_offset", 0)
        count     = self._dc.get_digit_count(group) if group else p.get("count", 3)

        outer = tk.Frame(self._canvas, bg="black")
        col   = 0

        if overflow > 0:
            of = tk.Frame(outer, bg="black")
            of.grid(row=0, column=0, padx=(0, 4))
            for i in range(overflow):
                seg = _seg(of, "Vertical")
                seg.grid(row=i, column=0, pady=2)
                li = i
                seg.bind("<Button-1>", lambda _, g=group, idx=li: self._on_click(g, idx))
                ai = self._abs(group, i)
                if ai is not None:
                    self._leds_ui[ai] = seg
            col = 1

        df = tk.Frame(outer, bg="black")
        df.grid(row=0, column=col)
        self._render_digits(df, group, count, offset)
        return outer

    def _render_digits(self, frame: tk.Frame, group: str, count: int, start: int) -> None:
        idx = start
        for di in range(count):
            digit_f = tk.Frame(frame, bg="black")
            digit_f.grid(row=0, column=di, padx=3)
            for pos in SEGMENT_POSITIONS.values():
                seg = _seg(digit_f, pos["orientation"])
                seg.grid(
                    row=pos["row"], column=pos["col"],
                    padx=pos["padx"], pady=pos["pady"],
                )
                li = idx
                seg.bind("<Button-1>", lambda _, g=group, i=li: self._on_click(g, i))
                ai = self._abs(group, idx)
                if ai is not None:
                    self._leds_ui[ai] = seg
                idx += 1

    # ------------------------------------------------------------------
    # Label widget
    # ------------------------------------------------------------------

    def _label_widget(self, p: dict, group: str) -> tk.Label:
        text      = p.get("text", "?")
        led_index = p.get("led_index")

        lbl = tk.Label(
            self._canvas,
            text=text,
            bg="black", fg="white",
            font=("Arial", 16),
            cursor="hand2",
        )
        lbl.bind("<Button-1>",
                 lambda e, g=group, li=led_index: self._on_click(g, li))

        ai = self._abs(group, led_index)
        if ai is not None:
            self._leds_ui[ai] = lbl
        return lbl

    # ------------------------------------------------------------------
    # LED strip widget
    # ------------------------------------------------------------------

    def _leds_widget(self, p: dict, group: str) -> tk.Frame:
        orient      = p.get("orientation", "horizontal")
        led_w       = p.get("led_width",  UNIT_PX - 2)
        led_h       = p.get("led_height", UNIT_PX - 2)
        led_indices = p.get("led_indices")

        g_leds = self._leds_indexes.get(group, [])
        if isinstance(g_leds, int):
            g_leds = [g_leds]

        pairs = (
            [(i, g_leds[i]) for i in led_indices if i < len(g_leds)]
            if led_indices is not None
            else list(enumerate(g_leds))
        )

        frame = tk.Frame(self._canvas, bg="black")
        for pos, (gi, ai) in enumerate(pairs):
            c = tk.Canvas(frame, width=led_w, height=led_h,
                          highlightthickness=0, bg="black")
            if orient == "horizontal":
                c.grid(row=0, column=pos, padx=2, pady=2)
            else:
                c.grid(row=pos, column=0, padx=2, pady=2)
            gi_ = gi
            c.bind("<Button-1>", lambda _, g=group, i=gi_: self._on_click(g, i))
            self._leds_ui[ai] = c
        return frame

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _abs(self, group: str, led_index=None):
        """Resolve group + optional within-group index → absolute LED index."""
        if group not in self._leds_indexes:
            return None
        g = self._leds_indexes[group]
        if isinstance(g, int):
            return g
        if not g:
            return None
        if led_index is None:
            return g[0]
        if led_index < len(g):
            return g[led_index]
        return None


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def _seg(parent: tk.Frame, orientation: str) -> tk.Canvas:
    """Create a single segment canvas."""
    if orientation == "Vertical":
        return tk.Canvas(parent, width=5, height=20, highlightthickness=0, bg="black")
    return tk.Canvas(parent, width=20, height=5, highlightthickness=0, bg="black")
