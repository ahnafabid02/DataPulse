"""Hospital-local connection contracts and secret resolution, separate from scanning."""

import ipaddress
import json
from pathlib import Path
from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, model_validator

from datapulse.contracts.schema import Contract

Failure = Literal[
    "credential_unavailable",
    "source_mismatch",
    "authentication_failed",
    "database_denied",
    "database_unavailable",
    "connection_unavailable",
    "timeout",
    "tls_failed",
    "unsafe_privileges",
    "vendor_mismatch",
    "unexpected_failure",
]


class ConnectionConfig(Contract):
    contract_version: Literal[1] = 1
    source_system_id: UUID
    vendor: Literal["mysql", "mariadb"]
    host: str = Field(min_length=1, max_length=253, repr=False)
    port: int = Field(default=3306, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    credential_ref: str = Field(min_length=1, max_length=256, repr=False)
    tls_mode: Literal["verify_identity", "disabled_local_demo"] = "verify_identity"
    ca_file: Path | None = Field(default=None, repr=False)
    connect_timeout_seconds: int = Field(default=3, ge=1, le=30)
    read_timeout_seconds: int = Field(default=3, ge=1, le=30)

    @model_validator(mode="after")
    def transport_policy(self) -> Self:
        if self.tls_mode == "verify_identity":
            if self.ca_file is None:
                raise ValueError("Verified TLS requires a CA file")
        else:
            try:
                local = ipaddress.ip_address(self.host).is_loopback
            except ValueError:
                local = False
            if not local or self.ca_file is not None:
                raise ValueError("Plaintext demo transport requires literal loopback and no CA")
        return self


class ResolvedCredential(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_system_id: UUID
    username: SecretStr
    password: SecretStr

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not self.username.get_secret_value() or not self.password.get_secret_value():
            raise ValueError("Credential values are required")
        return self


class CredentialUnavailable(Exception):
    """Deliberately contains no file, reference or submitted value."""


class CredentialResolver(Protocol):
    def resolve(self, reference: str) -> ResolvedCredential: ...


class FileCredentialResolver:
    def __init__(self, path: Path) -> None:
        self._path = path

    def resolve(self, reference: str) -> ResolvedCredential:
        try:
            with self._path.open("rb") as file:
                payload = file.read(65537)
            if len(payload) > 65536:
                raise ValueError("Credential file exceeds bound")
            entries = json.loads(payload)
            if not isinstance(entries, dict) or reference not in entries:
                raise ValueError("Credential reference unavailable")
            return ResolvedCredential.model_validate(entries[reference])
        except (OSError, ValueError, TypeError):
            raise CredentialUnavailable("Credential unavailable") from None


class ConnectionHealth(Contract):
    contract_version: Literal[1] = 1
    source_system_id: UUID
    status: Literal["healthy", "unhealthy"]
    checked_at: AwareDatetime
    elapsed_ms: int = Field(ge=0)
    failure: Failure | None = None

    @model_validator(mode="after")
    def consistent_status(self) -> Self:
        if (self.status == "healthy") != (self.failure is None):
            raise ValueError("Health status and failure must agree")
        return self


class ConnectionProbe(Protocol):
    def check(self) -> ConnectionHealth: ...
