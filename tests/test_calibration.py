"""
Step 13 — Tests for model/calibration.py's apply_calibration().

Pure verification only -- nothing here refits the calibrator (that's
model/calibrate.py's job) or touches model/artifacts/calibrator.joblib.

How to run just this file:
    venv\\Scripts\\python.exe -m pytest tests/test_calibration.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pytest

from model.calibration import apply_calibration


@pytest.mark.parametrize("raw_probability", [0.0, 0.3, 0.7, 1.0])
def test_apply_calibration_returns_probability_in_range(raw_probability):
    calibrated = apply_calibration(raw_probability)
    assert 0.0 <= calibrated <= 1.0


def test_apply_calibration_is_monotonic():
    """A real property Platt (sigmoid) scaling must satisfy: it's just a
    monotonic logistic transform of its single input, so a HIGHER raw
    probability must never produce a LOWER calibrated probability.
    Checked across a fine, strictly increasing sequence of raw inputs."""
    raw_probabilities = np.linspace(0.0, 1.0, 21)
    calibrated = apply_calibration(raw_probabilities)

    step_by_step_changes = np.diff(calibrated)
    assert (step_by_step_changes >= -1e-9).all(), (
        "apply_calibration() is not monotonic -- calibrated probabilities "
        f"{calibrated} decrease somewhere as raw probabilities increase "
        f"({raw_probabilities})."
    )
