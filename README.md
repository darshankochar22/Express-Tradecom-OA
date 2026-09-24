# User Management API

A JSON REST API for managing users, built with Flask, SQLAlchemy and MySQL 8. It includes JWT authentication and a date-of-birth based forgot-password flow. The whole stack runs with Docker Compose, and there's a Swagger UI at `/docs` for testing every endpoint from the browser.

## Project structure

```
.
├── app/
│   ├── __init__.py            # create_app() application factory
│   ├── config.py              # env-driven configuration
│   ├── extensions.py          # SQLAlchemy instance
│   ├── errors.py              # APIError types + JSON error handlers
│   ├── models/
│   │   └── user.py            # User model, password hashing
│   ├── routes/
│   │   ├── __init__.py        # blueprint registration, /health
│   │   ├── auth.py            # /auth/login, /auth/me, forgot + reset password
│   │   ├── decorators.py      # @jwt_required
│   │   ├── docs.py            # Swagger UI at /docs
│   │   └── users.py           # /users endpoints
│   ├── services/
│   │   ├── auth_service.py    # tokens, login, forgot/reset password, lockout
│   │   ├── user_service.py    # user queries and creation
│   │   └── validators.py      # request payload and query-param validation
│   └── static/
│       └── openapi.yaml       # OpenAPI 3 spec used by /docs
├── db/init.sql                # database + table schema
├── docs/screenshots/          # Swagger UI screenshots used in this README
├── wsgi.py                    # WSGI entrypoint (gunicorn wsgi:app)
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── requirements.txt
```

Each layer has one job:

- **Routes** only deal with HTTP.
- **Services** hold the business rules.
- **Models** define the table mapping.

A service raises a typed `APIError` (`ValidationError`, `UnauthorizedError`, `NotFoundError`, `ConflictError`, `TooManyRequestsError`), and a single error handler turns it into the standard JSON error response.

## Setup

### Option 1: Docker (recommended)

You only need Docker with the Compose plugin.

```bash
cp .env.example .env        # optional, since compose has working defaults
docker compose up --build -d
docker compose ps           # wait until both services show "healthy"
curl http://localhost:5000/health
```

Then open **http://localhost:5000/docs** to try every endpoint in Swagger UI.

What happens when you run it:

- **`db`**: runs `mysql:8.4`. On the first start with an empty volume, it creates the `users` database and the app user from the env vars, then runs `db/init.sql` to create the table. Data is kept in the `db_data` named volume.
- **Database healthcheck**: runs `mysqladmin ping` over TCP (`-h 127.0.0.1`). While MySQL runs its init scripts, it starts a temporary server that listens only on the socket. Pinging over TCP keeps the container "unhealthy" until the real server is up and the schema exists.
- **`api`**: waits for `depends_on: condition: service_healthy`, so it never starts before the database is ready.
- **API image**:
  - A multi-stage build: wheels are built in a builder stage, so the runtime image has no build tools.
  - It runs as a non-root user (`appuser`) under gunicorn.
  - It has its own `HEALTHCHECK` against `/health`.
- **Configuration**: comes only from environment variables. Nothing secret is baked into the image, and `.env` is excluded by both `.gitignore` and `.dockerignore`. The app refuses to start if `JWT_SECRET_KEY` is missing.

Useful commands:

```bash
docker compose logs -f api                                                  # follow API logs
docker compose exec db mysql -uapp -papp_password users -e "SELECT id, name, email, role FROM users"
docker compose down                                                         # stop the stack
docker compose down -v                                                      # stop and wipe the DB volume
```

`db/init.sql` only runs on an empty volume. If you started the stack before the auth columns were added, run `docker compose down -v` once so the table is recreated.

| Variable | Default | Purpose |
|---|---|---|
| `DB_NAME` | `users` | Database name |
| `DB_USER` / `DB_PASSWORD` | `app` / `app_password` | Application DB credentials |
| `MYSQL_ROOT_PASSWORD` | `root_password` | MySQL root password |
| `JWT_SECRET_KEY` | dev-only value | Secret used to sign tokens. **Change it outside local development.** |
| `ACCESS_TOKEN_EXPIRES_MINUTES` | `60` | Access token lifetime |
| `RESET_TOKEN_EXPIRES_MINUTES` | `15` | Reset token lifetime |
| `RESET_MAX_ATTEMPTS` | `5` | Wrong date-of-birth attempts allowed before lockout |
| `RESET_LOCKOUT_MINUTES` | `15` | How long forgot-password stays locked |
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

