# Domain docs

Use a single-context layout: root `GLOSSARY.md` and `docs/adr/`.

## Before exploring

- Read `docs/DOMAIN_MODEL.md` for current domain concepts.
- Read `docs/DECISIONS.md` for existing architecture decisions. It remains the
  authoritative record; this setup does not move or supersede its ADRs.
- Read root `GLOSSARY.md`, when present, and relevant decisions in `docs/adr/`.
- If the glossary or ADR directory is absent, proceed silently. Create domain
  documents lazily when domain-modeling resolves terms or decisions.

## Vocabulary and decisions

Use glossary terms in issue titles, hypotheses, tests, and proposals. For concepts
not yet in the glossary, follow `docs/DOMAIN_MODEL.md` and flag real vocabulary gaps
for domain-modeling.

Surface conflicts with an existing ADR explicitly. Record a superseding decision
and update affected contracts and documentation before changing accepted policy.
Choose new ADR identifiers that do not collide with those in `docs/DECISIONS.md`.
