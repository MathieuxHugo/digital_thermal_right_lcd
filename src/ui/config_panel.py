"""
config_panel.py
===============
Configuration settings panel (update intervals, temperature bounds, USB IDs).
"""

import tkinter as tk
from tkinter import ttk


_FLOAT_KEYS = [
    "update_interval",
    "metrics_update_interval",
    "cycle_duration",
    "gpu_min_temp",
    "gpu_max_temp",
    "cpu_min_temp",
    "cpu_max_temp",
]
_STRING_KEYS = ["product_id", "vendor_id"]
_TEMP_UNIT_KEYS = ["cpu_temperature_unit", "gpu_temperature_unit"]


class ConfigPanel:
    """
    Side panel for editing numeric configuration parameters.

    Parameters
    ----------
    parent:
        Parent widget.
    config:
        The live config dict (mutated in-place on save).
    on_save:
        Callable invoked after writing updated values to ``config``.
    """

    def __init__(self, parent, config: dict, on_save):
        self._config  = config
        self._on_save = on_save
        self._vars: dict[str, tk.Variable] = {}

        frame = ttk.LabelFrame(parent, text="Configuration", padding=(10, 10),
                               style="Dark.TLabelframe")
        frame.grid(row=0, column=1, padx=10, pady=10, sticky="ns")
        self.frame = frame

        row = 0

        # Temperature unit dropdowns
        for key in _TEMP_UNIT_KEYS:
            ttk.Label(frame, text=key.replace("_", " ").capitalize() + ":",
                      style="Dark.TLabel").grid(row=row, column=0, padx=5, pady=8, sticky="w")
            var = tk.StringVar(value=config.get(key, "celsius"))
            ttk.Combobox(frame, textvariable=var, state="readonly",
                         values=["celsius", "fahrenheit"],
                         style="Dark.TCombobox").grid(row=row, column=1, padx=5, pady=8, sticky="ew")
            self._vars[key] = var
            row += 1

        # Float parameters
        for key in _FLOAT_KEYS:
            ttk.Label(frame, text=key.replace("_", " ").capitalize() + ":",
                      style="Dark.TLabel").grid(row=row, column=0, padx=5, pady=8, sticky="w")
            var = tk.DoubleVar(value=config.get(key, 0.0))
            ttk.Entry(frame, textvariable=var,
                      style="Dark.TEntry").grid(row=row, column=1, padx=5, pady=8, sticky="ew")
            self._vars[key] = var
            row += 1

        # String parameters (USB IDs)
        for key in _STRING_KEYS:
            ttk.Label(frame, text=key.replace("_", " ").capitalize() + ":",
                      style="Dark.TLabel").grid(row=row, column=0, padx=5, pady=8, sticky="w")
            var = tk.StringVar(value=str(config.get(key, "")))
            ttk.Entry(frame, textvariable=var,
                      style="Dark.TEntry").grid(row=row, column=1, padx=5, pady=8, sticky="ew")
            self._vars[key] = var
            row += 1

        ttk.Button(frame, text="Save", command=self._save,
                   style="Dark.TButton").grid(row=row, column=0, columnspan=2, pady=16)

        frame.columnconfigure(1, weight=1)

    def _save(self) -> None:
        for key, var in self._vars.items():
            self._config[key] = var.get()
        self._on_save()

    def destroy(self) -> None:
        self.frame.destroy()