cp .env.example .env
set -a; source .env; set +a             # the app reads env vars, not the .env file itself
python wsgi.py                          # dev server on :5000
# or: gunicorn -b 0.0.0.0:5000 wsgi:app
```

## Database schema

The database is `users` and the table is `users`. See [`db/init.sql`](db/init.sql).

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `INT` | `PRIMARY KEY`, `AUTO_INCREMENT` | |
| `name` | `VARCHAR(100)` | `NOT NULL` | |
| `email` | `VARCHAR(255)` | `NOT NULL`, `UNIQUE` (`uq_users_email`) | Login identifier |
| `role` | `VARCHAR(50)` | `NOT NULL` | |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | scrypt hash, never the raw password |
| `date_of_birth` | `DATE` | `NOT NULL` | Verifies a forgot-password request |
| `token_version` | `INT` | `NOT NULL DEFAULT 0` | Goes up on each password reset, which revokes older tokens |
| `reset_attempts` | `INT` | `NOT NULL DEFAULT 0` | Wrong date-of-birth attempts so far |
| `reset_locked_until` | `DATETIME` | `NULL` | Forgot-password lockout expiry (UTC) |

The first four columns are the ones the assignment asks for. The rest exist for the JWT and password-reset bonus.

The table uses `utf8mb4` with the case-insensitive `utf8mb4_unicode_ci` collation, on InnoDB.

## Authentication

1. **Register** with `POST /users`. This endpoint is public, and it needs `password` and `date_of_birth` as well as name, email and role.
2. **Log in** with `POST /auth/login` to get an `access_token`, a JWT signed with HS256 that's valid for 60 minutes.
3. **Send the token** as `Authorization: Bearer <access_token>` on the protected endpoints: `GET /users`, `GET /users/<id>` and `GET /auth/me`.

### Forgot password (date of birth)

1. `POST /auth/forgot-password` with `email` and `date_of_birth`. If both match, you get a `reset_token` that's valid for 15 minutes.
2. `POST /auth/reset-password` with `reset_token` and `new_password`.

How the flow is made safe:

- **Separate token types.** Every token carries a `type` claim, so a reset token can't be used as an access token, and an access token can't be used as a reset token.
- **Single-use reset.** Every token also carries the user's `token_version`. A reset increments `token_version`, so the reset token can't be used a second time. The same increment logs out every access token issued before the reset.
- **Brute-force lockout.** A date of birth is easy to guess, so after 5 wrong attempts forgot-password is locked for 15 minutes and returns `429`, even if the correct date of birth is sent.
- **No account discovery.** An unknown email and a wrong date of birth return the same error. Login returns "Invalid email or password" in both cases. For an unknown email it still checks a dummy hash, so the response time doesn't reveal whether the account exists.
- **Secrets never leave the database.** Passwords are hashed with scrypt, and neither the password hash nor the date of birth ever appears in a response.

## API

Base URL: `http://localhost:5000`. Every response is JSON.

**Interactive docs:** `http://localhost:5000/docs` (Swagger UI).

1. Log in with `POST /auth/login`.
2. Click **Authorize** and paste the `access_token`.
3. Use **Try it out** on any endpoint.

The spec is in [`app/static/openapi.yaml`](app/static/openapi.yaml).

