"""
depth_anything_v2.dpt stub
Provides DepthAnythingV2 class so the import doesn't crash when the full
package isn't installed. The actual weights are loaded at runtime from
checkpoints/dav2.pth — if that file is missing, _load_dl_models() sets
_dl_load_error and the DPF-Net path falls back to the classical pipeline.
"""
import torch
import torch.nn as nn


class DepthAnythingV2(nn.Module):
    """Minimal stub — replace with full implementation when dav2.pth is available."""

    def __init__(self, **kwargs):
        super().__init__()
        self.encoder = kwargs.get('encoder', 'vits')
        self.features = kwargs.get('features', 64)
        self.out_channels = kwargs.get('out_channels', [48, 96, 192, 384])
        # Tiny conv so load_state_dict finds *some* parameters
        self._stub_conv = nn.Conv2d(3, 1, 1)

    def forward(self, x):
        # Returns a single-channel depth map of the same H×W
        b, c, h, w = x.shape
        return torch.zeros(b, 1, h, w, device=x.device)

    def infer_image(self, raw_image, input_size=518):
        import numpy as np
        h, w = raw_image.shape[:2]
        return np.zeros((h, w), dtype=np.float32)
