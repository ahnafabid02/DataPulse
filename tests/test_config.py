import pytest
from pydantic import SecretStr, ValidationError

from datapulse.central.config import Settings


def test_configuration_is_required_and_redacted(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATAPULSE_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv(
        "DATAPULSE_DATABASE_URL", "postgresql+psycopg://demo:private-value@localhost/test"
    )
    settings = Settings()
    assert "private-value" not in repr(settings)
    assert "private-value" not in settings.model_dump_json()


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///test.db",
        "postgresql://user:private-value@localhost/test",
        "postgresql+psycopg://user@localhost/test",
        "postgresql+psycopg://user:CHANGE_ME@localhost/test",
        "private-value",
        "postgresql+psycopg://user:private-value@localhost:bad/test",
    ],
)
def test_invalid_urls_fail_without_echoing_secrets(url):
    with pytest.raises(ValidationError) as failure:
        Settings(database_url=SecretStr(url), _env_file=None)
    assert url not in str(failure.value)
    assert "private-value" not in str(failure.value)
