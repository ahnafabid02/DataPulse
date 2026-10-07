# M1-UI: connected care, made clear

The user explicitly requested an English interface friendly to non-technical users
before M2. This supersedes the original UI timing; it does not accelerate business
API implementation. ADR-015 records the boundary.

## Screens and vocabulary

- Overview: four-step introduction, sample review tasks, actual live system status.
- Hospitals: fictional sources, search, two-step example setup. No password fields.
- Field review: plain-language meaning, before/after values, evidence and decision.
  Ambiguous dates cannot be approved. Technical source/FHIR details are expandable.
- Patient matching: side-by-side source identities, agreements and uncertainty,
  review note and affirmative confirmation before linking a sample identity.
- Patient records: chronological source-labelled history, source details, hospital/
  record-type filters. Sources are separate until the sample match is confirmed.
- Help: task-oriented steps, everyday definitions and current capability explanation.

Use “hospital”, “field review”, “patient matching”, “care timeline” and “where this
record came from”. Do not use “agent”, “schema introspection”, “probabilistic score”
or technical resource paths in primary flows. Technical details remain available
to a colleague without overwhelming the main view.

## Truthful state and integration

Persistent “Guided preview” banner identifies all records/actions as fictional and
session-only. Counts describe sample tasks, never real hospitals/clinical activity.
No localStorage, cookies or clinical server requests. Reset restores initial sample
state. Page navigation uses hashes and preserves state for the current loaded app.
Reload resets all example actions; history is not a real audit trail.

Only `/health/live` and `/health/ready` are requested. Refresh runs immediately and
every 45 seconds, with a 5-second abort timeout, last-check time and clear unavailable/
partial states. A successful health check never implies real hospital connectivity.
Source matching and review are still hospital/central contracts for future integration;
this UI does not replace approval authorities or authenticate fictitious users.

## Design system and accessibility

Calm forest sidebar, sage surfaces, restrained lime accents, white review surfaces.
Consistent semantic badges and inline instructions explain status in words; color
is supplemental. Responsive navigation on small screens; native dialog supplies
modal focus containment/Escape, forms have visible labels and disabled-state
guidance. Skip link, visible keyboard focus, navigation current-page state, focus to
main on page changes, live feedback and reduced-motion handling are included.
Source filters and review decisions use native controls. Decorative illustration
is hidden from assistive technology; content remains readable without it.

## Development and build

React/TypeScript source lives in `web/`. Node 24, npm lockfile, Vite, Vitest and
Testing Library. `npm ci`, `npm test`, `npm run build`. The build writes generated
assets to ignored `src/datapulse/central/static/`; package data includes those assets.
Docker builds the frontend first and copies it into the Python package. FastAPI
serves `/`, `/favicon.svg` and `/assets/*`; other files/routes are not exposed.
No Node runtime service is needed for the built app. `npm run dev` provides an
optional loopback development server with health proxy to port 8000.

Future integration must implement authenticated endpoints first, swap preview data
through explicit adapters, preserve source ownership/reviewer roles and show real
audit/validation errors. Never reinterpret preview approvals as real approvals.

Technical references: [React state](https://react.dev/reference/react/useState),
[Vite](https://vite.dev/guide/), [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/).
