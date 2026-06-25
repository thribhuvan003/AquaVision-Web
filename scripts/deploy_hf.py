"""Deploy AquaVision to a Hugging Face Docker Space.

Usage:
    export HF_TOKEN=hf_xxx            # a WRITE token from huggingface.co/settings/tokens
    python scripts/deploy_hf.py thribhuvan003/AquaVision

Uploads the repo to a Docker Space (handles large files via LFS automatically),
skipping local/dev/research clutter. The Space builds the Dockerfile and serves
the app on port 7860.
"""
import os
import sys
import tempfile

from huggingface_hub import HfApi

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SPACE_README = """---
title: AquaVision
emoji: 🌊
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---

"""

# things that should never ship to the running Space
IGNORE = [
    ".git/*", ".github/*", ".venv/*", "venv/*", "__pycache__/*", "*.pyc",
    "legacy_and_research/*", "checkpoints/*", "weights/*", "benchmark/*",
    "tests/*", "docs/*", ".env", "database.db", "videoTasks.db",
    "_smoke_check.py", "_verify_*.py", "static/uploads/*", "static/enhanced/*",
    "static/video_*/*", "static/depth/*",
]


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/deploy_hf.py <user>/<space-name>")
    repo_id = sys.argv[1]
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("Set HF_TOKEN (a write token from huggingface.co/settings/tokens)")

    api = HfApi(token=token)
    print(f"[deploy] creating Space {repo_id} (docker)…")
    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)

    # Space needs its own README with the HF metadata header on top.
    with open(os.path.join(REPO_ROOT, "README.md"), encoding="utf-8") as f:
        body = f.read()
    with tempfile.TemporaryDirectory() as td:
        readme = os.path.join(td, "README.md")
        with open(readme, "w", encoding="utf-8") as f:
            f.write(SPACE_README + body)
        api.upload_file(path_or_fileobj=readme, path_in_repo="README.md",
                        repo_id=repo_id, repo_type="space")

    print("[deploy] uploading application files (large weights via LFS)…")
    api.upload_folder(
        folder_path=REPO_ROOT, repo_id=repo_id, repo_type="space",
        ignore_patterns=IGNORE + ["README.md"],
        commit_message="Deploy AquaVision",
    )
    print(f"[deploy] done: https://huggingface.co/spaces/{repo_id}")
    print("[deploy] first build takes a few minutes (installing torch + opencv).")


if __name__ == "__main__":
    main()
