import numpy as np
import datetime
from metrics import Metrics

class Displayer:
    # digit and letter masks used to convert numbers to segment arrays
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
        'C': [1, 1, 0, 0, 1, 1, 0],
    }

    def __init__(self, leds_indexes, number_of_leds, metrics, metrics_colors, time_colors,
                 temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration, device_config=None):
        self.leds_indexes = leds_indexes
        self.number_of_leds = number_of_leds
        self.metrics = metrics
        self.metrics_colors = np.array(metrics_colors)
        self.time_colors = np.array(time_colors)
        self.temp_unit = temp_unit
        self.metrics_min_value = metrics_min_value
        self.metrics_max_value = metrics_max_value
        self.update_interval = update_interval
        self.cycle_duration = cycle_duration
        self.device_config = device_config

    def _number_to_array(self, number):
        number = int(number)
        if number >= 10:
            return self._number_to_array(int(number / 10)) + [number % 10]
        else:
            return [number]

    def get_number_array(self, number, array_length=3, fill_value=-1):
        if number < 0:
            return [fill_value] * array_length
        else:
            narray = self._number_to_array(number)
            if len(narray) != array_length:
                if len(narray) < array_length:
                    narray = [fill_value] * (array_length - len(narray)) + narray
                else:
                    narray = narray[1:]
            return narray

    def _set_leds(self, leds, key, value):
        # leds: numpy array representing the whole LEDs mask
        try:
            idxs = self.leds_indexes[key]
        except KeyError:
            return
        if np.isscalar(value):
            leds[idxs] = value
        else:
            leds[idxs] = value

    def clamp_metric_factor(self, metric, value):
        # compute factor between min and max for color interpolation logic used by controller.get_config_colors
        minv = self.metrics_min_value.get(metric)
        maxv = self.metrics_max_value.get(metric)
        if minv is None or maxv is None or minv == maxv:
            return 0
        factor = (value - minv) / (maxv - minv)
        if factor > 1:
            factor = 1
        elif factor < 0:
            factor = 0
        return factor

    def _apply_mapping(self, leds, led_group, data_source, time_dict):
        """Apply a single mapping: display data_source on led_group."""
        if "temp_unit" in led_group:
            unit = self.temp_unit[led_group.replace("_temp_unit", "")]
            led_group = led_group.replace("temp_unit", unit.lower())
        
        if data_source == "on":
            self._set_leds(leds, led_group, 1)
        elif data_source == "off":
            self._set_leds(leds, led_group, 0)
        elif data_source in self.letter_mask:
            self._set_leds(leds, led_group, self.letter_mask[data_source])
        else:
            value = None
            if data_source in time_dict:
                value = time_dict[data_source]
            elif data_source in Metrics.METRICS_KEYS:
                metrics_vals = self.metrics.get_metrics(self.temp_unit)
                value = int(metrics_vals[data_source])
            if value is not None:
                digit_count = self.device_config.get_digit_count(led_group)
                if digit_count<len(str(value)):
                    if len(self.leds_indexes[led_group])%7 == 0:
                        print(f"Warning: {data_source} value {value} is too large to be displayed on {led_group} as it has only {digit_count} digits (if this is a mistake, consider increasing the digit count in the device configuration).") 
                    prefix = [1]*(len(self.leds_indexes[led_group]) - digit_count*7)# one before the digits
                else:
                    prefix = [0]*(len(self.leds_indexes[led_group]) - digit_count*7)# nothing before the digits

                arr = np.concatenate([prefix, self.digit_mask[self.get_number_array(value, array_length=digit_count, fill_value=-1)].flatten()])
                self._set_leds(leds, led_group, arr)


                

    def _execute_display_config(self, leds, colors, mappings):
        """Execute a display configuration defined by mappings."""
        now = datetime.datetime.now()
        time_dict = {
            "hours": now.hour,
            "minutes": now.minute,
            "seconds": now.second,
        }
        colors = self.metrics_colors
        for led_group, data_source in mappings.items():
            if data_source in ["hours", "minutes", "seconds"]:
                colors[self.leds_indexes[led_group]] = self.time_colors[self.leds_indexes[led_group]]
            self._apply_mapping(leds, led_group, data_source, time_dict)
        

    def _get_state_from_config(self, display_mode, cpt, leds, colors):
        """Get display state using JSON-based device configuration."""
        nb_displays = 1
        display_mode_config = self.device_config.get_display_mode(display_mode)
        if not display_mode_config:
            return leds, colors
        
        if display_mode_config.type == "static":
            # Static display: apply mappings once
            mappings = display_mode_config.mode_dict.get("mappings", {})
            self._execute_display_config(leds, colors, mappings)
        
        elif display_mode_config.type == "alternating":
            # Alternating display: cycle through displays
            displays = display_mode_config.displays
            if not displays:
                return leds, colors
            nb_displays = len(displays)
            # Calculate which display to show based on cpt and interval
            display_index = (cpt // self.cycle_duration) % len(displays)
            current_display = displays[display_index]
            if isinstance(current_display, str):
                current_display = self.device_config.get_display_mode(current_display).mode_dict
            mappings = current_display.get("mappings", {})
            self._execute_display_config(leds, colors, mappings)
        
        return leds, colors, nb_displays

    def get_state(self, display_mode, cpt):
        """Get the LED state and colors for the current display mode."""
        leds = np.array([0] * self.number_of_leds)
        colors = self.metrics_colors
        
        # Use JSON-based config if available
        if self.device_config:
            return self._get_state_from_config(display_mode, cpt, leds, colors)
        
        return leds, colors


class DisplayerFactory:
    """Factory that returns a displayer instance. It reuses the existing instance
    if configuration hasn't changed; otherwise it creates a new one."""
    instance = None

    @classmethod
    def get_displayer(cls, leds_indexes, number_of_leds, metrics, metrics_colors, time_colors, temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration, device_config=None):
        # Create new instance only if no instance exists
        if cls.instance is None:
            inst = Displayer(leds_indexes, number_of_leds, metrics, metrics_colors, time_colors, temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration, device_config=device_config)
            cls.instance = inst
        else:
            # Update existing instance's attributes
            inst = cls.instance
            inst.leds_indexes = leds_indexes
            inst.number_of_leds = number_of_leds
            inst.metrics = metrics
            inst.metrics_colors = np.array(metrics_colors)
            inst.time_colors = np.array(time_colors)
            inst.temp_unit = temp_unit
            inst.metrics_min_value = metrics_min_value
            inst.metrics_max_value = metrics_max_value
            inst.update_interval = update_interval
            inst.cycle_duration = cycle_duration
            inst.device_config = device_config
        return cls.instance