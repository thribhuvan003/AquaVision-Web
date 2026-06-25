"""The benchmark metrics behave sanely on known inputs."""
import numpy as np

from benchmark import metrics as M


def _img(seed=0):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (96, 96, 3), dtype=np.uint8)


def test_psnr_identical_is_infinite():
    a = _img()
    assert M.psnr(a, a) == float("inf")


def test_ssim_identical_is_one():
    a = _img()
    assert abs(M.ssim(a, a) - 1.0) < 1e-6


def test_mse_zero_for_identical():
    a = _img()
    assert M.mse(a, a) == 0.0


def test_psnr_worse_for_noisier():
    a = _img(1)
    noisy = np.clip(a.astype(int) + 40, 0, 255).astype(np.uint8)
    noisier = np.clip(a.astype(int) + 80, 0, 255).astype(np.uint8)
    assert M.psnr(a, noisy) > M.psnr(a, noisier)


def test_uiqm_uciqe_return_finite_floats():
    a = _img(2)
    u, c = M.uiqm(a), M.uciqe(a)
    assert isinstance(u, float) and np.isfinite(u)
    assert isinstance(c, float) and np.isfinite(c)
