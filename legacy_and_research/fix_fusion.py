
lines = open('app.py', 'r', encoding='utf-8').readlines()

new_fn = (
    "def _multiscale_fusion(img1, img2, levels=4):\n"
    "    \"\"\"Fuse two enhanced images using Ancuti-style weight maps.\n"
    "    Simple weighted-average blend - NO Laplacian pyramid (avoids checkerboard blocks).\n"
    "    Uses contrast, saturation, saliency weight maps from original Ancuti paper.\n"
    "    Input/output: uint8 RGB arrays.\"\"\"\n"
    "    w1 = (_laplacian_contrast_weight(img1) +\n"
    "          _saturation_weight(img1) +\n"
    "          _saliency_weight(img1) + 1e-6)\n"
    "    w2 = (_laplacian_contrast_weight(img2) +\n"
    "          _saturation_weight(img2) +\n"
    "          _saliency_weight(img2) + 1e-6)\n"
    "    w_sum = w1 + w2\n"
    "    w1_norm = (w1 / w_sum)[:, :, np.newaxis]\n"
    "    w2_norm = (w2 / w_sum)[:, :, np.newaxis]\n"
    "    fused = (img1.astype(np.float64) * w1_norm +\n"
    "             img2.astype(np.float64) * w2_norm)\n"
    "    return np.clip(fused, 0, 255).astype(np.uint8)\n"
    "\n"
)

start = None
end = None
for i, line in enumerate(lines):
    if 'def _multiscale_fusion' in line and start is None:
        start = i
    if start is not None and i > start and line.strip().startswith('def ') and '_multiscale_fusion' not in line:
        end = i
        break

print(f'Found _multiscale_fusion: lines {start+1} to {end}')
new_lines = lines[:start] + [new_fn] + lines[end:]
open('app.py', 'w', encoding='utf-8').writelines(new_lines)
print(f'Done. Was {len(lines)} lines, now {len(new_lines)} lines')