```json
{ "success": true, "data": ... }
{ "success": false, "error": "message", "details": { "...": "optional per-field errors" } }
```

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/users` | — | Register a user |
| GET | `/users` | Bearer | List all users |
| GET | `/users?search=<term>` | Bearer | Search by name or email (partial, case-insensitive) |
| GET | `/users?page=1&limit=10` | Bearer | Paginated list |
| GET | `/users?search=<term>&page=1&limit=10` | Bearer | Search and pagination together |
| GET | `/users/<id>` | Bearer | Get one user |
| POST | `/auth/login` | — | Log in and get an access token |
| GET | `/auth/me` | Bearer | The logged-in user |
| POST | `/auth/forgot-password` | — | Verify email and date of birth, get a reset token |
| POST | `/auth/reset-password` | — (reset token in body) | Set a new password |
| GET | `/health` | — | Liveness check (used by Docker) |
| GET | `/docs` | — | Swagger UI |

### POST /users

```bash
curl -X POST http://localhost:5000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Sharma", "email": "Alice@Example.com", "role": "admin", "password": "Secret@123", "date_of_birth": "1998-04-12"}'
```

The request above returns `201 Created`:

```json
{ "success": true, "data": { "id": 1, "name": "Alice Sharma", "email": "alice@example.com", "role": "admin" } }
```

Error responses:

- `409`: `{"success": false, "error": "Email already exists"}`.
- `400`: `{"success": false, "error": "Validation failed", "details": {...}}`. Every invalid field is listed.

Validation rules:

- `name`, `email`, `role`, `password` and `date_of_birth` are all required.
- The email must be a valid format.
- The password must be 8 to 128 characters.
- `date_of_birth` must be a real `YYYY-MM-DD` date, not in the future, and not before 1900.

### POST /auth/login

```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "Secret@123"}'
```

The request above returns `200 OK`:

```json
{ "success": true, "data": { "access_token": "eyJhbGciOi...", "token_type": "Bearer", "expires_in": 3600 } }
```

A wrong email or password returns `401`: `{"success": false, "error": "Invalid email or password"}`.

### GET /users (search and pagination)

```bash
TOKEN="<access_token>"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:5000/users?search=example.com&page=1&limit=2"
```

The request above returns `200 OK`:

```json
{
  "success": true,
  "data": [
    { "id": 1, "name": "Alice Sharma", "email": "alice@example.com", "role": "admin" },
    { "id": 2, "name": "Bob Mehta", "email": "bob.mehta@example.com", "role": "editor" }
  ],
  "pagination": { "page": 1, "limit": 2, "total": 9, "pages": 5 }
}
```

- The `pagination` block only appears when `page` or `limit` is passed.
- `400` is returned when `page` or `limit` isn't a positive integer, or when `limit` is over 100.
- `401` is returned when the token is missing, invalid, expired or revoked.

### GET /users/&lt;id&gt;

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:5000/users/1
```

The request above returns `200 OK` with the user. An unknown ID returns `404`: `{"success": false, "error": "User not found"}`.

### POST /auth/forgot-password → POST /auth/reset-password

```bash
curl -X POST http://localhost:5000/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "date_of_birth": "1998-04-12"}'
```

The request above returns `200 OK`:

```json
{ "success": true, "data": { "reset_token": "eyJhbGciOi...", "expires_in": 900 } }
```

Then send the reset token with the new password:

```bash
curl -X POST http://localhost:5000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"reset_token": "<reset_token>", "new_password": "NewSecret@456"}'
```

The reset returns `200 OK`:

```json
{ "success": true, "message": "Password has been reset. Please log in again." }
```

| Case | Status | Error |
|---|---|---|
| Email and date of birth don't match (or the email doesn't exist) | 400 | `Email and date of birth do not match` |
| 5 wrong attempts, now locked | 429 | `Too many failed attempts. Try again later.` |
| Reset token reused, or the password already changed | 401 | `Token is no longer valid` |
| Reset token expired | 401 | `Token has expired` |
| New password under 8 characters | 400 | `Validation failed` + `details.new_password` |

### Status codes

| Code | When |
|---|---|
| 200 | Successful request |
| 201 | User created |
| 400 | Invalid JSON body, failed validation, bad pagination params, or date of birth mismatch |
| 401 | Missing, invalid, expired or revoked token, or wrong login |
| 404 | User not found, or unknown route |
| 405 | Wrong HTTP method |
| 409 | Duplicate email |
| 429 | Forgot-password locked after too many wrong attempts |
| 500 | Unexpected server error. It's logged, and no internals are leaked in the response. |

## Swagger UI screenshots

Every endpoint and every success and error case, run live from `/docs` against MySQL. Each screenshot shows the input, the generated curl command, the status code and the actual response body.

<img src="docs/screenshots/01-swagger-overview.png" alt="Swagger UI overview" width="720">

### Register: POST /users

**201 Created.** The email is stored lowercase. The password hash and date of birth are never returned.

<img src="docs/screenshots/02-register-201.png" alt="Register 201" width="720">

**409 Conflict: duplicate email.** `ALICE@example.com` counts as a duplicate of `alice@example.com`.

<img src="docs/screenshots/03-register-409-duplicate-email.png" alt="Duplicate email 409" width="720">

