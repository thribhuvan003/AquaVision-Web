# AquaVision — Resume Material

All numbers below are **real and reproducible** (`python -m benchmark.run`).
Replace `<LIVE_URL>` once the Hugging Face Space is live.

## Resume bullets (pick 2–3)

**Product + impact**
- Built and deployed **AquaVision** (<LIVE_URL>), a CPU-only underwater image &
  video enhancement web app (Flask, PyTorch, OpenCV); a MobileNetV2 classifier
  routes 9 image-degradation types to a classical restoration pipeline that lifts
  image quality by **+8.2 UCIQE** and **+3.6 dB PSNR** on a reproducible 48-image
  benchmark, processing images in **~0.8 s on CPU** (no GPU, no paid API).

**Engineering rigor / production-readiness**
- Hardened the project for production: built a **17-route end-to-end verification
  harness** that surfaced **3 latent bugs** (a JSON-serialization API 500, a
  worker-crashing logging bug, and a **322 MB dead-model pipeline** never wired
  into any route), added a **16-test pytest suite with GitHub Actions CI**, and
  replaced **plaintext password storage with salted hashing**.

**Measurement / evaluation**
- Designed a **reproducible benchmark** (UIQM, UCIQE, PSNR, SSIM) that synthesizes
  ground-truth pairs from a physical underwater image-formation model, enabling
  objective before/after evaluation instead of subjective claims.

## One-liner (if space is tight)
- **AquaVision** — deployed CPU-only underwater image/video enhancement web app
  (Flask + PyTorch + OpenCV) with a MobileNetV2 degradation router; +8.2 UCIQE /
  +3.6 dB PSNR on a reproducible benchmark, 16-test CI, live demo at <LIVE_URL>.

## Interview talking points (when they open the repo)

- **"Why classical CV, not deep learning?"** A trained DL pipeline existed in the
  repo but was never invoked and underperformed; I measured the classical pipeline,
  saw it was strong and 0.8 s/CPU, removed 322 MB of dead weights, and kept what was
  real. Engineering judgment over hype.
- **"How do you know it works?"** Reproducible benchmark with standard metrics —
  full-reference (PSNR/SSIM vs synthetic ground truth) and no-reference (UIQM/UCIQE
  on real photos). I report UIQM's slight dip honestly rather than cherry-picking.
- **"What was broken and how did you find it?"** A 17-route harness caught a 500 in
  the JSON API (numpy float32 not serializable) and a video worker crash on a
  non-ASCII log line — both invisible through the web UI.
- **System design:** classify → route → restore → quality-gate → adaptive re-boost;
  async background video jobs with progress polling; token-auth REST API.
