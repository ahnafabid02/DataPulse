# DataPulse interface: connected care, made clear

The user explicitly requested an English interface friendly to non-technical users
before M2. ADR-015 records the initial preview. ADR-016 integrates saved hospital
setup in M2 at the user's request; other workflows remain previews.

## Screens and vocabulary

- Overview: four-step introduction, sample review tasks, actual live system status.
- Hospitals: administrator sign-in, persisted fictional registrations, search,
  two-step setup and source access management. No hospital database passwords.
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

The hospital page banner says setup is saved and no database is connected. Its
registrations are fetched from authenticated APIs, persist in PostgreSQL, and do not
mix with sample patient hospitals. Signed-out users see a clear administrator form
and first-use guidance. Setup can create a hospital or add a source to an existing
hospital in one backend transaction. Stable codes and database labels have help text.
Confirmation explains what will be saved before submitting. Duplicate/expired/offline
errors keep the user informed without claiming success. No automatic write retries.

Each newly issued source access key appears once in a native dialog, with copy,
expiry and a secure-storage reminder. Closing/navigation/reload removes it from
component memory; keys cannot be retrieved. The access-management dialog supports
metadata changes, pausing/resuming, replacement, revocation and explicit retirement.
The real activity dialog reads audit events with actor, action, target, time and
expandable change details. Administrator password change signs out all sessions.

Other pages retain the “Guided preview” banner: sample review/matching decisions
are session-only, never approvals. Reset affects only these examples and is disabled
on the hospital page. No localStorage or sessionStorage. Authentication uses a
backend-issued HttpOnly cookie; tokens/passwords are never written to browser storage.

Health refresh runs immediately and
every 45 seconds, with a 5-second abort timeout, last-check time and clear unavailable/
partial states. A successful health check never implies real hospital connectivity.
Source matching and review are still hospital/central contracts for future integration;
this UI does not replace future review authorities. Hospital setup uses the M2
APIs in API_CONTRACTS.md; clinical preview pages never call those business endpoints.

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
optional loopback development server with health and `/v1` proxy to port 8000.
Its backend browser origin must be configured for port 5173 (README).

Future integration must implement authenticated endpoints first, swap preview data
through explicit adapters, preserve source ownership/reviewer roles and show real
audit/validation errors. Never reinterpret preview approvals as real approvals.

Technical references: [React state](https://react.dev/reference/react/useState),
[Vite](https://vite.dev/guide/), [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/).
