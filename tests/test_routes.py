"""Every user-facing route returns a sane response."""
from conftest import upload


def test_public_pages(client):
    assert client.get("/").status_code == 200
    assert client.get("/about").status_code == 200


def test_gated_route_redirects_when_logged_out(client):
    assert client.get("/prediction").status_code in (301, 302)


def test_register_and_login(client):
    import random
    email = f"r{random.randint(1, 10**9)}@example.com"
    r = client.post("/register", data={
        "name": "T", "email": email, "password": "pw", "c_password": "pw"})
    assert b"Successfully Registered" in r.data
    r = client.post("/login", data={"email": email, "password": "pw"})
    assert r.status_code == 200
    # wrong password is rejected
    r = client.post("/login", data={"email": email, "password": "nope"})
    assert b"Invalid Password" in r.data


def test_gated_pages_accessible_when_logged_in(logged_in):
    for path in ["/home", "/batch", "/api_docs", "/gallery", "/api_dashboard", "/model"]:
        assert logged_in.get(path).status_code == 200, path


def test_prediction_enhances_image(logged_in, image_bytes):
    r = logged_in.post("/prediction", data=upload(image_bytes),
                       content_type="multipart/form-data")
    assert r.status_code == 200
    assert b"prediction" in r.data.lower() or b"enhanced" in r.data.lower()


def test_api_preview(logged_in, image_bytes):
    r = logged_in.post("/api/preview", data=upload(image_bytes),
                       content_type="multipart/form-data")
    assert r.status_code == 200
    assert b"enhanced_image_base64" in r.data


def test_api_v1_enhance_serializes(logged_in, image_bytes):
    """Regression: metrics must JSON-serialize (numpy float32 once broke this)."""
    r = logged_in.post("/api/v1/enhance", data=upload(image_bytes),
                       content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()
    assert "enhanced_image_base64" in body
    assert "metrics_original" in body or "prediction" in body


def test_batch_enhance(logged_in, image_bytes):
    import io
    data = {"files": [(io.BytesIO(image_bytes), "a.jpg"),
                      (io.BytesIO(image_bytes), "b.jpg")]}
    r = logged_in.post("/batch_enhance", data=data,
                       content_type="multipart/form-data")
    assert r.status_code == 200