**400 Bad Request: invalid fields.** Bad email, short password and a future date of birth are all reported together.

<img src="docs/screenshots/04-register-400-invalid-fields.png" alt="Invalid fields 400" width="720">

**400 Bad Request: missing required fields.**

<img src="docs/screenshots/05-register-400-missing-fields.png" alt="Missing fields 400" width="720">

**400 Bad Request: body is not valid JSON.**

<img src="docs/screenshots/06-register-400-invalid-json.png" alt="Invalid JSON 400" width="720">

### Login: POST /auth/login

**200 OK: access token issued.**

<img src="docs/screenshots/07-login-200.png" alt="Login 200" width="720">

**401 Unauthorized: wrong password.**

<img src="docs/screenshots/08-login-401-wrong-password.png" alt="Login 401" width="720">

### Protected endpoints

**401 Unauthorized: `GET /users` without a token.**

<img src="docs/screenshots/09-list-users-401-no-token.png" alt="No token 401" width="720">

**Authorize in Swagger** with the access token.

<img src="docs/screenshots/10-authorize-with-token.png" alt="Authorize dialog" width="520">

**200 OK: `GET /auth/me`** returns the logged-in user.

<img src="docs/screenshots/11-me-200.png" alt="Me 200" width="720">

### List, search and paginate: GET /users

**200 OK: all users.** There's no pagination block, because `page` and `limit` weren't passed.

<img src="docs/screenshots/12-list-all-users-200.png" alt="List all users" width="720">

**200 OK: search** (`?search=sharma`).

<img src="docs/screenshots/13-search-users-200.png" alt="Search users" width="720">

**200 OK: pagination** (`?page=2&limit=3`).

<img src="docs/screenshots/14-paginate-users-200.png" alt="Paginate users" width="720">

**200 OK: search and pagination together** (`?search=example.com&page=1&limit=2`).

<img src="docs/screenshots/15-search-and-paginate-200.png" alt="Search and paginate" width="720">

**400 Bad Request: `limit` above 100.**

<img src="docs/screenshots/16-paginate-400-limit-too-large.png" alt="Limit too large 400" width="720">

**400 Bad Request: `page` isn't a positive integer** (`page=0`).

<img src="docs/screenshots/17-paginate-400-invalid-page.png" alt="Invalid page 400" width="720">

### Get by ID: GET /users/{id}

**200 OK.**

<img src="docs/screenshots/18-get-user-200.png" alt="Get user 200" width="720">

**404 Not Found.**

<img src="docs/screenshots/19-get-user-404.png" alt="User not found 404" width="720">

### Forgot and reset password

**400 Bad Request: wrong date of birth.**

<img src="docs/screenshots/20-forgot-password-400-wrong-dob.png" alt="Wrong DOB 400" width="720">

**200 OK: email and date of birth match, reset token issued.**

<img src="docs/screenshots/21-forgot-password-200.png" alt="Forgot password 200" width="720">

**200 OK: password reset with that token.**

<img src="docs/screenshots/22-reset-password-200.png" alt="Reset password 200" width="720">

**401 Unauthorized: the same reset token used again is rejected.**

<img src="docs/screenshots/23-reset-password-401-token-reused.png" alt="Reset token reused 401" width="720">

**200 OK: login works with the new password.**

<img src="docs/screenshots/24-login-with-new-password-200.png" alt="Login with new password" width="720">

**429 Too Many Requests: locked after 5 wrong date-of-birth attempts.** The correct date of birth is refused while the lock is active.

<img src="docs/screenshots/25-forgot-password-429-locked.png" alt="Locked 429" width="720">

### GET /health

<img src="docs/screenshots/26-health-200.png" alt="Health" width="720">

## Assumptions

- **Registration is public.** `POST /users` is the sign-up endpoint, so it doesn't need a token. The read endpoints require one.
- **Extra columns for auth.** The assignment's table has `id`, `name`, `email` and `role`. The JWT and password-reset bonus needs a password hash and a date of birth, plus three bookkeeping columns. The original four columns are unchanged.
- **Reset token delivery.** The forgot-password flow verifies identity by date of birth and returns the reset token in the response, since no email or SMS provider is part of this assignment.
- **Any logged-in user can read all users.** The spec doesn't define what each role is allowed to do, so there's no role-based access control.
- **Pagination is opt-in.**
  - Plain `GET /users` returns all users.
  - Pagination applies when `page` or `limit` is present, with defaults `page=1` and `limit=10`.
  - `limit` is capped at 100.
