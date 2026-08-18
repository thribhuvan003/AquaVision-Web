"""Split labeled comparison composites into before/after stills."""
from pathlib import Path
from PIL import Image

SRC = Path(r"D:\AquaVision-Web\_src_photos")
OUT = Path(r"D:\AquaVision-Web\static\examples")
OUT.mkdir(parents=True, exist_ok=True)


def save(img: Image.Image, name: str) -> None:
    img.convert("RGB").save(OUT / name, "JPEG", quality=90, optimize=True)
    print(name, img.size)


def split_labeled(path: Path, stem: str) -> None:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    # Top caption + bottom metric bar from the existing composites.
    top, bottom = int(h * 0.08), int(h * 0.86)
    mid = w // 2
    before = im.crop((0, top, mid, bottom))
    after = im.crop((mid, top, w, bottom))
    save(before, f"{stem}-before.jpg")
    save(after, f"{stem}-after.jpg")


def split_grid(path: Path) -> None:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    rows, cols = 4, 2
    cell_w, cell_h = w // cols, h // rows
    # Row 1 (index 1) is the cleanest fish/kelp pair for a second slider.
    # Row 0 is rocks; use as the third pair.
    picks = [(0, "rocks"), (1, "kelp")]
    for row, stem in picks:
        y0 = row * cell_h
        before = im.crop((0, y0, cell_w, y0 + cell_h))
        after = im.crop((cell_w, y0, w, y0 + cell_h))
        save(before, f"{stem}-before.jpg")
        save(after, f"{stem}-after.jpg")


if __name__ == "__main__":
    split_labeled(SRC / "diver_green_real.jpg", "diver")
    split_labeled(SRC / "ruins_blue_real.jpg", "ruins")
    split_labeled(SRC / "shipwreck_real.jpg", "shipwreck")
    split_grid(SRC / "grid.png")
    print("done")
