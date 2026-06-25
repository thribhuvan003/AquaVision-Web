FROM python:3.10-slim

# Prevent Python from writing .pyc files / buffering output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System libraries required for OpenCV
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run the container as a non-root user (uid 1000).
# Create it so the app can write its SQLite DBs and upload folders.
RUN useradd -m -u 1000 user

WORKDIR /app

# Install deps first (as root) to leverage Docker layer cache.
# CPU-only PyTorch — avoids the ~2GB CUDA build.
COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code owned by the runtime user
COPY --chown=user:user . .

# Ensure writable runtime directories, owned by the runtime user
RUN mkdir -p static/uploads static/enhanced static/depth \
    static/video_uploads static/video_frames static/video_enhanced \
    && chown -R user:user /app

USER user

# Hugging Face Spaces serve on 7860; app.py reads $PORT.
ENV PORT=7860
EXPOSE 7860

CMD ["python", "app.py"]
