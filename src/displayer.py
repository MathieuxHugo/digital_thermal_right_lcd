import numpy as np
import datetime


class BaseDisplayer:
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
                 temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration):
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

    def apply_device_block(self, leds, colors, device, metrics_vals, area_key='digit_frame'):
        """Common per-device rendering: light indicator, usage, temp, frequency, power and apply area colors."""
        # light device indicator
        try:
            self._set_leds(leds, device + '_led', 1)
        except Exception:
            pass

        # usage bar
        usage = metrics_vals.get(f"{device}_usage")
        if usage is not None:
            try:
                self.set_usage(leds, usage, device=device)
            except Exception:
                pass

        # temperature
        temp = metrics_vals.get(f"{device}_temp")
        if temp is not None:
            try:
                self.set_temp(leds, temp, device=device, unit=self.temp_unit[device])
            except Exception:
                pass

        # frequency (4 digits)
        freq = metrics_vals.get(f"{device}_frequency")
        if freq is not None:
            try:
                self.set_frequency(leds, freq)
            except Exception:
                pass

        # power (3 digits)
        power = metrics_vals.get(f"{device}_power")
        if power is not None:
            try:
                self.set_power(leds, power)
            except Exception:
                pass

        # apply colors for the device area
        try:
            idxs = self.leds_indexes.get(area_key, None)
            if idxs is not None:
                colors[idxs] = self.metrics_colors[idxs]
        except Exception:
            pass

    def get_state(self, display_mode, cpt):
        # Should be implemented by subclasses
        leds = np.array([0] * self.number_of_leds)
        colors = np.array(["000000"] * self.number_of_leds)
        return leds, colors


