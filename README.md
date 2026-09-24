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
│   │   ├── docs.py          # Swagger UI at /docs
│   │   └── users.py         # HTTP layer: parse request, call service, shape response
│   ├── static/
│   │   └── openapi.yaml     # OpenAPI 3 spec
│   └── services/
│       ├── user_service.py  # business logic + DB queries
│       └── validators.py    # payload / query-param validation
├── db/init.sql              # database + table schema
├── docs/screenshots/        # Swagger UI screenshots used in this README
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

Then open **http://localhost:5000/docs** to try every endpoint from the browser (Swagger UI).

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

**Interactive docs:** open `http://localhost:5000/docs` for Swagger UI. It lists every endpoint with its parameters, request body and example responses, and you can send real requests from the page with **Try it out**. The spec it reads is [`app/static/openapi.yaml`](app/static/openapi.yaml).

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
| GET | `/docs` | Swagger UI (interactive API docs) |

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

## Swagger UI screenshots

Every endpoint and every success or error case, run live from `/docs` against MySQL. Each screenshot shows the input, the generated curl command, the status code and the actual response body.

<img src="docs/screenshots/01-swagger-overview.png" alt="Swagger UI overview" width="720">

### POST /users: create a user

**201 Created.** The email is saved lowercase (`Meera.Joshi@Example.com` becomes `meera.joshi@example.com`).

<img src="docs/screenshots/02-create-user-201.png" alt="Create user 201" width="720">

**409 Conflict: duplicate email.** `ALICE@example.com` counts as a duplicate of `alice@example.com`.

<img src="docs/screenshots/03-create-user-409-duplicate-email.png" alt="Duplicate email 409" width="720">

**400 Bad Request: invalid email format.**

<img src="docs/screenshots/04-create-user-400-invalid-email.png" alt="Invalid email 400" width="720">

**400 Bad Request: missing required fields.** Every missing field is reported, not just the first one.

<img src="docs/screenshots/05-create-user-400-missing-fields.png" alt="Missing fields 400" width="720">

**400 Bad Request: body is not valid JSON.**

<img src="docs/screenshots/06-create-user-400-invalid-json.png" alt="Invalid JSON 400" width="720">

### GET /users: list, search and paginate

**200 OK: all users.** No pagination block, because `page` and `limit` weren't passed.

<img src="docs/screenshots/07-list-all-users.png" alt="List all users" width="720">

**200 OK: search** (`?search=sharma`). A partial, case-insensitive match on name or email.

<img src="docs/screenshots/08-search-users.png" alt="Search users" width="720">

**200 OK: pagination** (`?page=2&limit=3`). The response includes `pagination` metadata.

<img src="docs/screenshots/09-paginate-users.png" alt="Paginate users" width="720">

**200 OK: search and pagination together** (`?search=example.com&page=1&limit=2`).

<img src="docs/screenshots/10-search-and-paginate.png" alt="Search and paginate" width="720">

**400 Bad Request: `limit` above 100.**

<img src="docs/screenshots/11-paginate-400-limit-too-large.png" alt="Limit too large 400" width="720">

**400 Bad Request: `page` isn't a positive integer** (`page=0`).

<img src="docs/screenshots/12-paginate-400-invalid-page.png" alt="Invalid page 400" width="720">

### GET /users/{id}: get a user by ID

**200 OK.**

<img src="docs/screenshots/13-get-user-by-id-200.png" alt="Get user by id 200" width="720">

**404 Not Found: user doesn't exist.**

<img src="docs/screenshots/14-get-user-by-id-404.png" alt="User not found 404" width="720">

### GET /health

**200 OK.**

<img src="docs/screenshots/15-health.png" alt="Health check" width="720">

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

**1. Why did you choose Flask?**

The assignment is basically a few JSON endpoints over a single table, and I wanted the code to stay about that size. With Flask I only pull in what I actually use. That's blueprints for the routes, Flask-SQLAlchemy for the model and pagination, and that's pretty much it. Django is great, but here most of what it gives you out of the box would sit unused: the admin, templates, the auth system and the migrations framework. I'd also end up adding DRF just to return JSON cleanly. If this grew into a bigger product with an admin panel and proper user accounts, I'd seriously consider Django. For this scope, Flask felt like the honest choice.

**2. How would you scale this system?**

The good news is the API is stateless, so the app side is the easy part. I'd run more containers behind a load balancer and add more as traffic grows. The database is where it would actually hurt first, so most of my effort would go there. Since this API is mostly reads, I'd add read replicas and send the `GET` traffic to them.

A couple of the queries would also need changing as the table grows:

- **Pagination**: `OFFSET` gets slower the deeper you page, so I'd switch to cursor-style pagination (`WHERE id > last_seen_id LIMIT n`).
- **Search**: `LIKE '%term%'` can't use an index, so I'd move it to a `FULLTEXT` index first, and to something like Elasticsearch if search became a real feature.

On top of that, caching `GET /users/<id>` in Redis would take a lot of load off, and I'd want proper metrics in place. That way I'd be scaling the part that's actually slow rather than guessing.

**3. What changes would you make for production?**

The first thing is security. Right now anyone can create users, so I'd add authentication (JWT, the bonus I skipped) and restrict who can hit the write endpoints. I'd also move the credentials out of `.env` into a proper secrets manager, serve everything over HTTPS, and stop exposing the MySQL port.

After that, the things that make it safe to change and easy to debug:

- **Migrations**: real schema migrations with Alembic instead of a one-off SQL script.
- **Tests and CI**: an automated test suite that runs in CI on every pull request.
- **Logging and errors**: structured logs with request IDs, plus error tracking like Sentry, so I hear about problems before users do.
- **Health checks**: a readiness check that also verifies the database is reachable.
- **API basics**: rate limiting, request size limits, a CORS policy and versioned URLs (`/api/v1`).
- **Database**: a managed MySQL with automatic backups, so losing data isn't something I have to think about at 2 a.m.

## AI usage declaration

- **Tools used:** Claude (Anthropic), through Claude Code.
- **What was AI-generated:** the initial project scaffold, Flask app factory, model, service and route code, validators, Dockerfile, docker-compose file and this README.
- **What I did or changed manually:**
  - Reviewed every file and decided on the design choices: opt-in pagination, lower-cased emails, a `db/init.sql` schema instead of `create_all`, and the layer boundaries.
  - Tested every endpoint and error case with curl against a real MySQL-compatible database.
  - Adjusted the configuration, for example URL-encoding the DB password and the TCP-based MySQL healthcheck.
  - I can explain each part of the implementation.
