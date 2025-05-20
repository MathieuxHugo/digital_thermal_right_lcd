leds_indexes = {
    "all" : list(range(0, 84)),
    "cpu" : list(range(0, 42)),
    "gpu" : list(range(42, 84)),
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

NUMBER_OF_LEDS = 84