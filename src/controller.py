"""
controller.py
=============

Application entry point and HID device driver.

Responsibilities
----------------
This module is intentionally thin.  It owns exactly two concerns:

1. **HID communication** — :meth:`Controller.send_packets` formats the
   per-LED colour array into the binary packet format expected by the
   Thermal Right cooler firmware and writes it over USB HID.

2. **Main display loop** — :meth:`Controller.display` is the top-level
   ``while True`` that ties everything together: reload configuration,
   compute the current LED state, and push the result to the device.

Everything else has been delegated:

* Configuration loading and validation → :mod:`config_parser`
* LED mask and colour computation → :mod:`displayer`
* System metric collection → :mod:`metrics`

Packet format
-------------
The firmware expects a stream of 128-character (64-byte) hex packets:

* **Packet 0** (first): ``HEADER (20 bytes) || payload slice``
* **Packet n** (subsequent): ``0x00 || payload slice``

The total colour payload must be at least :data:`MINIMUM_MESSAGE_LENGTH`
hex characters long, zero-padded with ``0xFF`` bytes if the device has
fewer LEDs.
"""

import numpy as np
import hid
import time
import sys
import os
from pathlib import Path

from metrics import Metrics
from config_parser import load_parsed_config
from displayer import Displayer


# Minimum HID payload length in hex characters (each byte = 2 hex chars)
MINIMUM_MESSAGE_LENGTH = 504

# Fixed firmware header prepended to the first HID packet
HID_HEADER = "dadbdcdd000000000000000000000000fc0000ff"


class Controller:
    """
    HID device controller for Thermal Right ARGB coolers.

    The Controller opens the USB HID device, runs the display loop, and sends
    formatted colour packets to the firmware.  All business logic (config
    parsing, LED masking, colour resolution) is handled by imported modules.

    Parameters
    ----------
    config_path:
        Path to the directory containing ``config.json`` and the device
        layout JSON files, or directly to ``config.json``.  Accepts ``None``
        for auto-detection via the ``DIGITAL_LCD_CONFIG`` environment variable,
        falling back to the project's ``conf/`` directory.

    Attributes
    ----------
    VENDOR_ID, PRODUCT_ID:
        USB identifiers of the connected HID device.  Updated from config when
        they change.
    cpt:
        Monotonically increasing tick counter.  Drives colour animations and
        alternating-display cycling inside :class:`~displayer.Displayer`.
    """

    VENDOR_ID  = 0x0416
    PRODUCT_ID = 0x8001

    def __init__(self, config_path: str = None):
        self.config_path = self._resolve_config_path(config_path)
        self.metrics     = Metrics()
        self.dev         = self._open_device()
        self.cpt         = 0

    # ------------------------------------------------------------------
    # HID device management
    # ------------------------------------------------------------------

    def _open_device(self):
        """
        Open the HID device.

        Returns the :class:`hid.Device` object on success, or ``None`` if the
        device is not connected.  The caller is responsible for retrying.
        """
        try:
            return hid.Device(self.VENDOR_ID, self.PRODUCT_ID)
        except Exception as exc:
            print(f"Warning: Could not open HID device: {exc}")
            return None

    # ------------------------------------------------------------------
    # Packet sending
    # ------------------------------------------------------------------

    def send_packets(self, effective_colors: np.ndarray, update_interval: float) -> None:
        """
        Encode per-LED colours into HID packets and write them to the device.

        Parameters
        ----------
        effective_colors:
            Array of six-character hex strings, one per LED.  Off-LEDs must
            already carry ``"000000"`` — this is guaranteed by
            :meth:`~displayer.Displayer.get_state`.
        update_interval:
            Seconds per display tick.  Used to compute the inter-packet delay
            that prevents overwhelming the firmware.

        Notes
        -----
        The colour payload is assembled by joining all hex strings.  If the
        resulting string is shorter than :data:`MINIMUM_MESSAGE_LENGTH`
        characters (devices with few LEDs) it is padded with ``"FF"`` bytes.

        The first packet contains the fixed :data:`HID_HEADER` followed by the
        first slice of the payload.  All subsequent packets carry a single
        ``0x00`` prefix byte.
        """
        message = "".join(effective_colors)

        # Pad to minimum required firmware length
        if len(message) < MINIMUM_MESSAGE_LENGTH:
            message += "FF" * (MINIMUM_MESSAGE_LENGTH - len(message))

        # First packet: header + initial payload
        header_len = len(HID_HEADER)
        packet0 = bytes.fromhex(HID_HEADER + message[:128 - header_len])
        self.dev.write(packet0)

        # Remaining 128-character payload slices
        rest      = message[128 - header_len:]
        n_packets = int(np.ceil(len(rest) / 128))
        delay     = update_interval / (10 + n_packets)

        for i in range(n_packets):
            chunk = rest[i * 128:(i + 1) * 128]
            self.dev.write(bytes.fromhex("00" + chunk))
            time.sleep(delay)

    # ------------------------------------------------------------------
    # Main display loop
    # ------------------------------------------------------------------

    def display(self) -> None:
        """
        Run the display loop indefinitely.

        Each iteration:

        1. Reload ``config.json`` from disk — picks up live edits made by the
           Tkinter UI or a text editor without restarting the process.
        2. Apply any hardware-identity changes (vendor/product ID).
        3. If the HID device is not connected, wait and retry.
        4. Ask :class:`~displayer.Displayer` for the current effective colour array.
        5. Send colour packets to the device.
        6. Sleep for ``update_interval`` seconds.
        """
        while True:
            cfg = load_parsed_config(self.config_path)

            # Update metrics collection interval from config
            self.metrics.update_interval = cfg.metrics_update_interval
            if cfg.nvme_disk:
                self.metrics.set_nvme_disk(cfg.nvme_disk)

            # Reinitialise HID device if vendor/product IDs changed in config
            if cfg.vendor_id != self.VENDOR_ID or cfg.product_id != self.PRODUCT_ID:
                self.VENDOR_ID  = cfg.vendor_id
                self.PRODUCT_ID = cfg.product_id
                self.dev = self._open_device()

            if self.dev is None:
                print(
                    f"No HID device found "
                    f"(vendor=0x{self.VENDOR_ID:04x} "
                    f"product=0x{self.PRODUCT_ID:04x}). "
                    f"Retrying in 5 s."
                )
                time.sleep(5)
                self.dev = self._open_device()
                time.sleep(cfg.update_interval)
                continue

            # Compute effective per-LED colours and push to hardware
            displayer = Displayer(cfg, self.metrics)
            effective_colors, nb_displays = displayer.get_state(
                cfg.display_mode, self.cpt
            )

            cycle_ticks = max(1, int(cfg.cycle_duration / cfg.update_interval))
            self.cpt = (self.cpt + 1) % (cycle_ticks * nb_displays)

            self.send_packets(effective_colors, cfg.update_interval)
            time.sleep(cfg.update_interval)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_config_path(config_path: str) -> str:
        """
        Resolve the config path, honouring the ``DIGITAL_LCD_CONFIG``
        environment variable when *config_path* is ``None``.
        """
        if config_path is not None:
            return config_path
        env = os.environ.get("DIGITAL_LCD_CONFIG")
        if env:
            return env
        return str(Path(__file__).parent.parent / "conf")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(config_path: str = None) -> None:
    """Create a :class:`Controller` and run the display loop."""
    controller = Controller(config_path=config_path)
    controller.display()


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    if config_path:
        print(f"Using config path: {config_path}")
    else:
        print("No config path provided, using default.")
    main(config_path)
