import json
import os
from pathlib import Path


def _parse_led_range(range_spec):
    """
    Parse a range specification into a list of indices.
    
    Args:
        range_spec: Can be:
            - A list: returned as-is
            - A dict with "type": "classic", "start", "stop"
            - A dict with "type": "reversed", "start", "stop"
    
    Returns:
        List of LED indices
    """
    if isinstance(range_spec, list):
        return range_spec
    
    if isinstance(range_spec, dict):
        range_type = range_spec.get("type", "classic")
        
        if range_type == "classic":
            # Continuous range: start to stop
            start = range_spec.get("start", 0)
            stop = range_spec.get("stop", 1)
            return list(range(start, stop))
        
        elif range_type == "reversed":
            # Reversed range: start down to stop with step
            start = range_spec.get("start", 0)
            stop = range_spec.get("stop", 0)
            return list(range(start, stop, -1))
    
    return []


def _expand_led_group(group_spec):
    """
    Expand a group specification into LED indices.
    
    A group can be:
    - An integer (single LED)
    - A list of integers (specific LEDs)
    - A dict with "type": "digit" or "leds" and range specification
    """
    if isinstance(group_spec, int):
        return group_spec
    
    if isinstance(group_spec, list):
        return group_spec
    
    if isinstance(group_spec, dict):
        group_type = group_spec.get("type", "leds")
        
        if group_type == "digit":
            # A digit is 7 LEDs
            num_digits = group_spec.get("count", 1)
            led_range = _parse_led_range(group_spec.get("leds", []))
            # For digits, the range should contain 7*num_digits elements
            return led_range
        
        elif group_type == "leds":
            # Direct LED specification
            return _parse_led_range(group_spec.get("leds", []))
    
    return []


class DisplayMode:
    """Represents a display mode configuration."""
    
    def __init__(self, mode_dict):
        self.mode_dict = mode_dict
        self.name = mode_dict.get("name", "")
        self.type = mode_dict.get("type", "static")  # "static" or "alternating"
        self.displays = mode_dict.get("displays", [])
        self.interval = mode_dict.get("interval", 5)  # For alternating modes
    
    def get_display_groups(self):
        """Get the group mappings for this display mode."""
        return self.displays


class DeviceConfig:
    """Represents a device configuration loaded from JSON."""
    
    def __init__(self, config_dict):
        self.config_dict = config_dict
        self.leds_indexes = self._build_leds_indexes()
        self.display_modes = self._build_display_modes()
    
    def _build_leds_indexes(self):
        """Build the leds_indexes dictionary from the JSON config."""
        leds_indexes = {}
        groups = self.config_dict.get("groups", {})
        
        for group_name, group_spec in groups.items():
            leds_indexes[group_name] = _expand_led_group(group_spec)
        
        return leds_indexes
    
    def _build_display_modes(self):
        """Build the display_modes dictionary from the JSON config."""
        display_modes_dict = {}
        modes = self.config_dict.get("display_modes", {})
        
        if isinstance(modes, dict):
            for mode_name, mode_spec in modes.items():
                display_modes_dict[mode_name] = DisplayMode(mode_spec)
        elif isinstance(modes, list):
            # For backward compatibility with list of mode names
            for mode_name in modes:
                display_modes_dict[mode_name] = DisplayMode({"name": mode_name})
        
        return display_modes_dict
    
    def get_display_mode(self, mode_name):
        """Get a display mode by name."""
        return self.display_modes.get(mode_name)
    
    def get_mode_names(self):
        """Get list of available display mode names."""
        return list(self.display_modes.keys())


def load_device_config_from_json(json_path):
    """Load a device configuration from a JSON file."""
    try:
        with open(json_path, 'r') as f:
            config_dict = json.load(f)
        return DeviceConfig(config_dict)
    except Exception as e:
        print(f"Error loading config from {json_path}: {e}")
        return None


def get_device_config(config_name, config_path=None):
    """Get a device configuration by name."""
    # Build path to config file
    if config_path:
        config_dir = Path(config_path).parent/"src"/"device_configs"
    else:
        config_dir = Path(__file__).parent / "device_configs"
    
    config_file = config_dir / f"{config_name.lower().replace(' ', '_')}.json"
    
    if config_file.exists():
        config = load_device_config_from_json(config_file)
        if config:
            return config
    
    print(f"Warning: Configuration '{config_name}' not found. Defaulting to Pearless Assasin 120.")
    # Fallback to default
    default_file = config_dir / "pearless_assasin_120.json"
    if default_file.exists():
        return load_device_config_from_json(default_file)
    
    # If no files available, return empty config
    return DeviceConfig({"groups": {}, "display_modes": {}})


# Device names for UI
CONFIG_NAMES = [
    'Pearless Assasin 120',
    'Pearless Assasin 140',
    'TR Assassin X 120R',
    'Pearless Assasin 140 BIG',
]