# User Management API

A small JSON REST API for managing users. It uses Flask, SQLAlchemy and MySQL 8, and the whole stack runs with Docker Compose.

## Project structure

```
.
├── app/
│   ├── __init__.py          # create_app() application factory
│   ├── config.py            # env-driven configuration
│   ├── extensions.py        # SQLAlchemy instance
│   ├── errors.py            # APIError types + JSON error handlers
│   ├── models/
│   │   └── user.py          # User ORM model
│   ├── routes/
│   │   ├── __init__.py      # blueprint registration, /health
│   │   └── users.py         # HTTP layer: parse request, call service, shape response
│   └── services/
│       ├── user_service.py  # business logic + DB queries
│       └── validators.py    # payload / query-param validation
├── db/init.sql              # database + table schema
├── wsgi.py                  # WSGI entrypoint (gunicorn wsgi:app)
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

Each layer has one job. Routes only handle HTTP. Services hold the business rules and don't import anything from Flask's request context. Models only define the table mapping. A service raises a typed `APIError` (`ValidationError`, `NotFoundError`, `ConflictError`), and one error handler turns it into the standard error response.

## Setup

### Option 1: Docker (recommended)

You only need Docker with the Compose plugin.

```bash
cp .env.example .env        # optional, since compose has sane defaults
docker compose up --build -d
docker compose ps           # wait until both services show "healthy"
curl http://localhost:5000/health
```

What happens when you run it:

- **`db`**: runs `mysql:8.4`. On the first start with an empty volume, it creates the `users` database and the app user from the env vars, then runs `db/init.sql` to create the table. Data is kept in the `db_data` named volume.
- **Database healthcheck**: runs `mysqladmin ping` over TCP (`-h 127.0.0.1`). While MySQL runs its init scripts, it starts a temporary server that listens only on the socket. Pinging over TCP keeps the container "unhealthy" until the real server is up and the schema exists.
- **`api`**: waits for `depends_on: condition: service_healthy`, so it never starts before the database is ready.
- **API image**: a multi-stage build. Wheels are built in a builder stage, so the runtime image has no build tools. It runs as a non-root user (`appuser`) under gunicorn, with its own `HEALTHCHECK` against `/health`.
- **Configuration**: comes only from environment variables (12-factor). Nothing secret is baked into the image, and `.env` is in both `.gitignore` and `.dockerignore`.

Useful commands:

```bash
docker compose logs -f api                                                  # follow API logs
docker compose exec db mysql -uapp -papp_password users -e "SELECT * FROM users"
docker compose down                                                         # stop the stack
docker compose down -v                                                      # stop and wipe the DB volume (re-runs init.sql next time)
```

| Variable | Default | Purpose |
|---|---|---|
| `DB_NAME` | `users` | Database name |
| `DB_USER` / `DB_PASSWORD` | `app` / `app_password` | Application DB credentials |
| `MYSQL_ROOT_PASSWORD` | `root_password` | MySQL root password |
| `API_PORT` | `5000` | Host port for the API |
| `DB_HOST_PORT` | `3307` | Host port for MySQL (3307 avoids clashing with a local MySQL) |
| `GUNICORN_WORKERS` | `2` | Number of gunicorn worker processes |

### Option 2: Run locally (without Docker)

This needs Python 3.10+ and a running MySQL 8.

```bash
mysql -uroot -p < db/init.sql
mysql -uroot -p -e "CREATE USER 'app'@'%' IDENTIFIED BY 'app_password'; GRANT ALL ON users.* TO 'app'@'%';"

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DB_HOST=localhost DB_PORT=3306 DB_USER=app DB_PASSWORD=app_password DB_NAME=users
python wsgi.py                          # dev server on :5000
# or: gunicorn -b 0.0.0.0:5000 wsgi:app
```

## Database schema

The database is `users` and the table is `users`. See [`db/init.sql`](db/init.sql).

| Column | Type | Constraints |
|---|---|---|
| `id` | `INT` | `PRIMARY KEY`, `AUTO_INCREMENT` |
| `name` | `VARCHAR(100)` | `NOT NULL` |
| `email` | `VARCHAR(255)` | `NOT NULL`, `UNIQUE` (`uq_users_email`) |
| `role` | `VARCHAR(50)` | `NOT NULL` |

The table uses the `utf8mb4` charset with the case-insensitive `utf8mb4_unicode_ci` collation, on the InnoDB engine.

## API

Base URL: `http://localhost:5000`. Every response is JSON.

Successful responses look like this:

```json
{ "success": true, "data": ... }
```

Errors look like this:

```json
{ "success": false, "error": "message", "details": { ...optional per-field errors... } }
```

| Method | Endpoint | Description |
|---|---|---|
| GET | `/users` | List all users |
| GET | `/users?search=<term>` | Search by name or email (partial, case-insensitive) |
| GET | `/users?page=1&limit=10` | Paginated list |
| GET | `/users?search=<term>&page=1&limit=10` | Search and pagination combined |
| GET | `/users/<id>` | Get one user |
| POST | `/users` | Create a user |
| GET | `/health` | Liveness check (used by Docker) |

### POST /users

```bash
curl -X POST http://localhost:5000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Sharma", "email": "Alice@Example.com", "role": "admin"}'
```

`201 Created`

```json
{ "success": true, "data": { "id": 1, "name": "Alice Sharma", "email": "alice@example.com", "role": "admin" } }
```

`409 Conflict`: the email already exists.

```json
{ "success": false, "error": "Email already exists" }
```

`400 Bad Request`: validation failed.

```json
{
  "success": false,
  "error": "Validation failed",
  "details": { "email": "Invalid email format", "role": "role is required" }
}
```

### GET /users

```bash
curl http://localhost:5000/users
```

`200 OK`

