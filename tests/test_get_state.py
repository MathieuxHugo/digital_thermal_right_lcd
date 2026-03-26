"""
Non-regression tests for Displayer.get_state.

Each parametrised case loads a pre-recorded reference file from
tests/references/<device>/<display_mode>_<scenario>.json and asserts that
the live output of get_state matches exactly.

To create or refresh reference files run:
    python tests/generate_references.py
    python tests/generate_references.py --devices "Pearless Assasin 120"
"""

import json
import pytest

from helpers import ALL_TEST_CASES, run_get_state, get_reference_path


def _case_id(case) -> str:
    device, mode, scenario, *_ = case
    return f"{device.replace(' ', '_')}-{mode}-{scenario}"


@pytest.mark.parametrize(
    "device_name,display_mode,scenario,metrics_values,mock_time,cpt",
    ALL_TEST_CASES,
    ids=[_case_id(c) for c in ALL_TEST_CASES],
)
def test_get_state_non_regression(
    device_name, display_mode, scenario, metrics_values, mock_time, cpt
):
    ref_path = get_reference_path(device_name, display_mode, scenario)
    if not ref_path.exists():
        pytest.skip(
            f"Reference not found: {ref_path}. "
            "Run `python tests/generate_references.py` to create it."
        )

    with open(ref_path) as fh:
        reference = json.load(fh)

    result = run_get_state(device_name, display_mode, metrics_values, mock_time, cpt)

    assert result["effective_colors"] == reference["effective_colors"], (
        f"Effective colors mismatch for {device_name} / {display_mode} / {scenario}"
    )
    assert result["nb_displays"] == reference["nb_displays"], (
        f"nb_displays mismatch for {device_name} / {display_mode} / {scenario}"
    )
