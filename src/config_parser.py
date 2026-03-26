"""
config_parser.py
================

Responsible for loading, validating, and exposing the application configuration
stored in ``config.json``.

Public surface
--------------
``ParsedConfig``
    Typed dataclass holding every configuration value the rest of the application
    needs.  All raw JSON strings have been converted to their proper Python types.
    The device layout has been resolved to a :class:`~device_configurations.DeviceConfig`
    object, and the requested display mode has been verified against the modes
    that the chosen device actually supports.

``load_parsed_config(config_path)``
    Read ``config.json`` from a file or directory path, validate it, and return
    a ``ParsedConfig``.  Any detected inconsistency (unknown display mode, colour
    list length mismatch, …) is reported as a warning and automatically corrected
    so callers never have to handle a partially-configured state.

``parse_config_from_dict(raw, config_dir)``
    Same validation logic, but operates on an already-loaded dict.  Used by the
    Tkinter UI, which manages its own in-memory config state and only wants to
    convert it to a ``ParsedConfig`` without touching the file system.

``resolve_config_path(config_path)``
    Normalise the *config_path* parameter, which may be:

    * ``None``         → ``DIGITAL_LCD_CONFIG`` env-var, or project ``conf/``
    * a directory path → ``<dir>/config.json``
    * a file path      → used directly

    Always returns an absolute ``pathlib.Path`` to the ``.json`` file.

Error policy
------------
Validation errors are non-fatal: the parser logs a ``Warning:`` message and
applies a sensible default.  This lets the application recover gracefully from
hand-edited configs, truncated colour lists, or display modes that were
available on a previous device but not on the currently selected one.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import default_config
from device_configurations import DeviceConfig, get_device_config


# ---------------------------------------------------------------------------
# Typed configuration container
# ---------------------------------------------------------------------------

@dataclass
class ParsedConfig:
    """
    Validated, typed application configuration.

    Attributes
    ----------
    device_config:
        Fully parsed device-layout object loaded from the appropriate JSON file
        in ``conf/``.  Provides ``leds_indexes``, ``display_modes``, etc.
    layout_mode:
        Human-readable device name (e.g. ``"Pearless Assasin 120"``).
    display_mode:
        The active display mode, guaranteed to exist in ``device_config``.
    metrics_color_specs:
        Per-LED colour specification strings for the *metrics* colour palette.
        Length equals ``device_config.config_dict["total_leds"]``.
        Each entry is one of:

        * ``"rrggbb"``              — static hex colour
        * ``"random"``              — new random colour each frame
        * ``"start-end"``           — animated gradient driven by the tick counter
        * ``"start-end-key"``       — gradient keyed on time (``seconds`` /
          ``minutes`` / ``hours``) or a metric name (``cpu_temp``, etc.)

    time_color_specs:
        Same format as ``metrics_color_specs``, but used for LED groups that
        display time values (hours, minutes, seconds).
    temp_unit:
        Temperature unit per device: ``{"cpu": "celsius"|"fahrenheit",
        "gpu": "celsius"|"fahrenheit"}``.
    metrics_min_value:
        Lower bound for each metric, used to normalise colour-gradient factors.
        Keys: ``cpu_temp``, ``gpu_temp``, ``cpu_usage``, ``gpu_usage``.
    metrics_max_value:
        Upper bound for each metric.  Same keys as ``metrics_min_value``.
    update_interval:
        Seconds between consecutive LED-state updates.
    metrics_update_interval:
        Seconds between consecutive metric-collection calls.
    cycle_duration:
        Raw duration in *seconds* of one animation/alternating-display cycle.
        Convert to ticks with ``int(cycle_duration / update_interval)``.
    vendor_id:
        USB vendor ID of the HID device.
    product_id:
        USB product ID of the HID device.
    nvme_disk:
        Optional disk name passed to ``psutil.disk_io_counters`` for NVMe stats
        (e.g. ``"nvme0n1"``).  ``None`` means "use the default".
    """

    device_config: DeviceConfig
    layout_mode: str
    display_mode: str
    metrics_color_specs: list
    time_color_specs: list
    temp_unit: dict
    metrics_min_value: dict
    metrics_max_value: dict
    update_interval: float
    metrics_update_interval: float
    cycle_duration: float
    vendor_id: int
    product_id: int
    nvme_disk: Optional[str] = None


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def resolve_config_path(config_path: Optional[str]) -> Path:
    """
    Return the absolute path to the ``config.json`` file.

    Accepts any of:

    * ``None``        → ``$DIGITAL_LCD_CONFIG/config.json``, or
                        ``<project_root>/conf/config.json``
    * directory path  → ``<dir>/config.json``
    * ``.json`` file  → used as-is

    Parameters
    ----------
    config_path:
        Raw path string provided by the caller, or ``None`` for auto-detection.

    Returns
    -------
    pathlib.Path
        Absolute, resolved path to the config file.
    """
    if config_path is None:
        env = os.environ.get("DIGITAL_LCD_CONFIG")
        base = Path(env) if env else Path(__file__).parent.parent / "conf"
    else:
        base = Path(config_path)

    # If it looks like a directory (no .json suffix) or is actually a dir
    if base.suffix != ".json":
        base = base / "config.json"

    return base.resolve()


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

def load_parsed_config(config_path: Optional[str] = None) -> ParsedConfig:
    """
    Load, parse, and validate ``config.json``.

    Parameters
    ----------
    config_path:
        Path to the directory that contains ``config.json``, or directly to the
        file, or ``None`` for auto-detection.  See :func:`resolve_config_path`.

    Returns
    -------
    ParsedConfig
        Fully validated configuration.  Never raises; falls back to
        ``default_config`` values on any error.
    """
    json_file = resolve_config_path(config_path)
    config_dir = str(json_file.parent)

    try:
        with open(json_file, "r") as fh:
            raw = json.load(fh)
    except Exception as exc:
        print(f"Warning: Could not load config from {json_file}: {exc}. Using defaults.")
        raw = default_config.copy()

    return parse_config_from_dict(raw, config_dir)


def parse_config_from_dict(raw: dict, config_dir: Optional[str] = None) -> ParsedConfig:
    """
    Parse and validate an already-loaded config dict into a :class:`ParsedConfig`.

    This is the canonical validation logic shared by both :func:`load_parsed_config`
    (which reads from disk) and the Tkinter UI (which manages an in-memory dict).

    Parameters
    ----------
    raw:
        Raw config dict, typically loaded from ``config.json``.
    config_dir:
        Directory that contains the device-layout JSON files.  ``None`` uses the
        project's default ``conf/`` directory.

    Returns
    -------
    ParsedConfig
        Validated configuration.  Any inconsistency is corrected silently after
        emitting a ``Warning:`` log line.
    """
    # --- HID device identifiers ----------------------------------------
    vendor_id  = int(raw.get("vendor_id",  "0x0416"), 16)
    product_id = int(raw.get("product_id", "0x8001"), 16)

    # --- Device layout -------------------------------------------------
    layout_mode = raw.get("layout_mode", "Pearless Assasin 120")
    device_config = get_device_config(layout_mode, config_dir)
    n_leds = device_config.config_dict.get("total_leds", 84)

    # --- Display mode (validated against the device) -------------------
    display_mode = _validate_display_mode(
        raw.get("display_mode", "metrics"), device_config
    )

    # --- Timing ---------------------------------------------------------
    update_interval          = float(raw.get("update_interval",          0.1))
    metrics_update_interval  = float(raw.get("metrics_update_interval",  1.0))
    cycle_duration           = float(raw.get("cycle_duration",           5.0))

    # --- Temperature units ---------------------------------------------
    temp_unit = {
        "cpu": raw.get("cpu_temperature_unit", "celsius"),
        "gpu": raw.get("gpu_temperature_unit", "celsius"),
    }

    # --- Colour-gradient metric bounds ---------------------------------
    metrics_min_value = {
        "cpu_temp":  float(raw.get("cpu_min_temp",   30.0)),
        "gpu_temp":  float(raw.get("gpu_min_temp",   30.0)),
        "cpu_usage": float(raw.get("cpu_min_usage",   0.0)),
        "gpu_usage": float(raw.get("gpu_min_usage",   0.0)),
    }
    metrics_max_value = {
        "cpu_temp":  float(raw.get("cpu_max_temp",  80.0)),
        "gpu_temp":  float(raw.get("gpu_max_temp",  90.0)),
        "cpu_usage": float(raw.get("cpu_max_usage", 100.0)),
        "gpu_usage": float(raw.get("gpu_max_usage", 100.0)),
    }

    # --- Colour spec lists (one entry per LED) -------------------------
    fallback_metrics = default_config["metrics"]["colors"]
    fallback_time    = default_config["time"]["colors"]

    metrics_color_specs = _normalise_color_specs(
        raw.get("metrics", {}).get("colors", fallback_metrics),
        n_leds,
        "metrics",
    )
    time_color_specs = _normalise_color_specs(
        raw.get("time", {}).get("colors", fallback_time),
        n_leds,
        "time",
    )

    return ParsedConfig(
        device_config          = device_config,
        layout_mode            = layout_mode,
        display_mode           = display_mode,
        metrics_color_specs    = metrics_color_specs,
        time_color_specs       = time_color_specs,
        temp_unit              = temp_unit,
        metrics_min_value      = metrics_min_value,
        metrics_max_value      = metrics_max_value,
        update_interval        = update_interval,
        metrics_update_interval= metrics_update_interval,
        cycle_duration         = cycle_duration,
        vendor_id              = vendor_id,
        product_id             = product_id,
        nvme_disk              = raw.get("nvme_disk"),
    )


# ---------------------------------------------------------------------------
# Internal validation helpers
# ---------------------------------------------------------------------------

def _validate_display_mode(requested: str, device_config: DeviceConfig) -> str:
    """
    Return ``requested`` if the device supports it; otherwise log a warning and
    return the best available fallback.

    Fallback priority: ``"metrics"`` → ``"alternate_metrics"`` → first available.
    """
    if requested in device_config.display_modes:
        return requested

    device_name = device_config.config_dict.get("name", "unknown device")
    print(
        f"Warning: Display mode '{requested}' is not available for "
        f"'{device_name}'.  Selecting a compatible fallback."
    )

    for preferred in ("metrics", "alternate_metrics"):
        if preferred in device_config.display_modes:
            return preferred

    fallback = next(iter(device_config.display_modes), None)
    if fallback is None:
        raise ValueError(
            f"Device configuration for '{device_name}' defines no display modes."
        )
    return fallback


def _normalise_color_specs(specs: list, n_leds: int, label: str) -> list:
    """
    Ensure *specs* contains exactly *n_leds* entries.

    If the list is too short it is padded by repeating the last colour.
    If it is too long it is truncated.  A warning is emitted when any
    adjustment is made.
    """
    current = len(specs)
    if current == n_leds:
        return list(specs)

    print(
        f"Warning: Colour spec list '{label}' has {current} entries but the "
        f"device has {n_leds} LEDs.  Adjusting automatically."
    )

    if current == 0:
        return ["ffffff"] * n_leds
    if current < n_leds:
        return list(specs) + [specs[-1]] * (n_leds - current)
    return list(specs[:n_leds])
