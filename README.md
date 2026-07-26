# AquaVision

**Underwater image and video enhancement that runs on a normal CPU.**

Live demo: [Hugging Face Spaces](https://huggingface.co/spaces/mark2423432/AquaVision)

Water absorbs red light and scatters blue-green. Photos come out hazy and tinted. AquaVision classifies the degradation, then restores colour and contrast with classical computer vision (plus a small MobileNetV2 router). **No account required** for the main enhance flow. No GPU. No paid AI API.

[![CI](https://github.com/thribhuvan003/AquaVision-Web/actions/workflows/ci.yml/badge.svg)](https://github.com/thribhuvan003/AquaVision-Web/actions/workflows/ci.yml)

---

## Try it

1. Open the live demo or run locally.
2. Go to **Enhance** — upload a photo.
3. Download the result. Optional: video, batch, gallery.

Sign-in is only for saving an API key dashboard identity. Guests can enhance freely.

---

## How it works

```text
Upload → classify (9 modes) → matched classical pipeline → metrics → download
```

| Stage | What happens |
| --- | --- |
| Classify | MobileNetV2 picks blue tint, haze, low light, blur, … |
| Enhance | White balance, red recovery, dehaze, CLAHE, multi-scale fusion |
| Check | Quality metrics (UCIQE, UIQM, …); optional stronger pass |
| Video | Frame-by-frame job with progress polling |

Measured results (reproducible harness in `benchmark/`):

| Metric | Before → After |
| --- | --- |
| UCIQE | 23.16 → **31.33** (+8.2) |
| PSNR (simulated) | 9.97 → **13.53** dB (+3.6) |

---

## Architecture

```text
Browser (templates + static/)
    │  multipart upload / poll
    ▼
Flask (app.py)
    ├── /prediction          image enhance (guest OK)
    ├── /video_prediction    video jobs (guest OK)
    ├── /batch_enhance       multi-image zip (guest OK)
    ├── /api/v1/enhance      REST + optional API key
    └── SQLite               users · api_keys · video_tasks
    │
    ▼
CPU pipeline: MobileNetV2 + OpenCV / NumPy / PIL classical stages
```

Frontend and backend are the same Flask app: Jinja templates call `url_for(...)` routes; forms POST to the same origin; JS polls `/api/task_status/...` for video.

---

## Repository layout

```text
AquaVision-Web/
├── app.py                 Flask app + enhancement pipeline
├── templates/             HTML pages (landing, enhance, video, …)
├── static/
│   ├── css/               abyssal design system + pages
│   ├── js/                nav, a11y, interactions
│   ├── uploads/           user uploads (runtime)
│   └── enhanced/          outputs (runtime)
├── benchmark/             Metrics harness + results grid
├── tests/                 pytest routes + pipeline
├── docs/                  Resume notes, plans
├── scripts/               Deploy helpers
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Local run

**Python 3.10+**

```bash
git clone https://github.com/thribhuvan003/AquaVision-Web.git
cd AquaVision-Web
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
set SECRET_KEY=dev-secret-change-me
python app.py
```

Open `http://127.0.0.1:5000` → **Enhance an image** (no login).

```bash
pytest
```

---

## API (optional)

`POST /api/v1/enhance` — multipart image. Works without a key for demo; use a Bearer key from the optional dashboard for production clients.

Docs page: `/api_docs` when the server is running.

---

## Author

[thribhuvan003](https://github.com/thribhuvan003)

MIT License
