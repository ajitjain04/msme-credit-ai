"""
Step 12c — apply_calibration(): the lightweight, reusable half of
probability calibration.

model/calibrate.py (the one-time fitting script) fits TWO candidate
calibrators (isotonic regression and Platt/sigmoid scaling, the latter's
PlattCalibrator class defined below -- see why) on the same out-of-fold
training probabilities, evaluates both honestly on the test set, and
saves whichever one actually wins to model/artifacts/calibrator.joblib.
This module only LOADS that already-fitted, already-chosen calibrator
and applies it -- it doesn't know or care which kind it is (both expose
the same `.predict()` interface). Nothing here fits or retrains anything,
and it never touches model/artifacts/model.joblib.

model/scoring.py's score_company() calls apply_calibration() on the base
model's raw probability BEFORE converting it to a 300-900 score, so the
score/risk-band boundaries are based on realistic, calibrated
probabilities rather than the base model's raw, class-weight-inflated
ones. See model/calibrate.py's module docstring for the full "why".

model/explainer.py's SHAP explanations are UNCHANGED by this step -- they
keep explaining the base model's raw decision function, which is correct;
see model/scoring.py's score_company() docstring for why.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Union

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CALIBRATOR_PATH = PROJECT_ROOT / "model" / "artifacts" / "calibrator.joblib"


class PlattCalibrator:
    """Platt scaling (sigmoid calibration): a plain 1-feature
    LogisticRegression where the single input is the base model's raw
    probability and the target is the true label -- the standard manual
    implementation of Platt/sigmoid calibration. It fits only 2 numbers
    (a slope and an intercept), which makes it far less prone to
    overfitting on a small training set than isotonic regression's
    flexible step-wise curve. See model/calibrate.py's module docstring
    for the full comparison.

    Wrapped in this tiny class purely so it exposes a `.predict(raw_probs)
    -> calibrated_probs` method, matching sklearn.isotonic.IsotonicRegression's
    interface, so apply_calibration() below doesn't need to know or care
    which kind of calibrator it loaded.

    Lives HERE (not in model/calibrate.py, where it's fitted) specifically
    so joblib pickles it under a stable, importable module path
    (model.calibration.PlattCalibrator) rather than under whatever script
    happened to create it -- e.g. `__main__` if calibrate.py is run
    directly, which would make the saved calibrator.joblib file
    unloadable from any OTHER script (a real bug this project hit once).
    """

    def __init__(self, logistic_model: LogisticRegression):
        self._logistic_model = logistic_model

    def predict(self, raw_probabilities: np.ndarray) -> np.ndarray:
        x = np.atleast_1d(np.asarray(raw_probabilities, dtype=float)).reshape(-1, 1)
        return self._logistic_model.predict_proba(x)[:, 1]

# Loaded LAZILY (on first use, then cached), NOT at import time. This is
# deliberate, not an inconsistency with model/scoring.py's/model/explainer.py's
# eager module-level loads: model/calibrate.py itself needs to import pure
# helper functions from model/scoring.py (which imports this module) BEFORE
# calibrator.joblib exists on a fresh run -- an eager load here would make
# that first-ever run impossible (a chicken-and-egg import error). Every
# other caller (score_company(), the API, the dashboard) only ever calls
# apply_calibration() AFTER model/calibrate.py has already been run once,
# so the lazy load resolves on their first real use and is cached after
# that, same effective behavior as an eager load.
_CALIBRATOR = None


def _get_calibrator():
    global _CALIBRATOR
    if _CALIBRATOR is None:
        if not CALIBRATOR_PATH.exists():
            raise FileNotFoundError(
                f"{CALIBRATOR_PATH} not found. Run `python model/calibrate.py` "
                "once first -- it fits and saves this calibrator -- before "
                "calling apply_calibration() or model.scoring.score_company()."
            )
        _CALIBRATOR = joblib.load(CALIBRATOR_PATH)
    return _CALIBRATOR


def apply_calibration(
    raw_probability: Union[float, np.ndarray],
) -> Union[float, np.ndarray]:
    """Maps a raw (base-model) default probability to its calibrated
    equivalent, using whichever calibrator (isotonic regression or Platt
    scaling) won the comparison in model/calibrate.py and got saved to
    model/artifacts/calibrator.joblib.

    Either way, this is just a lookup/curve learned from history: "when
    the base model said X%, what fraction of companies like that actually
    defaulted?" -- and this function applies that lookup, nothing more.

    Accepts a single float OR a numpy array/pandas Series of floats (e.g.
    a whole test set's probabilities at once). Returns the same shape it
    was given: a float in, a float out; an array in, an array out.
    """
    calibrator = _get_calibrator()
    single_value = np.isscalar(raw_probability)
    arr = np.atleast_1d(np.asarray(raw_probability, dtype=float))
    calibrated = calibrator.predict(arr)
    return float(calibrated[0]) if single_value else calibrated
