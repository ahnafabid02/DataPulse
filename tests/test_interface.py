from fastapi.testclient import TestClient
from pydantic import SecretStr

from datapulse.central.app import create_app
from datapulse.central.config import Settings


def test_interface_serving_does_not_expose_business_routes_or_files(empty_engine, tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (tmp_path / "index.html").write_text("<html><title>DataPulse</title></html>", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('interface');", encoding="utf-8")
    (tmp_path / "private.env").write_text("private-value", encoding="utf-8")
    settings = Settings(database_url=SecretStr("postgresql+psycopg://demo:test@localhost/test"))
    with TestClient(create_app(settings, engine=empty_engine, ui_directory=tmp_path)) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "DataPulse" in response.text
        assert response.headers["cache-control"] == "no-cache"
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/favicon.svg").headers["content-type"].startswith("image/svg+xml")
        assert client.get("/private.env").status_code == 404
        assert client.get("/assets/%2e%2e/private.env").status_code == 404
        assert client.post("/v1/sources", json={"name": "test"}).status_code == 404
        assert set(client.get("/openapi.json").json()["paths"]) == {"/health/live", "/health/ready"}


def test_unbuilt_interface_fails_explicitly(empty_engine, tmp_path):
    settings = Settings(database_url=SecretStr("postgresql+psycopg://demo:test@localhost/test"))
    with TestClient(create_app(settings, engine=empty_engine, ui_directory=tmp_path)) as client:
        assert client.get("/").status_code == 503
        assert client.get("/").json() == {"error": "interface_not_built"}
        assert client.get("/favicon.svg").status_code == 404
