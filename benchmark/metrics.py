"""Underwater image-quality metrics.

Full-reference (need a clean ground-truth): PSNR, SSIM, MSE.
No-reference (the standard underwater metrics):
  * UIQM  - Underwater Image Quality Measure (Panetta et al., IEEE JOE 2016)
  * UCIQE - Underwater Colour Image Quality Evaluation (Yang & Sowmya, IEEE TIP 2015)

The UIQM/UCIQE code is a faithful port of the most widely-cited reference
implementation (Xuelei Chen, github.com/xueleichen/PSNR-SSIM-UCIQE-UIQM-Python),
updated for modern scikit-image and made float-safe to avoid the uint8 subtraction
wrap-around in the original. Using a recognised reference - rather than the generic
colourfulness/entropy proxies the original app mislabelled "UIQM/UCIQE" - keeps the
README/resume numbers comparable to published work.
"""
from __future__ import annotations

import math

import numpy as np
from skimage import color, filters
from skimage.metrics import peak_signal_noise_ratio, structural_similarity


# --------------------------------------------------------------------------- #
# Full-reference
# --------------------------------------------------------------------------- #
def mse(gt: np.ndarray, x: np.ndarray) -> float:
    return float(np.mean((gt.astype(np.float64) - x.astype(np.float64)) ** 2))


def psnr(gt: np.ndarray, x: np.ndarray) -> float:
    return float(peak_signal_noise_ratio(gt, x, data_range=255))


def ssim(gt: np.ndarray, x: np.ndarray) -> float:
    return float(structural_similarity(gt, x, channel_axis=-1, data_range=255))


# --------------------------------------------------------------------------- #
# UCIQE (Yang & Sowmya 2015)
# --------------------------------------------------------------------------- #
def uciqe(rgb_uint8: np.ndarray) -> float:
    c1, c2, c3 = 0.4680, 0.2745, 0.2576
    lab = color.rgb2lab(rgb_uint8.astype(np.float64) / 255.0)
    l = lab[:, :, 0]

    chroma = (lab[:, :, 1] ** 2 + lab[:, :, 2] ** 2) ** 0.5
    uc = np.mean(chroma)
    sc = (np.mean((chroma - uc) ** 2)) ** 0.5

    top = int(round(0.01 * l.shape[0] * l.shape[1])) or 1
    sl = np.sort(l, axis=None)
    conl = np.mean(sl[::-1][:top]) - np.mean(sl[:top])

    l1 = l.flatten()
    chroma1 = chroma.flatten()
    sat = np.divide(chroma1, l1, out=np.zeros_like(chroma1), where=l1 != 0)
    us = np.mean(sat)

    return float(c1 * sc + c2 * conl + c3 * us)


# --------------------------------------------------------------------------- #
# UIQM (Panetta et al. 2016)
# --------------------------------------------------------------------------- #
def _eme(ch: np.ndarray, blocksize: int = 8) -> float:
    num_x = math.ceil(ch.shape[0] / blocksize)
    num_y = math.ceil(ch.shape[1] / blocksize)
    eme = 0.0
    w = 2.0 / (num_x * num_y)
    for i in range(num_x):
        xlb = i * blocksize
        xrb = (i + 1) * blocksize if i < num_x - 1 else ch.shape[0]
        for j in range(num_y):
            ylb = j * blocksize
            yrb = (j + 1) * blocksize if j < num_y - 1 else ch.shape[1]
            block = ch[xlb:xrb, ylb:yrb]
            bmin = float(np.min(block)) or 1.0
            bmax = float(np.max(block)) or 1.0
            eme += w * math.log(bmax / bmin)
    return eme


def _plipsum(i, j, gamma=1026): return i + j - i * j / gamma
def _plipsub(i, j, k=1026): return k * (i - j) / (k - j)
def _plipmult(c, j, gamma=1026): return gamma - gamma * (1 - j / gamma) ** c


def _logamee(ch: np.ndarray, blocksize: int = 8) -> float:
    num_x = math.ceil(ch.shape[0] / blocksize)
    num_y = math.ceil(ch.shape[1] / blocksize)
    s = 0.0
    w = 1.0 / (num_x * num_y)
    for i in range(num_x):
        xlb = i * blocksize
        xrb = (i + 1) * blocksize if i < num_x - 1 else ch.shape[0]
        for j in range(num_y):
            ylb = j * blocksize
            yrb = (j + 1) * blocksize if j < num_y - 1 else ch.shape[1]
            block = ch[xlb:xrb, ylb:yrb]
            bmin = float(np.min(block))
            bmax = float(np.max(block))
            top = _plipsub(bmax, bmin)
            bottom = _plipsum(bmax, bmin)
            m = top / bottom if bottom != 0 else 0.0
            if m != 0.0:
                s += m * np.log(abs(m))
    return _plipmult(w, s)


def uiqm(rgb_uint8: np.ndarray) -> float:
    p1, p2, p3 = 0.0282, 0.2953, 3.5753
    rgb = rgb_uint8.astype(np.float64)          # float-safe (no uint8 wrap-around)

    # UICM
    rg = rgb[:, :, 0] - rgb[:, :, 1]
    yb = (rgb[:, :, 0] + rgb[:, :, 1]) / 2 - rgb[:, :, 2]
    rgl = np.sort(rg, axis=None)
    ybl = np.sort(yb, axis=None)
    T = int(0.1 * len(rgl)) or 1
    rgl_tr, ybl_tr = rgl[T:-T], ybl[T:-T]
    urg, uyb = np.mean(rgl_tr), np.mean(ybl_tr)
    s2rg, s2yb = np.mean((rgl_tr - urg) ** 2), np.mean((ybl_tr - uyb) ** 2)
    uicm = -0.0268 * np.sqrt(urg ** 2 + uyb ** 2) + 0.1586 * np.sqrt(s2rg + s2yb)

    # UISM
    gray01 = color.rgb2gray(rgb_uint8)          # [0,1]
    rs = rgb[:, :, 0] * filters.sobel(rgb_uint8[:, :, 0].astype(np.float64))
    gs = rgb[:, :, 1] * filters.sobel(rgb_uint8[:, :, 1].astype(np.float64))
    bs = rgb[:, :, 2] * filters.sobel(rgb_uint8[:, :, 2].astype(np.float64))
    uism = 0.299 * _eme(rs) + 0.587 * _eme(gs) + 0.114 * _eme(bs)

    # UIConM
    uiconm = _logamee(gray01)

    return float(p1 * uicm + p2 * uism + p3 * uiconm)


def all_no_reference(img_rgb: np.ndarray) -> dict:
    return {"UIQM": round(uiqm(img_rgb), 4), "UCIQE": round(uciqe(img_rgb), 4)}
