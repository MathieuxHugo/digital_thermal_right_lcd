"""
displayer.py
============

The displayer is the rendering heart of the application.  It is composed of
two cooperating parts:

1. :class:`ColorResolver` — **what colour** is each LED?

   Resolves raw per-LED colour specification strings (read from ``config.json``)
   into concrete six-character hex strings at the current moment.  Supports
   static colours, random colours, animated gradients, time-keyed gradients,
   and metric-keyed gradients.

2. :class:`Displayer` — **which LEDs are lit**, and what is their final colour?

   Combines the LED-mask logic (determines which LEDs are on or off based on
   the active display mode and the current metrics) with the resolved colour
   palettes produced by :class:`ColorResolver`.  The public method
   :meth:`Displayer.get_state` returns the *effective colour array*: lit LEDs
   carry their resolved colour, off LEDs carry ``"000000"`` (black).

Both components depend on :class:`~config_parser.ParsedConfig` for all
configuration data, ensuring a single source of truth.

A helper :class:`NullMetrics` stub is provided so the Tkinter UI can use the
same :class:`Displayer` interface without requiring live sensor data.

Typical call pattern
--------------------
::

    from config_parser import load_parsed_config
    from displayer import Displayer
    from metrics import Metrics

    cfg      = load_parsed_config("/path/to/conf")
    metrics  = Metrics()
    renderer = Displayer(cfg, metrics)

    # Called each tick:
    effective_colors, nb_displays = renderer.get_state(cfg.display_mode, cpt)
    # effective_colors[i] == "000000"  → LED i is off
    # effective_colors[i] == "rrggbb"  → LED i is lit with that colour
"""

import datetime
import numpy as np

from metrics import Metrics
from config_parser import ParsedConfig
from utils import interpolate_color, get_random_color


# ---------------------------------------------------------------------------
# NullMetrics stub
# ---------------------------------------------------------------------------

class NullMetrics:
    """
    Drop-in replacement for :class:`~metrics.Metrics` that returns zero for
    every metric value.

    Used by :class:`~led_display_ui.LEDDisplayUI` so the UI preview thread
    can call :meth:`Displayer.get_state` without initialising hardware sensors
    (pyamdgpuinfo, NVML, RAPL, …).

    Metric-keyed colour gradients will always show the *start* colour in the
    UI preview (factor = 0), which is correct behaviour when live data is
    unavailable.
    """

    def get_metrics(self, _temp_unit: dict) -> dict:
        """Return a dict of ``{metric_key: 0}`` for all known metric keys."""
        return {key: 0 for key in Metrics.METRICS_KEYS}

    def set_nvme_disk(self, _disk: str) -> None:
        """No-op (no NVMe monitoring in the stub)."""


# ---------------------------------------------------------------------------
# ColorResolver
# ---------------------------------------------------------------------------

