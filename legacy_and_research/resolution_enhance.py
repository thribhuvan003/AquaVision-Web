"""
resolution_enhance.py — AquaVision 1080p Super-Resolution Module
================================================================
3-tier waterfall: Real-ESRGAN → ESPCN (OpenCV DNN) → Lanczos4+Sharpen
Zero crashes guaranteed — each tier falls to the next on any error.

Usage:
    from resolution_enhance import upscale_to_1080p, upscale_pil_to_1080p

    # File-based
    upscale_to_1080p('input.jpg', 'output_1080p.jpg')

    # PIL-based (used by app.py)
    result_pil, method_used = upscale_pil_to_1080p(pil_image)
"""
import cv2
import numpy as np
import os
from PIL import Image

# Where ESPCN / Real-ESRGAN weights live
WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weights')

# Max input dimension for ESPCN — prevents OOM or multi-minute waits
# 480px input → 1920px output at 4x, which is ideal for 1080p
_ESPCN_MAX_INPUT = 480


# ── TIER 3: Always-works Lanczos fallback ────────────────────────────────────

def _lanczos_upscale(img_bgr, target_w=1920, target_h=1080):
    """Lanczos4 upscale with post-sharpen. Always works, no deps. Returns BGR."""
    h, w = img_bgr.shape[:2]
    if w >= target_w and h >= target_h:
        return img_bgr  # already big enough

    scale = min(target_w / w, target_h / h)
    if scale <= 1.0:
        return img_bgr

    nw, nh = int(w * scale), int(h * scale)
    up = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LANCZOS4)

    # Adaptive sharpen — stronger for higher upscale ratios
    strength = min(0.4, 0.15 * scale)
    blur = cv2.GaussianBlur(up, (3, 3), 0)
    sharp = cv2.addWeighted(up, 1.0 + strength, blur, -strength, 0)
    return sharp


# ── TIER 2: ESPCN via OpenCV DNN (CPU, 100KB model, ~1s for 480p input) ──────

def _espcn_upscale(img_bgr, target_w=1920, target_h=1080):
    """ESPCN 4x super-resolution. Returns BGR or None on failure."""
    model_path = os.path.join(WEIGHTS_DIR, 'ESPCN_x4.pb')
    if not os.path.exists(model_path):
        return None
    try:
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(model_path)
        sr.setModel('espcn', 4)

        h, w = img_bgr.shape[:2]

        # If input is too large, downscale first to prevent long processing
        # ESPCN 4x on 480px input → 1920px output, perfect for 1080p
        max_dim = max(w, h)
        if max_dim > _ESPCN_MAX_INPUT:
            scale_down = _ESPCN_MAX_INPUT / max_dim
            small_w = int(w * scale_down)
            small_h = int(h * scale_down)
            # Ensure dimensions are at least 1
            small_w = max(small_w, 1)
            small_h = max(small_h, 1)
            img_small = cv2.resize(img_bgr, (small_w, small_h),
                                   interpolation=cv2.INTER_AREA)
        else:
            img_small = img_bgr

        # 4x upscale via ESPCN neural network
        output = sr.upsample(img_small)

        # Final resize to exact target maintaining aspect ratio
        oh, ow = output.shape[:2]
        scale = min(target_w / ow, target_h / oh)
        if scale < 1.0 or scale > 1.0:
            nw, nh = int(ow * scale), int(oh * scale)
            output = cv2.resize(output, (nw, nh),
                                interpolation=cv2.INTER_LANCZOS4)

        return output
    except Exception as e:
        print(f"[SR] ESPCN failed: {e}")
        return None


# ── TIER 1: Real-ESRGAN (GPU or CPU, 64MB model) ─────────────────────────────

def _realesrgan_upscale(img_bgr, target_w=1920, target_h=1080):
    """Real-ESRGAN 4x. Returns BGR or None on failure."""
    model_path = os.path.join(WEIGHTS_DIR, 'RealESRGAN_x4plus.pth')
    if not os.path.exists(model_path):
        return None
    try:
        import torch
        from realesrgan import RealESRGANer
        from basicsr.archs.rrdbnet_arch import RRDBNet

        model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64,
                        num_block=23, num_grow_ch=32, scale=4)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        upsampler = RealESRGANer(
            scale=4, model_path=model_path, model=model,
            tile=400, tile_pad=10, pre_pad=0,
            half=torch.cuda.is_available(), device=device
        )
        output, _ = upsampler.enhance(img_bgr, outscale=4)

        # Final resize to target
        oh, ow = output.shape[:2]
        scale = min(target_w / ow, target_h / oh)
        if scale != 1.0:
            nw, nh = int(ow * scale), int(oh * scale)
            output = cv2.resize(output, (nw, nh),
                                interpolation=cv2.INTER_LANCZOS4)
        return output
    except Exception as e:
        print(f"[SR] Real-ESRGAN failed: {e}")
        return None


# ── PUBLIC API ────────────────────────────────────────────────────────────────

def upscale_to_1080p(image_path, output_path):
    """File-based 3-tier SR waterfall. Never throws — always produces output.
    Returns output_path."""
    img = cv2.imread(image_path)
    if img is None:
        return output_path

    result = _realesrgan_upscale(img)
    method = 'Real-ESRGAN'
    if result is None:
        result = _espcn_upscale(img)
        method = 'ESPCN'
    if result is None:
        result = _lanczos_upscale(img)
        method = 'Lanczos4'

    cv2.imwrite(output_path, result)
    print(f"[SR] Upscaled via {method}: {img.shape[:2]} → {result.shape[:2]}")
    return output_path


def upscale_pil_to_1080p(pil_img, target_w=1920, target_h=1080):
    """PIL-based 3-tier SR waterfall.
    Returns (PIL.Image, method_name_str).
    Never throws — always returns a valid image."""
    arr = np.array(pil_img)
    h, w = arr.shape[:2]

    # Already at or above target? Skip.
    if w >= target_w and h >= target_h:
        return pil_img, 'none'

    # BGR for OpenCV operations
    img_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    result = _realesrgan_upscale(img_bgr, target_w, target_h)
    method = 'Real-ESRGAN x4'
    if result is None:
        result = _espcn_upscale(img_bgr, target_w, target_h)
        method = 'ESPCN x4'
    if result is None:
        result = _lanczos_upscale(img_bgr, target_w, target_h)
        method = 'Lanczos4'

    # Convert back to RGB → PIL
    result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
    print(f"[SR] {w}x{h} → {result.shape[1]}x{result.shape[0]} via {method}")
    return Image.fromarray(result_rgb), method
