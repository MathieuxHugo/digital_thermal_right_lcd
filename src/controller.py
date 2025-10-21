import numpy as np
from metrics import Metrics
from config import NUMBER_OF_LEDS
from device_configurations import get_device_config
from utils import interpolate_color, get_random_color
from displayer import DisplayerFactory
import hid
import time
import datetime 
import json
import os
import sys


digit_mask = np.array(
    [
        [1, 1, 1, 0, 1, 1, 1],  # 0
        [0, 0, 1, 0, 0, 0, 1],  # 1
        [0, 1, 1, 1, 1, 1, 0],  # 2
        [0, 1, 1, 1, 0, 1, 1],  # 3
        [1, 0, 1, 1, 0, 0, 1],  # 4
        [1, 1, 0, 1, 0, 1, 1],  # 5
        [1, 1, 0, 1, 1, 1, 1],  # 6
        [0, 1, 1, 0, 0, 0, 1],  # 7
        [1, 1, 1, 1, 1, 1, 1],  # 8
        [1, 1, 1, 1, 0, 1, 1],  # 9
        [0, 0, 0, 0, 0, 0, 0],  # nothing
    ]
)

letter_mask = {
    'H': [1, 0, 1, 1, 1, 0, 1],
}

def _number_to_array(number):
    if number>=10:
        return _number_to_array(int(number/10))+[number%10]
    else:
        return [number]

def get_number_array(temp, array_length=3, fill_value=-1):
    if temp<0:
        return [fill_value]*array_length
    else:
        narray = _number_to_array(temp)
        if (len(narray)!=array_length):
            if(len(narray)<array_length):
                narray = np.concatenate([[fill_value]*(array_length-len(narray)),narray])
            else:
                narray = narray[1:]
        return narray

