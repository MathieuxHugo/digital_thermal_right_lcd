"""Shared helpers for Displayer.get_state non-regression tests."""

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from displayer import Displayer
from config_parser import ParsedConfig
from device_configurations import get_device_config

REFERENCES_DIR = Path(__file__).parent / "references"

# ---------------------------------------------------------------------------
# Fixed metric values used across all test scenarios
# ---------------------------------------------------------------------------

NORMAL_METRICS = {
    "cpu_temp": 65,
    "gpu_temp": 75,
    "cpu_usage": 45,
    "gpu_usage": 60,
    "cpu_frequency": 3600,
    "gpu_frequency": 1500,
    "cpu_power": 65,
    "gpu_power": 150,
    "nvme_temp": 45,
    "nvme_read_speed": 500,
    "nvme_write_speed": 200,
    "nvme_usage": 30,
}

# Edge values push every LED group to its maximum digit count.
# usage=100 tests a 3-digit value on a 2-digit display (truncation path).
# frequency=9999 fills a 4-digit display; nvme_read/write_speed=99999 fills
# the 5-digit display on the HR-10.
EDGE_METRICS = {
    "cpu_temp": 999,
    "gpu_temp": 999,
    "cpu_usage": 100,
    "gpu_usage": 100,
    "cpu_frequency": 9999,
    "gpu_frequency": 9999,
    "cpu_power": 999,
    "gpu_power": 999,
    "nvme_temp": 999,
    "nvme_read_speed": 99999,
    "nvme_write_speed": 99999,
    "nvme_usage": 100,
}

NORMAL_TIME = datetime.datetime(2024, 1, 15, 14, 30, 45)   # 14:30:45
EDGE_TIME = datetime.datetime(2024, 1, 15, 23, 59, 59)     # 23:59:59 (max digits)

# ---------------------------------------------------------------------------
# Test-case table
# Columns: device_name, display_mode, scenario, metrics_values, mock_time, cpt
# ---------------------------------------------------------------------------

