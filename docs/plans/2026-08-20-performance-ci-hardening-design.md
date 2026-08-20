# Performance CI hardening: issues 274-276

## Objective

Make the performance CI exercise the actual login submission, make its external
dependency evidence reproducible without network access, and ensure a clean
development Compose start uses one consistent database contract.

## Decisions

1. Replace the anonymous `GET` login probe with a successful `POST` login probe.
   It is the operation that authenticates, persists the single-session marker,
   and therefore has a meaningful database cost. Each CI worker gets an isolated
   synthetic user so this does not race the single-session policy.
2. Put the SIIS, Personas, and RENAPER simulations behind one CI-only helper.
   The helper records the existing redacted dependency aggregate, supports a
   configurable synthetic delay and success/error outcome, and rejects network
   use in its tests. It does not change production clients.
3. Use the same database name, user and password defaults in the MySQL and app
   Compose services. The healthcheck keeps using the MySQL container variables.
4. Give write probes a worker-specific synthetic identity. The CI failure is
   caused by two workers generating the same DNI, so the second write becomes
   invalid and responds 200 instead of the required redirect.

## Validation

- Unit tests for POST login, external simulation outcomes and no-network behavior.
- Performance-audit tests and the CI worker contract under the repository venv.
- `docker compose config` to verify clean Compose interpolation.
- Focused lint/format checks and the remote PR checks after push.

## Out of scope

- Changes to real SIIS, Personas, or RENAPER integrations.
- Changes to production credentials, persistent data, or the production Compose.