class Controller:
    def __init__(self, config_path=None):
        self.temp_unit = {"cpu": "celsius", "gpu": "celsius"}
        self.metrics = Metrics()
        self.VENDOR_ID = 0x0416   
        self.PRODUCT_ID = 0x8001 
        self.dev = self.get_device()
        self.HEADER = 'dadbdcdd000000000000000000000000fc0000ff'
        self.leds = np.array([0] * NUMBER_OF_LEDS)
        # default to PA120 configuration until config is loaded
        self.leds_indexes = get_device_config('Pearless Assasin 120').leds_indexes
        # Configurable config path
        if config_path is None:
            self.config_path = os.environ.get('DIGITAL_LCD_CONFIG', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json'))
        else:
            self.config_path = config_path
        self.cpt = 0  # For alternate_time cycling
        self.cycle_duration = 50
        self.display_mode = None
        self.colors = np.array(["ffe000"] * NUMBER_OF_LEDS)  # Will be set in update()
        # Factory to manage displayer creation/reuse
        self.displayer = None
        self.update()

    def load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None

    def get_device(self):
        try:
            return hid.Device(self.VENDOR_ID, self.PRODUCT_ID)
        except Exception as e:
            print(f"Error initializing HID device: {e}")
            return None

    def set_leds(self, key, value):
        try:
            self.leds[self.leds_indexes[key]] = value
        except KeyError:
            print(f"Warning: Key {key} not found in leds_indexes.")

    def send_packets(self):
        message = "".join([self.colors[i] if self.leds[i] != 0 else "000000" for i in range(NUMBER_OF_LEDS)])
        packet0 = bytes.fromhex(self.HEADER+message[:128-len(self.HEADER)])
        self.dev.write(packet0)
        packets = message[88:]
        for i in range(0,4):
            packet = bytes.fromhex('00'+packets[i*128:(i+1)*128])
            self.dev.write(packet)

    def get_config_colors(self, config, key="metrics"):
        conf_colors = config.get(key, {}).get('colors', ["ffe000"] * NUMBER_OF_LEDS)
        if len(conf_colors) != NUMBER_OF_LEDS:
            print(f"Warning: config {key} colors length mismatch, using default colors.")
            colors = ["ff0000"] * NUMBER_OF_LEDS
        else:
            colors = []
            for color in conf_colors:
                if color.lower()=="random":
                    colors.append(get_random_color())
                elif "-" in color:
                    split_color = color.split("-")
                    if len(split_color) == 3:
                        start_color, end_color, key = split_color
                        current_time = datetime.datetime.now()
                        if key == "seconds":
                            factor = current_time.second / 59
                        elif key == "minutes":
                            factor = current_time.minute / 59
                        elif key == "hours":
                            factor = current_time.hour / 23
                        else:
                            metric = key
                            if metric not in self.metrics.get_metrics(self.temp_unit):
                                print(f"Warning: {metric} not found in metrics, using start color.")
                                factor = 0
                            if self.metrics_min_value[metric] == self.metrics_max_value[metric]:
                                print(f"Warning: {metric} min and max values are the same, using start color.")
                                factor = 0
                            else:
                                factor = (self.metrics.get_metrics(self.temp_unit)[metric]-self.metrics_min_value[metric]) / (self.metrics_max_value[metric]-self.metrics_min_value[metric])
                                if factor > 1:
                                    factor = 1
                                    print(f"Warning: {metric} value exceeds max value, clamping to 1.")
                                elif factor < 0:
                                    factor = 0
                                    print(f"Warning: {metric} value below min value, clamping to 0.")
                    else:
                        start_color, end_color = split_color

                        factor = 1 - abs((self.cpt%self.cycle_duration) - (self.cycle_duration/2)) / (self.cycle_duration/2)
                    
                    colors.append(interpolate_color(start_color, end_color, factor))
                else:
                    colors.append(color)
        return np.array(colors)
    
    def update(self):
        self.leds = np.array([0] * NUMBER_OF_LEDS)
        self.config = self.load_config()
        if self.config:
            VENDOR_ID = int(self.config.get('vendor_id', "0x0416"),16)
            PRODUCT_ID = int(self.config.get('product_id', "0x8001"),16)
            self.metrics_max_value = {
                "cpu_temp": self.config.get('cpu_max_temp', 90),
                "gpu_temp": self.config.get('gpu_max_temp', 90),
                "cpu_usage": self.config.get('cpu_max_usage', 100),
                "gpu_usage": self.config.get('gpu_max_usage', 100),
            }
            self.metrics_min_value = {
                "cpu_temp": self.config.get('cpu_min_temp', 30),
                "gpu_temp": self.config.get('gpu_min_temp', 30),
                "cpu_usage": self.config.get('cpu_min_usage', 0),
                "gpu_usage": self.config.get('gpu_min_usage', 0),
            }
            self.display_mode = self.config.get('display_mode', 'metrics')
            self.metrics_colors = self.get_config_colors(self.config, key="metrics")
            self.time_colors = self.get_config_colors(self.config, key="time")
            self.update_interval = self.config.get('update_interval', 0.1)
            self.cycle_duration = int(self.config.get('cycle_duration', 5)/self.update_interval)
            self.metrics.update_interval = self.config.get('metrics_update_interval', 0.5)
            # Use device_configurations to obtain leds_indexes and supported display modes
            layout_name = self.config.get('layout_mode', 'Pearless Assasin 120')
            device_conf = get_device_config(layout_name)
            self.leds_indexes = device_conf.leds_indexes
            if self.display_mode not in device_conf.display_modes:
                print(f"Warning: Display mode {self.display_mode} not compatible with {layout_name} layout, switching to a compatible mode.")
                # Prefer 'metrics' or 'alternate_metrics' if available, otherwise pick the first supported mode
                if 'metrics' in device_conf.display_modes:
                    self.display_mode = 'metrics'
                elif 'alternate_metrics' in device_conf.display_modes:
                    self.display_mode = 'alternate_metrics'
                else:
                    self.display_mode = device_conf.display_modes[0]

            # Use factory to get or reuse appropriate displayer
            self.displayer = DisplayerFactory.get_displayer(
                layout_name,
                self.leds_indexes,
                NUMBER_OF_LEDS,
                self.metrics,
                self.metrics_colors,
                self.time_colors,
                self.temp_unit,
                self.metrics_min_value,
                self.metrics_max_value,
                self.update_interval,
                self.cycle_duration,
            )
        else:
            VENDOR_ID = 0x0416
            PRODUCT_ID = 0x8001
            self.metrics_max_value = {
                "cpu_temp": 90,
                "gpu_temp": 90,
                "cpu_usage": 100,
                "gpu_usage": 100,
            }
            self.metrics_min_value = {
                "cpu_temp": 30,
                "gpu_temp": 30,
                "cpu_usage": 0,
                "gpu_usage": 0,
            }
            self.display_mode = 'metrics'
            self.time_colors = np.array(["ffe000"] * NUMBER_OF_LEDS)
            self.metrics_colors = np.array(["ff0000"] * NUMBER_OF_LEDS)
            self.update_interval = 0.1
            self.cycle_duration = int(5/self.update_interval)
            self.metrics.update_interval = 0.5
            self.leds_indexes = get_device_config('Pearless Assasin 120').leds_indexes

            # Use factory for default displayer as well
            self.displayer = DisplayerFactory.get_displayer(
                'Pearless Assasin 120',
                self.leds_indexes,
                NUMBER_OF_LEDS,
                self.metrics,
                self.metrics_colors,
                self.time_colors,
                self.temp_unit,
                self.metrics_min_value,
                self.metrics_max_value,
                self.update_interval,
                self.cycle_duration,
            )
        # Note: leds_indexes may have been updated above using device_configurations

        if VENDOR_ID != self.VENDOR_ID or PRODUCT_ID != self.PRODUCT_ID:
            print("Warning: Config VENDOR_ID or PRODUCT_ID changed, reinitializing device.")
            self.VENDOR_ID = VENDOR_ID
            self.PRODUCT_ID = PRODUCT_ID
            self.dev = self.get_device()

    def display(self):
        while True:
            self.config = self.load_config()
            self.update()
            if self.dev is None:
                print("No device found, with VENDOR_ID: {}, PRODUCT_ID: {}".format(self.VENDOR_ID, self.PRODUCT_ID))
                time.sleep(5)
            else:
                # Delegate the per-layout display construction to the displayer
                try:
                    leds_mask, colors = self.displayer.get_state(self.display_mode, self.cpt)
                    # ensure arrays are numpy arrays of correct length
                    self.leds = np.array(leds_mask, dtype=int)
                    self.colors = np.array(colors)
                except Exception as e:
                    print(f"Error generating display state: {e}")
                    # fallback to blank
                    self.leds = np.array([0] * NUMBER_OF_LEDS)
                    self.colors = np.array(["000000"] * NUMBER_OF_LEDS)

                self.cpt = (self.cpt + 1) % (self.cycle_duration*2)
                self.send_packets()
            time.sleep(self.update_interval)



def main(config_path):
    controller = Controller(config_path=config_path)
    controller.display()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        print(f"Using config path: {config_path}")
    else:
        print("No config path provided, using default.")
        config_path = None
    main(config_path)

