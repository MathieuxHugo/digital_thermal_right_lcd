#!/usr/bin/env python3
"""
Generate (or regenerate) reference files for Displayer.get_state non-regression tests.

Each reference file captures the exact LED state and colors produced by get_state
for a specific (device, display_mode, scenario) combination. The test suite then
compares live output against these snapshots.

Usage
-----
Generate references for all devices (default):
    python tests/generate_references.py

Generate for a subset of devices:
    python tests/generate_references.py --devices "Pearless Assasin 120" "TR Assassin X 120R"

Available device names
----------------------
"""

import argparse
import json
import sys
import os

# Allow running this script directly from the project root without installing.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from helpers import ALL_TEST_CASES, ALL_DEVICE_NAMES, run_get_state, get_reference_path


def generate(device_names: list[str] | None = None) -> None:
    targets = device_names or ALL_DEVICE_NAMES

    unknown = [d for d in targets if d not in ALL_DEVICE_NAMES]
    if unknown:
        print("Unknown device(s):", unknown)
        print("Available:", ALL_DEVICE_NAMES)
        sys.exit(1)

    target_set = set(targets)
    cases = [c for c in ALL_TEST_CASES if c[0] in target_set]

    print(f"Generating {len(cases)} reference file(s)…\n")
    for device_name, display_mode, scenario, metrics_values, mock_time, cpt in cases:
        ref_path = get_reference_path(device_name, display_mode, scenario)
        action = "updated" if ref_path.exists() else "created"

        ref_path.parent.mkdir(parents=True, exist_ok=True)
        result = run_get_state(device_name, display_mode, metrics_values, mock_time, cpt)

        with open(ref_path, "w") as fh:
            json.dump(result, fh, indent=2)

        rel = ref_path.relative_to(ref_path.parents[2])  # relative to project root
        print(f"  [{action}] {rel}")

    print(f"\nDone — {len(cases)} file(s) written.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--devices",
        nargs="+",
        metavar="DEVICE",
        help=(
            "One or more device names to (re)generate. "
            "Defaults to all devices. "
            f"Choices: {ALL_DEVICE_NAMES}"
        ),
    )
    args = parser.parse_args()
    generate(args.devices)


if __name__ == "__main__":
    main()
