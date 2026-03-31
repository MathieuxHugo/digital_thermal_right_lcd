# Device Configuration JSON Documentation

This document explains the structure and usage of device configuration JSON files.

## Overview

Device configuration files define how ARGB coolers and their LED layouts are structured, which groups of LEDs display which metrics, and what display modes are available.  Each configuration is device-specific and maps physical LED positions to logical groups that represent system metrics (CPU/GPU temperature, usage, frequency, power consumption, etc.).

## File Structure

```json
{
  "name": "Device Name",
  "total_leds": 84,
  "groups": { ... },
  "ui_layout": { ... },
  "display_modes": { ... }
}
```

---

## Root Properties

### `name` (String, Required)
Human-readable name of the device.

### `total_leds` (Integer, Required)
Total number of addressable LEDs (valid indices: 0 to `total_leds - 1`).

---

## Groups Section

The `groups` object defines logical groupings of LEDs.  Every LED is addressed by its zero-based index within the device's LED strip.

### Group Types

#### 1. Single LED (Integer)
```json
"cpu_led": 0
```

#### 2. Multiple Specific LEDs (Array)
```json
"gpu_led": [82, 83]
```

#### 3. LED Range Group
```json
"all": {
  "type": "leds",
  "leds": {"type": "classic", "start": 0, "stop": 84}
}
```

#### 4. Digit Display Group
Used for multi-digit 7-segment displays (temperature, usage, frequency, …).  Contains 7 LEDs per digit × `count` digits.

```json
"cpu_temp": {
  "type": "digit",
  "count": 3,
  "leds": {"type": "classic", "start": 2, "stop": 23}
}
```

- `count`: Number of digits.
- `leds`: LED range or explicit array covering all 7 × count segments.

### LED Range Specifications

| Field   | Meaning |
|---------|---------|
| `type`  | `"classic"` (forward) or `"reversed"` (backward) |
| `start` | First LED index (inclusive) |
| `stop`  | Exclusive end index (use `-1` to reach LED 0 with `reversed`) |

**Classic** — LEDs start, start+1, …, stop-1
**Reversed** — LEDs start, start-1, …, stop+1

---

## Digit LED Mapping

Each digit uses exactly 7 LEDs, one per segment.  The physical wiring order determines which segment index maps to which position.

### Canonical order (top-to-bottom, left-to-right)

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

Segment indices within one digit:

| Index | Segment      |
|-------|--------------|
| 0     | top-left vertical |
| 1     | top horizontal |
| 2     | top-right vertical |
| 3     | middle horizontal |
| 4     | bottom-left vertical |
| 5     | bottom horizontal |
| 6     | bottom-right vertical |

**Example** — 3 digits, LEDs 0–20, canonical order:
```json
"cpu_temp": {
  "type": "digit",
  "count": 3,
  "leds": {"type": "classic", "start": 0, "stop": 21}
}
```

### Reversed order

Some devices wire LEDs from bottom to top:

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

```json
"cpu_temp": {
  "type": "digit",
  "count": 3,
  "leds": {"type": "reversed", "start": 20, "stop": -1}
}
```

### Arbitrary / non-sequential order

When LEDs are not laid out sequentially, supply an explicit array.  The first 7 elements correspond to digit 1 (leftmost), the next 7 to digit 2, and so on.

Example layout:
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

```json
"cpu_temp": {
  "type": "digit",
  "count": 3,
  "leds": [5, 0, 1, 6, 4, 3, 2, 12, 7, 8, 13, 11, 10, 9, 19, 14, 15, 20, 18, 17, 16]
}
```

---

## `ui_layout` Section

`ui_layout` drives the configuration UI.  It declares a grid-based canvas on which LED groups are positioned at explicit `(x, y)` coordinates.

### Top-level fields

```json
"ui_layout": {
  "grid_width":  17,
  "grid_height":  9,
  "color_modes": ["metrics"],
  "placements": [ ... ]
}
```

| Field         | Type    | Description |
|---------------|---------|-------------|
| `grid_width`  | Integer | Canvas width in grid units |
| `grid_height` | Integer | Canvas height in grid units |
| `color_modes` | Array   | Palette names the user can edit (e.g. `["metrics", "time"]`) |
| `placements`  | Array   | List of placement objects (see below) |

Each grid unit is rendered as **25 px**.

### Sizing rules (for authoring)

These are *conventions* for keeping the grid tidy; they are not enforced at runtime:

| Placement type | Width (grid units) | Height (grid units) |
|----------------|--------------------|---------------------|
| `digit` with N digits | N × 2 (+ 1 if `overflow_leds > 0`) | 4 |
| `label` with text T | len(T) | 1 |
| `leds` strip | depends on `orientation` and count | depends on `led_height` |

### Validation (enforced at runtime)

1. No two placements may overlap.
2. The union of all placed groups' LED indices must cover every index that appears in the device's display modes.

> Groups that are only used as *sub-targets* within `display_modes` (e.g. `two_first_digit`, `four_first_digit` on the HR-10) do not need a placement of their own, as long as their LED indices are covered by another placed group.

---

### Placement types

#### `digit` — 7-segment display

```json
{
  "type": "digit",
  "group": "cpu_temp",
  "x": 0,
  "y": 1,
  "overflow_leds": 0,
  "led_offset": 0
}
```

| Field           | Default | Description |
|-----------------|---------|-------------|
| `group`         | —       | Group name (must be a `"type": "digit"` group) |
| `x`, `y`        | —       | Top-left corner in grid units |
| `overflow_leds` | `0`     | Extra single-LED canvases prepended to the left (e.g. a "100s" overflow LED) |
| `led_offset`    | `0`     | Index within the group's LED list where the digit rendering starts (used when `overflow_leds > 0`) |

