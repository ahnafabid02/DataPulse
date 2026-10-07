# Demo integration gate (M3)

No EHR images are deployed in M1. At M3 select and pin upstream releases/compose
commits and image digests, confirm their database compatibility and resource budget,
then introduce separate profiles and controlled seed data.

Official starting points, reviewed 2026-10-07:

- [OpenMRS O3 reference distribution](https://github.com/openmrs/openmrs-distro-referenceapplication)
- [O3 deployment guide](https://o3-docs.openmrs.org/en-US/docs/recipes/deploy-to-production/)
- [OpenEMR official Docker compose](https://github.com/openemr/openemr/blob/master/docker/production/docker-compose.yml)

The OpenMRS reference stack includes gateway/frontend/backend and its database;
OpenEMR's upstream compose includes MariaDB. Moving branch/tag definitions are
research references, not pinned deployment dependencies. Never share central/source
DB roles or silently treat these two installations as one schema. Validate adapter
support using the actual pinned source schema, not copied online table guesses.
