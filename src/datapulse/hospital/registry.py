"""Immutable observations, structural deduplication, explicit Alembic provisioning."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from datapulse.connectors.evidence import EvidenceObservation, EvidenceRequest
from datapulse.contracts.schema import Contract, DatabaseSchema
from datapulse.mapping.contracts import MappingRunResult


class RegistryError(Exception):
    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(category)


class ScanReceipt(Contract):
    scan_id: UUID
    source_system_id: UUID
    schema_fingerprint: str
    scanned_at: str


def _engine(path: Path) -> sa.Engine:
    return sa.create_engine(
        sa.URL.create("sqlite", database=str(path)), connect_args={"timeout": 5}
    )


def migrate_registry(path: Path, revision: str = "head") -> None:
    """Explicit provisioning command; no implicit schema creation on open."""
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = _engine(path)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            config.attributes["connection"] = connection
            command.upgrade(config, revision)
    finally:
        engine.dispose()


class HospitalRegistry:
    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise RegistryError("registry_not_provisioned")
        self._engine = _engine(path)
        with self._engine.connect() as connection:
            try:
                head = connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar()
            except sa.exc.SQLAlchemyError:
                self._engine.dispose()
                raise RegistryError("registry_not_provisioned") from None
            if head != "hospital_0003":
                self._engine.dispose()
                raise RegistryError("registry_revision_mismatch")

    def close(self) -> None:
        self._engine.dispose()

    def begin_evidence_access(self, scan_id: UUID, request: EvidenceRequest, actor: str) -> UUID:
        scan = self.load_scan(scan_id, request.source_system_id)
        if scan.structural_fingerprint() != request.schema_fingerprint:
            raise RegistryError("run_fingerprint_mismatch")
        if not actor.strip() or len(actor) > 100 or any(ord(c) < 32 for c in actor):
            raise RegistryError("invalid_actor")
        access_id = uuid4()
        digest = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with self._engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql(
                "INSERT INTO evidence_access VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    str(access_id),
                    str(request.source_system_id),
                    str(scan_id),
                    actor,
                    digest,
                    "started",
                    None,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return access_id

    def finish_evidence_access(
        self, access_id: UUID, observation: EvidenceObservation | None, category: str | None = None
    ) -> None:
        # Fixed categories only. Arbitrary driver/model text never enters audit.
        safe = {
            "source_mismatch",
            "schema_changed",
            "scope_unavailable",
            "timeout",
            "limit_exceeded",
            "value_limit_exceeded",
            "unsupported_value",
            "unsupported_relationship_type",
            "unsupported_snapshot_engine",
            "evidence_unavailable",
            "authentication_failed",
            "credential_unavailable",
            "database_denied",
            "database_unavailable",
            "connection_unavailable",
            "unsafe_privileges",
            "tls_failed",
            "vendor_mismatch",
        }
        with self._engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            row = connection.exec_driver_sql(
                "SELECT source_id,scan_id,actor,request_digest FROM evidence_access "
                "WHERE access_id=? AND phase='started'",
                (str(access_id),),
            ).first()
            finished = connection.exec_driver_sql(
                "SELECT 1 FROM evidence_access WHERE access_id=? AND phase!='started'",
                (str(access_id),),
            ).first()
            if row is None or finished:
                raise RegistryError("access_unavailable")
            if observation is not None:
                scan = self.load_scan(UUID(row[1]), UUID(row[0]))
                if (
                    str(observation.source_system_id) != row[0]
                    or observation.request.source_system_id != observation.source_system_id
                    or observation.schema_fingerprint != scan.structural_fingerprint()
                    or observation.request.schema_fingerprint != observation.schema_fingerprint
                    or hashlib.sha256(observation.request.model_dump_json().encode()).hexdigest()
                    != row[3]
                ):
                    raise RegistryError("evidence_identity_mismatch")
                payload = observation.model_dump_json()
                if len(payload.encode()) > observation.request.policy.max_evidence_bytes:
                    raise RegistryError("evidence_limit_exceeded")
                connection.exec_driver_sql(
                    "INSERT INTO evidence_observations VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(observation.observation_id),
                        str(access_id),
                        row[0],
                        row[1],
                        observation.digest(),
                        payload,
                    ),
                )
            connection.exec_driver_sql(
                "INSERT INTO evidence_access VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    str(access_id),
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    "completed" if observation is not None else "failed",
                    None
                    if observation is not None
                    else (category if category in safe else "evidence_unavailable"),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def load_evidence(self, observation_id: UUID, source_system_id: UUID) -> EvidenceObservation:
        with self._engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT payload_json,digest FROM evidence_observations WHERE id=? AND source_id=?",
                (str(observation_id), str(source_system_id)),
            ).first()
        if row is None:
            raise RegistryError("evidence_unavailable")
        observed = EvidenceObservation.model_validate_json(row[0])
        if observed.source_system_id != source_system_id or observed.digest() != row[1]:
            raise RegistryError("evidence_integrity_failed")
        return observed

    def save_scan(self, schema: DatabaseSchema) -> ScanReceipt:
        payload = schema.model_dump(mode="json", exclude={"scanned_at"})
        observation: dict[str, Any] = {"tables": {}}
        payload["tables"].sort(key=lambda t: (t["namespace"], t["name"]))
        for table in payload["tables"]:
            key = json.dumps([table["namespace"], table["name"]])
            observation["tables"][key] = {
                "comment": table.pop("comment"),
                "relationship_hints": table.pop("relationship_hints"),
                "columns": {},
            }
            table["columns"].sort(key=lambda c: c["ordinal"])
            for column in table["columns"]:
                observation["tables"][key]["columns"][column["name"]] = {
                    "comment": column.pop("comment"),
                    "default": column.pop("default"),
                }
            for collection in ("foreign_keys", "unique_constraints", "indexes"):
                table[collection].sort(key=lambda item: item["name"])
        fingerprint = schema.structural_fingerprint()
        structure = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        receipt = ScanReceipt(
            scan_id=uuid4(),
            source_system_id=schema.source_system_id,
            schema_fingerprint=fingerprint,
            scanned_at=schema.scanned_at.isoformat(),
        )
        try:
            with self._engine.begin() as connection:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.exec_driver_sql(
                    "INSERT OR IGNORE INTO schema_snapshots VALUES (?, ?)",
                    (fingerprint, structure),
                )
                connection.exec_driver_sql(
                    "INSERT INTO schema_scans VALUES (?, ?, ?, ?, ?)",
                    (
                        str(receipt.scan_id),
                        str(schema.source_system_id),
                        fingerprint,
                        receipt.scanned_at,
                        json.dumps(observation),
                    ),
                )
        except sa.exc.SQLAlchemyError:
            raise RegistryError("registry_write_failed") from None
        return receipt

    def load_scan(self, scan_id: UUID, source_system_id: UUID) -> DatabaseSchema:
        with self._engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT s.scanned_at,s.observation_json,p.structure_json,s.fingerprint "
                "FROM schema_scans s JOIN schema_snapshots p ON p.fingerprint=s.fingerprint "
                "WHERE s.id=? AND s.source_id=?",
                (str(scan_id), str(source_system_id)),
            ).first()
        if row is None:
            raise RegistryError("scan_unavailable")
        payload = json.loads(row[2])
        observed = json.loads(row[1])["tables"]
        payload["scanned_at"] = row[0]
        for table in payload["tables"]:
            metadata = observed[json.dumps([table["namespace"], table["name"]])]
            table.update(
                comment=metadata["comment"], relationship_hints=metadata["relationship_hints"]
            )
            for column in table["columns"]:
                column.update(metadata["columns"][column["name"]])
        schema = DatabaseSchema.model_validate(payload)
        if schema.source_system_id != source_system_id or schema.structural_fingerprint() != row[3]:
            raise RegistryError("scan_integrity_failed")
        return schema

    def save_run(self, scan_id: UUID, source_system_id: UUID, run: MappingRunResult) -> UUID:
        scan = self.load_scan(scan_id, source_system_id)
        payload = run.model_dump(mode="json")
        if payload.get("source_system_id") != str(source_system_id):
            raise RegistryError("run_source_mismatch")
        if run.schema_fingerprint != scan.structural_fingerprint():
            raise RegistryError("run_fingerprint_mismatch")
        if len(run.model_dump_json().encode()) > 32000000:
            raise RegistryError("run_size_limit")
        # M4 stores proposal observations, never approval commands or runtime releases.
        if payload.get("status") not in {"completed", "partial", "failed"}:
            raise RegistryError("invalid_run_state")
        run_id = UUID(payload["run_id"])
        with self._engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.exec_driver_sql(
                "INSERT INTO mapping_runs "
                "(id,source_id,scan_id,created_at,result_json,reuse_key) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(run_id),
                    str(source_system_id),
                    str(scan_id),
                    datetime.now(UTC).isoformat(),
                    json.dumps(payload),
                    payload.get("provider_run_metadata", {}).get("reuse_key"),
                ),
            )
        return run_id

    def find_run(self, source_system_id: UUID, reuse_key: str) -> dict[str, Any] | None:
        with self._engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT result_json FROM mapping_runs WHERE source_id=? AND reuse_key=? "
                "ORDER BY created_at DESC LIMIT 1",
                (str(source_system_id), reuse_key),
            ).first()
        if row:
            payload = dict(json.loads(row[0]))
            if payload.get("status") in {"completed", "partial"}:
                return payload
        return None
