"""The detector registry."""

from __future__ import annotations

from zbf.detect.base import Detector
from zbf.detect.spectral import AUTOCORRELATION, SPECTRAL
from zbf.detect.statistics import BOWLEY_SKEW, INTERVAL_CV, MAD_RATIO

DETECTORS: dict[str, Detector] = {
    detector.name: detector for detector in (INTERVAL_CV, MAD_RATIO, BOWLEY_SKEW, AUTOCORRELATION, SPECTRAL)
}

__all__ = ["DETECTORS", "Detector"]