#### `label` — Text label mapped to one LED

```json
{
  "type": "label",
  "group": "cpu_celsius",
  "text": "°C",
  "led_index": null,
  "x": 6,
  "y": 1
}
```

| Field       | Default | Description |
|-------------|---------|-------------|
| `group`     | —       | Group name |
| `text`      | `"?"`   | Label text (displayed in white) |
| `led_index` | `null`  | `null` → group's first LED; integer → `group[led_index]` |
| `x`, `y`    | —       | Top-left corner in grid units |

#### `leds` — Plain rectangular LED strip

```json
{
  "type": "leds",
  "group": "middle_led",
  "orientation": "horizontal",
  "led_width": 23,
  "led_height": 8,
  "led_indices": null,
  "x": 0,
  "y": 5
}
```

| Field         | Default       | Description |
|---------------|---------------|-------------|
| `group`       | —             | Group name |
| `orientation` | `"horizontal"` | `"horizontal"` or `"vertical"` |
| `led_width`   | 23            | Canvas width per LED (pixels) |
| `led_height`  | 8             | Canvas height per LED (pixels) |
| `led_indices` | `null`        | `null` → all group LEDs; array → subset by within-group position |
| `x`, `y`      | —             | Top-left corner in grid units |

---

### Full `ui_layout` example

```json
"ui_layout": {
  "grid_width": 17,
  "grid_height": 9,
  "color_modes": ["metrics"],
  "placements": [
    {"type": "label",  "group": "cpu_led",       "text": "CPU", "x": 0,  "y": 0},
    {"type": "label",  "group": "gpu_led",       "text": "GPU", "x": 12, "y": 0},
    {"type": "digit",  "group": "temp",                         "x": 0,  "y": 1},
    {"type": "label",  "group": "celsius",       "text": "°C",  "x": 6,  "y": 1},
    {"type": "label",  "group": "fahrenheit",    "text": "°F",  "x": 6,  "y": 2},
    {"type": "digit",  "group": "watt",                         "x": 8,  "y": 1},
    {"type": "label",  "group": "watt_led",      "text": "W",   "x": 14, "y": 1},
    {"type": "digit",  "group": "frequency",                    "x": 0,  "y": 5},
    {"type": "label",  "group": "frequency_led", "text": "MHz", "x": 8,  "y": 5},
    {
      "type": "digit", "group": "usage",
      "overflow_leds": 2, "led_offset": 2,
      "x": 11, "y": 5
    },
    {"type": "label",  "group": "percent_led",   "text": "%",   "x": 16, "y": 5}
  ]
}
```

---

## Display Modes Section

Display modes determine what is shown on the LCD and which metric maps to each group.

### Static Mode

```json
"cpu": {
  "type": "static",
  "mappings": {
    "cpu_led": "on",
    "temp":    "cpu_temp",
    "watt":    "cpu_watt"
  }
}
```

- `mappings` keys: group names.
- `mappings` values: metric source name, `"on"` (always lit), or a letter/special string.

### Alternating Mode

```json
"alternate_devices": {
  "type": "alternating",
  "interval": 5,
  "displays": [
    {
      "name": "cpu_metrics",
      "mappings": {"temp": "cpu_temp", "watt": "cpu_watt"}
    },
    {
      "name": "gpu_metrics",
      "mappings": {"temp": "gpu_temp", "watt": "gpu_watt"}
    }
  ]
}
```

`displays` entries may also be strings that reference another top-level display mode by name.

### Mapping Values

| Value | Source |
|-------|--------|
| `"on"` | LED always lit |
| `"cpu_temp"` | CPU temperature |
| `"gpu_temp"` | GPU temperature |
| `"cpu_usage"` | CPU usage % |
| `"gpu_usage"` | GPU usage % |
| `"cpu_frequency"` | CPU frequency (MHz) |
| `"gpu_frequency"` | GPU frequency (MHz) |
| `"cpu_watt"` | CPU power (W) |
| `"gpu_watt"` | GPU power (W) |
| `"nvme_temp"` | NVMe temperature |
| `"nvme_read_speed"` | NVMe read speed (MB/s) |
| `"nvme_write_speed"` | NVMe write speed (MB/s) |
| `"nvme_usage"` | NVMe usage % |
| `"hours"` | Current hour (00–23) |
| `"minutes"` | Current minute (00–59) |
| `"seconds"` | Current second (00–59) |
| `"H"`, `"C"`, … | Literal character shown on a digit segment |
| `"debug"` | Debug test pattern |

---

## Creating a New Device Configuration

1. **Map the LEDs** — document total LED count, physical positions, and wiring order.
2. **Define groups** — decide which LEDs display which metrics; use digit groups for 7-segment displays.
3. **Determine the digit segment order** — wire up segments using the canonical, reversed, or array form above.
4. **Write `ui_layout`** — choose grid dimensions and place each group at `(x, y)`.  Use the sizing rules to avoid overlaps.
5. **Write `display_modes`** — define at least one static mode and an alternating mode if needed.
6. **Register the file** — add the JSON filename to `device_configurations.py` (or equivalent registry).

See [`conf/pearless_assasin_120.json`](../conf/pearless_assasin_120.json) and [`conf/thermalright_hr-10_2280_pro.json`](../conf/thermalright_hr-10_2280_pro.json) for complete real-world examples.
