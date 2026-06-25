"""The enhancement pipeline actually changes the image and reports metrics."""
import numpy as np
from PIL import Image

from conftest import FIXTURE


def test_classify_returns_known_class(aqua_app):
    res, _, _ = aqua_app.predict_underwater_image(FIXTURE)
    assert res["prediction"] in aqua_app.CLASSES
    assert 0 <= res["confidence"] <= 100


def test_enhance_changes_pixels(aqua_app):
    img = Image.open(FIXTURE).convert("RGB")
    res, original, _ = aqua_app.predict_underwater_image(FIXTURE)
    enhanced = aqua_app.adaptive_classical_enhance(original, res["prediction"])
    diff = np.mean(np.abs(np.array(original).astype(int) -
                          np.array(enhanced.resize(original.size)).astype(int)))
    assert diff > 1.0  # output is not a no-op


def test_quality_metrics_are_native_floats(aqua_app):
    img = Image.open(FIXTURE).convert("RGB")
    metrics = aqua_app.get_quality_metrics(img)
    for k, v in metrics.items():
        assert type(v) is float, f"{k} is {type(v)} (must be JSON-serializable float)"
