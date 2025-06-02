import tkinter as tk
from tkinter import ttk, colorchooser
import json
import sys
from config import leds_indexes, NUMBER_OF_LEDS, display_modes
import numpy as np
import threading
import time
from utils import interpolate_color, get_random_color
segmented_digit_layout = {# Position segments in a 7-segment layout
    "top_left":
        {"row":1, "column":0, "padx":2, "pady":0, "orientation": "Vertical"},
    "top":
        {"row":0, "column":1, "pady":2, "padx":0,  "orientation": "Horizontal"},
    "top_right":
        {"row":1, "column":2, "padx":2, "pady":0, "orientation": "Vertical"},
    "middle":
        {"row":2, "column":1, "pady":2, "padx":0, "orientation": "Horizontal"},
    "bottom_left":
        {"row":3, "column":0, "padx":2, "pady":0, "orientation": "Vertical"},
    "bottom":
        {"row":4, "column":1, "pady":2, "padx":0, "orientation": "Horizontal"},
    "bottom_right":
        {"row":3, "column":2, "padx":2, "pady":0, "orientation": "Vertical"},
}

class LEDDisplayUI:
    def __init__(self, root, config_path="config.json"):
        self.root = root
        self.config_path = config_path
        self.config = self.load_config()
        self.root.title("LED Display Layout")
        self.style = ttk.Style()

        self.leds_ui = [None] * NUMBER_OF_LEDS

        color_frame = ttk.Frame(root, padding=(10, 10))
        color_frame.grid(row=0, column=0, padx=10, pady=10)
        self.create_config_panel(root)

        display_frame = ttk.Frame(color_frame, padding=(10, 10))
        display_frame.grid(row=0, column=0, padx=10, pady=10)
        self.create_color_mode(display_frame)
        self.create_display_mode(display_frame)
        # Create frames for CPU and GPU
        self.cpu_frame = self.create_device_frame(color_frame, "cpu", 1)
        self.gpu_frame = self.create_device_frame(color_frame, "gpu", 2)

        # Add controls for group selection and color change
        self.create_controls(color_frame)
        self.update_interval = self.config["update_interval"]
        self.cycle_duration = self.config["cycle_duration"]
        self.start_time = time.time()
        threading.Thread(target=self.update_ui_loop, daemon=True).start()

    def update_ui_loop(self):
        while True:
            current_time = time.time()
            elapsed_time = (current_time - self.start_time)%(self.cycle_duration*2)
            colors = np.array(self.config[self.color_mode.get()]["colors"])
            for index in range(NUMBER_OF_LEDS):
                color = colors[index]
                if color.lower() == "random":
                    color = get_random_color()
                elif "-" in color:
                    split_color = color.split("-")
                    if len(split_color) == 3:
                        start_color, end_color, metric = split_color
                        factor=elapsed_time/(self.cycle_duration*2)
                    else:
                        start_color, end_color = split_color
                        factor=abs(elapsed_time-self.cycle_duration)/(self.cycle_duration)
                    color = interpolate_color(start_color=start_color, end_color=end_color, factor=factor)
                self.set_ui_color(index, color="#"+color)
            time.sleep(self.update_interval)

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
        
    def get_index(self, led_key, index=None):
        if index is None or isinstance(leds_indexes[led_key],int):
            return leds_indexes[led_key]
        else:
            return leds_indexes[led_key][index]

    def get_color(self, led_key, index=None):
        return f"#{np.array(self.config[self.color_mode.get()]["colors"])[self.get_index(led_key, index)]}"
    
    def set_color(self, led_index, color):
        if self.config:
            self.config[self.color_mode.get()]["colors"][led_index] = color
        else:
            print("Config not loaded. Cannot set color.")

    def write_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error writing config: {e}")

    def set_ui_color(self, index, color):
        if isinstance(self.leds_ui[index],(ttk.Label)):
            self.leds_ui[index].config(foreground=color)
        else:
            self.leds_ui[index].config(background=color)

    def create_device_frame(self, root, device_name, row):
        frame = ttk.LabelFrame(root, text=device_name.upper(), padding=(10, 10))
        frame.grid(row=row, column=0, padx=10, pady=10)

        device_led_frame = ttk.Frame(frame)
        device_led_frame.grid(row=0, column=0, padx=0, pady=0)
        self.create_label(device_led_frame, device_name+"_led", device_name.upper()[0], 0, 0, index=int(device_name=="cpu"))
        self.create_label(device_led_frame, device_name+"_led", device_name.upper()[1:], 0, 1, index=int(device_name!="cpu"))

        temp_frame = ttk.LabelFrame(frame, text=device_name.upper()+" temp", padding=(10, 10))
        temp_frame.grid(row=1, column=0, padx=10, pady=10)

        # Add temperature unit selection
        unit_frame = ttk.Frame(frame)
        unit_frame.grid(row=1, column=1, padx=5, pady=5)
        
        # Create clickable labels for °C and °F
        self.create_label(unit_frame, device_name+"_celsius", "°C", 0, 0)
        self.create_label(unit_frame, device_name+"_fahrenheit", "°F", 1, 0)

        usage_frame = ttk.LabelFrame(frame, text=device_name.upper()+" usage", padding=(10, 10))
        usage_frame.grid(row=1, column=2, padx=10, pady=10)

        # Create LED layout for CPU and GPU
        self.create_segmented_digit_layout(temp_frame, device_name+"_temp")
        self.create_usage_frame(usage_frame, device_name+"_usage")

        
        self.create_label(frame, device_name+"_percent_led", "%", 1, 3)
        return frame
    

    def create_label(self, parent_frame, led_key, text, row, column, index=None):
        unit_style = {"font": ("Arial", 20), "cursor": "hand2"}
        label = ttk.Label(parent_frame, text=text, **unit_style)
        label.grid(row=row, column=column, padx=0, pady=5)
        label.config(foreground=self.get_color(led_key,index).split("-")[0])
        label.bind(
            "<Button-1>",
            lambda event,
            led_key=led_key, led_index=index: self.change_led_color(
                led_key, index=led_index
            ),
        )
        if index is not None:
            self.leds_ui[leds_indexes[led_key][index]] = label
        else:
            self.leds_ui[leds_indexes[led_key]] = label

    def create_usage_frame(self, frame, label):
        index = 0
        one_frame = ttk.Frame(frame, padding=(5, 5))
        one_frame.grid(row=1, column=0, padx=5, pady=5)
        for one_index in range(2,0,-1):
            self.create_segment(
                one_frame,
                label,
                led_index=index,
                row=one_index,
                column=0,
                pady=4,
            )
            index+=1
        
        digit_frame = ttk.Frame(frame, padding=(5, 5))
        digit_frame.grid(row=1, column=1, padx=0, pady=0)
        self.create_segmented_digit_layout(digit_frame, label, number_of_digits=2, index=index)


    def create_segment(self, parent_frame, label, led_index, row, column, orientation="Vertical", pady=0, padx=0):
        if orientation == "Vertical":
            segment = tk.Canvas(
                parent_frame,
                width=5,
                height=20,
                highlightthickness=0,
            )
        else:
            segment = tk.Canvas(
                parent_frame,
                width=20,
                height=5,
                highlightthickness=0,
            )
        segment.grid(
            row=row,
            column=column,
            padx=padx,
            pady=pady,
        )
        segment.bind(
            "<Button-1>",
            lambda event,
            led_key=label, led_index=led_index: self.change_led_color(
                led_key, index=led_index
            ),
        )
        if led_index is not None:
            self.leds_ui[leds_indexes[label][led_index]] = segment
        else:
            self.leds_ui[leds_indexes[label]] = segment

    def create_segmented_digit_layout(self, frame, label, number_of_digits=3, index = 0):
        for digit_index in range(number_of_digits):
            digit_frame = ttk.Frame(frame, padding=(5, 5))
            digit_frame.grid(row=1, column=digit_index, padx=5, pady=5)

            # Create 7 segments for the digit
            for segment_name in segmented_digit_layout.keys():
                self.create_segment(
                    digit_frame,
                    label,
                    led_index=index,
                    row=segmented_digit_layout[segment_name]["row"],
                    column=segmented_digit_layout[segment_name]["column"],
                    orientation=segmented_digit_layout[segment_name]["orientation"],
                    pady=segmented_digit_layout[segment_name]["pady"],
                    padx=segmented_digit_layout[segment_name]["padx"],
                )
                index+=1

    def create_display_mode(self, root, row=0, column=0):
        display_mode_frame = ttk.LabelFrame(root, text="Choose display mode :", padding=(10, 10))
        display_mode_frame.grid(row=row, column=column, pady=10)
        self.display_mode = tk.StringVar(value=self.config["display_mode"])
        group_dropdown = ttk.Combobox(
            display_mode_frame, textvariable=self.display_mode, state="readonly"
        )
        group_dropdown["values"] = display_modes
        group_dropdown.grid(row=0, column=0, padx=5, pady=5)
        group_dropdown.bind(
            "<<ComboboxSelected>>",
            lambda event: self.change_display_mode(),
        )

    def create_color_mode(self, root, row=0, column=1):
        color_mode_frame = ttk.LabelFrame(root, text="Change the color of the :", padding=(10, 10))
        color_mode_frame.grid(row=row, column=column, pady=10)        
        self.color_mode = tk.StringVar(value="time")
        group_dropdown = ttk.Combobox(
            color_mode_frame, textvariable=self.color_mode, state="readonly"
        )
        group_dropdown["values"] = ["time", "metrics"]
        group_dropdown.grid(row=0, column=0, padx=5, pady=5)

    def change_display_mode(self):
        self.config["display_mode"] = self.display_mode.get()
        if self.display_mode.get() == "time":
            self.color_mode.set("time")
        elif self.display_mode.get() == "metrics":
            self.color_mode.set("metrics")
        self.write_config()

    def create_controls(self, root, row=3):
        controls_frame = ttk.LabelFrame(root, text="Group color :", padding=(10, 10))
        controls_frame.grid(row=row, column=0, columnspan=2, pady=10)
        # Dropdown for group selection
        self.group_var = tk.StringVar(value="ALL")
        group_dropdown = ttk.Combobox(
            controls_frame, textvariable=self.group_var, state="readonly"
        )
        group_dropdown["values"] = [led_key.upper() for led_key in leds_indexes]
        
        group_dropdown.grid(row=0, column=0, padx=5, pady=5)

        # Button to change color of selected group
        change_color_button = ttk.Button(
            controls_frame,
            text="Change Group Color",
            command=self.change_group_color,
        )
        change_color_button.grid(row=0, column=1, padx=5, pady=5)

    def custom_color_popup(self, initial_color="#ffffff"):
        popup = tk.Toplevel(self.root)
        popup.title("Choose Color Mode")

        mode_var = tk.StringVar(value="color")
        tk.Label(popup, text="Select Mode:").grid(row=0, column=0, padx=5, pady=5)
        mode_dropdown = ttk.Combobox(popup, textvariable=mode_var, state="readonly")
        mode_dropdown["values"] = ["color", "color gradient", "metrics dependent", "time dependent", "random"]
        mode_dropdown.grid(row=0, column=1, padx=5, pady=5)

        metric = "cpu_usage"
        time_unit = "seconds"
        if initial_color == "random":
            mode_var.set("random")
        elif "-" in initial_color:
            split_color = initial_color.split("-")
            if len(split_color) == 3:
                start_color, end_color, key = split_color
                if key in ["cpu_usage", "cpu_temp", "gpu_usage", "gpu_temp"]:
                    metric = key
                    mode_var.set("metrics dependent")
                else:
                    time_unit = key
                    mode_var.set("time dependent")

            else:
                mode_var.set("color gradient")
                start_color, end_color = split_color
        else:
            start_color = initial_color
            end_color = initial_color
            

        color1_var = tk.StringVar(value=start_color)
        color2_var = tk.StringVar(value=end_color)
        metric_var = tk.StringVar(value=metric)
        time_unit_var = tk.StringVar(value=time_unit)

        def update_ui(*args):
            color1_label.grid_remove()
            color1_entry.grid_remove()
            color1_button.grid_remove()
            color2_label.grid_remove()
            color2_entry.grid_remove()
            color2_button.grid_remove()
            metric_dropdown.grid_remove()
            time_dropdown.grid_remove()
            metric_label.grid_remove()
            time_label.grid_remove()
            if mode_var.get() == "color gradient":
                color2_label.grid()
                color2_entry.grid()
                color2_button.grid()
            elif mode_var.get() == "metrics dependent":
                color2_label.grid()
                color2_entry.grid()
                color2_button.grid()
                metric_dropdown.grid()
                metric_label.grid()
            elif mode_var.get() == "time dependent":
                color2_label.grid()
                color2_entry.grid()
                color2_button.grid()
                time_label.grid()
                time_dropdown.grid()

        mode_var.trace("w", update_ui)

        color1_label = tk.Label(popup, text="Color 1:")
        color1_label.grid(row=1, column=0, padx=5, pady=5)
        color1_entry = tk.Entry(popup, textvariable=color1_var)
        color1_entry.grid(row=1, column=1, padx=5, pady=5)
        color1_button = tk.Button(popup, text="Choose", command=lambda: color1_var.set(colorchooser.askcolor()[1]))
        color1_button.grid(row=1, column=2, padx=5, pady=5)

        color2_label = tk.Label(popup, text="Color 2:")
        color2_label.grid(row=2, column=0, padx=5, pady=5)
        color2_entry = tk.Entry(popup, textvariable=color2_var)
        color2_entry.grid(row=2, column=1, padx=5, pady=5)
        color2_button = tk.Button(popup, text="Choose", command=lambda: color2_var.set(colorchooser.askcolor()[1]))
        color2_button.grid(row=2, column=2, padx=5, pady=5)

        metric_label = tk.Label(popup, text="Metric:")
        metric_label.grid(row=3, column=0, padx=5, pady=5)
        metric_dropdown = ttk.Combobox(popup, textvariable=metric_var, state="readonly")
        metric_dropdown["values"] = ["cpu_usage", "cpu_temp", "gpu_usage", "gpu_temp"]
        metric_dropdown.grid(row=3, column=1, padx=5, pady=5)

        time_label = tk.Label(popup, text="Time Unit:")
        time_label.grid(row=4, column=0, padx=5, pady=5)
        time_dropdown = ttk.Combobox(popup, textvariable=time_unit_var, state="readonly")
        time_dropdown["values"] = ["seconds", "minutes", "hours"]
        time_dropdown.grid(row=4, column=1, padx=5, pady=5)

        update_ui()

        def on_submit():
            color1 = color1_var.get().replace("#", "")
            color2 = color2_var.get().replace("#", "")
            if mode_var.get() == "color":
                result = color1
            elif mode_var.get() == "color gradient":
                result = f"{color1}-{color2}"
            elif mode_var.get() == "metrics dependent":
                result = f"{color1}-{color2}-{metric_var.get()}"
            elif mode_var.get() == "time dependent":
                result = f"{color1}-{color2}-{time_unit_var.get()}"
            elif mode_var.get() == "random":
                result = "random"
            popup.result = result
            popup.destroy()

        tk.Button(popup, text="Submit", command=on_submit).grid(row=5, column=0, columnspan=3, pady=10)

        popup.transient(self.root)
        self.root.update_idletasks()  # Ensure the popup is fully initialized
        popup.grab_set()
        self.root.wait_window(popup)

        return getattr(popup, "result", None)

    def change_group_color(self):
        group_name = self.group_var.get().lower()
        if group_name in leds_indexes:
            result = self.custom_color_popup(initial_color=self.get_color(group_name, index=0))
            if result:
                if isinstance(leds_indexes[group_name], int):
                    self.set_color(leds_indexes[group_name], result)
                else:
                    for index in leds_indexes[group_name]:
                        self.set_color(index, result)
            self.write_config()
        else:
            print("Invalid group selected.")

    def change_led_color(self, led_key, index=None):
        led_index = self.get_index(led_key, index)
        result = self.custom_color_popup(initial_color=self.get_color(led_key, index))
        if result:
            self.set_color(led_index, result)
            self.write_config()
    
    def create_config_panel(self, root):
        config_frame = ttk.LabelFrame(root, text="Configuration Settings", padding=(10, 10))
        config_frame.grid(row=0, column=1, padx=10, pady=10, sticky="n")

        self.config_vars = {}
        config_keys = ["update_interval", "metrics_update_interval", "cycle_duration", "gpu_min_temp", "gpu_max_temp", "cpu_min_temp", "cpu_max_temp"]

        for i, key in enumerate(config_keys):
            label = ttk.Label(config_frame, text=key.replace("_", " ").capitalize() + ":")
            label.grid(row=i, column=0, padx=5, pady=5, sticky="w")

            var = tk.DoubleVar(value=self.config.get(key, 0))
            entry = ttk.Entry(config_frame, textvariable=var)
            entry.grid(row=i, column=1, padx=5, pady=5)

            self.config_vars[key] = var

        save_button = ttk.Button(config_frame, text="Save", command=self.save_config_changes)
        save_button.grid(row=len(config_keys), column=0, columnspan=2, pady=10)

    def save_config_changes(self):
        for key, var in self.config_vars.items():
            self.config[key] = var.get()
        self.write_config()

if __name__ == "__main__":
    root = tk.Tk()
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        print(f"Using config path: {config_path}")
        app = LEDDisplayUI(root, config_path=config_path)
    else:
        print("No config path provided, using default.")
        app = LEDDisplayUI(root)

    root.mainloop()
