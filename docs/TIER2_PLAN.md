# AquaVision-Web — Tier 2 Upgrade Plan

**Goal:** Turn AquaVision-Web into a portfolio project credible enough to compete with
top-tier-college engineers for high-package roles — every claim measured, code
structured at a senior level, demo live.

**Owner:** thribhuvan003 <thribhuvan003@gmail.com>
**Date:** 2026-06-25

## Current state (as cloned)
- `app.py`: 2,428-line Flask monolith — routing, auth (SQLite), two enhancement
  engines, video pipeline, REST API all in one file.
- Two enhancement engines:
  1. Classical CV (Ancuti multi-scale fusion + DCP dehaze + white balance) routed by
     a MobileNetV2 degradation classifier (`best_model.pth`, 12 MB).
  2. Deep-learning path: DPEM → Depth-Anything-V2 → DPF-Net (`checkpoints/*.pth`, ~340 MB),
     lazy-loaded.
- README is feature-rich but marketing-heavy with **no measured metrics**.
- No tests, no CI.

## Workstreams
0. **Setup** — clone, salvage eval harness from old research repo, set git identity. *(done)*
1. **Baseline + smoke test** — run app in venv, push one image + one video through,
   lock behavior with a smoke test before refactoring.
2. **Real metrics** — `benchmark/` computing PSNR/SSIM/MSE on synthetic degraded↔GT
   pairs and UIQM/UCIQE (no-reference) on real underwater images, over a fixed test set.
   Output: metrics table + before/after grid.
3. **Refactor** — split `app.py` into an `aquavision/` package
   (`routes`, `pipelines/{classical,deeplearning}`, `models`, `video`, `api`, `auth`),
   behavior guarded by the smoke test.
4. **Tests + CI** — pytest for pipeline + metrics; GitHub Actions (lint + test) with badge.
5. **README rewrite** — value prop, live link + GIF, real metrics table, architecture
   diagram, reproducible run/benchmark instructions, honest claims only.
6. **Deploy** — Hugging Face Spaces (Docker, free CPU tier, ~16 GB RAM fits full pipeline).
7. **Resume bullets** — 2–3 honest, quantified XYZ bullets with the live link.

## Principles
- No claim in README/resume that isn't produced by the benchmark harness.
- Refactor must not change observable behavior (smoke test is the guard).
- Commit/push as thribhuvan003, no AI co-author trailers.
