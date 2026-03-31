"""
app.py
======
Main UI application for LED display live configuration.

The ``UIApp`` is designed to be launched from within the controller process
(``python controller.py --ui``) so that it shares the same
:class:`~metrics.Metrics` instance as the display loop, giving the preview
pane live sensor data.  It can also be run standalone (e.g. without hardware)
in which case a :class:`~displayer.NullMetrics` stub is used.

Usage from the controller
-------------------------
::

    controller = Controller(config_path)
    # Controller loop runs in a background daemon thread.
    t = threading.Thread(target=controller.display, daemon=True)
    t.start()

    root = tk.Tk()
    UIApp(root, config_path=controller.config_path, metrics=controller.metrics)
    root.mainloop()
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

import numpy as np
import tkinter as tk
from tkinter import ttk

# Make sure src/ is importable when ui/app.py is the entry point
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import default_config, old_layout_mode
from device_configurations import get_device_config, CONFIG_NAMES
from config_parser import parse_config_from_dict, validate_and_correct_raw_config
from displayer import Displayer, NullMetrics

from .theme import apply_dark_theme
from .device_view import DeviceView
from .config_panel import ConfigPanel
from .color_popup import open_color_popup


class UIApp:
    """
    Tkinter configuration UI.

    Parameters
    ----------
    root:
        Root ``tk.Tk`` window.
    config_path:
        Path to ``config.json`` or its parent directory.  Defaults to the
        ``DIGITAL_LCD_CONFIG`` env var, then the project's ``conf/`` directory.
    metrics:
        Optional live :class:`~metrics.Metrics` instance shared with the
        controller.  When ``None``, :class:`~displayer.NullMetrics` is used
        (preview shows start-colours for metric-driven gradients).
    """

    def __init__(self, root: tk.Tk, config_path: str = None, metrics=None):
        self.root    = root
        self.metrics = metrics or NullMetrics()

        self.config_path = self._resolve_config_path(config_path)
        self.config_dir  = str(Path(self.config_path).parent)

        # Apply dark theme
        self._style = ttk.Style()
        apply_dark_theme(root, self._style)
        root.title("LED Display Configuration")

        self.config = self._load_config()

        # --- Device selector ---
        layout_name = self.config.get("layout_mode", CONFIG_NAMES[0])
        if layout_name in old_layout_mode:
            layout_name = old_layout_mode[layout_name]
        self._layout_mode = tk.StringVar(value=layout_name)

        selector_frame = ttk.LabelFrame(root, text="Device:", padding=(10, 10),
                                        style="Dark.TLabelframe")
        selector_frame.grid(row=0, column=0, pady=10, sticky="w", padx=10)
        dd = ttk.Combobox(selector_frame, textvariable=self._layout_mode,
                          values=CONFIG_NAMES, state="readonly", style="Dark.TCombobox")
        dd.grid(row=0, column=0, padx=5, pady=5)
        dd.bind("<<ComboboxSelected>>", lambda _: self._on_device_change())

        # --- Main content area ---
        self._content = ttk.Frame(root)
        self._content.grid(row=1, column=0, columnspan=3, padx=10, pady=10)

        # --- Reset button ---
        ttk.Button(root, text="Reset to defaults",
                   command=self._reset_config).grid(row=2, column=0, padx=10, pady=10)

        # Build initial layout
        self._build_layout()

        # Start preview thread
        threading.Thread(target=self._preview_loop, daemon=True).start()

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        for w in self._content.winfo_children():
            w.destroy()

        layout_name   = self._layout_mode.get()
        device_config = get_device_config(layout_name, self.config_dir)
        self._device_config = device_config
        self._leds_indexes  = device_config.leds_indexes

        n_leds = device_config.config_dict.get(
            "total_leds",
            len(self._leds_indexes.get("all", []))
        )
        self._leds_ui = np.empty(n_leds, dtype=object)

        # Left column: controls + device preview
        led_frame = ttk.Frame(self._content, padding=(10, 10))
        led_frame.grid(row=0, column=0, padx=10, pady=10)

        # Right column: configuration panel
        ConfigPanel(self._content, self.config, on_save=self._write_config)

        # Display mode selector (row 0 of led_frame)
        ctrl_frame = ttk.Frame(led_frame, padding=(5, 5))
        ctrl_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        mode_names = device_config.get_mode_names()
        self._create_display_mode_selector(ctrl_frame, mode_names)

        # Color mode selector — only when the device config declares multiple palettes
        ui_layout   = device_config.config_dict.get("ui_layout", {})
        color_modes = ui_layout.get("color_modes", ["metrics"])
        self._create_color_mode_selector(ctrl_frame, color_modes)

        # Device view (row 1 of led_frame)
        device_frame = ttk.Frame(led_frame)
        device_frame.grid(row=1, column=0, padx=5, pady=5)
        DeviceView(device_frame, device_config, self._leds_ui,
                   on_led_click=self._on_led_click)

        # Group color controls (row 2 of led_frame)
        self._create_group_controls(led_frame, row=2)

    def _create_display_mode_selector(self, parent, mode_names: list) -> None:
        frame = ttk.LabelFrame(parent, text="Display mode:", padding=(5, 5))
        frame.grid(row=0, column=0, padx=5, pady=5)
        current = self.config.get("display_mode", mode_names[0] if mode_names else "")
        self._display_mode = tk.StringVar(value=current)
        dd = ttk.Combobox(frame, textvariable=self._display_mode,
                          values=mode_names, state="readonly", style="Dark.TCombobox")
        dd.grid(row=0, column=0, padx=5, pady=5)
        dd.bind("<<ComboboxSelected>>", lambda _: self._on_display_mode_change())

    def _create_color_mode_selector(self, parent, color_modes: list) -> None:
        self._color_mode = tk.StringVar(value=color_modes[0])
        if len(color_modes) <= 1:
            return
        frame = ttk.LabelFrame(parent, text="Edit colors for:", padding=(5, 5))
        frame.grid(row=0, column=1, padx=5, pady=5)
        ttk.Combobox(frame, textvariable=self._color_mode,
                     values=color_modes, state="readonly",
                     style="Dark.TCombobox").grid(row=0, column=0, padx=5, pady=5)

    def _create_group_controls(self, parent, row: int) -> None:
        frame = ttk.LabelFrame(parent, text="Group color:", padding=(10, 10),
                               style="Dark.TLabelframe")
        frame.grid(row=row, column=0, columnspan=2, pady=10)

        self._group_var = tk.StringVar(value="")
        dd = ttk.Combobox(frame, textvariable=self._group_var, state="readonly",
                          style="Dark.TCombobox")
        dd["values"] = [k.upper() for k in self._leds_indexes]
        dd.grid(row=0, column=0, padx=5, pady=5)

        ttk.Button(frame, text="Change Group Color",
                   command=self._change_group_color,
                   style="Dark.TButton").grid(row=0, column=1, padx=5, pady=5)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_device_change(self) -> None:
        layout_name   = self._layout_mode.get()
        device_config = get_device_config(layout_name, self.config_dir)
        self.config["layout_mode"] = layout_name

        modes = device_config.get_mode_names()
        if self.config.get("display_mode") not in modes:
            for preferred in ("metrics", "alternate_metrics"):
                if preferred in modes:
                    self.config["display_mode"] = preferred
                    break
            else:
                self.config["display_mode"] = modes[0] if modes else ""

        self._build_layout()
        self._write_config()

    def _on_display_mode_change(self) -> None:
        self.config["display_mode"] = self._display_mode.get()
        self._write_config()

    def _on_led_click(self, group: str, led_index=None) -> None:
        abs_idx = self._abs_index(group, led_index)
        if abs_idx is None:
            return
        initial = self._get_color_spec(abs_idx)
        result  = open_color_popup(self.root, initial)
        if result is not None:
            self._set_color_spec(abs_idx, result)
            self._write_config()

    def _change_group_color(self) -> None:
        group = self._group_var.get().lower()
        if group not in self._leds_indexes:
            return
        abs_idx = self._abs_index(group, None)
        initial = self._get_color_spec(abs_idx) if abs_idx is not None else "ffffff"
        result  = open_color_popup(self.root, initial)
        if result is None:
            return
        indices = self._leds_indexes[group]
        if isinstance(indices, int):
            indices = [indices]
        for idx in indices:
            self._set_color_spec(idx, result)
        self._write_config()

    def _reset_config(self) -> None:
        self.config = default_config.copy()
        self._write_config()
        self._build_layout()

    # ------------------------------------------------------------------
    # Config I/O
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        try:
            with open(self.config_path) as f:
                config = json.load(f)
        except Exception as exc:
            print(f"Warning: could not load config ({exc}); using defaults.")
            config = default_config.copy()

        if validate_and_correct_raw_config(config, self.config_dir):
            self._write_config(config)
        return config

    def _write_config(self, config: dict = None) -> None:
        try:
            with open(self.config_path, "w") as f:
                json.dump(config or self.config, f, indent=4)
        except Exception as exc:
            print(f"Warning: could not write config: {exc}")

    # ------------------------------------------------------------------
    # Color helpers
    # ------------------------------------------------------------------

    def _get_color_spec(self, abs_idx: int) -> str:
        """Return the color spec string for ``abs_idx`` from the active palette."""
        palette = self.config.get(self._color_mode.get(), {})
        colors  = palette.get("colors", [])
        if abs_idx < len(colors):
            return colors[abs_idx]
        return "ffffff"

    def _set_color_spec(self, abs_idx: int, spec: str) -> None:
        """Write a color spec string into the active palette at ``abs_idx``."""
        key    = self._color_mode.get()
        palette = self.config.setdefault(key, {})
        colors  = palette.setdefault("colors", [])
        if abs_idx < len(colors):
            colors[abs_idx] = spec

    def _abs_index(self, group: str, led_index=None):
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

    # ------------------------------------------------------------------
    # Preview loop
    # ------------------------------------------------------------------

    def _preview_loop(self) -> None:
        """
        Background thread that refreshes LED colours in the UI each tick.

        Uses the same :class:`~displayer.Displayer` pipeline as the hardware
        controller.  When a live :class:`~metrics.Metrics` instance was
        injected, the preview shows real sensor values; otherwise it shows the
        start-colours of metric-driven gradients (factor = 0).
        """
        cpt = 0
        while True:
            try:
                cfg = parse_config_from_dict(self.config, self.config_dir)
                displayer = Displayer(cfg, self.metrics)
                effective_colors, nb_displays = displayer.get_state(
                    self._display_mode.get(), cpt
                )
                for i, color in enumerate(effective_colors):
                    self._set_ui_color(i, f"#{color}")

                cycle_ticks = max(1, int(cfg.cycle_duration / cfg.update_interval))
                cpt = (cpt + 1) % (cycle_ticks * nb_displays)
            except Exception as exc:
                print(f"Preview error: {exc}")

            time.sleep(self.config.get("update_interval", 0.1))

    def _set_ui_color(self, index: int, color: str) -> None:
        if index >= len(self._leds_ui):
            return
        widget = self._leds_ui[index]
        if widget is None:
            return
        try:
            if isinstance(widget, (ttk.Label, tk.Label)):
                widget.config(foreground=color)
            else:
                widget.config(background=color)
        except tk.TclError:
            pass  # widget was destroyed between frames

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_config_path(config_path: str | None) -> str:
        if config_path is None:
            env = os.environ.get("DIGITAL_LCD_CONFIG")
            if env:
                config_path = env
            else:
                config_path = str(Path(__file__).parent.parent.parent / "conf")
        if os.path.isdir(config_path):
            config_path = os.path.join(config_path, "config.json")
        return config_path
