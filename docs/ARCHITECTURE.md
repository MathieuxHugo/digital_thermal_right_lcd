# Architecture

This document describes the module structure of the `digital-thermal-right-lcd` application, the responsibilities of each component, how data flows between them, and how to extend the system.

---

## Table of Contents

1. [Overview](#overview)
2. [Module Map](#module-map)
3. [Data Flow](#data-flow)
4. [Module Reference](#module-reference)
   - [config_parser.py](#config_parserpy)
   - [displayer.py](#displayerpy)
   - [controller.py](#controllerpy)
   - [led_display_ui.py](#led_display_uipy)
   - [device_configurations.py](#device_configurationspy)
   - [metrics.py](#metricspy)
   - [utils.py](#utilspy)
5. [Color Specification Format](#color-specification-format)
6. [Device Configuration Format](#device-configuration-format)
7. [Adding a New Device](#adding-a-new-device)
8. [Adding a New Display Mode](#adding-a-new-display-mode)
9. [Testing](#testing)

---

## Overview

The application reads system metrics (CPU/GPU temperature, usage, NVMe I/O…) and renders them as RGB colours on a Thermal Right ARGB USB cooler. The same rendering pipeline is shared between:

- **The controller** (`controller.py`) — sends colours to the physical device over USB HID.
- **The Tkinter UI** (`led_display_ui.py`) — previews the colour layout on screen without hardware.

Both paths call `Displayer.get_state()`, which is the single authoritative implementation of "what should each LED show right now".

```
config.json ──► config_parser ──► ParsedConfig
                                        │
                  ┌─────────────────────┤
                  │                     │
              Displayer ◄─── Metrics / NullMetrics
                  │
        ┌─────────┴─────────┐
        │                   │
   Controller          LEDDisplayUI
  (HID device)         (Tkinter UI)
```

---

## Module Map

| File | Responsibility |
|------|---------------|
| `config_parser.py` | Load, validate, and normalise `config.json` → `ParsedConfig` |
| `displayer.py` | Compute per-LED effective colour array (`Displayer`, `ColorResolver`, `NullMetrics`) |
| `controller.py` | Main display loop + USB HID packet sending |
| `led_display_ui.py` | Tkinter configuration UI + live preview |
| `device_configurations.py` | Load per-device layout JSON, expose LED groups and display modes |
| `metrics.py` | Collect live system metrics (CPU, GPU, NVMe…) |
| `utils.py` | Colour math helpers (`interpolate_color`, `get_random_color`) |
| `config.py` | Default `config.json` values used as fallbacks |

---

## Data Flow

### Controller path (one display tick)

```
1. load_parsed_config(config_path)
        └─► resolve_config_path       # normalise None / dir / file path
        └─► json.load                 # read config.json from disk
        └─► parse_config_from_dict    # validate → ParsedConfig

2. Displayer(cfg, metrics).get_state(display_mode, cpt)
        └─► datetime.datetime.now()   # wall-clock snapshot (patchable in tests)
        └─► ColorResolver.resolve(metrics_color_specs, cpt, cycle_ticks, now)
        │       └─► metrics.get_metrics(temp_unit)  # ONE sensor call per frame
        │       └─► _resolve_one() × n_leds         # static / random / gradient
        └─► ColorResolver.resolve(time_color_specs, ...)
        └─► _apply_display_mode(...)  # LED mask + colour override for time groups
        └─► np.where(led_mask, led_colors, "000000")
        └─► returns (effective_colors, nb_displays)

3. Controller.send_packets(effective_colors, update_interval)
        └─► "".join(effective_colors) # flat hex string
        └─► zero-pad to MINIMUM_MESSAGE_LENGTH
        └─► split into 128-char HID packets and write to device
```

### UI path (one preview tick)

```
1. parse_config_from_dict(self.config, self.config_dir)
        └─► same validation logic as controller, but from in-memory dict

2. Displayer(cfg, NullMetrics()).get_state(self.display_mode.get(), cpt)
        └─► identical rendering pipeline, NullMetrics returns 0 for all values

3. self.set_ui_color(i, "#" + effective_colors[i])  for each LED
        └─► updates Tkinter canvas squares directly
```

---

## Module Reference

### config_parser.py

**Purpose:** The single source of truth for application configuration.

#### `ParsedConfig` (dataclass)

A typed, validated snapshot of `config.json`. Fields:

| Field | Type | Description |
|-------|------|-------------|
| `device_config` | `DeviceConfig` | Loaded device layout object |
| `layout_mode` | `str` | Human-readable device name |
| `display_mode` | `str` | Active display mode (guaranteed to exist in `device_config`) |
| `metrics_color_specs` | `list[str]` | Per-LED colour specs for metric-driven groups |
| `time_color_specs` | `list[str]` | Per-LED colour specs for time-driven groups |
| `temp_unit` | `dict` | `{"cpu": "celsius"/"fahrenheit", "gpu": "celsius"/"fahrenheit"}` |
| `metrics_min_value` | `dict` | Lower bound per metric key for gradient normalisation |
| `metrics_max_value` | `dict` | Upper bound per metric key |
| `update_interval` | `float` | Seconds between display ticks |
| `metrics_update_interval` | `float` | Seconds between metric reads |
| `cycle_duration` | `float` | Seconds for one animation / alternating-display cycle |
| `vendor_id` | `int` | USB vendor ID |
| `product_id` | `int` | USB product ID |
| `nvme_disk` | `Optional[str]` | NVMe disk name for `psutil`, or `None` |

#### `load_parsed_config(config_path=None)`

Reads `config.json` from disk and returns a `ParsedConfig`. `config_path` may be:
- `None` → reads `$DIGITAL_LCD_CONFIG`, or `<project_root>/conf/config.json`
- a directory → appends `/config.json`
- a `.json` file → used directly

Errors are non-fatal: a warning is printed and the default value is used.

#### `parse_config_from_dict(raw, config_dir=None)`

The canonical validation logic, shared by both `load_parsed_config` and the Tkinter UI. The UI calls this directly with its in-memory dict, avoiding a disk round-trip.

#### Error policy

Any inconsistency (unknown display mode, colour list length mismatch) is auto-corrected with a `Warning:` log line. The application never crashes due to a bad config.

---

### displayer.py

**Purpose:** Compute per-LED effective colours for a single display frame. This is where "which LEDs are lit" meets "what colour should they be".

#### `NullMetrics`

A drop-in stub for `Metrics` that returns `0` for every metric key. Used by the Tkinter UI so the preview loop works without hardware sensors. Metric-keyed gradients always show the start colour (factor = 0) in the preview.

#### `ColorResolver`

Resolves raw colour specification strings to concrete six-character hex colours.

Construction:
```python
resolver = ColorResolver(metrics, metrics_min_value, metrics_max_value, temp_unit)
```

`resolve(color_specs, cpt, cycle_ticks, now)` → `np.ndarray`
- Calls `metrics.get_metrics()` **once** per frame to avoid multiple sensor reads.
- Delegates each spec string to `_resolve_one()`.

`_resolve_one(spec, cpt, cycle_ticks, now, current_metrics)` → `str`
- Dispatches based on spec format (see [Color Specification Format](#color-specification-format)).

`_key_to_factor(key, now, current_metrics)` → `float`
- Converts a time or metric key to a `[0.0, 1.0]` interpolation factor.
- Time: `seconds/59`, `minutes/59`, `hours/23`.
- Metric: `clamp((value - min) / (max - min), 0, 1)`.

#### `Displayer`

The public rendering interface. Owns:
- `_DIGIT_MASK` — 7-segment patterns for digits 0–9 plus blank.
- `_LETTER_MASK` — single-letter patterns (`"H"`, `"C"`).
- A `ColorResolver` instance.

`get_state(display_mode, cpt)` → `(effective_colors, nb_displays)`
1. Calls `datetime.datetime.now()` once (injectable via `patch("displayer.datetime")` in tests).
2. Resolves both colour palettes (metrics + time) via `ColorResolver`.
3. Builds a zero-initialised `led_mask` and a copy of `metrics_colors` as `led_colors`.
4. Calls `_apply_display_mode()` to populate the mask and override colours for time groups.
5. Returns `np.where(led_mask != 0, led_colors, "000000")`.

`_apply_display_mode()` handles:
- **`"static"`** modes — a single fixed mapping applied directly.
- **`"alternating"`** modes — multiple sub-displays cycled by `cpt // cycle_ticks`.

`_apply_mappings()` iterates over `{led_group: data_source}` pairs and:
- Expands `"cpu_temp_unit"` / `"gpu_temp_unit"` placeholders to `"cpu_celsius"` etc.
- Switches to the time colour palette for groups driven by time values.
- Delegates to `_apply_one_mapping()`.

`_apply_one_mapping()` writes into `led_mask`:
- `"on"` / `"off"` → scalar 1 or 0.
- Letter key → letter segment pattern.
- Time key → 7-segment encoded time value.
- Metric key → 7-segment encoded metric value.

`_encode_number(led_group, value)` → `np.ndarray`:
- Looks up the digit count for the group.
- Pads value with leading blanks or truncates most-significant digit.
- If the group has non-digit leading LEDs and the value overflows, sets them to 1 as an overflow indicator.

---

### controller.py

**Purpose:** Owns exactly two concerns: the main display loop and USB HID packet sending.

#### `Controller`

```python
controller = Controller(config_path=None)
controller.display()   # runs forever
```

`display()` (main loop):
1. `load_parsed_config(self.config_path)` — picks up live config edits without restart.
2. Reinitialises the HID device if vendor/product IDs changed in config.
3. If device is unavailable, waits 5 s and retries.
4. `Displayer(cfg, self.metrics).get_state(cfg.display_mode, self.cpt)`.
5. `send_packets(effective_colors, cfg.update_interval)`.
6. Increments `cpt` modulo `cycle_ticks × nb_displays`.

`send_packets(effective_colors, update_interval)`:
1. Joins `effective_colors` into a flat hex string.
2. Zero-pads with `FF` bytes to `MINIMUM_MESSAGE_LENGTH` (504 hex chars).
3. Writes first 64-byte packet: `HID_HEADER (20 bytes) || payload slice`.
4. Writes subsequent packets: `0x00 || 64-byte slice` with inter-packet delays.

#### HID packet format

```
Packet 0:  dadbdcdd000000000000000000000000fc0000ff  || payload[0:44]
Packet n:  00 || payload[44 + (n-1)*64 : 44 + n*64]
```

Each packet is written as raw bytes to the HID device. The total payload must be at least 252 bytes (504 hex chars).

---

### led_display_ui.py

**Purpose:** Tkinter GUI for editing `config.json` and previewing the LED layout in real time.

The UI stores `config.json` as an in-memory dict (`self.config`) and writes it back to disk when the user saves. Configuration changes are validated immediately via `parse_config_from_dict`.

#### Preview loop (`update_ui_loop`)

Runs in a background thread:

```python
cfg = parse_config_from_dict(self.config, self.config_dir)
displayer = Displayer(cfg, NullMetrics())
effective_colors, nb_displays = displayer.get_state(self.display_mode.get(), cpt)
for i in range(self.number_of_leds):
    self.set_ui_color(i, "#" + effective_colors[i])
```

The Tkinter canvas shows only lit LEDs (non-black), exactly matching what the controller sends to the device. Off-LEDs appear black in both.

---

### device_configurations.py

**Purpose:** Load and expose device-specific LED layout and display mode configuration.

Each device has a JSON file in `conf/` (e.g. `conf/pearless_assasin_120.json`). The file defines:
- `total_leds` — total LED count.
- `groups` — named LED groups, each with an index list/range and optional `type: "digit"` with `count`.
- `display_modes` — named modes, each `"static"` or `"alternating"`.

`get_device_config(config_name, config_path=None)` → `DeviceConfig`
- Looks up `<config_name.lower().replace(' ', '_')>.json`.
- Falls back to `pearless_assasin_120.json` with a warning if not found.

`DeviceConfig` exposes:
- `leds_indexes: dict[str, list[int]]` — LED indices per group name.
- `digit_count: dict[str, int]` — digit count per digit group.
- `display_modes: dict[str, DisplayMode]` — available modes.
- `get_digit_count(group_name)` → `int`.
- `get_display_mode(mode_name)` → `DisplayMode | None`.

---

### metrics.py

**Purpose:** Collect live system metrics, caching results between calls to avoid hammering sensors.

`Metrics.get_metrics(temp_unit)` → `dict`
Returns values for all keys in `Metrics.METRICS_KEYS`:

```
cpu_temp, gpu_temp, cpu_usage, gpu_usage,
cpu_frequency, gpu_frequency, cpu_power, gpu_power,
nvme_temp, nvme_read_speed, nvme_write_speed, nvme_usage
```

Sensor reads are rate-limited by `Metrics.update_interval` (configurable from `config.json`). Between updates the cached value from the last read is returned.

`NullMetrics` (in `displayer.py`) is the stub that returns `0` for all keys — used by the UI and in tests.

---

### utils.py

**Purpose:** Pure colour math helpers.

`interpolate_color(start_hex, end_hex, factor)` → `str`
Linear interpolation between two hex colours. `factor=0` → start, `factor=1` → end.

`get_random_color()` → `str`
Returns a random six-character hex colour string.

---

## Color Specification Format

Each entry in `metrics.colors` and `time.colors` in `config.json` describes how one LED should be coloured. Four formats are supported:

| Format | Example | Behaviour |
|--------|---------|-----------|
| `"rrggbb"` | `"ff4400"` | Static hex colour, never changes |
| `"random"` | `"random"` | New random colour on every frame |
| `"start-end"` | `"00d9d9-d8d900"` | Animated: factor sweeps 0→1→0 over `cycle_duration` |
| `"start-end-key"` | `"00d9d9-ffd900-seconds"` | Gradient driven by a time or metric key |

Valid keys for the third form:

| Key | Range | Factor formula |
|-----|-------|---------------|
| `seconds` | 0–59 | `second / 59` |
| `minutes` | 0–59 | `minute / 59` |
| `hours` | 0–23 | `hour / 23` |
| `cpu_temp` | configurable | `(value − min) / (max − min)` |
| `gpu_temp` | configurable | same |
| `cpu_usage` | 0–100 | same |
| `gpu_usage` | 0–100 | same |
| any `METRICS_KEYS` entry | configurable | same |

---

## Device Configuration Format

Device JSON files live in `conf/`. Filename must match `device_name.lower().replace(' ', '_') + ".json"`.

```jsonc
{
  "name": "Pearless Assasin 120",
  "total_leds": 84,
  "groups": {
    // Simple list of indices
    "ring": [0, 1, 2, 3],

    // Continuous range (start inclusive, stop exclusive)
    "cpu_d2": { "type": "classic", "start": 0, "stop": 14 },

    // Reversed range (start inclusive, stop exclusive, descending)
    "cpu_d1": { "type": "reversed", "start": 13, "stop": -1 },

    // Digit group — drives 7-segment encoding
    "cpu_usage": { "type": "digit", "count": 2, "leds": { "type": "classic", "start": 14, "stop": 28 } }
  },
  "display_modes": {
    "metrics": {
      "name": "metrics",
      "type": "static",
      "mappings": {
        "cpu_usage":     "cpu_usage",
        "cpu_temp_unit": "cpu_temp",
        "ring":          "on"
      }
    },
    "alternate_metrics": {
      "name": "alternate_metrics",
      "type": "alternating",
      "displays": ["metrics", "time"]
    }
  }
}
```

### Mapping data sources

| Value | Effect |
|-------|--------|
| `"on"` | All LEDs in the group are lit |
| `"off"` | All LEDs in the group are dark |
| `"H"`, `"C"` | Display the letter pattern (7-segment) |
| `"hours"`, `"minutes"`, `"seconds"` | Display the time value as 7-segment digits; uses time colour palette |
| any `METRICS_KEYS` entry | Display the metric value as 7-segment digits; uses metrics colour palette |

### Temperature unit placeholder

Group names containing `"temp_unit"` are expanded at render time:
- `"cpu_temp_unit"` → `"cpu_celsius"` or `"cpu_fahrenheit"` based on config.
- `"gpu_temp_unit"` → `"gpu_celsius"` or `"gpu_fahrenheit"`.

This means a device config only needs to define groups for both units once; the controller selects the right group automatically.

---

## Adding a New Device

1. Create `conf/<device_name_slug>.json` following the format above.
   The slug is `device_name.lower().replace(' ', '_')`.

2. Add the human-readable name to `CONFIG_NAMES` in `device_configurations.py`.

3. Add test cases for the new device in `tests/helpers.py` (`ALL_TEST_CASES`).

4. Run `python tests/generate_references.py --devices "New Device Name"` to create reference files.

5. Run `pytest` to verify the new tests pass.

---

## Adding a New Display Mode

1. Add the mode definition to the device's JSON file under `display_modes`.

2. If the mode references LED groups that do not yet exist, add them under `groups`.

3. If the mode is meant to be a default fallback, update `_validate_display_mode()` in `config_parser.py`.

4. Add test cases for the new mode in `tests/helpers.py`.

5. Re-run `python tests/generate_references.py` to capture the new references.

---

## Testing

### Non-regression tests for `Displayer.get_state`

The test suite lives in `tests/`. It uses JSON snapshot testing: reference files are generated once and checked into the repository; the test suite compares live output against the snapshots on every run.

#### Directory structure

```
tests/
  helpers.py              # shared fixtures, test-case table, run_get_state()
  generate_references.py  # CLI script to create/refresh reference files
  test_get_state.py       # parametrized pytest tests
  references/
    pearless_assasin_120/
      metrics_normal.json
      metrics_edge.json
      time_normal.json
      time_edge.json
    ...
```

#### Reference file schema

```json
{
  "effective_colors": ["ff4400", "000000", "00ff88", ...],
  "nb_displays": 1
}
```

`effective_colors[i]` is the resolved hex colour for LED `i` (`"000000"` = off).

#### Test cases

Each case in `ALL_TEST_CASES` is a 6-tuple:

```
(device_name, display_mode, scenario, metrics_values, mock_time, cpt)
```

Two scenarios per device+mode:
- **`normal`** — realistic mid-range metric values, `14:30:45`.
- **`edge`** — maximum values (`cpu_usage=100`, `cpu_temp=999`, …), `23:59:59`.

#### Running the tests

```bash
# Generate / refresh reference files (only needed after code changes that alter rendering)
python tests/generate_references.py

# Run the test suite
pytest

# Run for a single device
pytest -k "Pearless_Assasin_120"
```

#### Mocking strategy

`run_get_state()` in `helpers.py`:
- Constructs a `ParsedConfig` with deterministic per-LED colour specs (unique colour per LED position, easily spotted in diffs).
- Uses `unittest.mock.MagicMock` for `Metrics`, configured to return the scenario's metric dict.
- Patches `displayer.datetime` so `datetime.datetime.now()` returns the fixed `mock_time`.
- Returns `{"effective_colors": [...], "nb_displays": int}`.
