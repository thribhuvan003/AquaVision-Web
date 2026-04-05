# AquaVision KAIROS Project Memory

## Overview
AquaVision is a Flask-based underwater imagery/video enhancement tool using PyTorch deep learning models + classical computer vision pipelines (CLAHE, dehazing, super-resolution).
It accepts image and video uploads, processes them to remove underwater artifacts (color casts, turbidity), and provides processed downloads.

## Key Architectures
- **Frontend:** Vanilla HTML/JS, Vite-based React components (where applicable), Tailwind/Vanilla CSS (Glassmorphic underwater theme).
- **Backend:** Flask web server.
- **Machine Learning:** PyTorch (`best_model.pth` classifying valid underwater formats), followed by classical `_video_frame_enhance`.
- **Database:** SQLite (`videoTasks.db`) for tracking long-running queue jobs for video processing. Contains columns: `id`, `user_email`, `original_filename`, `status`, `progress`, `result_path`, `timestamp`, `frames_processed`, `total_frames`.
- **Video Pipeline:** Uses a fallback `ffmpeg` (system binary) → `imageio` → OpenCV `VideoWriter` mechanism. Employs short temp file generation to bypass 260 character max path limitations on Windows, and remuxes output to H.264 `faststart` for browser playable `.mp4`.

## Active Patterns (KAIROS Mode)
- **Zero-Block Execution:** Do not prompt the user for arbitrary input unless fundamentally blocked.
- **Relentless Tool Use:** Verify state using tools instead of making logical leaps.
- **Memory Consolidation:** Maintain records of debugging runs inside `docs/logs/YYYY-MM-DD.md`.
- **Relative Paths vs Absolute Paths:** Because the server could be launched differently, critical DB pathways and directories use `BASE_DIR = os.path.dirname(os.path.abspath(__file__))`.

## Development Commands
- `python app.py` (Development server on port 5000)

## Security & Auth
- Relies on basic session storage (`session['user_email']`).
- No external APIs are integrated right now, but remain vigilant for Supabase JWT/Anon interactions if introduced.
