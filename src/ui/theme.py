"""
theme.py
========
Dark theme setup for the LED Display UI.
"""

from tkinter import ttk


# 7-segment display position map: segment_name -> grid placement and orientation.
# Layout:
#    top
# TL   TR
#   mid
# BL   BR
#   bot
SEGMENT_POSITIONS = {
    "top_left":    {"row": 1, "col": 0, "padx": 2, "pady": 0, "orientation": "Vertical"},
    "top":         {"row": 0, "col": 1, "pady": 2, "padx": 0, "orientation": "Horizontal"},
    "top_right":   {"row": 1, "col": 2, "padx": 2, "pady": 0, "orientation": "Vertical"},
    "middle":      {"row": 2, "col": 1, "pady": 2, "padx": 0, "orientation": "Horizontal"},
    "bottom_left": {"row": 3, "col": 0, "padx": 2, "pady": 0, "orientation": "Vertical"},
    "bottom":      {"row": 4, "col": 1, "pady": 2, "padx": 0, "orientation": "Horizontal"},
    "bottom_right":{"row": 3, "col": 2, "padx": 2, "pady": 0, "orientation": "Vertical"},
}


def apply_dark_theme(root, style: ttk.Style) -> None:
    """Apply dark theme to a Tk root window and its ttk Style."""
    root.configure(bg="black")
    root.option_add("*foreground", "white")
    root.option_add("*background", "black")

    try:
        style.theme_use("clam")
    except Exception:
        try:
            style.theme_use("default")
        except Exception:
            pass

    for cls in ("TLabel", "TFrame", "TButton", "TEntry", "TCombobox", "TLabelframe"):
        try:
            style.configure(cls, background="black", foreground="white")
        except Exception:
            pass

    try:
        style.configure("Dark.TLabel", background="black", foreground="white")
        style.configure("Dark.TFrame", background="black")
        style.configure("Dark.TLabelframe", background="black", foreground="white")
        style.configure("Dark.TLabelframe.Label", background="black", foreground="white")
        style.configure("TLabelframe.Label", background="black", foreground="white")
        style.configure("Dark.TButton", background="black", foreground="white")
        style.configure(
            "Dark.TCombobox",
            fieldbackground="black", background="black", foreground="white",
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", "black"), ("!disabled", "black")],
            foreground=[("readonly", "white"), ("!disabled", "white")],
        )
        style.configure("Dark.TEntry", fieldbackground="black", background="black", foreground="white")
        style.map("Dark.TEntry", fieldbackground=[("!disabled", "black")])
    except Exception:
        pass
