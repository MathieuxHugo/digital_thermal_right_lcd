import tkinter as tk
from tkinter import ttk, colorchooser


segmented_digit_layout = {# Position segments in a 7-segment layout
    "top":
        {"row":0, "column":1, "pady":2},
    "top_left":
        {"row":1, "column":0, "padx":2},
    "top_right":
        {"row":1, "column":2, "padx":2},
    "middle":
        {"row":2, "column":1, "pady":2},
    "bottom_left":
        {"row":3, "column":0, "padx":2},
    "bottom_right":
        {"row":3, "column":2, "padx":2},
    "bottom":
        {"row":4, "column":1, "pady":2}
}

class LEDDisplayUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LED Display Layout")

        # Create frames for CPU and GPU
        self.cpu_frame = self.create_device_frame(root, "CPU", 0)

        self.gpu_frame = self.create_device_frame(root, "GPU", 1)

        # Add controls for group selection and color change
        self.controls_frame = ttk.LabelFrame(root, text="Controls", padding=(10, 10))
        self.controls_frame.grid(row=2, column=0, columnspan=2, pady=10)
        self.create_controls()

    def create_device_frame(self, root, device_name, row):
        frame = ttk.LabelFrame(root, text=device_name.upper(), padding=(10, 10))
        frame.grid(row=row, column=0, padx=10, pady=10)

        temp_frame = ttk.LabelFrame(frame, text=device_name.upper()+" temp", padding=(10, 10))
        temp_frame.grid(row=0, column=0, padx=10, pady=10)

        usage_frame = ttk.LabelFrame(frame, text=device_name.upper()+" usage", padding=(10, 10))
        usage_frame.grid(row=0, column=1, padx=10, pady=10)

        # Create LED layout for CPU and GPU
        self.cpu_temp_leds = self.create_segmented_digit_layout(temp_frame, device_name+"_temp")
        self.cpu_usage_leds = self.create_segmented_digit_layout(usage_frame, device_name+"_usage", number_of_digits=2)
        return frame
    


    def create_segmented_digit_layout(self, frame, label, number_of_digits=3):
        leds = {}

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
                

                # Add click event to change color
                segment.bind(
                    "<Button-1>",
                    lambda event,
                    segment=segment_name, digit=digit_index, led_group=label: self.change_led_color(
                        segment, digit, led_group
                    ),
                )

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

    def change_led_color(self, led_key):
        color = colorchooser.askcolor(title="Choose LED Color")[1]
        if color:
            parts = led_key.split("_")
            if "CPU" in parts:
                digit = parts[2]
                segment = parts[4]
                self.cpu_leds[digit][segment].config(bg=color)
            elif "GPU" in parts:
                digit = parts[2]
                segment = parts[4]
                self.gpu_leds[digit][segment].config(bg=color)

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
    app = LEDDisplayUI(root)
    root.mainloop()
