# 🌊 AquaVision — SOTA Marine Image & Video Enhancement

AquaVision is an industry-grade, **State-Of-The-Art (SOTA)** web application for processing, classifying, and mathematically restoring heavily degraded underwater media.

By leveraging a **Hybrid-SOTA Pipeline** (Ancuti Multi-Scale Fusion + Temporal Smoothing + MobileNetV2), AquaVision restores 4K pelagic photography and deep-sea cave videos with zero flickering, running comfortably on CPU infrastructure.

---

## 📸 Key Features

- **Abyssal Light Engine** — Detects extreme low-illumination (cave diving) and runs Adaptive Gamma (AGC) to rescue shadow detail without blowing highlights.
- **Zero-Flicker Video Processing** — T=5 Exponential Moving Average (EMA) temporal memory smooths White Balance, DCP Dehazing, and Auto-Exposure across frames.
- **Multi-Scale Laplacian Fusion** — Blends color-compensated frames with physical haze-removal to generate explosive 3D contrast.
- **AI Degradation Routing** — MobileNetV2 (`best_model.pth`) detects 9 water degradation classes (Blue Tint, Green Turbidity, Blur, etc.) and routes to optimised physics algorithms.
- **Async Video Pipeline** — Video jobs run in background threads with live progress polling; never blocks the server.
- **Batch Enhancement** — Upload up to 20 images at once; results are zipped and served for download.
- **API Access** — REST API with key-based auth; dashboard available at `/api-docs`.
- **Premium UI** — Dark Ocean glassmorphic frontend: GSAP scroll triggers, WebGL fluid simulation, magnetic hover buttons.

---

## 🔧 The Mathematical Pipeline

```text
Input
  ↳ 1. Bilateral Pre-Denoise (protects JPEG compression)
  ↳ 2. Physics-Based Red Channel Recovery (K_R capped at 1.3)
  ↳ 3. Abyssal Rescue: Adaptive Gamma Illumination Map
  ↳ 4. Gray World White Balance (Temporally Smoothed)
  ↳ 5. CLAHE (LAB-Space Contrast, clip=2.0)
  ↳ 6. Dark Channel Prior Dehazing
  ↳ 7. Ancuti Multi-Scale Pyramidal Fusion
  ↳ 8. Proportional LAB Shift
  ↳ 9. Unsharp Mask & Auto-Exposure Normalisation
  ↳ 10. Output HD Frame
```

---

## 🚀 Quick Start

### 1. System Dependencies (Required First)

> **⚠️ ffmpeg is a hard dependency for video processing.** Without it, all video uploads will fail silently.

**Windows:**
```bash
winget install ffmpeg
# or download from https://ffmpeg.org/download.html and add to PATH
```

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt update && sudo apt install -y ffmpeg
```

Verify installation:
```bash
ffmpeg -version
```

---

### 2. Python Environment

Requires **Python 3.10+**.

```bash
pip install -r requirements.txt
```

---

### 3. Environment Configuration

Copy and fill in the template:
```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ Yes | Flask session key. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MAIL_SENDER` | Optional | Gmail address for video-ready email notifications |
| `MAIL_APP_PASSWORD` | Optional | 16-char Google App Password for the above |

> If `SECRET_KEY` is absent, AquaVision generates a random key at startup — **sessions will not survive a server restart.**

---

### 4. Verify Weights

Ensure `best_model.pth` (≈12 MB) is in the project root alongside `checkpoints/`.

---

### 5. Launch

**Development:**
```bash
python app.py
```

**Production (multi-threaded, recommended):**
```bash
python -c "
from waitress import serve
from app import app
import os
port = int(os.environ.get('PORT', 5050))
print(f'AquaVision running on http://0.0.0.0:{port}')
serve(app, host='0.0.0.0', port=port, threads=8)
"
```

Open **http://127.0.0.1:5050** in your browser.

---

## 📁 Project Structure

```text
AquaVision/
├── app.py                  # Master Flask application & SOTA pipeline
├── best_model.pth          # MobileNetV2 classification weights (≈12 MB)
├── checkpoints/            # Additional model checkpoints
├── database.db             # SQLite — users & API keys
├── videoTasks.db           # SQLite — async video job state
├── requirements.txt        # Python dependency manifest
├── .env                    # Local secrets (never commit)
├── .env.example            # Template — copy to .env
├── static/                 # CSS, JS, uploaded media
│   ├── css/abyssal.css     # Abyssal Design System tokens
│   └── js/abyssal.js       # Global interactions & animations
├── templates/              # Jinja2 HTML templates
│   ├── index.html          # Landing page
│   ├── home.html           # Dashboard
│   ├── prediction.html     # Image enhancement
│   ├── video_prediction.html # Video upload & async tracking
│   ├── batch.html          # Batch processing
│   └── ...                 # Gallery, API docs, auth pages
├── Run_AquaVision.bat      # One-click Windows launcher
├── DPEM/                   # Depth Prior Enhancement Module
├── Depth_Anything_V2_main/ # Depth estimation backbone
└── legacy_and_research/    # Archived R&D notebooks & unused GAN models
```

---

## 🔐 Security Notes

- `SECRET_KEY` **must** be set to a secure random value in production.
- `database.db` and `videoTasks.db` contain user data — **never expose publicly**.
- The `static/uploads/` directory should be served behind a web server (nginx/caddy) in production, not directly by Flask.
- Uploaded filenames are UUID-based — no path traversal risk.

---

## 📚 Core Academic References

1. **Ancuti, C. et al. (2012/2018).** *Enhancing underwater images and videos by fusion*
2. **He, K. et al. (2009).** *Single Image Haze Removal Using Dark Channel Prior*
3. **Guo, X. et al. (2016).** *LIME: Low-light Image Enhancement via Illumination Map*
4. **Sandler et al. (2018).** *MobileNetV2: Inverted Residuals and Linear Bottlenecks*
