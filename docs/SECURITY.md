# Security and engineering boundaries

M1 serves only non-sensitive health endpoints, bound locally by default. It contains
no authentication implementation and must not gain patient/admin endpoints until M2
establishes source authentication, authorization and business audit.

## Planned trust boundaries

- Hospital source principals authenticate to central API using registered scoped
  credentials initially (hashed, rotating opaque tokens over TLS); source binding
  comes from server-side principal records. Adopt OIDC/service credentials as needed.
- Human admin/reviewer/clinical-reader principals have separate scoped roles; review
  commands require authenticated human actor, reason, optimistic revision and audit.
- Hospital DB read-only accounts access allowlisted schemas/tables. Source extraction
  never writes the EHR. DB credentials live in hospital environment/secret storage;
  central source records and LLM tasks contain only references, never credentials.
- Models can inspect actual patient records where needed for mapping or difficult
  identity reasoning. No blanket anonymization changes that requirement. Access must
  still be purpose-scoped, bounded, auditable, encrypted in transit and governed by
  deployment retention/access rules. Remote providers require explicit configuration
  of location/retention; local inference is supported through a replaceable adapter.
- Source data/comments/model responses are untrusted input. JSON Schema validation,
  candidate allowlists and a safe transformation AST prevent prompt injection from
  becoming database queries, shell execution, code evaluation or approval decisions.

## Engineering controls

Secrets through environment/secrets manager; `.env` and patient dumps ignored. The
example environment has blank password fields and no runnable default credentials.
Local Postgres uses the official image's bootstrap superuser for controlled demo
data only; production uses distinct migration and
least-privilege runtime roles. Secrets are redacted by configuration representation;
DB exception details/SQL parameters are never returned or logged.

Use TLS for deployment, encrypted disks/backups, access-controlled PHI and quarantine
stores, tested restores and retention/deletion policy before real clinical usage.
Identity unlink is not a physical data deletion operation. Jurisdictional/data-sharing
requirements and clinical acceptance must be resolved with responsible hospital
owners; this repository does not make legal or clinical certification claims.

Operational logs are JSON event metadata without request bodies/querystrings,
patient values or token headers. Audit is a distinct append-only domain store with
actor, source, action, revision, timestamps and evidence references. M1 has request
logs only; it does not pretend to have business audit storage.

Enforce bounded body sizes, sample/candidate/token limits, timeouts, rate limits and
retry budgets. Durable at-least-once jobs use deduplication/leases. Source authentication
failures and deterministic validation failures are not transient retry candidates.
Readiness exposes generic dependency status; liveness never depends on the DB.
Supply-chain dependencies are pinned; update deliberately with verification. CI
uses controlled data only and tests authorization cross-source denial once introduced.
