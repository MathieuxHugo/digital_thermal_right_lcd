import numpy as np
import datetime


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

    def get_number_array(self, temp, array_length=3, fill_value=-1):
        if temp < 0:
            return [fill_value] * array_length
        else:
            narray = self._number_to_array(temp)
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

    def set_temp(self, leds, temperature: int, device='cpu', unit="celsius"):
        if temperature is None:
            return
        if temperature < 1000:
            arr = self.digit_mask[self.get_number_array(temperature)].flatten()
            # try device-specific key first, fall back to generic keys
            self._set_leds(leds, device + '_temp', arr)
            self._set_leds(leds, 'temp', arr)
            # device-specific unit leds
            if unit == "celsius":
                self._set_leds(leds, device + '_celsius', 1)
                # fallback generic
                self._set_leds(leds, 'celsius', 1)
            elif unit == "fahrenheit":
                self._set_leds(leds, device + '_fahrenheit', 1)
                self._set_leds(leds, 'fahrenheit', 1)
        else:
            raise Exception("The numbers displayed on the temperature LCD must be less than 1000")

    def set_usage(self, leds, usage: int, device='cpu'):
        if usage is None:
            return
        if usage < 200:
            arr = np.concatenate(([int(usage >= 100)] * 2, self.digit_mask[self.get_number_array(usage, array_length=2)].flatten()))
            # try device-specific usage first, fallback handled inside _set_leds
            self._set_leds(leds, device + '_usage', arr)
            self._set_leds(leds, 'usage', arr)
            # try device specific percent led and generic percent led
            self._set_leds(leds, device + '_percent_led', 1)
            self._set_leds(leds, 'percent_led', 1)
        else:
            raise Exception("The numbers displayed on the usage LCD must be less than 200")

    def set_frequency(self, leds, frequency: int):
        """Display frequency on the 4-digit frequency field and light the frequency unit LED."""
        if frequency is None:
            return
        # frequency displayed on 4 digits (4 * 7 = 28 LEDs)
        arr = self.digit_mask[self.get_number_array(frequency, array_length=4)].flatten()
        self._set_leds(leds, 'frequency', arr)
        # light the frequency unit led if present
        self._set_leds(leds, 'frequency_led', 1)

    def set_power(self, leds, power: int):
        """Display power (watts) on the 3-digit watt field and light the watt unit LED."""
        if power is None:
            return
        arr = self.digit_mask[self.get_number_array(power, array_length=3)].flatten()
        self._set_leds(leds, 'watt', arr)
        self._set_leds(leds, 'watt_led', 1)

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

    def _apply_mapping(self, leds, colors, led_group, data_source, metrics_vals, now):
        """Apply a single mapping: display data_source on led_group."""
        if data_source == "debug":
            # Debug mode: light all LEDs for this group
            self._set_leds(leds, led_group, 1)
            return
        
        if data_source == "hours":
            arr = np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"]))
            self._set_leds(leds, led_group, arr)
        elif data_source == "minutes":
            arr = np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten()))
            self._set_leds(leds, led_group, arr)
        elif data_source == "seconds":
            arr = np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.second, array_length=2, fill_value=0)].flatten()))
            self._set_leds(leds, led_group, arr)
        elif data_source in metrics_vals:
            value = metrics_vals[data_source]
            if value is None:
                return
            
            # Determine how to display the metric based on the LED group type
            if "temp" in led_group:
                try:
                    self.set_temp(leds, value, device=led_group.replace('_temp', ''), unit=self.temp_unit.get(led_group.replace('_temp', ''), "celsius"))
                except:
                    # Fallback: treat as generic 3-digit number
                    arr = self.digit_mask[self.get_number_array(value, array_length=3)].flatten()
                    self._set_leds(leds, led_group, arr)
            elif "usage" in led_group:
                try:
                    self.set_usage(leds, value, device=led_group.replace('_usage', ''))
                except:
                    # Fallback: treat as 2-digit percentage
                    arr = np.concatenate(([int(value >= 100)] * 2, self.digit_mask[self.get_number_array(value, array_length=2)].flatten()))
                    self._set_leds(leds, led_group, arr)
            elif "frequency" in led_group:
                try:
                    self.set_frequency(leds, value)
                except:
                    # Fallback: treat as 4-digit number
                    arr = self.digit_mask[self.get_number_array(value, array_length=4)].flatten()
                    self._set_leds(leds, led_group, arr)
            elif "watt" in led_group or "power" in led_group:
                try:
                    self.set_power(leds, value)
                except:
                    # Fallback: treat as 3-digit number
                    arr = self.digit_mask[self.get_number_array(value, array_length=3)].flatten()
                    self._set_leds(leds, led_group, arr)
            else:
                # Generic numeric display: determine array length based on LED group
                try:
                    idxs = self.leds_indexes.get(led_group)
                    if idxs:
                        array_length = len(idxs) // 7  # Assume 7 LEDs per digit
                        arr = self.digit_mask[self.get_number_array(value, array_length=array_length)].flatten()
                        self._set_leds(leds, led_group, arr)
                except:
                    pass

    def _execute_display_config(self, leds, colors, mappings, metrics_vals, now, is_time_display=False):
        """Execute a display configuration defined by mappings."""
        for led_group, data_source in mappings.items():
            self._apply_mapping(leds, colors, led_group, data_source, metrics_vals, now)
        
        # Apply colors
        try:
            if is_time_display:
                lit = leds.astype(bool)
                colors[lit] = self.time_colors[lit]
            else:
                lit = leds.astype(bool)
                colors[lit] = self.metrics_colors[lit]
        except:
            pass

    def _get_state_from_config(self, display_mode, cpt, leds, colors):
        """Get display state using JSON-based device configuration."""
        metrics_vals = self.metrics.get_metrics(self.temp_unit)
        now = datetime.datetime.now()
        
        display_mode_config = self.device_config.get_display_mode(display_mode)
        if not display_mode_config:
            return leds, colors
        
        if display_mode_config.type == "static":
            # Static display: apply mappings once
            mappings = display_mode_config.mode_dict.get("mappings", {})
            is_time = any(src in ["hours", "minutes", "seconds"] for src in mappings.values())
            self._execute_display_config(leds, colors, mappings, metrics_vals, now, is_time_display=is_time)
        
        elif display_mode_config.type == "alternating":
            # Alternating display: cycle through displays
            displays = display_mode_config.displays
            if not displays:
                return leds, colors
            
            # Calculate which display to show based on cpt and interval
            interval_ticks = int(display_mode_config.interval / self.update_interval)
            display_index = (cpt // interval_ticks) % len(displays)
            current_display = displays[display_index]
            
            mappings = current_display.get("mappings", {})
            is_time = any(src in ["hours", "minutes", "seconds"] for src in mappings.values())
            self._execute_display_config(leds, colors, mappings, metrics_vals, now, is_time_display=is_time)
        
        return leds, colors

    def get_state(self, display_mode, cpt):
        """Get the LED state and colors for the current display mode."""
        leds = np.array([0] * self.number_of_leds)
        colors = np.array(["000000"] * self.number_of_leds)
        
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