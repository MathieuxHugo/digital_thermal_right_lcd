# Device Configuration JSON Documentation

This document explains the structure and usage of device configuration JSON files in the Digital Thermal Right LCD project.

## Overview

Device configuration files define how ARGB coolers and their LED layouts are structured, which groups of LEDs display which metrics, and what display modes are available. Each configuration is device-specific and maps physical LED positions to logical groups.

## File Structure

Each device configuration JSON file contains three main sections:

```json
{
  "name": "Device Name",
  "total_leds": 84,
  "groups": { ... },
  "display_modes": { ... }
}
```

## Root Properties

### `name` (String, Required)
The human-readable name of the device.

```json
"name": "Pearless Assassin 120 ARGB"
```

### `total_leds` (Integer, Required)
The total number of addressable LEDs on the device. This defines the valid range for LED indices (0 to `total_leds - 1`).

```json
"total_leds": 84
```

---

## Groups Section

The `groups` object defines logical groupings of LEDs. Groups serve two purposes:
1. **Display groups**: Map physical LEDs to metrics (temperature, usage, etc.)
2. **LED range groups**: Define ranges of LEDs for bulk operations

### Group Types

#### 1. Single LED (Integer)
A single LED specified by its index.

```json
"cpu_led": 0
```

#### 2. Multiple Specific LEDs (Array)
An array of LED indices.

```json
"gpu_led": [82, 83]
```

#### 3. LED Range Group
A named group that references a range of LEDs using a range specification.

```json
"all": {
  "type": "leds",
  "leds": {"type": "classic", "start": 0, "stop": 84}
}
```

#### 4. Digit Display Group
A group used to display multi-digit numbers (temperature, usage percentage, etc.). Contains 7 segments per digit multiplied by digit count.

```json
"cpu_temp": {
  "type": "digit",
  "count": 3,
  "leds": {"type": "classic", "start": 2, "stop": 23}
}
```

- `count`: Number of digits to display
- `leds`: Specifies which physical LEDs are used for this digit display

### LED Range Specifications

LED ranges use `start` and `stop` properties. The range includes LEDs from `start` up to (but not including) `stop`.

#### Classic Range
Continuous forward range of LEDs.

```json
{"type": "classic", "start": 0, "stop": 42}
```
**Result**: LEDs 0, 1, 2, ..., 41 (42 total LEDs)

#### Reversed Range
Continuous backward range of LEDs. Useful when physical LEDs are arranged in reverse order.

```json
{"type": "reversed", "start": 81, "stop": 60}
```
**Result**: LEDs 81, 80, 79, ..., 61 (21 total LEDs, counting down)

### Metric Display Groups

Certain group names are reserved and used by the display logic to show specific metrics:

| Group Name | Purpose | Type |
|---|---|---|
| `cpu_temp` / `gpu_temp` | Temperature display (7-segment digits) | Digit |
| `cpu_usage` / `gpu_usage` | Usage percentage display (7-segment digits) | Digit |
| `cpu_celsius` / `gpu_celsius` | Single LED for Celsius indicator | Integer |
| `cpu_fahrenheit` / `gpu_fahrenheit` | Single LED for Fahrenheit indicator | Integer |
| `cpu_percent_led` / `gpu_percent_led` | Single LED for percentage indicator | Integer |
| `cpu_led` / `gpu_led` | Status indicator for CPU/GPU | Integer or Array |

### Example Groups Section

```json
"groups": {
  "all": {
    "type": "leds",
    "leds": {"type": "classic", "start": 0, "stop": 84}
  },
  "cpu": {
    "type": "leds",
    "leds": {"type": "classic", "start": 0, "stop": 42}
  },
  "gpu": {
    "type": "leds",
    "leds": {"type": "classic", "start": 42, "stop": 84}
  },
  "cpu_led": [0, 1],
  "cpu_temp": {
    "type": "digit",
    "count": 3,
    "leds": {"type": "classic", "start": 2, "stop": 23}
  },
  "cpu_celsius": 23,
  "cpu_fahrenheit": 24,
  "cpu_usage": {
    "type": "digit",
    "count": 2,
    "leds": {"type": "classic", "start": 25, "stop": 41}
  }
}
```