ALL_TEST_CASES = [
    # --- Pearless Assasin 120 ---
    ("Pearless Assasin 120", "metrics", "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Pearless Assasin 120", "metrics", "edge",   EDGE_METRICS,   NORMAL_TIME, 0),
    ("Pearless Assasin 120", "time",    "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Pearless Assasin 120", "time",    "edge",   NORMAL_METRICS, EDGE_TIME,   0),

    # --- Pearless Assasin 140 ---
    ("Pearless Assasin 140", "cpu", "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Pearless Assasin 140", "cpu", "edge",   EDGE_METRICS,   NORMAL_TIME, 0),
    ("Pearless Assasin 140", "gpu", "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Pearless Assasin 140", "gpu", "edge",   EDGE_METRICS,   NORMAL_TIME, 0),

    # --- TR Assassin X 120R ---
    ("TR Assassin X 120R", "cpu_temp",  "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("TR Assassin X 120R", "cpu_temp",  "edge",   EDGE_METRICS,   NORMAL_TIME, 0),
    ("TR Assassin X 120R", "cpu_usage", "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("TR Assassin X 120R", "cpu_usage", "edge",   EDGE_METRICS,   NORMAL_TIME, 0),

    # --- Pearless Assasin 140 BIG ---
    ("Pearless Assasin 140 BIG", "cpu", "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Pearless Assasin 140 BIG", "cpu", "edge",   EDGE_METRICS,   NORMAL_TIME, 0),
    ("Pearless Assasin 140 BIG", "gpu", "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Pearless Assasin 140 BIG", "gpu", "edge",   EDGE_METRICS,   NORMAL_TIME, 0),

    # --- Thermalright HR-10 2280 PRO ---
    ("Thermalright HR-10 2280 PRO", "temp",  "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Thermalright HR-10 2280 PRO", "temp",  "edge",   EDGE_METRICS,   NORMAL_TIME, 0),
    ("Thermalright HR-10 2280 PRO", "usage", "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Thermalright HR-10 2280 PRO", "usage", "edge",   EDGE_METRICS,   NORMAL_TIME, 0),
    ("Thermalright HR-10 2280 PRO", "time",  "normal", NORMAL_METRICS, NORMAL_TIME, 0),
    ("Thermalright HR-10 2280 PRO", "time",  "edge",   NORMAL_METRICS, EDGE_TIME,   0),
]

ALL_DEVICE_NAMES = list(dict.fromkeys(c[0] for c in ALL_TEST_CASES))

# ---------------------------------------------------------------------------
# Deterministic, per-LED color generators
# ---------------------------------------------------------------------------

def _make_metrics_colors(n_leds: int) -> list:
    """One unique static hex color per LED position for metrics display."""
    colors = []
    for i in range(n_leds):
        r = (i * 37 + 10) % 256
        g = (i * 71 + 50) % 256
        b = (i * 113 + 100) % 256
        colors.append(f"{r:02x}{g:02x}{b:02x}")
    return colors


def _make_time_colors(n_leds: int) -> list:
    """One unique static hex color per LED position for time display (different palette)."""
    colors = []
    for i in range(n_leds):
        r = (i * 53 + 150) % 256
        g = (i * 89 + 30) % 256
        b = (i * 127 + 200) % 256
        colors.append(f"{r:02x}{g:02x}{b:02x}")
    return colors


# ---------------------------------------------------------------------------
# Core helper
# ---------------------------------------------------------------------------

def run_get_state(
    device_name: str,
    display_mode: str,
    metrics_values: dict,
    mock_time: datetime.datetime,
    cpt: int = 0,
) -> dict:
    """
    Run Displayer.get_state with fully mocked metrics and datetime.

    Builds a ParsedConfig with deterministic per-LED colour specs (unique static
    colour per LED, easily spotted in diffs) and a MagicMock Metrics instance
    that returns the given metrics_values.  datetime.datetime.now() is patched
    to return mock_time so the output is fully deterministic.

    Returns a JSON-serialisable dict:
        {"effective_colors": [...], "nb_displays": int}
    """
    device_config = get_device_config(device_name)
    n_leds = device_config.config_dict.get("total_leds", 84)

    cfg = ParsedConfig(
        device_config=device_config,
        layout_mode=device_name,
        display_mode=display_mode,
        metrics_color_specs=_make_metrics_colors(n_leds),
        time_color_specs=_make_time_colors(n_leds),
        temp_unit={"cpu": "celsius", "gpu": "celsius"},
        metrics_min_value={
            "cpu_temp": 30, "gpu_temp": 30,
            "cpu_usage": 0, "gpu_usage": 0,
            "cpu_frequency": 0, "gpu_frequency": 0,
            "cpu_power": 0, "gpu_power": 0,
            "nvme_temp": 20, "nvme_read_speed": 0,
            "nvme_write_speed": 0, "nvme_usage": 0,
        },
        metrics_max_value={
            "cpu_temp": 90, "gpu_temp": 90,
            "cpu_usage": 100, "gpu_usage": 100,
            "cpu_frequency": 5000, "gpu_frequency": 2000,
            "cpu_power": 200, "gpu_power": 350,
            "nvme_temp": 80, "nvme_read_speed": 3500,
            "nvme_write_speed": 3500, "nvme_usage": 100,
        },
        update_interval=0.1,
        metrics_update_interval=1.0,
        cycle_duration=5.0,
        vendor_id=0x0416,
        product_id=0x8001,
    )

    mock_metrics = MagicMock()
    mock_metrics.get_metrics.return_value = metrics_values.copy()

    with patch("displayer.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = mock_time
        effective_colors, nb_displays = Displayer(cfg, mock_metrics).get_state(
            display_mode, cpt
        )

    return {
        "effective_colors": effective_colors.tolist(),
        "nb_displays": int(nb_displays),
    }


def get_reference_path(device_name: str, display_mode: str, scenario: str) -> Path:
    """Return the expected path for a reference JSON file."""
    device_slug = device_name.lower().replace(" ", "_")
    return REFERENCES_DIR / device_slug / f"{display_mode}_{scenario}.json"
