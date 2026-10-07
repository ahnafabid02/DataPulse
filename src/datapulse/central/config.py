"""Validated, redacted environment configuration."""

from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATAPULSE_", env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except (ArgumentError, ValueError):
            raise ValueError("Invalid database URL") from None
        if url.drivername != "postgresql+psycopg":
            raise ValueError("Central runtime requires postgresql+psycopg")
        if not url.host or not url.database or not url.username or not url.password:
            raise ValueError("Database URL requires host, database, username and password")
        if url.password == "CHANGE_ME":
            raise ValueError("Configure a development database password")
        return value