---

## Display Modes Section

Display modes define how information is shown on the LCD screen and which metrics are mapped to which display areas.

### Display Mode Types

#### Static Mode
Displays metrics in a fixed configuration.

```json
"metrics": {
  "type": "static",
  "mappings": {
    "cpu_temp": "cpu_temp",
    "cpu_usage": "cpu_usage",
    "gpu_temp": "gpu_temp",
    "gpu_usage": "gpu_usage"
  }
}
```

**Properties:**
- `type`: Always `"static"`
- `mappings`: Object mapping display positions to data sources
  - **Key**: Display area name (e.g., `cpu_temp`, `gpu_usage`)
  - **Value**: Data source (metric name or special value like `"hours"`, `"minutes"`, `"seconds"` for time)

#### Alternating Mode
Cycles between multiple display configurations at a specified interval.

```json
"alternate_time": {
  "type": "alternating",
  "interval": 5,
  "displays": [
    {
      "name": "time_hours",
      "mappings": {
        "cpu_temp": "hours",
        "cpu_usage": "minutes",
        "gpu_usage": "seconds"
      }
    },
    {
      "name": "metrics",
      "mappings": {
        "cpu_temp": "cpu_temp",
        "cpu_usage": "cpu_usage",
        "gpu_temp": "gpu_temp",
        "gpu_usage": "gpu_usage"
      }
    }
  ]
}
```

**Properties:**
- `type`: Always `"alternating"`
- `interval`: Seconds between switching displays
- `displays`: Array of display configurations, each with:
  - `name`: Identifier for this display configuration
  - `mappings`: Same structure as static mode mappings

### Mapping Values

The `mappings` object connects display areas to data sources. Common values include:

| Value | Source |
|---|---|
| `"cpu_temp"` | Current CPU temperature |
| `"gpu_temp"` | Current GPU temperature |
| `"cpu_usage"` | Current CPU usage percentage |
| `"gpu_usage"` | Current GPU usage percentage |
| `"hours"` | Current hour (00-23) |
| `"minutes"` | Current minute (00-59) |
| `"seconds"` | Current second (00-59) |
| `"debug"` | Debug display (shows test patterns) |
| `"cpu_frequency"` | CPU frequency (MHz) |
| `"gpu_frequency"` | GPU frequency (MHz) |
| `"cpu_watt"` | CPU power consumption (W) |
| `"gpu_watt"` | GPU power consumption (W) |

### Example Display Modes Section

```json
"display_modes": {
  "metrics": {
    "type": "static",
    "mappings": {
      "cpu_temp": "cpu_temp",
      "cpu_usage": "cpu_usage",
      "gpu_temp": "gpu_temp",
      "gpu_usage": "gpu_usage"
    }
  },
  "time": {
    "type": "static",
    "mappings": {
      "cpu_temp": "hours",
      "cpu_usage": "minutes",
      "gpu_usage": "seconds"
    }
  },
  "alternate_time": {
    "type": "alternating",
    "interval": 5,
    "displays": [
      {
        "name": "time_display",
        "mappings": {
          "cpu_temp": "hours",
          "cpu_usage": "minutes",
          "gpu_usage": "seconds"
        }
      },
      {
        "name": "metrics_display",
        "mappings": {
          "cpu_temp": "cpu_temp",
          "cpu_usage": "cpu_usage",
          "gpu_temp": "gpu_temp",
          "gpu_usage": "gpu_usage"
        }
      }
    ]
  },
  "debug_ui": {
    "type": "static",
    "mappings": {
      "cpu_temp": "debug",
      "cpu_usage": "debug",
      "gpu_temp": "debug",
      "gpu_usage": "debug"
    }
  }
}
```

---

## Complete Example

Here's a minimal but complete device configuration:

```json
{
  "name": "Example Cooler 120",
  "total_leds": 50,
  "groups": {
    "all": {
      "type": "leds",
      "leds": {"type": "classic", "start": 0, "stop": 50}
    },
    "cpu_led": 0,
    "gpu_led": 1,
    "cpu_temp": {
      "type": "digit",
      "count": 2,
      "leds": {"type": "classic", "start": 2, "stop": 16}
    },
    "cpu_celsius": 16,
    "cpu_usage": {
      "type": "digit",
      "count": 2,
      "leds": {"type": "classic", "start": 17, "stop": 31}
    },
    "cpu_percent_led": 31,
    "gpu_temp": {
      "type": "digit",
      "count": 2,
      "leds": {"type": "reversed", "start": 49, "stop": 35}
    },
    "gpu_celsius": 34,
    "gpu_usage": {
      "type": "digit",
      "count": 2,
      "leds": {"type": "reversed", "start": 33, "stop": 19}
    },
    "gpu_percent_led": 18
  },
  "display_modes": {
    "metrics": {
      "type": "static",
      "mappings": {
        "cpu_temp": "cpu_temp",
        "cpu_usage": "cpu_usage",
        "gpu_temp": "gpu_temp",
        "gpu_usage": "gpu_usage"
      }
    },
    "time": {
      "type": "static",
      "mappings": {
        "cpu_temp": "hours",
        "cpu_usage": "minutes",
        "gpu_temp": "seconds",
        "gpu_usage": "cpu_temp"
      }
    },
    "debug_ui": {
      "type": "static",
      "mappings": {
        "cpu_temp": "debug",
        "cpu_usage": "debug",
        "gpu_temp": "debug",
        "gpu_usage": "debug"
      }
    }
  }
}
```

---

## Creating a New Device Configuration

### Step 1: Identify LED Layout
Map out the physical LED layout of your device. Document:
- Total number of LEDs
- Which LED indices correspond to which physical locations
- LED order (forward or reverse)

### Step 2: Plan LED Groups
Define which LEDs display which metrics:
- Which LEDs show CPU temperature
- Which LEDs show GPU temperature
- Which LEDs show usage percentages
- Indicator LEDs for status

### Step 3: Calculate Ranges
For continuous ranges, use `start` and `stop`:
- `start`: First LED index (inclusive)
- `stop`: Last LED index + 1 (exclusive)
- For reversed ranges, `start` > `stop` and count backwards

Example:
- LEDs 2-22 (21 total) for CPU temp: `{"type": "classic", "start": 2, "stop": 23}`
- LEDs 81 down to 61 (21 total) for GPU temp: `{"type": "reversed", "start": 81, "stop": 60}`

### Step 4: Define Display Modes
Choose which display modes to support:
- **Metrics**: Show system metrics
- **Time**: Show current time
- **Alternating**: Cycle between modes
- **Debug**: Test pattern for development

### Step 5: Create JSON File
Save as `device_configs/{device_name_lowercase}.json` in the project.

---

## Validation Tips

When creating or modifying configurations:

1. **LED Count**: Ensure digit groups have exactly `count * 7` LEDs
2. **Range Bounds**: Verify `start` and `stop` values are within `[0, total_leds)`
3. **No Overlaps**: Avoid assigning the same LED to multiple display metrics (overlaps are allowed for indicator LEDs)
4. **Mappings**: Verify all mapping values reference valid data sources
5. **Reversals**: Double-check reversed ranges count downward correctly

---

## Implementation Details

### How Configurations are Loaded

The `device_configurations.py` module provides the following functions:

- `load_device_config_from_json(json_path)`: Load a config from a JSON file
- `get_device_config(config_name)`: Load a config by name (auto-converts to filename)
- `_parse_led_range(range_spec)`: Parse LED range specifications into index lists
- `_expand_led_group(group_spec)`: Expand group specifications into LED lists

### Range Parsing Logic

**Classic Range:**
```
start: 2, stop: 23  →  [2, 3, 4, ..., 21, 22]  (21 LEDs)
```

**Reversed Range:**
```
start: 81, stop: 60  →  [81, 80, 79, ..., 61]  (21 LEDs)
```

