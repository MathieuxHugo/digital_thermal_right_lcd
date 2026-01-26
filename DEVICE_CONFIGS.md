# Device Configuration JSON Documentation

This document explains the structure and usage of device configuration JSON files in the Digital Thermal Right LCD project.

## Overview

Device configuration files define how ARGB coolers and their LED layouts are structured, which groups of LEDs display which metrics, and what display modes are available. Each configuration is device-specific and maps physical LED positions to logical groups that represent system metrics (CPU/GPU temperature, usage, frequency, power consumption, etc.).

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

The `groups` object defines logical groupings of LEDs. For example the group "cpu" represent all the led that are used for the cpu and "cpu_temp" is a subset of "cpu" containing only the leds that are used to display the cpu temperature. All leds are represented by a index between 0 and 'total_leds'.

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

- `count`: Number of digits that can be displayed
- `leds`: Specifies which physical LEDs are used for this digit display

The usage as generally the digit time eventhough the first digit can only display one as there is only two leds in it, for it to work properly the digit count must be set to 2.

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
Display modes determine how information appears on the LCD screen and define which metrics correspond to each display area. Every LED group that needs to be illuminated must be specified within the display mode. The temperature unit LEDs are managed through the "temp_unit" LED group, which is evaluated at runtime according to the configuration file.

### Display Mode Types

#### Static Mode
Displays metrics in a fixed configuration.

```json
"metrics": {
  "type": "static",
  "mappings": {
    "cpu_led": "on",
    "cpu_percent_led": "on",
    "cpu_temp_unit": "on",
    "cpu_temp": "cpu_temp",
    "cpu_usage": "cpu_usage",
    "gpu_led": "on",
    "gpu_percent_led": "on",
    "gpu_temp_unit": "on",
    "gpu_temp": "gpu_temp",
    "gpu_usage": "gpu_usage"
  }
}
```

**Properties:**
- `type`: Always `"static"`
- `mappings`: Object mapping display positions to data sources
  - **Key**: Display area name (e.g., `cpu_temp`, `gpu_usage`)
  - **Value**: Data source (metric name or special value like `"hours"`, `"minutes"`, `"seconds"` for time) or '"on"' if the led is lit independently of any data source.

#### Alternating Mode
Cycles through multiple display configurations. In this example, each display configuration may reference a different display mode; here, it alternates between the time configuration defined in this section and the metrics configuration defined above.

```json
"alternate_time": {
  "type": "alternating",
  "displays": [
    {
      "name": "time_hours",
      "mappings": {
        "cpu_temp": "hours",
        "cpu_usage": "minutes",
        "gpu_usage": "seconds"
      }
    },
    "metrics"
  ]
}
```

**Properties:**
- `type`: Always `"alternating"`
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

### Example
For an example of device configuration you can use [the pearless assasin 120 configuration](src/device_configs/pearless_assasin_120.json)

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

# Digit LED mapping : 
Each index correspond to a LED, for the digits the LED mapping the indexes correspond to the following segments :
```
 111
0   2
0   2
0   2
 333
4   6
4   6
4   6
 555
```
If you have a series of 3 digit that starts at the index 0 then the group description would be : 

```json
  "cpu_temp": {
    "type": "digit",
    "count": 3,
    "leds": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
  },
```
or 
```json
  "cpu_temp": {
    "type": "digit",
    "count": 3,
    "leds": {"type": "classic", "start": 0, "stop": 21}
  },
```

But for your device the mapping may be different.

### It may be reversed : 
```
 555
6   4
6   4
6   4
 333
2   0
2   0
2   0
 111
```

In that case the mapping would be :
```json
  "cpu_temp": {
    "type": "digit",
    "count": 3,
    "leds": [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
  },
```
or 
```json
  "cpu_temp": {
    "type": "digit",
    "count": 3,
    "leds": {"type": "reversed", "start": 20, "stop": -1}
  },
```
Note that stop is not included in the range so to get to 0 you need to set -1.


### or completely different : 
```
 000
5   1
5   1
5   1
 666
4   2
4   2
4   2
 333
```
In that case the mapping should be :
```json
  "cpu_temp": {
    "type": "digit",
    "count": 3,
    "leds": [5, 0, 1, 6, 4, 3, 2, 12,  7,  8, 13, 11, 10,  9, 19, 14, 15, 20, 18, 17, 16]
  },
```