```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "Alice Sharma", "email": "alice@example.com", "role": "admin" },
    { "id": 2, "name": "Bob Mehta", "email": "bob@example.com", "role": "editor" }
  ]
}
```

### GET /users?search=

```bash
curl "http://localhost:5000/users?search=alice"
```

`200 OK`

```json
{ "success": true, "data": [ { "id": 1, "name": "Alice Sharma", "email": "alice@example.com", "role": "admin" } ] }
```

### GET /users?page=&limit=

```bash
curl "http://localhost:5000/users?page=2&limit=5"
```

`200 OK`

```json
{
  "success": true,
  "data": [ { "id": 6, "name": "User 4", "email": "user4@test.io", "role": "viewer" }, "..." ],
  "pagination": { "page": 2, "limit": 5, "total": 14, "pages": 3 }
}
```

`400 Bad Request`: returned when `page` or `limit` isn't a positive integer, or when `limit` is over 100.

```json
{ "success": false, "error": "limit must not exceed 100" }
```

### GET /users/<id>

```bash
curl http://localhost:5000/users/1
```

`200 OK`

```json
{ "success": true, "data": { "id": 1, "name": "Alice Sharma", "email": "alice@example.com", "role": "admin" } }
```

`404 Not Found`

```json
{ "success": false, "error": "User not found" }
```

### Status codes

| Code | When |
|---|---|
| 200 | Successful read |
| 201 | User created |
| 400 | Invalid JSON body, failed validation, or bad pagination params |
| 404 | User not found, or unknown route |
| 405 | Wrong HTTP method |
| 409 | Duplicate email |
| 500 | Unexpected server error. The error is logged, and no internals are leaked in the response. |

## Assumptions

- **Pagination is opt-in.** Plain `GET /users` returns all users, as the spec describes. Pagination applies when `page` or `limit` is present. The defaults are `page=1` and `limit=10`, and `limit` is capped at 100.
- **Search** is a partial match on name or email. It is case-insensitive through the column collation, and it combines with pagination. The characters `%` and `_` in the search term are treated literally, not as wildcards.
- **Emails** are trimmed and lower-cased before they are stored, so `Alice@x.com` and `alice@x.com` count as duplicates. Validation uses a pragmatic regex, not full RFC 5322.
- **Role** is free text up to 50 characters, because the spec doesn't define a fixed set of roles.
- **Field lengths**: name up to 100 characters, email up to 255, role up to 50.
- **Duplicate emails** are checked in the service layer. The DB `UNIQUE` constraint is the final guard against races: an `IntegrityError` is caught and returned as `409`.
- **Scope**: only the listed endpoints are implemented. Update and delete were not requested.
- **Schema management**: the schema is managed by `db/init.sql`, not by `db.create_all()`. That keeps the DDL explicit and reviewable.

## Short answers

**1. Why Flask?**
The scope is a handful of JSON endpoints over one table. Flask lets me build exactly that with little overhead. Blueprints give the routes/models/services split cleanly, and Flask-SQLAlchemy covers the ORM and pagination. Django's admin, templates, auth and migrations framework would mostly go unused here, and DRF would add more ceremony than this API needs. If the project grew into a larger product with admin and auth needs, Django would become the better fit.

**2. How would you scale this system?**
- **App tier**: the API is stateless, so I'd run more gunicorn workers or containers behind a load balancer and scale out horizontally (for example with Kubernetes or ECS).
- **Database**:
  - Add read replicas for the read-heavy `GET` traffic.
  - Tune connection pools, and put ProxySQL in front if connections become the bottleneck.
  - Switch to keyset (cursor) pagination, `WHERE id > :last_id LIMIT n`, because `OFFSET` gets slow on large tables.
- **Search**: `LIKE '%term%'` can't use an index. At scale I'd use a MySQL `FULLTEXT` index, or move search to Elasticsearch or OpenSearch.
- **Caching**: cache hot reads (`GET /users/<id>`) in Redis, and invalidate the entry on writes.
- **Operations**: rate limiting at the gateway, plus metrics, tracing and alerting so bottlenecks are found from data rather than guesses.

**3. What changes would you make for production?**
- **Authentication and authorisation**: JWT or OAuth2, with role-based access control on write endpoints.
- **Schema migrations**: Alembic / Flask-Migrate instead of a raw init script.
- **Secrets**: kept in a secrets manager (AWS Secrets Manager, Vault) rather than in `.env`.
- **Network**: TLS termination at a reverse proxy or load balancer. MySQL wouldn't be exposed publicly, so the `db` port mapping would be removed.
- **Tests**: automated tests (pytest with a MySQL test container) running in a CI pipeline that also runs lint, tests and the image build.
- **Observability**:
  - Structured JSON logging with request IDs.
  - Prometheus metrics.
  - Error tracking (Sentry).
  - A `/health` endpoint split into liveness and readiness checks, where readiness also checks the DB.
- **API hygiene**: request size limits, rate limiting, CORS policy, and API versioning (`/api/v1`).
- **Database operations**: managed MySQL (RDS or Cloud SQL) with automated backups and point-in-time recovery.
- **Images**: pinned image digests and container image vulnerability scanning.

## AI usage declaration

- **Tools used:** Claude (Anthropic), through Claude Code.
- **What was AI-generated:** the initial project scaffold, Flask app factory, model, service and route code, validators, Dockerfile, docker-compose file and this README.
- **What I did or changed manually:**
  - Reviewed every file and decided on the design choices: opt-in pagination, lower-cased emails, a `db/init.sql` schema instead of `create_all`, and the layer boundaries.
  - Tested every endpoint and error case with curl against a real MySQL-compatible database.
  - Adjusted the configuration, for example URL-encoding the DB password and the TCP-based MySQL healthcheck.
  - I can explain each part of the implementation.
