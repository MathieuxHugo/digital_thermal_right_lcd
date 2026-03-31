"""
color_popup.py
==============
Color specification picker popup for LED segments.

Supports the full color-spec syntax understood by :class:`~displayer.ColorResolver`:
static hex, animated gradient, metric-driven gradient, time-driven gradient, and random.
"""

import tkinter as tk
from tkinter import ttk, colorchooser


_MODES = ["color", "color gradient", "metrics dependent", "time dependent", "random"]
_METRICS = ["cpu_usage", "cpu_temp", "gpu_usage", "gpu_temp", "nvme_temp", "nvme_usage"]
_TIME_UNITS = ["seconds", "minutes", "hours"]


def open_color_popup(root: tk.Tk, initial_color: str) -> str | None:
    """
    Open a modal popup to edit a color specification string.

    Parameters
    ----------
    root:
        Parent Tk window (used for modality).
    initial_color:
        Current color spec string (e.g. ``"ff0000"``, ``"ff0000-0000ff"``,
        ``"ff0000-0000ff-cpu_temp"``, ``"random"``).

    Returns
    -------
    str or None
        New color spec string, or ``None`` if the user cancelled.
    """
    popup = tk.Toplevel(root)
    popup.title("Choose Color")
    popup.result = None

    # --- Parse initial color ---
    mode_var = tk.StringVar(value="color")
    start_color = "#ffffff"
    end_color = "#ffffff"
    metric = _METRICS[0]
    time_unit = _TIME_UNITS[0]

    if "random" in initial_color.lower():
        mode_var.set("random")
    elif "-" in initial_color:
        parts = initial_color.split("-")
        if len(parts) == 3:
            start_color, end_color, key = f"#{parts[0]}", f"#{parts[1]}", parts[2]
            if key in _METRICS:
                metric = key
                mode_var.set("metrics dependent")
            elif key in _TIME_UNITS:
                time_unit = key
                mode_var.set("time dependent")
            else:
                mode_var.set("color gradient")
        else:
            start_color, end_color = f"#{parts[0]}", f"#{parts[1]}"
            mode_var.set("color gradient")
    else:
        start_color = f"#{initial_color}" if not initial_color.startswith("#") else initial_color

    color1_var = tk.StringVar(value=start_color)
    color2_var = tk.StringVar(value=end_color)
    metric_var = tk.StringVar(value=metric)
    time_unit_var = tk.StringVar(value=time_unit)

    # --- Layout ---
    ttk.Label(popup, text="Mode:", style="Dark.TLabel").grid(row=0, column=0, padx=5, pady=5, sticky="w")
    mode_dd = ttk.Combobox(popup, textvariable=mode_var, values=_MODES, state="readonly", style="Dark.TCombobox")
    mode_dd.grid(row=0, column=1, columnspan=2, padx=5, pady=5)

    color1_label = ttk.Label(popup, text="Color 1:", style="Dark.TLabel")
    color1_entry = ttk.Entry(popup, textvariable=color1_var, style="Dark.TEntry")
    color1_btn   = ttk.Button(popup, text="Pick", style="Dark.TButton",
                               command=lambda: _pick(color1_var))

    color2_label = ttk.Label(popup, text="Color 2:", style="Dark.TLabel")
    color2_entry = ttk.Entry(popup, textvariable=color2_var, style="Dark.TEntry")
    color2_btn   = ttk.Button(popup, text="Pick", style="Dark.TButton",
                               command=lambda: _pick(color2_var))

    metric_label = ttk.Label(popup, text="Metric:", style="Dark.TLabel")
    metric_dd    = ttk.Combobox(popup, textvariable=metric_var, values=_METRICS,
                                 state="readonly", style="Dark.TCombobox")

    time_label   = ttk.Label(popup, text="Time unit:", style="Dark.TLabel")
    time_dd      = ttk.Combobox(popup, textvariable=time_unit_var, values=_TIME_UNITS,
                                 state="readonly", style="Dark.TCombobox")

    for row, (lbl, w1, w2) in enumerate([
        (color1_label, color1_entry, color1_btn),
        (color2_label, color2_entry, color2_btn),
        (metric_label, metric_dd,    None),
        (time_label,   time_dd,      None),
    ], start=1):
        lbl.grid(row=row, column=0, padx=5, pady=5, sticky="w")
        w1.grid(row=row, column=1, padx=5, pady=5)
        if w2:
            w2.grid(row=row, column=2, padx=5, pady=5)

    def _pick(var: tk.StringVar) -> None:
        _, hex_color = colorchooser.askcolor(color=var.get())
        if hex_color:
            var.set(hex_color)

    def _update_visibility(*_):
        mode = mode_var.get()
        show_c1 = mode != "random"
        show_c2 = mode in ("color gradient", "metrics dependent", "time dependent")
        show_metric = mode == "metrics dependent"
        show_time   = mode == "time dependent"

        for w in (color1_label, color1_entry, color1_btn):
            w.grid() if show_c1 else w.grid_remove()
        for w in (color2_label, color2_entry, color2_btn):
            w.grid() if show_c2 else w.grid_remove()
        metric_label.grid() if show_metric else metric_label.grid_remove()
        metric_dd.grid()    if show_metric else metric_dd.grid_remove()
        time_label.grid()   if show_time   else time_label.grid_remove()
        time_dd.grid()      if show_time   else time_dd.grid_remove()

    mode_var.trace_add("write", _update_visibility)
    _update_visibility()

    def _submit():
        c1 = color1_var.get().lstrip("#")
        c2 = color2_var.get().lstrip("#")
        mode = mode_var.get()
        if mode == "color":
            popup.result = c1
        elif mode == "color gradient":
            popup.result = f"{c1}-{c2}"
        elif mode == "metrics dependent":
            popup.result = f"{c1}-{c2}-{metric_var.get()}"
        elif mode == "time dependent":
            popup.result = f"{c1}-{c2}-{time_unit_var.get()}"
        else:
            popup.result = "random"
        popup.destroy()

    ttk.Button(popup, text="OK", command=_submit, style="Dark.TButton").grid(
        row=5, column=0, columnspan=3, pady=10
    )

    popup.transient(root)
    root.update_idletasks()
    popup.grab_set()
    root.wait_window(popup)

    return popup.result