class ColorResolver:
    """
    Resolve raw per-LED colour specification strings to concrete hex colours.

    Each specification string can be one of:

    ``"rrggbb"``
        Static six-character hex colour (e.g. ``"ff4400"``).

    ``"random"``
        A new random colour re-rolled on every :meth:`resolve` call.

    ``"start-end"``
        Animated gradient.  The interpolation factor sweeps from 0→1→0 over
        ``cycle_duration`` ticks, giving a smooth back-and-forth animation.

    ``"start-end-seconds"`` / ``"start-end-minutes"`` / ``"start-end-hours"``
        Gradient driven by the current wall-clock value.

        * ``seconds`` → factor = second / 59
        * ``minutes`` → factor = minute / 59
        * ``hours``   → factor = hour   / 23

    ``"start-end-<metric>"``
        Gradient driven by a live metric value.  ``<metric>`` must be a key in
        :attr:`~metrics.Metrics.METRICS_KEYS` (e.g. ``"cpu_temp"``).  The factor
        is linearly normalised between ``metrics_min_value[metric]`` and
        ``metrics_max_value[metric]`` and clamped to [0, 1].

    Parameters
    ----------
    metrics:
        Live :class:`~metrics.Metrics` instance, or a :class:`NullMetrics` stub.
    metrics_min_value:
        Lower bound per metric key (used for gradient normalisation).
    metrics_max_value:
        Upper bound per metric key.
    temp_unit:
        Temperature unit dict passed through to
        :meth:`~metrics.Metrics.get_metrics`.
    """

    def __init__(
        self,
        metrics,
        metrics_min_value: dict,
        metrics_max_value: dict,
        temp_unit: dict,
    ):
        self._metrics   = metrics
        self._min       = metrics_min_value
        self._max       = metrics_max_value
        self._temp_unit = temp_unit

    def resolve(
        self,
        color_specs: list,
        cpt: int,
        cycle_ticks: int,
        now: datetime.datetime,
    ) -> np.ndarray:
        """
        Resolve a list of colour spec strings to a numpy array of hex strings.

        Parameters
        ----------
        color_specs:
            Per-LED specification strings.  Length must equal the device LED count.
        cpt:
            Current tick counter (incremented by the display loop each frame).
        cycle_ticks:
            Number of ticks in one animation cycle
            (``int(cycle_duration_seconds / update_interval)``).
        now:
            Current wall-clock time, injected by the caller so that both colour
            resolution and LED-mask time values see the *same* timestamp within
            a single frame.

        Returns
        -------
        numpy.ndarray
            Array of six-character hex strings, same length as *color_specs*.
        """
        # Sample live metrics once per frame to avoid N sensor calls
        current_metrics = self._metrics.get_metrics(self._temp_unit)

        return np.array([
            self._resolve_one(spec, cpt, cycle_ticks, now, current_metrics)
            for spec in color_specs
        ])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _resolve_one(
        self,
        spec: str,
        cpt: int,
        cycle_ticks: int,
        now: datetime.datetime,
        current_metrics: dict,
    ) -> str:
        """Resolve a single colour spec string to a hex colour."""
        if spec.lower() == "random":
            return get_random_color()

        if "-" not in spec:
            return spec  # plain static hex colour

        parts = spec.split("-")

        if len(parts) == 3:
            start, end, key = parts
            factor = self._key_to_factor(key, now, current_metrics)
        else:
            # Two-part animated gradient: 0 → 1 → 0 over cycle_ticks
            start, end = parts
            factor = 1.0 - abs((cpt % cycle_ticks) / cycle_ticks - 1.0)

        return interpolate_color(start, end, factor)

    def _key_to_factor(
        self,
        key: str,
        now: datetime.datetime,
        current_metrics: dict,
    ) -> float:
        """Convert a gradient-key token to a [0.0, 1.0] interpolation factor.

        Handles time keys (``seconds``, ``minutes``, ``hours``) and metric keys.
        The two-part animated gradient (``"start-end"`` without a key) is handled
        directly in :meth:`_resolve_one` before this method is called.
        """
        if key == "seconds":
            return now.second / 59.0
        if key == "minutes":
            return now.minute / 59.0
        if key == "hours":
            return now.hour / 23.0

        # Metric-keyed gradient
        if key not in current_metrics:
            print(f"Warning: metric '{key}' not found in current metrics. Using factor 0.")
            return 0.0

        min_v = self._min.get(key)
        max_v = self._max.get(key)
        if min_v is None or max_v is None or min_v == max_v:
            return 0.0

        factor = (current_metrics[key] - min_v) / (max_v - min_v)
        return max(0.0, min(1.0, float(factor)))


# ---------------------------------------------------------------------------
# Displayer
# ---------------------------------------------------------------------------

