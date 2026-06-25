import io
import os
import random

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret")

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "underwater.jpg")


@pytest.fixture(scope="session")
def aqua_app():
    import app
    return app


@pytest.fixture
def client(aqua_app):
    return aqua_app.app.test_client()


@pytest.fixture
def image_bytes():
    with open(FIXTURE, "rb") as f:
        return f.read()


@pytest.fixture
def logged_in(client, image_bytes):
    email = f"t{random.randint(1, 10**9)}@example.com"
    client.post("/register", data={
        "name": "Test", "email": email, "password": "pw", "c_password": "pw"})
    client.post("/login", data={"email": email, "password": "pw"})
    return client


def upload(image_bytes, field="file", name="uw.jpg"):
    return {field: (io.BytesIO(image_bytes), name)}
