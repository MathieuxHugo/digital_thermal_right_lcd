"""
led_display_ui.py
=================
Thin entry-point shim — kept for backwards compatibility.

The UI has been refactored into ``src/ui/``.  Use the controller's ``--ui``
flag to launch the UI alongside the display loop (recommended), or run this
file directly for a standalone preview without hardware:

    python src/controller.py --ui          # controller + UI, shared metrics
    python src/led_display_ui.py           # standalone preview (NullMetrics)
    python src/led_display_ui.py conf/     # standalone with custom config path
"""

import sys
import tkinter as tk

from ui.app import UIApp


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    root = tk.Tk()
    UIApp(root, config_path=config_path)
    root.mainloop()
