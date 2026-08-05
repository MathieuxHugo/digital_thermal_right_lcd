import json
import os
from pathlib import Path


def _parse_led_range(range_spec, group_name):
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
            if start > stop:
                raise ValueError(f"The mapping of {group_name} is wrong : For 'classic' range, start should be < stop.")
            return list(range(start, stop))
        
        elif range_type == "reversed":
            # Reversed range: start down to stop with step
            start = range_spec.get("start", 0)
            stop = range_spec.get("stop", 0)
            if start < stop:
                raise ValueError(f"The mapping of {group_name} is wrong : For 'reversed' range, stop should be < start.")

            return list(range(start, stop, -1))
    
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
        self.leds_indexes, self.digit_count = self._build_leds_indexes()
        self.display_modes = self._build_display_modes()
    
    def _build_leds_indexes(self):
        """Build the leds_indexes dictionary from the JSON config."""
        leds_indexes = {}
        digit_count = {}
        groups = self.config_dict.get("groups", {})
        for group_name, group_spec in groups.items():
            if isinstance(group_spec, dict):
                leds_indexes[group_name] = _parse_led_range(group_spec.get("leds", []), group_name)
                if group_spec.get("type", "") == "digit":
                    digit_count[group_name] = group_spec.get("count", 3)
            else:
                leds_indexes[group_name] = group_spec
        return leds_indexes, digit_count
    
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
    
    def get_digit_count(self, group_name):
        """Get the number of digit in a led group."""
        if group_name not in self.digit_count:
            return 3  # Default
        else:
            return self.digit_count[group_name]

    def get_display_mode(self, mode_name):
        """Get a display mode by name."""
        return self.display_modes.get(mode_name)
    
    def get_mode_names(self):
        """Get list of available display mode names."""
        return list(self.display_modes.keys())


def load_device_config_from_json(json_path):
    """Load a device configuration from a JSON file."""
    with open(json_path, 'r') as f:
        config_dict = json.load(f)
    return DeviceConfig(config_dict)


def _get_device_name(json_file):
    """Get the display name of a device config file.
    The 'name' field inside the JSON is used if present, otherwise the
    display name is derived from the filename."""
    try:
        with open(json_file) as fh:
            data = json.load(fh)
        return data.get('name', json_file.stem.replace('_', ' ').title())
    except Exception:
        return json_file.stem.replace('_', ' ').title()


def _iter_device_config_files(config_path):
    """Yield (name, path) for each device config file in the conf/ directory.
    Each JSON file in conf/ (except config.json) defines a supported device."""
    conf_dir = Path(config_path)
    for f in sorted(conf_dir.glob('*.json')):
        if f.name in ('config.json', 'config.example.json'):
            continue
        yield _get_device_name(f), f


def list_available_devices(config_path):
    """Return list of device names available in the conf/ directory."""
    return [name for name, _ in _iter_device_config_files(config_path)]

def get_device_config(config_name, config_path=None):
    """Get a device configuration by name."""
    # Build path to config file
    if config_path:
        config_dir = Path(config_path)
    else:
        config_dir = Path(__file__).parent.parent / "conf"

    if config_name:
        for name, config_file in _iter_device_config_files(config_dir):
            if name.lower() == config_name.lower():
                return load_device_config_from_json(config_file)

    available = list_available_devices(config_dir)
    raise RuntimeError(
        f"Failed to load config.json from {config_dir}. "
        f"Create config.json with 'layout_mode' set to one of: {available}"
    )