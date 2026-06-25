# Benchmark

Measures how much AquaVision's enhancement actually improves an image, using
recognised image-quality metrics — so the numbers in the main README are real
and reproducible, not marketing.

## What it measures

**No-reference** (on real underwater photos — no clean version exists):
- **UIQM** and **UCIQE**, the two standard underwater quality scores.

**Full-reference** (clean photo → fake underwater → enhance → compare to original):
- **PSNR** and **SSIM** against the known clean image.

## Run it

```bash
pip install -r requirements-dev.txt
python -m benchmark.run
```

Outputs:
- `benchmark/results/metrics.md` — the results table
- `benchmark/results/grid.png` — before/after examples

## Notes
- Images are resized to max 768px so it finishes quickly on a normal CPU.
- UIQM/UCIQE use the widely-cited reference implementation by Xuelei Chen
  (github.com/xueleichen/PSNR-SSIM-UCIQE-UIQM-Python), ported to current
  scikit-image. PSNR/SSIM use scikit-image.