- **Search** is a partial, case-insensitive match on name or email, and it combines with pagination. `%` and `_` in the search term are treated literally, not as wildcards.
- **Emails** are trimmed and lower-cased before they're stored, so `Alice@x.com` and `alice@x.com` count as duplicates.
- **Role** is free text up to 50 characters, because the spec doesn't define a fixed set of roles.
- **Duplicate emails** are checked in the service layer. The DB `UNIQUE` constraint catches races between two requests, and that case also returns `409`.
- **Schema management** is done by `db/init.sql`, not `db.create_all()`, which keeps the DDL explicit.

## Short answers

**1. Why did you choose Flask?**

The core assignment is a few JSON endpoints over a single table, and I wanted the code to stay about that size. With Flask I only pull in what I actually use: blueprints for the routes, Flask-SQLAlchemy for the model and pagination, and PyJWT for tokens. Even the auth bonus turned out to be a couple of small, readable service functions rather than a framework feature I'd have to configure around. Django is great, but here most of what it gives you out of the box would sit unused: the admin, the templates, the session-based auth. I'd also end up adding DRF just to return JSON cleanly. If this grew into a bigger product with an admin panel and lots of models, I'd seriously consider Django. For this scope, Flask felt like the honest choice.

**2. How would you scale this system?**

The good news is the API is stateless. Auth is JWT, so there's no server-side session to share, and the app side is the easy part: run more containers behind a load balancer and add more as traffic grows. The database is where it would actually hurt first, so most of my effort would go there. Since this API is mostly reads, I'd add read replicas and send the `GET` traffic to them.

A couple of the queries would also need changing as the table grows:

- **Pagination**: `OFFSET` gets slower the deeper you page, so I'd switch to cursor-style pagination (`WHERE id > last_seen_id LIMIT n`).
- **Search**: `LIKE '%term%'` can't use an index, so I'd move it to a `FULLTEXT` index first, and to something like Elasticsearch if search became a real feature.

On top of that, caching `GET /users/<id>` in Redis would take a lot of load off, and I'd want proper metrics in place. That way I'd be scaling the part that's actually slow rather than guessing.

**3. What changes would you make for production?**

Security first. The date-of-birth check works for this assignment, but a date of birth isn't really a secret. In production I'd send a one-time reset link or code to the user's email or phone and keep the date of birth as an extra check at most. I'd also:

- **Login protection**: rate-limit login the same way forgot-password is limited now.
- **Tokens**: add refresh tokens so access tokens can be shorter-lived.
- **Permissions**: add role-based permissions once the roles actually mean something.
- **Secrets and network**: move the JWT secret and DB credentials into a secrets manager, serve everything over HTTPS, and stop exposing the MySQL port.

After that, the things that make it safe to change and easy to debug:

- **Migrations**: real schema migrations with Alembic instead of a one-off SQL script.
- **Tests and CI**: an automated test suite that runs in CI on every pull request.
- **Logging and errors**: structured logs with request IDs, plus error tracking like Sentry, so I hear about problems before users do.
- **Health checks**: a readiness check that also verifies the database is reachable.
- **API basics**: request size limits, a CORS policy and versioned URLs (`/api/v1`).
- **Database**: a managed MySQL with automatic backups, so losing data isn't something I have to think about at 2 a.m.

## AI usage declaration

- **Tools used:** Claude (Anthropic), through Claude Code.
- **What was AI-generated:** the initial project scaffold, the Flask app factory, the model, service and route code, the validators, the JWT and password-reset flow, the OpenAPI spec, the Dockerfile, the docker-compose file and this README.
- **What I did or changed manually:**
  - Reviewed every file and decided on the design choices:
    - opt-in pagination
    - lower-cased emails
    - a `db/init.sql` schema instead of `create_all`
    - public registration with protected reads
    - date-of-birth reset with lockout and single-use tokens
  - Tested every endpoint and error case against a real MySQL-compatible database, both with scripts and through Swagger UI.
  - Adjusted the configuration, for example URL-encoding the DB password and the TCP-based MySQL healthcheck.
  - I can explain each part of the implementation.
