"""Signal-to-noise-ratio utilities for GNSSpy v3."""

from gnsspy.io.manipulate import standardize_snr


standardize_signal_to_noise_ratio = standardize_snr

__all__ = [
    "standardize_snr",
    "standardize_signal_to_noise_ratio",
]
