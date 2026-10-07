# Security and engineering boundaries

M2 adds authenticated local demo registration endpoints. The first M3 slice adds
hospital-local connection/health probes for two independently installed fictional
EHR databases; clinical/patient APIs remain deferred. Central connector bearer
credentials remain separate from hospital-local source DB credentials.

## Implemented M2 authentication

The operator command creates one administrator (hidden password entry, no secret
arguments/default credentials). Human passwords use Argon2id with 19 MiB memory,
two iterations, one lane and per-password random salt. Password change and operator
recovery revoke all administrator sessions. Five wrong passwords lock the account
for 15 minutes; a bounded per-peer 20-attempt/15-minute login limiter additionally
protects the single local API process. It does not trust forwarded peer headers.
Distributed rate limiting is deferred with production deployment.

Browser sessions are random opaque tokens, expire after eight hours and are stored
only as SHA-256 hashes. HttpOnly, SameSite=Strict cookies have path `/v1`. The local
HTTP demo disables Secure; TLS deployments must set `DATAPULSE_COOKIE_SECURE=true`.
Mutation requests require a custom header and, when supplied, an exact configured
Origin. Login also checks these protections. No permissive CORS is configured.
Cookies and connector bearer tokens cannot substitute for each other's credential
kind. Browser tokens are never sent to frontend JavaScript or browser storage.

Each source receives one principal with a server-owned source binding. Generated
connector bearer credentials have 256 random secret bits, 90-day expiry and stored
SHA-256 verification hashes. One-time issue responses are `no-store`; keys stay
only in UI component memory until dismissed/navigation/reload. Rotation immediately
revokes prior keys; suspension, revocation and retirement block future requests.
An already authorized in-flight request may finish. Connectors can read only their
own source metadata: no lists, audit, administrator commands or clinical access.
All `/v1` permissions are checked in the backend. Future roles have a separate
permission registry; reserved reviewer/reader roles currently grant no permissions.

Business writes and their audit events commit atomically; login/logout, password
changes, credential operations, registration CRUD and audit reads are recorded.
Denied/invalid requests are recorded without echoing request bodies, submitted
usernames, passwords or tokens. Operator events have an explicit operator actor
kind; unauthenticated denials use an unauthenticated actor kind. There is no delete
or update audit API. Database triggers protect audit against direct UPDATE/DELETE/
TRUNCATE, subject to privileged-owner limitations in DATABASE_DESIGN.md.
Requests are capped at 64 KiB by streamed byte count. Validation/DB errors are
redacted. API replies are `no-store`; the workspace has a restrictive CSP, frame
protection and content-type protection. Database labels reject connection URIs.

References verified 2026-10-07: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[OWASP CSRF controls](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html),
[argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html).

## Implemented M3 source connections

Implemented M3 connection controls: locally resolved source-bound credential
references, separate SELECT-only DB accounts, exact database/vendor checks, bounded
connect/read/write timeouts, local-file reads capped at 64 KiB, disabled local-file
SQL loading, fixed metadata queries and fresh socket cleanup on each check. Excess
privileges, global/cross-database grants and role grants fail health. A read-only
transaction complements actual DB permission enforcement. Errors report categories,
never driver messages, query parameters, SQL or credential values.

Verified TLS defaults require a CA and hostname verification. The pinned driver's
otherwise possible plaintext fallback is blocked before authentication when server
TLS is absent. Wrapped certificate errors preserve their TLS failure category.
The explicit plaintext demo mode accepts only literal loopback addresses; no remote
plaintext endpoint is allowed. Successful remote TLS is not yet environment-tested.
Protect ignored source secret files with per-user OS permissions; the file resolver
is a local demo adapter, not a production secret manager. No model receives these
credentials. Upstream EHR environment/site secrets remain visible to local Docker
administrators and stay separate from DataPulse central storage and operational logs.

## Implemented M4 proposal controls

Metadata scans share the same source-bound SELECT-only credentials and verified
transport checks. Their fixed parameterized metadata queries never read patient
rows. Table/column/byte/deadline bounds and consistent repeated observations are
required. Local immutable scan/proposal evidence contains no connection config or
credentials; per-user file access remains an operator responsibility.

The model receives a bounded host-selected field/candidate task, never DB access.
All source names/descriptions are untrusted evidence. Host-owned JSON schemas and
semantic checks reject forged targets/fields/evidence, extra approval/SQL/code fields,
unsupported operations and unverified terminology. Every selected field receives a
proposal or unresolved disposition. Only unapproved proposals are persisted; ASTs
are not executed. No confidence threshold authorizes a mapping.

Ollama is restricted to an explicit loopback address, explicit model tag/digest and
exact runtime version. Cloud model forwarding, HTTP redirects and ambient proxies
are rejected. Input/context, output bytes/tokens and a total request deadline bound
inference. Initial generation plus at most two host-diagnostic correction attempts
uses no rejected output body. Only model/task digests and technical metrics enter
generic summaries. Exact-input proposal reuse does not grant approval or sync access.

The remaining trust boundaries below concern later clinical capabilities.

## Implemented ADR-020 evidence controls

ADR-020 evidence capture reads bounded selected column values through the same
SELECT-only source-bound connection. The trusted local actor and request digest are
audited before reads; observations retain values only in protected hospital files.
Stdout/audit errors contain categories/counts/identifiers, not bodies. Snapshots,
server deadlines and row/scalar/serialized bounds apply; incomplete evidence cannot
be silently treated as proof. Models do not receive source credentials or SQL.
Fictional seed writes belong exclusively to the fixed demo infrastructure operator.
The CLI actor is a trusted local attribution, not authenticated hospital review.

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
actor, source, action, revision, timestamps and evidence references. M1 had request
logs only; M2 now implements the separate audit store described above.

Enforce bounded body sizes, sample/candidate/token limits, timeouts, rate limits and
retry budgets. Durable at-least-once jobs use deduplication/leases. Source authentication
failures and deterministic validation failures are not transient retry candidates.
Readiness exposes generic dependency status; liveness never depends on the DB.
Supply-chain dependencies are pinned; update deliberately with verification. CI
uses controlled data only and tests authorization cross-source denial once introduced.
