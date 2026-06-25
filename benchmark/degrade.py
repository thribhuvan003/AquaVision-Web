"""Physically-inspired synthetic underwater degradation.

Used to build clean<->degraded pairs from in-air photos so we can compute
full-reference metrics (PSNR/SSIM) of an enhanced result against a known
ground truth - the standard way underwater enhancement is benchmarked when no
real clean reference exists.

Model (simplified image-formation):
    I = J * t + A * (1 - t),   t_c = exp(-beta_c * d)
where red light attenuates fastest, giving the classic blue-green cast.
"""
from __future__ import annotations

import numpy as np
import cv2

# Per-channel attenuation coefficients (R attenuates most -> blue-green water)
_BETA = np.array([0.85, 0.32, 0.18])          # R, G, B
_BACKGROUND = np.array([18, 95, 120], float)   # bluish veiling light (RGB)


def degrade(rgb: np.ndarray, depth: float = 1.6, seed: int = 0) -> np.ndarray:
    """Return a synthetically-degraded underwater version of a clean RGB image."""
    rng = np.random.default_rng(seed)
    J = rgb.astype(np.float64)
    t = np.exp(-_BETA * depth)                 # transmission per channel
    A = _BACKGROUND

    I = J * t[None, None, :] + A[None, None, :] * (1.0 - t[None, None, :])

    # mild forward-scatter blur + sensor noise
    I = cv2.GaussianBlur(I, (0, 0), sigmaX=0.8)
    I += rng.normal(0, 3.0, I.shape)

    return np.clip(I, 0, 255).astype(np.uint8)
