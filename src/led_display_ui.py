import tkinter as tk
from tkinter import ttk, colorchooser
import json
import sys
from config import default_config, old_layout_mode, MAX_NUMBER_OF_LEDS
from device_configurations import get_device_config, CONFIG_NAMES
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
        # Set dark theme defaults: black background, white font
        self.root.configure(bg='black')
        # Apply option defaults so tk widgets (tk.Label, tk.Canvas, etc.) pick up colors
        self.root.option_add('*foreground', 'white')
        self.root.option_add('*background', 'black')
        # ttk style configuration
        self.style = ttk.Style()
        # prefer the 'clam' theme which respects background settings across platforms
        try:
            self.style.theme_use('clam')
        except Exception:
            try:
                self.style.theme_use('default')
            except Exception:
                pass
        for cls in ['TLabel', 'TFrame', 'TButton', 'TEntry', 'TCombobox', 'TLabelframe']:
            try:
                self.style.configure(cls, background='black', foreground='white')
            except Exception:
                pass
        # Ensure combobox and entry field backgrounds are black and text is white (handles several themes)
        try:
            # Dark variant styles
            self.style.configure('Dark.TLabel', background='black', foreground='white')
            self.style.configure('Dark.TFrame', background='black')
            self.style.configure('Dark.TLabelframe', background='black', foreground='white')
            # Ensure the LabelFrame title label also uses the dark background (some themes use a separate element)
            self.style.configure('Dark.TLabelframe.Label', background='black', foreground='white')
            # Fallback for default labelframe label element
            self.style.configure('TLabelframe.Label', background='black', foreground='white')
            self.style.configure('Dark.TButton', background='black', foreground='white')
            self.style.configure('Dark.TCombobox', fieldbackground='black', background='black', foreground='white')
            self.style.map('Dark.TCombobox', fieldbackground=[('readonly', 'black'), ('!disabled', 'black')], foreground=[('readonly', 'white'), ('!disabled', 'white')])
            self.style.configure('Dark.TEntry', fieldbackground='black', background='black', foreground='white')
            self.style.map('Dark.TEntry', fieldbackground=[('!disabled', 'black')])
        except Exception:
            pass

        self.config_path = config_path
        self.config = self.load_config()
        self.root.title("LED Display Layout")
        # default to PA120 configuration until config is loaded
        self.leds_indexes = get_device_config('Pearless Assasin 120').leds_indexes
        # Layout mode selection
        self.layout_mode = tk.StringVar(value=self.config.get("layout_mode", "Pearless Assasin 120"))
        #Retro compatibility
        if self.layout_mode.get() in old_layout_mode:
            self.layout_mode.set(old_layout_mode[self.layout_mode.get()])
        layout_mode_frame = ttk.LabelFrame(root, text="Choose layout mode:", padding=(10, 10), style='Dark.TLabelframe')
        layout_mode_frame.grid(row=0, column=0, pady=10)
        layout_dropdown = ttk.Combobox(layout_mode_frame, textvariable=self.layout_mode, state="readonly", style='Dark.TCombobox')
        layout_dropdown["values"] = CONFIG_NAMES
        layout_dropdown.grid(row=0, column=0, padx=5, pady=5)
        layout_dropdown.bind("<<ComboboxSelected>>", lambda e: self.change_layout_mode())

        # Frames for layout
        self.layout_frame = ttk.Frame(root)
        self.layout_frame.grid(row=1, column=0, columnspan=3, padx=10, pady=10)

        # Create initial layout (big)
        self.change_layout_mode()

        # Start update thread
        self.update_interval = self.config["update_interval"]
        self.cycle_duration = self.config["cycle_duration"]
        self.start_time = time.time()
        threading.Thread(target=self.update_ui_loop, daemon=True).start()

        # Reset button
        reset_button = ttk.Button(
            root,
            text="Reset default config",
            command=lambda: self.set_default_config(),
        )
        reset_button.grid(row=2, column=0, padx=10, pady=10, columnspan=2)

    def clear_layout(self):
        """Remove widgets from the layout frame."""
        for widget in self.layout_frame.winfo_children():
            widget.destroy()

    def init_led_ui(self, number_of_leds):
        """Initialize number_of_leds and leds_ui array."""
        self.number_of_leds = number_of_leds
        self.leds_ui = np.array([None] * self.number_of_leds)

    def setup_led_frame_and_config(self):
        """Create and return the common led_frame and ensure config panel exists."""
        led_frame = ttk.Frame(self.layout_frame, padding=(10, 10))
        led_frame.grid(row=0, column=0, padx=10, pady=10)
        # Ensure config panel is always available
        self.config_frame = self.create_config_panel(self.layout_frame)
        return led_frame

    def create_pa120_layout(self, led_frame, display_frame):

        self.create_color_mode(display_frame)

        # Create frames for CPU and GPU
        self.cpu_frame = self.create_device_frame(led_frame, "cpu", 1)
        self.gpu_frame = self.create_device_frame(led_frame, "gpu", 2)

        return 3

    def create_ax120R_layout(self, led_frame):
        # Device LED labels in row 1
        device_led_frame = ttk.Frame(led_frame)
        device_led_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5)
        
        self.create_label(device_led_frame, "cpu_led", "CP", 0, 0, index=0)
        self.create_label(device_led_frame, "cpu_led", "U", 0, 1, index=1)
        self.create_label(device_led_frame, "gpu_led", "GP", 1, 0, index=0)
        self.create_label(device_led_frame, "gpu_led", "U", 1, 1, index=1)

        # Temperature unit selection in row 1, column 1
        unit_frame = ttk.Frame(led_frame)
        unit_frame.grid(row=1, column=1, padx=5, pady=5)
        
        # Create clickable labels for °C and °F
        self.create_label(unit_frame, "celsius", "°C", 0, 0)
        self.create_label(unit_frame, "fahrenheit", "°F", 1, 0)
        self.create_label(unit_frame, "percent_led", "%", 2, 0)
        
        # Digit frame in row 2
        digit_frame = ttk.Frame(led_frame)
        digit_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5)
        self.create_segmented_digit_layout(digit_frame, "digit_frame")
        
        return 3

    def create_pa140_layout_top(self, led_frame):
        device_frame = ttk.Frame(led_frame)
        device_frame.grid(row=1, column=0, padx=5, pady=5)
        self.create_label(device_frame, "cpu_led", "CPU", 0, 0, padx=5)
        self.create_label(device_frame, "gpu_led", "GPU", 0, 2, padx=5)


        # Temperature display (3-digit + °C)
        temp_frame = ttk.LabelFrame(led_frame, text="Temperature", padding=(10, 10), style='Dark.TLabelframe')
        temp_frame.grid(row=2, column=0)
        temp_digit_frame = ttk.Frame(temp_frame)
        temp_digit_frame.grid(row=0, column=0, padx=5, pady=5)
        self.create_segmented_digit_layout(temp_digit_frame, "temp", number_of_digits=3)
        unit_frame = ttk.Frame(temp_frame)
        unit_frame.grid(row=0, column=1, padx=5, pady=5)
        self.create_label(unit_frame, "celsius", "°C", 0, 0)
        self.create_label(unit_frame, "fahrenheit", "°F", 1, 0)

        # Power consumption display (3 digits + W)
        power_frame = ttk.LabelFrame(led_frame, text="Power Consumption", padding=(10, 10), style='Dark.TLabelframe')
        power_frame.grid(row=2, column=1)
        power_digit_frame = ttk.Frame(power_frame)
        power_digit_frame.grid(row=0, column=0, padx=5, pady=5)
        self.create_segmented_digit_layout(power_digit_frame, "watt", number_of_digits=3)
        power_unit_frame = ttk.Frame(power_frame)
        power_unit_frame.grid(row=0, column=1, padx=5, pady=5)
        self.create_label(power_unit_frame, "watt_led", "W", 0, 0)

    def create_pa140_layout_bottom(self, led_frame, shift=0):
        # Clock speed display (4 digits + MHz)
        clock_frame = ttk.LabelFrame(led_frame, text="Clock Frequency", padding=(10, 10), style='Dark.TLabelframe')
        clock_frame.grid(row=3+shift, column=0)
        clock_digit_frame = ttk.Frame(clock_frame)
        clock_digit_frame.grid(row=0, column=0, padx=5, pady=5)
        self.create_segmented_digit_layout(clock_digit_frame, "frequency", number_of_digits=4) 
        frequency_unit_frame = ttk.Frame(clock_frame)
        frequency_unit_frame.grid(row=0, column=1, padx=5, pady=5)
        self.create_label(frequency_unit_frame, "frequency_led", "MHz", 0, 0)

        # Usage percentage display (2 digits + %)
        usage_frame = ttk.LabelFrame(led_frame, text="Usage Percentage", padding=(10, 10), style='Dark.TLabelframe')
        usage_frame.grid(row=3+shift, column=1)
        self.create_usage_frame(usage_frame, "usage")
        self.create_label(usage_frame, "percent_led", "%", 1, 5)

    def create_pa140_layout(self, led_frame):
        self.create_pa140_layout_top(led_frame)
        self.create_pa140_layout_bottom(led_frame)
        return 4

    def create_pa140_big_layout(self, led_frame):
        self.create_pa140_layout_top(led_frame)

        middle_led_frame = ttk.Frame(led_frame)
        middle_led_frame.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

        for i in range(14):
            canvas = tk.Canvas(middle_led_frame, width=30, height=5, highlightthickness=0, bg='black')
            canvas.grid(row=0, column=i, padx=5, pady=5)
            rectangle_led_index = self.leds_indexes["middle_led"][i]
            canvas.bind("<Button-1>",
                lambda event,
                led_key="middle_led", led_index=i: self.change_led_color(
                    led_key, index=led_index
                ),
            )
            self.leds_ui[rectangle_led_index] = canvas

        right_led_frame = ttk.Frame(led_frame)
        right_led_frame.grid(row=2, column=2, rowspan=3, padx=5, pady=5)

        for i in range(7):
            canvas = tk.Canvas(right_led_frame, width=10, height=20, highlightthickness=0, bg='black')
            canvas.grid(row=i, column=0, padx=5, pady=5)
            rectangle_led_index = self.leds_indexes["right_led"][i]
            canvas.bind("<Button-1>",
                lambda event,
                led_key="right_led", led_index=i: self.change_led_color(
                    led_key, index=led_index
                ),
            )
            self.leds_ui[rectangle_led_index] = canvas


        self.create_pa140_layout_bottom(led_frame, shift=1)

        # Main area: left block with 5 vertical rectangles side-by-side
        main_area = ttk.Frame(led_frame)
        main_area.grid(row=5, column=1, padx=10, pady=10)

        left_frame = ttk.Frame(main_area)
        left_frame.grid(row=1, column=0, padx=10, pady=10)

        start_index = 0
        big_side = 60
        small_side = 15
        # create 5 vertical rectangles next to each other
        for i in range(5):
            canvas = tk.Canvas(left_frame, width=small_side, height=big_side, highlightthickness=0, bg='black')
            canvas.grid(row=0, column=i, padx=5, pady=5)
            rectangle_led_index = self.leds_indexes["bottom_right"][start_index]
            canvas.bind("<Button-1>",
                lambda event,
                led_key="bottom_right", led_index=start_index: self.change_led_color(
                    led_key, index=led_index
                ),
            )
            self.leds_ui[rectangle_led_index] = canvas
            start_index += 1

        # Right corner: 5 horizontal rectangles stacked vertically
        right_frame = ttk.Frame(main_area)
        right_frame.grid(row=0, column=1, padx=40, pady=10, sticky='n')

        for j in range(5):

            rectangle_led_index = self.leds_indexes["bottom_right"][start_index]
            canvas_h = tk.Canvas(right_frame, width=big_side, height=small_side, highlightthickness=0, bg='black')
            canvas_h.grid(row=j, column=0, padx=5, pady=5)
            canvas_h.bind("<Button-1>",
                lambda event,
                led_key="bottom_right", led_index=start_index: self.change_led_color(
                    led_key, index=led_index
                ),
            )
            self.leds_ui[rectangle_led_index] = canvas_h
            start_index += 1

        return 6

    def create_hr10_2280_pro_layout(self, led_frame):
        # Title frame
        title_frame = ttk.Frame(led_frame)
        title_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5)
        ttk.Label(title_frame, text="NVMe Storage Display", style='Dark.TLabel', font=("Arial", 14)).grid(row=0, column=0)

        # Main display frame with 5 digits + percent_led + speed_unit_led
        display_frame = ttk.LabelFrame(led_frame, text="Value Display", padding=(10, 10), style='Dark.TLabelframe')
        display_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=10)
        
        # Container for digits and degree LED
        digit_container = ttk.Frame(display_frame)
        digit_container.grid(row=0, column=0, padx=5, pady=5)
        
        # Degree LED above the last digit
        degree_frame = ttk.Frame(digit_container)
        degree_frame.grid(row=0, column=4, padx=0, pady=0)
        self.create_label(degree_frame, "degree_led", "■", 0, 0)
        
        digit_frame = ttk.Frame(digit_container)
        digit_frame.grid(row=1, column=0, columnspan=5, padx=0, pady=0)
        self.create_segmented_digit_layout(digit_frame, "digit", number_of_digits=5, index=0)
        
        unit_frame = ttk.Frame(display_frame)
        unit_frame.grid(row=0, column=1, padx=10, pady=5)
        self.create_label(unit_frame, "percent_led", "%", 0, 0)
        self.create_label(unit_frame, "speed_unit_led", "MB/s", 1, 0)

        return 3

    def change_layout_mode(self):
        layout_name = self.layout_mode.get()
        device_conf = get_device_config(layout_name)
        self.leds_indexes = device_conf.leds_indexes
        self.init_led_ui(len(self.leds_indexes["all"]))
        self.config["layout_mode"] = layout_name
        if self.config["display_mode"] not in device_conf.get_mode_names():
            print(f"Warning: Display mode {self.config['display_mode']} not compatible with {layout_name} layout, switching to a compatible mode.")
            if 'metrics' in device_conf.get_mode_names():
                self.config["display_mode"] = 'metrics'
            elif 'alternate_metrics' in device_conf.get_mode_names():
                self.config["display_mode"] = 'alternate_metrics'
            else:
                self.config["display_mode"] = device_conf.get_mode_names()[0]
        self.create_layout(layout_name)
        self.write_config()

    def create_layout(self, layout_name):
        controls_row_index = 0
        # Clear previous layout
        self.clear_layout()

        led_frame = self.setup_led_frame_and_config()

        # Display controls at the top
        display_frame = ttk.Frame(led_frame, padding=(10, 10))
        display_frame.grid(row=0, column=0, padx=10, pady=10)
        # use the same device config display modes as the standard PA140
        self.create_display_mode(display_frame, get_device_config(layout_name).get_mode_names())

        # Call the correct create_* layout function
        if layout_name == 'Pearless Assasin 120':
            controls_row_index = self.create_pa120_layout(led_frame, display_frame)
        elif layout_name == 'TR Assassin X 120R':
            controls_row_index = self.create_ax120R_layout(led_frame)
        elif layout_name == 'Pearless Assasin 140 BIG':
            controls_row_index = self.create_pa140_big_layout(led_frame)
        elif layout_name == 'Thermalright HR-10 2280 PRO':
            controls_row_index = self.create_hr10_2280_pro_layout(led_frame)
        else:
            # default to PA140 layout for any other name
            controls_row_index = self.create_pa140_layout(led_frame)
        
        # Add controls (group selection and color change)
        self.create_controls(led_frame, row=controls_row_index)

    def set_default_config(self):
        self.config = default_config.copy()
        self.write_config()
        self.config_frame.destroy()
        self.config_frame = self.create_config_panel(self.layout_frame)
        print("Default config set.")

    def update_ui_loop(self):
        while True:
            try:
                current_time = time.time()
                elapsed_time = (current_time - self.start_time)%(self.cycle_duration*2)
                colors = np.array(self.config[self.get_color_key()]["colors"])
                for index in range(self.number_of_leds):
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
            except Exception as e:
                print(f"Error in update_ui_loop: {e}")
            time.sleep(self.update_interval)

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            # Fall back to defaults if available
            try:
                config = default_config.copy()
            except Exception:
                config = {}

        # Enforce that every colors list matches the NUMBER_OF_LEDS constant
        expected_led_count = MAX_NUMBER_OF_LEDS

        for key, val in list(config.items()):
            if isinstance(val, dict):
                colors = val.get("colors")
                if isinstance(colors, list):
                    current_len = len(colors)
                    if current_len != expected_led_count:
                        # Resize: pad with last color or 'ffffff' if empty, or truncate if too long
                        if current_len == 0:
                            fill_color = "ffffff"
                            resized = [fill_color] * expected_led_count
                        elif current_len < expected_led_count:
                            last = colors[-1] if colors else "ffffff"
                            resized = colors + [last] * (expected_led_count - current_len)
                        else:
                            resized = colors[:expected_led_count]

                        config[key]["colors"] = resized
                        # Save corrected config immediately
                        try:
                            with open(self.config_path, 'w') as f:
                                json.dump(config, f, indent=4)
                            print(f"Adjusted colors for '{key}' from {current_len} to {expected_led_count} and saved config.")
                        except Exception as e:
                            print(f"Error saving resized config: {e}")

        return config

    def get_index(self, led_key, index=None):
        if index is None or isinstance(self.leds_indexes[led_key],int):
            return self.leds_indexes[led_key]
        else:
            return self.leds_indexes[led_key][index]

    def get_color_key(self):
        if self.layout_mode.get() == "Pearless Assasin 120":
            return self.color_mode.get()
        else:
            return "metrics"

    def get_color(self, led_key, index=None):
        return f"#{np.array(self.config[self.get_color_key()]['colors'])[self.get_index(led_key, index)]}"

    def set_color(self, led_index, color):
        if self.config:
            self.config[self.get_color_key()]["colors"][led_index] = color
        else:
            print("Config not loaded. Cannot set color.")

    def write_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error writing config: {e}")

    def set_ui_color(self, index, color):
        if self.leds_ui[index] is not None:
            if isinstance(self.leds_ui[index],(ttk.Label)):
                self.leds_ui[index].config(foreground=color)
            else:
                self.leds_ui[index].config(background=color)

    def create_device_frame(self, root, device_name, row):
        frame = ttk.LabelFrame(root, text=device_name.upper(), padding=(10, 10), style='Dark.TLabelframe')
        frame.grid(row=row, column=0, padx=10, pady=10)

        device_led_frame = ttk.Frame(frame)
        device_led_frame.grid(row=0, column=0, padx=0, pady=0)
        self.create_label(device_led_frame, device_name+"_led", device_name.upper()[0], 0, 0, index=int(device_name=="cpu"))
        self.create_label(device_led_frame, device_name+"_led", device_name.upper()[1:], 0, 1, index=int(device_name!="cpu"))

        temp_frame = ttk.LabelFrame(frame, text=device_name.upper()+" temp", padding=(10, 10), style='Dark.TLabelframe')
        temp_frame.grid(row=1, column=0, padx=10, pady=10)

        # Add temperature unit selection
        unit_frame = ttk.Frame(frame)
        unit_frame.grid(row=1, column=1, padx=5, pady=5)
        
        # Create clickable labels for °C and °F
        self.create_label(unit_frame, device_name+"_celsius", "°C", 0, 0)
        self.create_label(unit_frame, device_name+"_fahrenheit", "°F", 1, 0)

        usage_frame = ttk.LabelFrame(frame, text=device_name.upper()+" usage", padding=(10, 10), style='Dark.TLabelframe')
        usage_frame.grid(row=1, column=2, padx=10, pady=10)

        # Create LED layout for CPU and GPU
        self.create_segmented_digit_layout(temp_frame, device_name+"_temp")
        self.create_usage_frame(usage_frame, device_name+"_usage")
        
        self.create_label(frame, device_name+"_percent_led", "%", 1, 3)
        return frame

    def create_label(self, parent_frame, led_key, text, row, column, index=None, padx=0):
        unit_style = {"font": ("Arial", 20), "cursor": "hand2"}
        label = ttk.Label(parent_frame, text=text, style='Dark.TLabel', **unit_style)
        label.grid(row=row, column=column, padx=padx, pady=5)
        label.bind(
            "<Button-1>",
            lambda event,
            led_key=led_key, led_index=index: self.change_led_color(
                led_key, index=led_index
            ),
        )
        if index is not None:
            if led_key in self.leds_indexes and isinstance(self.leds_indexes[led_key], list):
                if index < len(self.leds_indexes[led_key]):
                    self.leds_ui[self.leds_indexes[led_key][index]] = label
            elif led_key in self.leds_indexes:
                self.leds_ui[self.leds_indexes[led_key]] = label
        else:
            if led_key in self.leds_indexes:
                self.leds_ui[self.leds_indexes[led_key]] = label

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
                bg='black',
            )
        else:
            segment = tk.Canvas(
                parent_frame,
                width=20,
                height=5,
                highlightthickness=0,
                bg='black',
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
        if led_index is not None and label in self.leds_indexes:
            if isinstance(self.leds_indexes[label], list) and led_index < len(self.leds_indexes[label]):
                self.leds_ui[self.leds_indexes[label][led_index]] = segment
            elif isinstance(self.leds_indexes[label], int):
                self.leds_ui[self.leds_indexes[label]] = segment

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

    def create_display_mode(self, root, display_modes, row=0, column=0):
        display_mode_frame = ttk.LabelFrame(root, text="Choose display mode :", padding=(10, 10))
        display_mode_frame.grid(row=row, column=column, pady=10)
        self.display_mode = tk.StringVar(value=self.config["display_mode"])
        group_dropdown = ttk.Combobox(
            display_mode_frame, textvariable=self.display_mode, state="readonly", style='Dark.TCombobox'
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
            color_mode_frame, textvariable=self.color_mode, state="readonly", style='Dark.TCombobox'
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
        controls_frame = ttk.LabelFrame(root, text="Group color :", padding=(10, 10), style='Dark.TLabelframe')
        controls_frame.grid(row=row, column=0, columnspan=2, pady=10)
        # Dropdown for group selection
        self.group_var = tk.StringVar(value="ALL")
        group_dropdown = ttk.Combobox(
            controls_frame, textvariable=self.group_var, state="readonly", style='Dark.TCombobox'
        )
        group_dropdown["values"] = [led_key.upper() for led_key in self.leds_indexes]
        
        group_dropdown.grid(row=0, column=0, padx=5, pady=5)

        # Button to change color of selected group
        change_color_button = ttk.Button(
            controls_frame,
            text="Change Group Color",
            command=self.change_group_color,
            style='Dark.TButton'
        )
        change_color_button.grid(row=0, column=1, padx=5, pady=5)

    def custom_color_popup(self, initial_color="#ffffff"):
        popup = tk.Toplevel(self.root)
        popup.title("Choose Color Mode")

        mode_var = tk.StringVar(value="color")
        # Use a ttk label with the dark style so it matches the rest
        ttk.Label(popup, text="Select Mode:", style='Dark.TLabel').grid(row=0, column=0, padx=5, pady=5)
        mode_dropdown = ttk.Combobox(popup, textvariable=mode_var, state="readonly", style='Dark.TCombobox')
        mode_dropdown["values"] = ["color", "color gradient", "metrics dependent", "time dependent", "random"]
        mode_dropdown.grid(row=0, column=1, padx=5, pady=5)

        metric = "cpu_usage"
        time_unit = "seconds"
        if "random" in initial_color.lower():
            start_color = "#ffffff"
            end_color = "#ffffff"
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
            if mode_var.get() == "random":
                color1_label.grid_remove()
                color1_entry.grid_remove()
                color1_button.grid_remove()
            else: 
                color1_label.grid()
                color1_entry.grid()
                color1_button.grid()
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

        color1_label = ttk.Label(popup, text="Color 1:", style='Dark.TLabel')
        color1_label.grid(row=1, column=0, padx=5, pady=5)
        color1_entry = ttk.Entry(popup, textvariable=color1_var, style='Dark.TEntry')
        color1_entry.grid(row=1, column=1, padx=5, pady=5)
        color1_button = ttk.Button(popup, text="Choose", command=lambda: color1_var.set(colorchooser.askcolor()[1]), style='Dark.TButton')
        color1_button.grid(row=1, column=2, padx=5, pady=5)

        color2_label = ttk.Label(popup, text="Color 2:", style='Dark.TLabel')
        color2_label.grid(row=2, column=0, padx=5, pady=5)
        color2_entry = ttk.Entry(popup, textvariable=color2_var, style='Dark.TEntry')
        color2_entry.grid(row=2, column=1, padx=5, pady=5)
        color2_button = ttk.Button(popup, text="Choose", command=lambda: color2_var.set(colorchooser.askcolor()[1]), style='Dark.TButton')
        color2_button.grid(row=2, column=2, padx=5, pady=5)

        metric_label = ttk.Label(popup, text="Metric:", style='Dark.TLabel')
        metric_label.grid(row=3, column=0, padx=5, pady=5)
        metric_dropdown = ttk.Combobox(popup, textvariable=metric_var, state="readonly", style='Dark.TCombobox')
        metric_dropdown["values"] = ["cpu_usage", "cpu_temp", "gpu_usage", "gpu_temp"]
        metric_dropdown.grid(row=3, column=1, padx=5, pady=5)

        time_label = ttk.Label(popup, text="Time Unit:", style='Dark.TLabel')
        time_label.grid(row=4, column=0, padx=5, pady=5)
        time_dropdown = ttk.Combobox(popup, textvariable=time_unit_var, state="readonly", style='Dark.TCombobox')
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

        ttk.Button(popup, text="Submit", command=on_submit, style='Dark.TButton').grid(row=5, column=0, columnspan=3, pady=10)

        popup.transient(self.root)
        self.root.update_idletasks()
        popup.grab_set()
        self.root.wait_window(popup)

        return getattr(popup, "result", None)

    def change_group_color(self):
        group_name = self.group_var.get().lower()
        if group_name in self.leds_indexes:
            result = self.custom_color_popup(initial_color=self.get_color(group_name, index=0))
            if result:
                if isinstance(self.leds_indexes[group_name], int):
                    self.set_color(self.leds_indexes[group_name], result)
                else:
                    for index in self.leds_indexes[group_name]:
                        self.set_color(index, result)
            self.write_config()
        else:
            print("Invalid group selected.")

    def change_led_color(self, led_key, index=None):
        if led_key in self.leds_indexes:
            led_index = self.get_index(led_key, index)
            result = self.custom_color_popup(initial_color=self.get_color(led_key, index))
            if result:
                self.set_color(led_index, result)
                self.write_config()
    
    def create_config_panel(self, root):
        config_frame = ttk.LabelFrame(root, text="Configuration Settings", padding=(10, 10), style='Dark.TLabelframe')
        config_frame.grid(row=0, column=1, padx=10, pady=10, sticky="ns")

        self.config_vars = {}
        # Add temperature unit dropdowns
        ttk.Label(config_frame, text="CPU Temperature Unit:", style='Dark.TLabel').grid(row=0, column=0, padx=5, pady=10, sticky="w")
        cpu_temp_unit = tk.StringVar(value=self.config.get("cpu_temperature_unit", "celsius"))
        cpu_unit_dropdown = ttk.Combobox(config_frame, textvariable=cpu_temp_unit, state="readonly", values=["celsius", "fahrenheit"], style='Dark.TCombobox')
        cpu_unit_dropdown.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        self.config_vars["cpu_temperature_unit"] = cpu_temp_unit

        ttk.Label(config_frame, text="GPU Temperature Unit:", style='Dark.TLabel').grid(row=1, column=0, padx=5, pady=10, sticky="w")
        gpu_temp_unit = tk.StringVar(value=self.config.get("gpu_temperature_unit", "celsius"))
        gpu_unit_dropdown = ttk.Combobox(config_frame, textvariable=gpu_temp_unit, state="readonly", values=["celsius", "fahrenheit"], style='Dark.TCombobox')
        gpu_unit_dropdown.grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        self.config_vars["gpu_temperature_unit"] = gpu_temp_unit
        config_keys = ["update_interval", "metrics_update_interval", "cycle_duration", "gpu_min_temp", "gpu_max_temp", "cpu_min_temp", "cpu_max_temp"]

        for i, key in enumerate(config_keys):
            label = ttk.Label(config_frame, text=key.replace("_", " ").capitalize() + ":", style='Dark.TLabel')
            label.grid(row=i+2, column=0, padx=5, pady=10, sticky="w")

            var = tk.DoubleVar(value=self.config.get(key, 0))
            entry = ttk.Entry(config_frame, textvariable=var, style='Dark.TEntry')
            entry.grid(row=i+2, column=1, padx=5, pady=10, sticky="ew")

            self.config_vars[key] = var

        for i, key in enumerate(["product_id", "vendor_id"]):
            label = ttk.Label(config_frame, text=key.replace("_", " ").capitalize() + ":", style='Dark.TLabel')
            label.grid(row=i+len(config_keys)+2, column=0, padx=5, pady=10, sticky="w")

            var = tk.StringVar(value=(self.config.get(key, 0)))
            entry = ttk.Entry(config_frame, textvariable=var, style='Dark.TEntry')
            entry.grid(row=i+len(config_keys)+2, column=1, padx=5, pady=10, sticky="ew")

            self.config_vars[key] = var
        
        config_frame.rowconfigure(tuple(range(len(config_keys))), weight=1)
        config_frame.columnconfigure(1, weight=1)

        save_button = ttk.Button(config_frame, text="Save", command=self.save_config_changes, style='Dark.TButton')
        save_button.grid(row=len(config_keys)+4, column=0, columnspan=2, pady=20)
        return config_frame

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