class PA120Displayer(BaseDisplayer):
    def _apply_metrics_for(self, leds, colors, device, metrics_vals):
        # light device indicator and show metrics for device
        self._set_leds(leds, device + "_led", 1)
        self.set_temp(leds, metrics_vals.get(f"{device}_temp"), device=device, unit=self.temp_unit[device])
        self.set_usage(leds, metrics_vals.get(f"{device}_usage"), device=device)
        try:
            colors[self.leds_indexes[device]] = self.metrics_colors[self.leds_indexes[device]]
        except Exception:
            pass

    def _apply_time_for(self, leds, colors, device, now):
        # show hour+H on <device>_temp and minute on <device>_usage
        temp_key = f"{device}_temp"
        usage_key = f"{device}_usage"
        self._set_leds(leds, temp_key, np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"])))
        self._set_leds(leds, usage_key, np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten())))
        try:
            colors[self.leds_indexes[device]] = self.time_colors[self.leds_indexes[device]]
        except Exception:
            pass

    def _apply_time_with_seconds(self, leds, colors, now):
        # show hours+H on cpu_temp, minutes on cpu_usage and seconds on gpu_usage
        self._set_leds(leds, 'cpu_temp', np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"])))
        self._set_leds(leds, 'cpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten())))
        self._set_leds(leds, 'gpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.second, array_length=2, fill_value=0)].flatten())))
        try:
            colors[:] = self.time_colors
        except Exception:
            pass

    def get_state(self, display_mode, cpt):
        leds = np.array([0] * self.number_of_leds)
        colors = np.array(["000000"] * self.number_of_leds)
        metrics_vals = self.metrics.get_metrics(self.temp_unit)

        now = datetime.datetime.now()

        half = self.cycle_duration
        if display_mode == "metrics":
            for device in ["cpu", "gpu"]:
                self._apply_metrics_for(leds, colors, device, metrics_vals)
        elif display_mode == "time":
            self._apply_time_with_seconds(leds, colors, now)
        elif display_mode == "time_cpu":
            # time shown on gpu, cpu metrics on cpu
            self._apply_time_for(leds, colors, 'gpu', now)
            self._apply_metrics_for(leds, colors, 'cpu', metrics_vals)
        elif display_mode == "time_gpu":
            # time shown on cpu, gpu metrics on gpu
            self._apply_time_for(leds, colors, 'cpu', now)
            self._apply_metrics_for(leds, colors, 'gpu', metrics_vals)
        elif display_mode == "alternate_time":
            if cpt < half:
                # time on cpu, metrics on gpu
                self._apply_time_for(leds, colors, 'cpu', now)
                self._apply_metrics_for(leds, colors, 'gpu', metrics_vals)
            else:
                # time on gpu, metrics on cpu
                self._apply_time_for(leds, colors, 'gpu', now)
                self._apply_metrics_for(leds, colors, 'cpu', metrics_vals)
        elif display_mode == "alternate_time_with_seconds":
            if cpt < half:
                self._apply_time_with_seconds(leds, colors, now)
            else:
                for device in ["cpu", "gpu"]:
                    self._apply_metrics_for(leds, colors, device, metrics_vals)
        elif display_mode == "debug_ui":
            leds[:] = 1
            colors = self.metrics_colors
        else:
            # fallback to showing metrics
            for device in ["cpu", "gpu"]:
                self._apply_metrics_for(leds, colors, device, metrics_vals)

        # if not explicitly set, apply direct color arrays for full-device modes
        if np.array_equal(colors, np.array(["000000"] * self.number_of_leds)):
            # default: apply metrics colors for any leds that are lit
            lit = leds.astype(bool)
            colors[lit] = self.metrics_colors[lit]
        return leds, colors


class AX120RDisplayer(BaseDisplayer):
    def get_state(self, display_mode, cpt):
        leds = np.array([0] * self.number_of_leds)
        colors = np.array(["000000"] * self.number_of_leds)
        metrics_vals = self.metrics.get_metrics(self.temp_unit)

        if display_mode == "alternate_metrics":
            # cycle through temp cpu/gpu then usage cpu/gpu
            quarter = int(self.cycle_duration / 2)
            if cpt < quarter:
                device = 'cpu'
                self.apply_device_block(leds, colors, device, metrics_vals, area_key='digit_frame')
            elif cpt < quarter * 2:
                device = 'gpu'
                self.apply_device_block(leds, colors, device, metrics_vals, area_key='digit_frame')
            elif cpt < quarter * 3:
                device = 'cpu'
                self.apply_device_block(leds, colors, device, metrics_vals, area_key='digit_frame')
            else:
                device = 'gpu'
                self.apply_device_block(leds, colors, device, metrics_vals, area_key='digit_frame')
        elif display_mode in ("cpu_temp", "gpu_temp"):
            device = 'cpu' if display_mode == 'cpu_temp' else 'gpu'
            self.apply_device_block(leds, colors, device, metrics_vals, area_key='digit_frame')
        elif display_mode in ("cpu_usage", "gpu_usage"):
            device = 'cpu' if display_mode == 'cpu_usage' else 'gpu'
            self.apply_device_block(leds, colors, device, metrics_vals, area_key='digit_frame')
        elif display_mode == 'debug_ui':
            leds[:] = 1
            colors = self.metrics_colors
        else:
            # default to cpu temp
            device = 'cpu'
            self.apply_device_block(leds, colors, device, metrics_vals, area_key='digit_frame')

        # apply metrics colors to any lit LEDs if colors still default
        if np.array_equal(colors, np.array(["000000"] * self.number_of_leds)):
            lit = leds.astype(bool)
            colors[lit] = self.metrics_colors[lit]
        return leds, colors


class PA140Displayer(BaseDisplayer):
    def get_state(self, display_mode, cpt):
        leds = np.array([0] * self.number_of_leds)
        colors = np.array(["000000"] * self.number_of_leds)
        metrics_vals = self.metrics.get_metrics(self.temp_unit)

        if display_mode == 'gpu':
            self.apply_device_block(leds, colors, 'gpu', metrics_vals, area_key='all')
        elif display_mode == 'cpu':
            self.apply_device_block(leds, colors, 'cpu', metrics_vals, area_key='all')
        elif display_mode == 'alternate_devices':
            half = self.cycle_duration
            if cpt < half:
                self.apply_device_block(leds, colors, 'cpu', metrics_vals, area_key='all')
            else:
                self.apply_device_block(leds, colors, 'gpu', metrics_vals, area_key='all')
        elif display_mode == 'debug_ui':
            leds[:] = 1
            colors = self.metrics_colors
        else:
            self.apply_device_block(leds, colors, 'cpu', metrics_vals, area_key='all')

        if np.array_equal(colors, np.array(["000000"] * self.number_of_leds)):
            lit = leds.astype(bool)
            colors[lit] = self.metrics_colors[lit]
        return leds, colors

class PA140DisplayerBig(PA140Displayer):
    def get_state(self, display_mode, cpt):
        leds, colors = super().get_state(display_mode, cpt)
        self._set_leds(leds, 'middle_led', 1)
        self._set_leds(leds, 'right_led', 1)
        self._set_leds(leds, 'bottom_right', 1)
        return leds, colors

class DisplayerFactory:
    """Factory that returns a displayer instance. It reuses the existing instance
    if the layout type hasn't changed; otherwise it creates a new one."""
    instance = None
    current_type = None

    @classmethod
    def get_displayer(cls, layout_name, leds_indexes, number_of_leds, metrics, metrics_colors, time_colors, temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration):
        # Create new instance only if layout type changed or no instance exists
        if cls.instance is None or cls.current_type != layout_name:
            if layout_name == 'Pearless Assasin 120':
                inst = PA120Displayer(leds_indexes, number_of_leds, metrics, metrics_colors, time_colors, temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration)
            elif layout_name == 'Pearless Assasin 140':
                inst = PA140Displayer(leds_indexes, number_of_leds, metrics, metrics_colors, time_colors, temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration)
            elif layout_name == 'Pearless Assasin 140 BIG':
                inst = PA140DisplayerBig(leds_indexes, number_of_leds, metrics, metrics_colors, time_colors, temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration)
            elif layout_name == 'TR Assassin X 120R':
                inst = AX120RDisplayer(leds_indexes, number_of_leds, metrics, metrics_colors, time_colors, temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration)
            else:
                inst = PA120Displayer(leds_indexes, number_of_leds, metrics, metrics_colors, time_colors, temp_unit, metrics_min_value, metrics_max_value, update_interval, cycle_duration)
            cls.instance = inst
            cls.current_type = layout_name
        else:
            # Update existing instance's attributes when reusing
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
        return cls.instance