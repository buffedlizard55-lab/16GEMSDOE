"""H18 hypothesis operators (see docs/research/preregistration_h18.md for the fixed constants).

All operators are *label-free transforms of a score surface* plus, where stated, a prior derived from the geometry of
the faults the evaluator is allowed to know.  They never touch held-out (hidden) faults.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import convolve, gaussian_filter
from skimage.morphology import skeletonize

EPS = 1e-4


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p.astype(np.float64), EPS, 1.0 - EPS)
    return np.log(p / (1.0 - p))


def sigmoid(z: np.ndarray) -> np.ndarray:
    return (1.0 / (1.0 + np.exp(-z))).astype(np.float32)


def product_of_experts(probs: list[np.ndarray]) -> np.ndarray:
    """H18-1: sum of log-odds of independent experts (naive-Bayes / product-of-experts fusion, equal weights)."""
    z = np.zeros_like(probs[0], dtype=np.float64)
    for p in probs:
        z += logit(p)
    return sigmoid(z)


def seam_free_calibrate(p: np.ndarray, lid_ok: np.ndarray, fold_fp: np.ndarray, n_folds: int = 4) -> np.ndarray:
    """Identical to H16-1's per-fold quantile mapping of the no-lidar region onto the lidar-covered distribution."""
    out = p.copy()
    q = np.linspace(0.0, 1.0, 1001)
    for f in range(n_folds):
        m_lid = (fold_fp == f) & lid_ok
        m_gap = (fold_fp == f) & ~lid_ok
        if m_lid.any() and m_gap.any():
            out[m_gap] = np.interp(p[m_gap], np.quantile(p[m_gap], q), np.quantile(p[m_lid], q))
    return out


# ------------------------------------------------------------------ catalogue geometry (H18-3)
def endpoint_junction_density(known: np.ndarray, footprint: np.ndarray, sigma_px: float = 50.0) -> np.ndarray:
    """Smoothed density of fault-trace endpoints and junctions, rescaled to [0, 1] by its 99th percentile."""
    skel = skeletonize(known)
    nn = convolve(skel.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), mode="constant") - skel.astype(np.uint8)
    ends = skel & (nn <= 1)
    junc = skel & (nn >= 3)
    d = gaussian_filter((ends | junc).astype(np.float32), sigma_px)
    scale = float(np.percentile(d[footprint], 99)) or 1.0
    return np.clip(d / scale, 0.0, 1.0).astype(np.float32)


def local_strike_field(mask: np.ndarray, sigma_px: float = 100.0, pre_sigma: float = 1.5) -> tuple[np.ndarray, np.ndarray]:
    """Local dominant *strike* (radians, image coordinates) of a line raster and its structure-tensor trace.

    Strike is 90 degrees from the dominant gradient orientation.  ``trace`` ~ how much fault information is nearby
    (used to stay neutral where there is none).
    """
    s = gaussian_filter(mask.astype(np.float32), pre_sigma)
    gy, gx = np.gradient(s)
    jxx = gaussian_filter(gx * gx, sigma_px)
    jyy = gaussian_filter(gy * gy, sigma_px)
    jxy = gaussian_filter(gx * gy, sigma_px)
    theta_grad = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    return (theta_grad + np.pi / 2.0).astype(np.float32), (jxx + jyy).astype(np.float32)


def ridge_strike(surface: np.ndarray, sigma_grad: float = 2.0, sigma_tensor: float = 4.0) -> np.ndarray:
    """Local strike (radians) of the structure in a score surface (perpendicular to its dominant gradient)."""
    s = gaussian_filter(surface.astype(np.float32), sigma_grad)
    gy, gx = np.gradient(s)
    jxx = gaussian_filter(gx * gx, sigma_tensor)
    jyy = gaussian_filter(gy * gy, sigma_tensor)
    jxy = gaussian_filter(gx * gy, sigma_tensor)
    return (0.5 * np.arctan2(2.0 * jxy, jxx - jyy) + np.pi / 2.0).astype(np.float32)


def oblique_boost(surface: np.ndarray, known: np.ndarray, footprint: np.ndarray, mu: float = 1.0,
                  sigma_px: float = 100.0) -> np.ndarray:
    """H18-3b: ``1 + mu*sin^2(strike_ridge - strike_known)``; neutral (1.0) where no known fault lies within reach."""
    k_strike, trace = local_strike_field(known, sigma_px)
    r_strike = ridge_strike(surface)
    boost = 1.0 + mu * np.sin(r_strike - k_strike) ** 2
    info = trace > 0.02 * float(np.percentile(trace[footprint], 99))   # neutral where no fault information nearby
    return np.where(info, boost, 1.0).astype(np.float32)
