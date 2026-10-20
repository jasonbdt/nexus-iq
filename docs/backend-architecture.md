# Backend architecture

The backend follows the dependency inversion, repository, service-layer and unit-of-work
patterns described in [Architecture Patterns with Python](https://www.cosmicpython.com/book/preface).
It remains a single FastAPI application with RQ workers. Dependencies and database tables
are unchanged.

## Boundaries

- `app/domain`: standard-library dataclasses, permission roles, errors and pure policies.
  Entities own their aggregate children: user account links, summoner leagues, match teams
  and participants, or conversation messages.
- `app/service_layer`: supported operations and typed ports. Application code imports
  domain objects and ports, never FastAPI, SQLModel, SDKs or concrete adapters.
- `app/adapters`: SQLModel tables, detached entity mapping, repositories, security, Riot,
  Redis/RQ, OpenAI, Qdrant, patch scraping and DDragon filesystem access.
- `app/entrypoints`: HTTP request/response schemas, authentication dependencies, routers,
  SSE framing and RQ entry functions.
- `app/bootstrap.py`: the composition root. It injects concrete adapters and owns their
  resources. `Settings.from_environment()` reads the existing environment variables
  when a process starts. Importing `app.main` does not connect to services or need secrets.

`app.main:app` is still the server entrypoint. `create_app(services)` creates an isolated
application using supplied ports, which allows API tests without a running stack.
The frontend proxy still strips `/api/v1`; FastAPI's `root_path` remains metadata.

HTTP Pydantic models describe the existing frontend payloads. Domain dataclasses describe
application state. SQLModel classes describe the existing physical schema. Explicit
aggregate relationships in the persistence mapper prevent lazy ORM values from escaping
an open session. DDragon enrichment occurs before response validation; serialization has
no filesystem side effects.

## Transactions and external effects

Each write operation creates a fresh unit of work from a factory. Its repositories share
one session. Repositories flush to obtain identities, but never commit. The application
operation calls `commit()` explicitly. Leaving a unit of work rolls back any uncommitted
changes and closes its session, including on exceptions.

- Registration commits the user, default role, newly fetched summoner and primary link
  together. An unavailable or missing required player account leaves no new user behind.
- A match import commits the match, teams, bans, objectives, participants and runes
  together. Participant profiles are resolved before the write transaction. An existing
  match is a no-op. Ranked profile updates preserve existing queue row identities.
- Coaching commits the question and initial title before retrieval. Its database session
  is closed during the token stream. Successful completion saves the assistant message
  in a new transaction before sending `[DONE]`. Failure or cancellation keeps the question
  and discards a partial assistant response. Stream and Redis subscription cleanup is
  protected from request cancellation.
- RQ entrypoints use the same player operations as HTTP. Redis progress keys, event
  payloads, job dependencies, retries and queue names retain their existing format.
  Match-list reload notifications are sent after a committed import.
- PostgreSQL, Redis and Qdrant are separate systems. A SQL unit of work does not promise
  a distributed transaction with a queue or vector upsert. Existing deterministic vector
  IDs and ingestion behavior remain in the Qdrant adapter.

RQ jobs use the entry functions in `app/entrypoints/workers.py`. The old controllers,
global resource helpers and job compatibility exports have been removed. API startup
does not import RQ; actual RQ execution continues to use the Linux worker image.

## Adding a use case

1. Put business rules in the domain and test them without infrastructure.
2. Define only the ports needed by the operation in `service_layer/ports.py`.
3. Add an application operation receiving ports or a unit-of-work factory. Fetch external
   data before the write transaction where possible, and commit at the operation boundary.
4. Implement missing adapters and connect them in the composition root.
5. Add a thin HTTP or worker entrypoint. Translate application errors at the HTTP boundary.
6. Test operation behavior with in-memory ports, adapter behavior with persistence tests,
   and externally visible behavior with contract tests.

## Validation

Run the normal suite and lint without changing the installed environment:

```sh
uv run --no-sync pytest
uv run --no-sync pylint app --fail-under=9.5
```

The default suite uses fresh SQLite databases, fake network ports and independent app
instances. It checks the pre-refactor database metadata snapshot, transactions, JWTs,
frontend payloads, SSE framing, cancellation, DDragon behavior and import boundaries.
The Windows API no longer requires importing the Linux-specific RQ runtime.

For PostgreSQL and actual Linux/RQ execution, use the existing worker image and stack.
This command binds the checkout read-only and does not install packages:

```sh
docker compose run --rm --no-deps -T -e NEXUS_TEST_POSTGRES=1 -e NEXUS_TEST_REDIS=1 --volume "${PWD}:/workspace:ro" --workdir /workspace worker /usr/src/app/.venv/bin/python -m pytest -q -p no:cacheprovider
```

PostgreSQL tests create and remove uniquely named temporary schemas. The RQ integration
test uses a uniquely named queue and fake upstream data, executes
`app.entrypoints.workers.persist_summoner_match_job`, checks published events, and cleans
up its keys. Existing application records are unused.

`tests/proxy_app.py` provides an optional isolated API for proxy smoke tests. Run it with
`uvicorn tests.proxy_app:create_app --factory`; point a temporary instance of the unchanged
frontend SSR server at it using `BACKEND_URL`. Run `tests/proxy_smoke.cjs` in the frontend
container, optionally setting `NEXUS_TEST_PROXY_URL`. It checks search, registration, login,
profile, matches, queue acknowledgement and both streaming flows.

## Taking the change into use

Build and restart API and workers together so every process uses the new application
operations. No database or vector-data migration is needed:

```sh
docker compose up -d --build backend worker
```

This rollout assumes no jobs remain queued, deferred or scheduled for retry under the
removed job paths. Frontend code, asset patch configuration, dependency manifests and
lockfiles need no changes for this migration.
