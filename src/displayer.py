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
            self._set_leds(leds, device + '_temp', arr)
            if unit == "celsius":
                self._set_leds(leds, device + '_celsius', 1)
            elif unit == "fahrenheit":
                self._set_leds(leds, device + '_fahrenheit', 1)
        else:
            raise Exception("The numbers displayed on the temperature LCD must be less than 1000")

    def set_usage(self, leds, usage: int, device='cpu'):
        if usage is None:
            return
        if usage < 200:
            arr = np.concatenate(([int(usage >= 100)] * 2, self.digit_mask[self.get_number_array(usage, array_length=2)].flatten()))
            self._set_leds(leds, device + '_usage', arr)
            self._set_leds(leds, device + '_percent_led', 1)
        else:
            raise Exception("The numbers displayed on the usage LCD must be less than 200")

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

    def get_state(self, display_mode, cpt):
        # Should be implemented by subclasses
        leds = np.array([0] * self.number_of_leds)
        colors = np.array(["000000"] * self.number_of_leds)
        return leds, colors


class PA120Displayer(BaseDisplayer):
    def get_state(self, display_mode, cpt):
        leds = np.array([0] * self.number_of_leds)
        colors = np.array(["000000"] * self.number_of_leds)
        metrics_vals = self.metrics.get_metrics(self.temp_unit)

        # helper to apply metrics colors and time colors
        def apply_metrics_colors_for_device(device):
            try:
                colors[self.leds_indexes[device]] = self.metrics_colors[self.leds_indexes[device]]
            except Exception:
                pass

        def apply_time_colors_for_device(device):
            try:
                colors[self.leds_indexes[device]] = self.time_colors[self.leds_indexes[device]]
            except Exception:
                pass

        if display_mode == "metrics":
            for device in ["cpu", "gpu"]:
                self._set_leds(leds, device + "_led", 1)
                self.set_temp(leds, metrics_vals.get(f"{device}_temp"), device=device, unit=self.temp_unit[device])
                self.set_usage(leds, metrics_vals.get(f"{device}_usage"), device=device)
                apply_metrics_colors_for_device(device)
        elif display_mode == "time":
            now = datetime.datetime.now()
            self._set_leds(leds, 'cpu_temp', np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"])))
            self._set_leds(leds, 'cpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten())))
            apply_time_colors_for_device('cpu')
        elif display_mode == "time_cpu":
            # time shown on gpu, cpu metrics on cpu
            now = datetime.datetime.now()
            self._set_leds(leds, 'gpu_temp', np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"])))
            self._set_leds(leds, 'gpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten())))
            apply_time_colors_for_device('gpu')
            # cpu metrics
            self._set_leds(leds, 'cpu_led', 1)
            self.set_temp(leds, metrics_vals.get("cpu_temp"), device='cpu', unit=self.temp_unit['cpu'])
            self.set_usage(leds, metrics_vals.get("cpu_usage"), device='cpu')
            apply_metrics_colors_for_device('cpu')
        elif display_mode == "time_gpu":
            now = datetime.datetime.now()
            self._set_leds(leds, 'cpu_temp', np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"])))
            self._set_leds(leds, 'cpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten())))
            apply_time_colors_for_device('cpu')
            # gpu metrics
            self._set_leds(leds, 'gpu_led', 1)
            self.set_temp(leds, metrics_vals.get("gpu_temp"), device='gpu', unit=self.temp_unit['gpu'])
            self.set_usage(leds, metrics_vals.get("gpu_usage"), device='gpu')
            apply_metrics_colors_for_device('gpu')
        elif display_mode == "alternate_time":
            # combine time and metrics for the two halves of the cycle
            half = self.cycle_duration
            if cpt < half:
                # time (cpu) + metrics gpu
                now = datetime.datetime.now()
                self._set_leds(leds, 'cpu_temp', np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"])))
                self._set_leds(leds, 'cpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten())))
                apply_time_colors_for_device('cpu')
                # gpu metrics
                self._set_leds(leds, 'gpu_led', 1)
                self.set_temp(leds, metrics_vals.get("gpu_temp"), device='gpu', unit=self.temp_unit['gpu'])
                self.set_usage(leds, metrics_vals.get("gpu_usage"), device='gpu')
                apply_metrics_colors_for_device('gpu')
            else:
                now = datetime.datetime.now()
                self._set_leds(leds, 'gpu_temp', np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"])))
                self._set_leds(leds, 'gpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten())))
                apply_time_colors_for_device('gpu')
                # cpu metrics
                self._set_leds(leds, 'cpu_led', 1)
                self.set_temp(leds, metrics_vals.get("cpu_temp"), device='cpu', unit=self.temp_unit['cpu'])
                self.set_usage(leds, metrics_vals.get("cpu_usage"), device='cpu')
                apply_metrics_colors_for_device('cpu')
        elif display_mode == "time_with_seconds" or display_mode == "alternate_time_with_seconds":
            # original project used 'time' variants with seconds; mimic a simple behavior
            now = datetime.datetime.now()
            # show hours+H on cpu_temp and minutes/seconds on usage fields
            self._set_leds(leds, 'cpu_temp', np.concatenate((self.digit_mask[self.get_number_array(now.hour, array_length=2, fill_value=0)].flatten(), self.letter_mask["H"])))
            self._set_leds(leds, 'cpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.minute, array_length=2, fill_value=0)].flatten())))
            self._set_leds(leds, 'gpu_usage', np.concatenate(([0, 0], self.digit_mask[self.get_number_array(now.second, array_length=2, fill_value=0)].flatten())))
            colors = self.time_colors
        elif display_mode == "debug_ui":
            leds[:] = 1
            colors = self.metrics_colors
        else:
            # fallback to showing metrics
            for device in ["cpu", "gpu"]:
                self._set_leds(leds, device + "_led", 1)
                self.set_temp(leds, metrics_vals.get(f"{device}_temp"), device=device, unit=self.temp_unit[device])
                self.set_usage(leds, metrics_vals.get(f"{device}_usage"), device=device)
                apply_metrics_colors_for_device(device)

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
                self.set_temp(leds, metrics_vals.get(f'{device}_temp'), device=device, unit=self.temp_unit[device])
                self._set_leds(leds, device + '_led', 1)
                colors[self.leds_indexes.get('digit_frame', [])] = self.metrics_colors[self.leds_indexes.get('digit_frame', [])]
            elif cpt < quarter * 2:
                device = 'gpu'
                self.set_temp(leds, metrics_vals.get(f'{device}_temp'), device=device, unit=self.temp_unit[device])
                self._set_leds(leds, device + '_led', 1)
                colors[self.leds_indexes.get('digit_frame', [])] = self.metrics_colors[self.leds_indexes.get('digit_frame', [])]
            elif cpt < quarter * 3:
                device = 'cpu'
                self.set_usage(leds, metrics_vals.get(f'{device}_usage'), device=device)
                self._set_leds(leds, device + '_led', 1)
                colors[self.leds_indexes.get('digit_frame', [])] = self.metrics_colors[self.leds_indexes.get('digit_frame', [])]
            else:
                device = 'gpu'
                self.set_usage(leds, metrics_vals.get(f'{device}_usage'), device=device)
                self._set_leds(leds, device + '_led', 1)
                colors[self.leds_indexes.get('digit_frame', [])] = self.metrics_colors[self.leds_indexes.get('digit_frame', [])]
        elif display_mode in ("cpu_temp", "gpu_temp"):
            device = 'cpu' if display_mode == 'cpu_temp' else 'gpu'
            self.set_temp(leds, metrics_vals.get(f'{device}_temp'), device=device, unit=self.temp_unit[device])
            self._set_leds(leds, device + '_led', 1)
            colors[self.leds_indexes.get('digit_frame', [])] = self.metrics_colors[self.leds_indexes.get('digit_frame', [])]
        elif display_mode in ("cpu_usage", "gpu_usage"):
            device = 'cpu' if display_mode == 'cpu_usage' else 'gpu'
            self.set_usage(leds, metrics_vals.get(f'{device}_usage'), device=device)
            self._set_leds(leds, device + '_led', 1)
            colors[self.leds_indexes.get('digit_frame', [])] = self.metrics_colors[self.leds_indexes.get('digit_frame', [])]
        elif display_mode == 'debug_ui':
            leds[:] = 1
            colors = self.metrics_colors
        else:
            # default to cpu temp
            device = 'cpu'
            self.set_temp(leds, metrics_vals.get(f'{device}_temp'), device=device, unit=self.temp_unit[device])
            self._set_leds(leds, device + '_led', 1)
            colors[self.leds_indexes.get('digit_frame', [])] = self.metrics_colors[self.leds_indexes.get('digit_frame', [])]

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

        def apply_device_block(device):
            # Simplified PA140 display: light up device led and show usage bar
            self._set_leds(leds, device + '_led', 1)
            usage = metrics_vals.get(f"{device}_usage")
            if usage is not None:
                # map usage to number of leds in 'usage' bar
                try:
                    idxs = self.leds_indexes['usage']
                    length = len(idxs)
                    on = int((usage / 100.0) * length)
                    # set the last `on` leds as lit (indexes already reversed in config)
                    bar = np.array([1] * on + [0] * (length - on))
                    self._set_leds(leds, 'usage', bar)
                    self._set_leds(leds, 'percent_led', 1)
                except Exception:
                    pass
            # temperature as a simple indicator: light celsius/fahrenheit led
            temp = metrics_vals.get(f"{device}_temp")
            if temp is not None:
                if self.temp_unit[device] == 'celsius':
                    self._set_leds(leds, 'celsius', 1)
                else:
                    self._set_leds(leds, 'fahrenheit', 1)
            # apply colors for the device area
            try:
                colors[self.leds_indexes['all']] = self.metrics_colors[self.leds_indexes['all']]
            except Exception:
                pass

        if display_mode == 'gpu':
            apply_device_block('gpu')
        elif display_mode == 'cpu':
            apply_device_block('cpu')
        elif display_mode == 'alternate_devices':
            half = self.cycle_duration
            if cpt < half:
                apply_device_block('cpu')
            else:
                apply_device_block('gpu')
        elif display_mode == 'debug_ui':
            leds[:] = 1
            colors = self.metrics_colors
        else:
            apply_device_block('cpu')

        if np.array_equal(colors, np.array(["000000"] * self.number_of_leds)):
            lit = leds.astype(bool)
            colors[lit] = self.metrics_colors[lit]
        return leds, colors
