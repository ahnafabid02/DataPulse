# ADR-016: Authenticated local onboarding

Accepted 2026-10-07 following the user's explicit M2 scope confirmation. Connect the
existing English hospital setup UI to central registration APIs now, superseding
the hospital-preview boundary in ADR-015 and the UI timing in M8. Field review,
patient matching and patient history remain fictional, session-only previews.

Use separate human and source connector principals with server-side role grants.
The first local administrator is provisioned through a trusted interactive operator
command, rather than public signup or a shared default password. Browser sessions
use revocable, expiring opaque HttpOnly cookies; connectors use separate expiring,
rotatable opaque bearer credentials. This keeps authentication separate from future
reviewer/reader permissions without introducing an external identity provider into
the local demonstration. Passwords are Argon2id hashes; high-entropy credentials
are stored as SHA-256 verification hashes and disclosed only once.

Registering means metadata saved, never connectivity verified. M2 creates only
registered sources; an administrator may suspend or retire them. Retirement is
logical, retains stable identities and history, and revokes access. Codes and source
ownership remain immutable. Changes require the current registration revision.
Successful writes and their append-only audit records commit together. Database
triggers prevent audit UPDATE, DELETE and (on PostgreSQL) TRUNCATE; a privileged
database owner remains outside this protection and production runtime-role
separation is still deferred. Operator bootstrap/recovery is also audited.

M2 uses fictional hospital metadata and central PostgreSQL only. Hospital database
connectivity, extraction, Agent 1, Agent 2 and clinical APIs remain out of scope.
