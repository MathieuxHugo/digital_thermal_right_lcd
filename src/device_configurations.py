class PA120Config():
    leds_indexes = {# pearless assassin 120 ARGB
        "all": list(range(0, 84)),
        "cpu": list(range(0, 42)),
        "gpu": list(range(42, 84)),
        "cpu_led": [0, 1],
        "cpu_temp": list(range(2, 23)),
        "cpu_celsius": 23,
        "cpu_fahrenheit": 24,
        "cpu_usage": list(range(25, 41)),
        "cpu_percent_led": 41,
        "gpu_led": [82, 83],
        "gpu_temp": list(range(81, 60, -1)),
        "gpu_celsius": 59,
        "gpu_fahrenheit": 60,
        "gpu_usage": list(range(58, 42, -1)),
        "gpu_percent_led": 42,
    }
    display_modes = [
        "alternate_time",
        "metrics",
        "time",
        "time_cpu",
        "time_gpu",
        "alternate_time_with_seconds",
        "debug_ui",
    ]

class PA140Config():
    leds_indexes = {
        "percent_led": 0,
        "usage": list(range(16, 0, -1)),
        "frequency": list(range(44, 16,-1)),
        "cpu_led": 53,
        "gpu_led": 59,
        # temp indexes (shared structure) - also expose per-device aliases for set_temp
        "temp": [49, 50, 51, 48, 45, 46, 47, 57, 58, 60, 56, 52, 54, 55, 65, 66, 67, 64, 61, 62, 63],
        "cpu_temp": [49, 50, 51, 48, 45, 46, 47, 57, 58, 60, 56, 52, 54, 55, 65, 66, 67, 64, 61, 62, 63],
        "gpu_temp": [49, 50, 51, 48, 45, 46, 47, 57, 58, 60, 56, 52, 54, 55, 65, 66, 67, 64, 61, 62, 63],
        "celsius": 68,
        "fahrenheit": 69,
        "watt": [74, 75, 76, 73, 70, 71, 72, 81, 82, 83, 80, 77, 78, 79, 88, 89, 90, 87, 84, 85, 86],
        "watt_led": 91,
        "frequency_led": 92,
        "all": list(range(0, 93)),
        # per-device usage aliases so set_usage can use device+'_usage'
        "cpu_usage": list(range(16, 0, -1)),
        "gpu_usage": list(range(16, 0, -1)),
    }

    display_modes = [
        "gpu",
        "cpu",
        "alternate_devices",
        "debug_ui",
    ]
class AX120RConfig():
    leds_indexes = {# Thermalright Assassin X 120R ARGB
        "all": list(range(0, 31)),
        "digit_frame": [14, 9, 10, 15, 13, 12, 11, 21, 16, 17, 22, 20, 19, 18, 28, 23, 24, 29, 27, 26, 25],
        "celsius": 6,
        "fahrenheit": 7,
        "percent_led": 8,
        "gpu_led": [4, 5],
        "cpu_led": [2, 3],
    }

    display_modes = [
        "alternate_metrics",
        "cpu_temp",
        "gpu_temp",
        "cpu_usage",
        "gpu_usage",
        "debug_ui",
    ]

CONFIG_NAMES = [
    'Pearless Assasin 120',
    'Pearless Assasin 140',
    'TR Assassin X 120R',
]

def get_device_config(config_name):
    if config_name == 'Pearless Assasin 120':
        return PA120Config()
    elif config_name == 'Pearless Assasin 140':
        return PA140Config()
    elif config_name == 'TR Assassin X 120R':
        return AX120RConfig()
    else:
        print(f"Warning: Unknown configuration '{config_name}'. Defaulting to Pearless Assasin 120.")
        return PA120Config()