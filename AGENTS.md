# Project instructions

- Read `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, and the relevant domain documents before implementation or architecture changes.
- Follow `docs/IMPLEMENTATION_ROADMAP.md`. Implement the smallest coherent milestone; do not jump to agent or UI work.
- Inspect existing code, migrations, contracts, and tests before modifying them. Never assume generated code is correct.
- Keep changes scoped to the task and preserve component boundaries.
- Hospital connectors own source credentials and database access. Models never receive credentials or execute arbitrary SQL.
- Agent 1 proposes per-source mappings; human approval precedes deterministic runtime use.
- Agent 2 preserves source identities and links them to global identities. LLM reasoning alone never authorizes a patient link.
- Preserve clinical source data, mapping/transformation versions, and provenance.
- FHIR R4 4.0.1 is the interoperability target. Do not silently change this or any major ADR.
- Record architecture changes in `docs/DECISIONS.md` and update affected contracts/documentation in the same change.
- Add or update meaningful tests, including failure cases. Run relevant tests, lint, and type checks before finishing.
- Apply database changes through Alembic; do not use ORM `create_all` in application startup.
- Never commit credentials, patient exports, local environment files, or model prompts containing patient data.
- Log metadata and identifiers for technical requests, not patient bodies, tokens, SQL parameters, or connection strings.
- Clearly distinguish implemented behavior, proposed design, and unverified environment-dependent checks.
- Resolve uncertainties with official documentation or source code; record assumptions instead of inventing conformance claims.
- Current scope: M1–M4 plus the confirmed ADR-020 sequence: fictional seeds and bounded evidence first, then hospital-local M5 review/releases, Patient first and all clinical domains tracked. Read `docs/EVIDENCE_RUNBOOK.md`, `docs/M4_RUNBOOK.md` and `docs/AGENT_1_MAPPING.md` before evidence/registry changes. Preserve source pins and human approval; M6–M9 and extraction cursors remain deferred.
- Hospital setup uses authenticated persistent APIs. Field-review, matching and patient-history previews remain fictional and session-only.

## Agent skills

### Issue tracker

Track issues and specs in GitHub Issues for `ahnafabid02/DataPulse`.
Before issue operations, read `docs/agents/issue-tracker.md`.

### Triage labels

Use the five canonical triage labels. Before triage, read
`docs/agents/triage-labels.md`.

### Domain docs

Use a single-context domain layout. Before codebase exploration, read
`docs/agents/domain.md` for glossary and architecture-decision rules.
