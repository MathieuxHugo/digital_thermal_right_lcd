import tkinter as tk
from tkinter import ttk, colorchooser
import json
import sys
from config import leds_indexes, NUMBER_OF_LEDS
import numpy as np

segmented_digit_layout = {# Position segments in a 7-segment layout
    "top_left":
        {"row":1, "column":0, "padx":2},
    "top":
        {"row":0, "column":1, "pady":2},
    "top_right":
        {"row":1, "column":2, "padx":2},
    "middle":
        {"row":2, "column":1, "pady":2},
    "bottom_left":
        {"row":3, "column":0, "padx":2},
    "bottom":
        {"row":4, "column":1, "pady":2},
    "bottom_right":
        {"row":3, "column":2, "padx":2}
}

class LEDDisplayUI:
    def __init__(self, root, config_path="config.json"):
        self.root = root
        self.config_path = config_path
        self.color_mode = "time"
        self.config = self.load_config()
        self.root.title("LED Display Layout")
        self.style = ttk.Style()
        # Create frames for CPU and GPU
        self.cpu_frame = self.create_device_frame(root, "cpu", 0)

        self.gpu_frame = self.create_device_frame(root, "gpu", 1)

        # Add controls for group selection and color change
        self.controls_frame = ttk.LabelFrame(root, text="Controls", padding=(10, 10))
        self.controls_frame.grid(row=2, column=0, columnspan=2, pady=10)
        self.create_controls()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
        
    def get_color(self, led_key, index=None):
        if index is None:
            return f"#{np.array(self.config[self.color_mode]["colors"])[leds_indexes[led_key]]}"
        else:
            return f"#{np.array(self.config[self.color_mode]["colors"])[leds_indexes[led_key]][index]}"
    
    def set_color(self, led_key, color, index=None):
        if self.config:
            colors = np.array(self.config[self.color_mode]["colors"])
            if index is None:
                colors[leds_indexes[led_key]] = color
            else:
                colors[leds_indexes[led_key][index]] = color
            self.config[self.color_mode]["colors"] = colors.tolist()
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        else:
            print("Config not loaded. Cannot set color.")


    def create_device_frame(self, root, device_name, row):
        frame = ttk.LabelFrame(root, text=device_name.upper(), padding=(10, 10))
        frame.grid(row=row, column=0, padx=10, pady=10)

        temp_frame = ttk.LabelFrame(frame, text=device_name.upper()+" temp", padding=(10, 10))
        temp_frame.grid(row=0, column=0, padx=10, pady=10)

        # Add temperature unit selection
        unit_frame = ttk.Frame(frame)
        unit_frame.grid(row=0, column=2, padx=5, pady=5)
        
        # Create variables to store the selected unit and style for labels
        self.temp_unit_var = getattr(self, f"{device_name.lower()}_temp_unit_var", tk.StringVar(value="C"))
        unit_style = {"font": ("Arial", 10), "cursor": "hand2", "padding": 5}
        
        # Create clickable labels for °C and °F
        celsius_label = ttk.Label(unit_frame, text="°C", **unit_style)
        celsius_label.pack(side=tk.LEFT, padx=2)
        celsius_label.config(foreground=self.get_color(device_name+"_celsius"))
        celsius_label.bind("<Button-1>", lambda e: self.temp_unit_var.set("C"))
        fahrenheit_label = ttk.Label(unit_frame, text="°F", **unit_style)
        fahrenheit_label.pack(side=tk.LEFT, padx=2)
        fahrenheit_label.config(foreground=self.get_color(device_name+"_fahrenheit"))
        fahrenheit_label.bind("<Button-1>", lambda e: self.temp_unit_var.set("F"))

        usage_frame = ttk.LabelFrame(frame, text=device_name.upper()+" usage", padding=(10, 10))
        usage_frame.grid(row=0, column=1, padx=10, pady=10)

        # Create LED layout for CPU and GPU
        self.cpu_temp_leds = self.create_segmented_digit_layout(temp_frame, device_name+"_temp")
        self.cpu_usage_leds = self.create_segmented_digit_layout(usage_frame, device_name+"_usage", number_of_digits=2)
        return frame
    
    def create_usage_frame(self, frame, label):
        one_frame = ttk.Frame(frame, padding=(5, 5))
        one_frame.grid(row=1, column=0, padx=5, pady=5)
        for one_index in range(2):
            segment = tk.Canvas(
                        frame,
                        width=5,
                        height=20,
                        bg="white",
                        highlightthickness=0,
                    )
            segment.grid(
                row=one_index,
                column=0,
                padx=0,
                pady=0,
            )
        
        index = 2
        for digit_index in range(2):
            digit_frame = ttk.Frame(frame, padding=(5, 5))
            digit_frame.grid(row=1, column=digit_index+1, padx=5, pady=5)

            segments = {}
            # Create 7 segments for the digit
            for segment_name in segmented_digit_layout.keys():
                if ("right" in segment_name) or ("left" in segment_name):  # Vertical segments
                    segment = tk.Canvas(
                        digit_frame,
                        width=5,
                        height=20,
                        bg="white",
                        highlightthickness=0,
                    )
                else:  # Horizontal segments
                    segment = tk.Canvas(
                        digit_frame,
                        width=20,
                        height=5,
                        bg="white",
                        highlightthickness=0,
                    )
                segments[f"{segment_name}"] = segment
                segment.grid(
                    row=segmented_digit_layout[segment_name]["row"],
                    column=segmented_digit_layout[segment_name]["column"],
                    padx=segmented_digit_layout[segment_name].get("padx", 0),
                    pady=segmented_digit_layout[segment_name].get("pady", 0),
                )
                segment.config(background=self.get_color(label,index))

                # Add click event to change color
                segment.bind(
                    "<Button-1>",
                    lambda event,
                    led_key=label, led_index=index: self.change_led_color(
                        led_key, led_index
                    ),
                )
                index+=1

    def create_segmented_digit_layout(self, frame, label, number_of_digits=3):
        leds = {}
        index = 0
        
        # Create 3 digits, each with 7 segments
        for digit_index in range(number_of_digits):
            digit_frame = ttk.Frame(frame, padding=(5, 5))
            digit_frame.grid(row=1, column=digit_index, padx=5, pady=5)

            segments = {}
            # Create 7 segments for the digit
            for segment_name in segmented_digit_layout.keys():
                if ("right" in segment_name) or ("left" in segment_name):  # Vertical segments
                    segment = tk.Canvas(
                        digit_frame,
                        width=5,
                        height=20,
                        bg="white",
                        highlightthickness=0,
                    )
                else:  # Horizontal segments
                    segment = tk.Canvas(
                        digit_frame,
                        width=20,
                        height=5,
                        bg="white",
                        highlightthickness=0,
                    )
                segments[f"{segment_name}"] = segment
                segment.grid(
                    row=segmented_digit_layout[segment_name]["row"],
                    column=segmented_digit_layout[segment_name]["column"],
                    padx=segmented_digit_layout[segment_name].get("padx", 0),
                    pady=segmented_digit_layout[segment_name].get("pady", 0),
                )
                segment.config(background=self.get_color(label,index))

                # Add click event to change color
                segment.bind(
                    "<Button-1>",
                    lambda event,
                    led_key=label, led_index=index: self.change_led_color(
                        led_key, led_index
                    ),
                )
                index+=1

            leds[f"{digit_index}"] = segments

        return leds

    def create_controls(self):
        # Dropdown for group selection
        self.group_var = tk.StringVar(value="Select Group")
        group_dropdown = ttk.Combobox(
            self.controls_frame, textvariable=self.group_var, state="readonly"
        )
        group_dropdown["values"] = [
            "All CPU LEDs",
            "All GPU LEDs",
            "CPU Temp",
            "GPU Temp",
            "CPU Usage",
            "GPU Usage",
        ]
        group_dropdown.grid(row=0, column=0, padx=5, pady=5)

        # Button to change color of selected group
        change_color_button = ttk.Button(
            self.controls_frame,
            text="Change Group Color",
            command=self.change_group_color,
        )
        change_color_button.grid(row=0, column=1, padx=5, pady=5)

    def change_led_color(self, led_key, index=None):
        color = colorchooser.askcolor(title="Choose LED Color")[1]
        if color:
            self.set_color(led_key, color.replace("#", ""), index)

    def change_group_color(self):
        color = colorchooser.askcolor(title="Choose Group Color")[1]
        if not color:
            return

        group = self.group_var.get()
        if group == "All CPU LEDs":
            for led in self.cpu_leds.values():
                led.config(bg=color)
        elif group == "All GPU LEDs":
            for led in self.gpu_leds.values():
                led.config(bg=color)
        elif group == "CPU Temp":
            for key in ["temp_0", "temp_1", "temp_2"]:
                self.cpu_leds[key].config(bg=color)
        elif group == "GPU Temp":
            for key in ["temp_0", "temp_1", "temp_2"]:
                self.gpu_leds[key].config(bg=color)
        elif group == "CPU Usage":
            for key in ["usage_0", "usage_1", "usage_2"]:
                self.cpu_leds[key].config(bg=color)
        elif group == "GPU Usage":
            for key in ["usage_0", "usage_1", "usage_2"]:
                self.gpu_leds[key].config(bg=color)


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