class Displayer:
    """
    Compute the per-LED effective colour array for a single display frame.

    This class is the single point of truth for "what should each LED show
    right now".  It combines:

    * **LED mask** — which LEDs are currently lit (1) or off (0), determined
      by the active display mode, the current metrics, and the current time.

    * **Colour assignment** — for each lit LED, the resolved colour from either
      the *metrics* palette or the *time* palette, depending on which data
      source drives that LED group.

    Off-LEDs are set to ``"000000"`` in the returned array, so the result can
    be consumed directly by both the HID controller and the Tkinter UI without
    any further masking step.

    Parameters
    ----------
    config:
        Parsed and validated application configuration
        (:class:`~config_parser.ParsedConfig`).
    metrics:
        Live :class:`~metrics.Metrics` instance, or a :class:`NullMetrics` stub
        for UI preview.

    Usage
    -----
    ::

        renderer = Displayer(config, metrics)
        effective_colors, nb_displays = renderer.get_state("metrics", cpt)
        # Pass effective_colors directly to Controller.send_packets() or
        # apply it to the Tkinter UI widgets.
    """

    # 7-segment display patterns, indexed 0–9 then index 10 (or -1) for blank
    _DIGIT_MASK = np.array([
        [1, 1, 1, 0, 1, 1, 1],  # 0
        [0, 0, 1, 0, 0, 0, 1],  # 1
        [0, 1, 1, 1, 1, 1, 0],  # 2
        [0, 1, 1, 1, 0, 1, 1],  # 3
        [1, 0, 1, 1, 0, 0, 1],  # 4
        [1, 1, 0, 1, 0, 1, 1],  # 5
        [1, 1, 0, 1, 1, 1, 1],  # 6
        [0, 1, 1, 0, 0, 0, 1],  # 7
        [1, 1, 1, 1, 1, 1, 1],  # 8
        [1, 1, 1, 1, 0, 1, 1],  # 9
        [0, 0, 0, 0, 0, 0, 0],  # blank (index -1 in numpy → same as index 10)
    ])

    # Single-segment letter patterns used for labels like "H" (hours) and "C" (celsius)
    _LETTER_MASK = {
        "H": [1, 0, 1, 1, 1, 0, 1],
        "C": [1, 1, 0, 0, 1, 1, 0],
    }

    def __init__(self, config: ParsedConfig, metrics):
        self._cfg    = config
        self._device = config.device_config
        # Number of ticks per animation / alternating-display cycle
        self._cycle_ticks = max(1, int(config.cycle_duration / config.update_interval))
        self._color_resolver = ColorResolver(
            metrics,
            config.metrics_min_value,
            config.metrics_max_value,
            config.temp_unit,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_state(self, display_mode: str, cpt: int) -> tuple:
        """
        Compute the effective per-LED colour array for the current frame.

        All LED-state logic (digit encoding, 7-segment masks, letter patterns,
        on/off groups) and colour resolution (gradients, random, time-keyed,
        metric-keyed) is handled internally.

        Parameters
        ----------
        display_mode:
            Active display mode name (must exist in the device configuration).
            Passed as a parameter rather than read from ``config`` so that the
            controller and the UI can independently drive different modes.
        cpt:
            Monotonically increasing tick counter.  Drives colour animations
            and alternating-display cycling.

        Returns
        -------
        (effective_colors, nb_displays)
            *effective_colors* : ``numpy.ndarray`` of six-character hex strings.
                ``effective_colors[i]`` is the resolved colour if LED *i* is lit,
                or ``"000000"`` if LED *i* is off.  Length equals
                ``device_config["total_leds"]``.

            *nb_displays* : ``int``
                Number of alternating sub-displays for the current mode.  The
                caller should wrap ``cpt`` modulo
                ``cycle_ticks * nb_displays`` to avoid integer overflow over
                very long runtimes.
        """
        n = self._device.config_dict.get("total_leds", 84)

        # Capture wall-clock time once so both colour resolution and LED-mask
        # time values see the same timestamp within this frame.
        now = datetime.datetime.now()

        # Resolve colour spec strings → concrete hex colours
        metrics_colors = self._color_resolver.resolve(
            self._cfg.metrics_color_specs, cpt, self._cycle_ticks, now
        )
        time_colors = self._color_resolver.resolve(
            self._cfg.time_color_specs, cpt, self._cycle_ticks, now
        )

        # led_mask[i] = 1 if LED i is lit, 0 if off
        led_mask = np.zeros(n, dtype=int)

        # led_colors[i] = the colour that LED i should show *if* it is lit.
        # Start with the metrics palette; time-driven groups will be overridden below.
        led_colors = metrics_colors.copy()

        time_dict = {
            "hours":   now.hour,
            "minutes": now.minute,
            "seconds": now.second,
        }

        nb_displays = self._apply_display_mode(
            display_mode, cpt, led_mask, led_colors, time_colors, time_dict
        )

        # Apply mask: off LEDs → "000000"
        effective_colors = np.where(led_mask != 0, led_colors, "000000")
        return effective_colors, nb_displays

    # ------------------------------------------------------------------
    # Internal: display mode dispatch
    # ------------------------------------------------------------------

    def _apply_display_mode(
        self,
        display_mode: str,
        cpt: int,
        led_mask: np.ndarray,
        led_colors: np.ndarray,
        time_colors: np.ndarray,
        time_dict: dict,
    ) -> int:
        """
        Populate *led_mask* and *led_colors* for the active display mode.

        Handles both ``"static"`` modes (single fixed mapping) and
        ``"alternating"`` modes (multiple sub-displays cycled by ``cpt``).

        Returns *nb_displays* (≥ 1).
        """
        mode_config = self._device.get_display_mode(display_mode)
        if mode_config is None:
            return 1

        if mode_config.type == "static":
            mappings = mode_config.mode_dict.get("mappings", {})
            self._apply_mappings(mappings, led_mask, led_colors, time_colors, time_dict)
            return 1

        if mode_config.type == "alternating":
            displays = mode_config.displays
            if not displays:
                return 1
            nb = len(displays)
            idx = int(cpt // self._cycle_ticks) % nb
            current = displays[idx]
            # Each element may be a string name (resolved to a mode dict) or
            # an inline mapping dict
            if isinstance(current, str):
                sub = self._device.get_display_mode(current)
                current = sub.mode_dict if sub else {}
            mappings = current.get("mappings", {})
            self._apply_mappings(mappings, led_mask, led_colors, time_colors, time_dict)
            return nb

        return 1

    def _apply_mappings(
        self,
        mappings: dict,
        led_mask: np.ndarray,
        led_colors: np.ndarray,
        time_colors: np.ndarray,
        time_dict: dict,
    ) -> None:
        """
        Process all ``{led_group: data_source}`` pairs in *mappings*.

        For each pair:

        * Resolves ``"<device>_temp_unit"`` group-name placeholders to their
          concrete names (e.g. ``"cpu_temp_unit"`` → ``"cpu_celsius"``).
        * Overrides *led_colors* with *time_colors* for groups whose data source
          is a time value (``"hours"``, ``"minutes"``, ``"seconds"``).
        * Updates *led_mask* via :meth:`_apply_one_mapping`.
        """
        for led_group, data_source in mappings.items():
            # Expand temperature-unit placeholder in group names.
            # e.g. "cpu_temp_unit" → "cpu_celsius" or "cpu_fahrenheit"
            if "temp_unit" in led_group:
                device = led_group.replace("_temp_unit", "")
                unit   = self._cfg.temp_unit.get(device, "celsius")
                led_group = led_group.replace("temp_unit", unit.lower())

            # Time-driven groups use the time colour palette instead of metrics
            if data_source in time_dict:
                idxs = self._device.leds_indexes.get(led_group)
                if idxs is not None:
                    led_colors[idxs] = time_colors[idxs]

            self._apply_one_mapping(led_group, data_source, time_dict, led_mask)

    def _apply_one_mapping(
        self,
        led_group: str,
        data_source: str,
        time_dict: dict,
        led_mask: np.ndarray,
    ) -> None:
        """
        Write a single mapping into *led_mask*.

        Data source semantics:

        ``"on"``
            All LEDs in the group are set to 1 (always lit).
        ``"off"``
            All LEDs in the group are set to 0 (always dark).
        Letter key (``"H"``, ``"C"``, …)
            The 7-segment letter pattern is written into the group.
        Time key (``"hours"``, ``"minutes"``, ``"seconds"``)
            The current time value is encoded as 7-segment digits.
        Metric key (any key in :attr:`~metrics.Metrics.METRICS_KEYS`)
            The live metric value is fetched and encoded as 7-segment digits.
        Unknown key
            Silently ignored.
        """
        if data_source == "on":
            self._set_mask(led_mask, led_group, 1)
            return

        if data_source == "off":
            self._set_mask(led_mask, led_group, 0)
            return

        if data_source in self._LETTER_MASK:
            self._set_mask(led_mask, led_group, self._LETTER_MASK[data_source])
            return

        # Numeric value — either time or a live metric
        value = time_dict.get(data_source)

        if value is None and data_source in Metrics.METRICS_KEYS:
            metrics_vals = self._color_resolver._metrics.get_metrics(
                self._cfg.temp_unit
            )
            value = int(metrics_vals[data_source])

        if value is not None:
            encoded = self._encode_number(led_group, int(value))
            self._set_mask(led_mask, led_group, encoded)

    # ------------------------------------------------------------------
    # Internal: number → 7-segment encoding
    # ------------------------------------------------------------------

    def _encode_number(self, led_group: str, value: int) -> np.ndarray:
        """
        Encode *value* as a flat 7-segment bit array sized for *led_group*.

        If the group has non-digit leading LEDs (``len(group_leds) > digit_count * 7``),
        those are set to 1 when the value overflows the display (indicating
        truncation), and 0 otherwise.

        Parameters
        ----------
        led_group:
            LED group name (used to look up LED indices and digit count).
        value:
            Non-negative integer to display.

        Returns
        -------
        numpy.ndarray of int (0/1 values), length = len(leds_indexes[led_group]).
        """
        idxs        = self._device.leds_indexes.get(led_group, [])
        digit_count = self._device.get_digit_count(led_group)
        n_extra     = len(idxs) - digit_count * 7  # leading non-digit LEDs

        overflow = digit_count < len(str(value))
        if overflow:
            # Signal overflow on non-digit leading segments only
            # (if every segment is a digit there is nowhere to place an indicator)
            if len(idxs) % 7 != 0:
                print(
                    f"Warning: value {value} is too large for group '{led_group}' "
                    f"({digit_count} digit(s) available)."
                )
            prefix = [1] * n_extra
        else:
            prefix = [0] * n_extra

        digit_indices = self._get_number_array(value, array_length=digit_count)
        segments = self._DIGIT_MASK[digit_indices].flatten()
        return np.concatenate([prefix, segments])

    # ------------------------------------------------------------------
    # Internal: number utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _number_to_digits(n: int) -> list:
        """Decompose a non-negative integer into a list of decimal digits."""
        if n >= 10:
            return Displayer._number_to_digits(n // 10) + [n % 10]
        return [n]

    @classmethod
    def _get_number_array(cls, value: int, array_length: int = 3) -> list:
        """
        Return a fixed-length list of digit indices for *value*.

        Missing leading digits are filled with ``-1`` (the blank segment row).
        If *value* has more digits than *array_length* the most-significant
        digit is dropped (the display shows the ``array_length`` least-significant
        digits).

        Parameters
        ----------
        value:
            Non-negative integer.
        array_length:
            Number of 7-segment digit positions in the target LED group.
        """
        if value < 0:
            return [-1] * array_length

        digits = cls._number_to_digits(int(value))

        if len(digits) < array_length:
            # Left-pad with blanks
            digits = [-1] * (array_length - len(digits)) + digits
        elif len(digits) > array_length:
            # Truncate most-significant digit
            digits = digits[1:]

        return digits

    # ------------------------------------------------------------------
    # Internal: LED mask helpers
    # ------------------------------------------------------------------

    def _set_mask(self, mask: np.ndarray, led_group: str, value) -> None:
        """
        Assign *value* to all LED positions belonging to *led_group* in *mask*.

        *value* may be a scalar (int) or an array of ints of the same length
        as the LED group.  Unknown group names are silently ignored.
        """
        try:
            idxs = self._device.leds_indexes[led_group]
        except KeyError:
            return
        mask[idxs] = value
