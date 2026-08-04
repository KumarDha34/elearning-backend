# E-Learning Platform for Nepal — Backend (Phase 1: Authentication)

Implements the recommended tech stack from the design documentation, built
out through the **Auth & Accounts** module (`/api/v1/auth/*`):

| Layer | Choice | Where |
|---|---|---|
| API framework | Django + Django REST Framework | `config/`, `apps/accounts/` |
| Auth | JWT via `djangorestframework-simplejwt` + custom OTP flow | `apps/accounts/serializers.py`, `views.py` |
| Database | PostgreSQL | `config/settings.py` → `DATABASES` |
| Cache / throttle store | Redis | `config/settings.py` → `CACHES` |
| Async tasks | Celery + Celery Beat | `config/celery.py`, `apps/accounts/tasks.py` |
| SMS / OTP | Sparrow SMS (primary) + Aakash SMS (fallback), pluggable adapter | `apps/accounts/services/sms/` |
| API docs | drf-spectacular (OpenAPI/Swagger) | `/api/v1/docs/` |
| Containerization | Docker + Docker Compose | `Dockerfile`, `docker-compose.yml` |

**Not included yet (by design — later phases):** `profiles`, `academics`,
and every other Django app from the full design document. Only `accounts`
(and the shared `common`/permission-layer scaffolding other apps will reuse)
is built here.

## A note on this environment

This code was written and syntax-checked (`python -m py_compile` on every
file) in a sandbox with no internet access, so Django itself could not be
installed or the server actually run/tested here. Everything below is
ready to run in your own environment — nothing here has been executed
against a live Postgres/Redis.

## Quick start (Docker — recommended)

```bash
cp .env.example .env
# Edit .env: at minimum set a real DJANGO_SECRET_KEY.
# Leave SMS_PRIMARY_PROVIDER=console for local dev — OTPs are logged to the
# celery_worker container's stdout instead of sending real SMS.

docker compose up --build
```

Then, in a second terminal:

```bash
docker compose exec web python manage.py createsuperuser
# createsuperuser prompts for phone_number (USERNAME_FIELD) instead of username.
```

API base URL: `http://localhost:8000/api/v1/auth/`
Interactive docs: `http://localhost:8000/api/v1/docs/`

## Quick start (local, no Docker)

Requires PostgreSQL and Redis running locally.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point POSTGRES_HOST / REDIS_URL at localhost

python manage.py migrate
python manage.py createsuperuser

# Terminal 1
python manage.py runserver

# Terminal 2 — Celery worker (required: OTP SMS sending is fully async)
celery -A config worker -l info

# Terminal 3 — Celery beat (not strictly needed yet, no scheduled jobs in
# this phase, but wired up for when notification/ads jobs are added)
celery -A config beat -l info
```

## Running tests

Tests use SQLite + synchronous Celery so no external services are needed:

```bash
DJANGO_SETTINGS_MODULE=config.test_settings python manage.py test apps.accounts
```

## Endpoint reference & example calls

All requests/responses are JSON. Base path: `/api/v1/auth/`.

### 1. Signup — `POST /auth/signup/`
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup/ \
  -H "Content-Type: application/json" \
  -d '{
        "full_name": "Sita Thapa",
        "phone_number": "9841234567",
        "role": "student",
        "password": "StrongPass123!",
        "password_confirm": "StrongPass123!"
      }'
```
Creates an inactive, unverified `User` and queues an OTP SMS via Celery
(purpose=`signup`). With `SMS_PRIMARY_PROVIDER=console`, watch the OTP in
the `celery_worker` logs: `docker compose logs -f celery_worker`.

### 2. Resend OTP — `POST /auth/otp/send/`
```bash
curl -X POST http://localhost:8000/api/v1/auth/otp/send/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "9841234567", "purpose": "signup"}'
```
Throttled to 5/hour per phone number (not per IP), plus a 60-second
resend cooldown — see `apps/accounts/throttling.py`.

### 3. Verify OTP — `POST /auth/otp/verify/`
```bash
curl -X POST http://localhost:8000/api/v1/auth/otp/verify/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "9841234567", "code": "123456", "purpose": "signup"}'
```
For `purpose=signup`, this activates the account and returns JWT tokens
immediately — no separate login step required right after verification.

### 4. Login — `POST /auth/login/`
```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "9841234567", "password": "StrongPass123!"}'
```
Returns `{"access": "...", "refresh": "...", "user": {...}}`. Blocked with
a 400 if `phone_verified` is false. Throttled to 10/minute per phone
number to blunt brute-force attempts.

### 5. Refresh token — `POST /auth/token/refresh/`
```bash
curl -X POST http://localhost:8000/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```
Access tokens live 15 minutes; refresh tokens live 7 days and rotate +
blacklist on every use (`ROTATE_REFRESH_TOKENS`, `BLACKLIST_AFTER_ROTATION`).

### 6. Logout — `POST /auth/logout/`
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```
Blacklists the refresh token so it can never be exchanged again.

### 7. Request password reset — `POST /auth/password/reset/`
```bash
curl -X POST http://localhost:8000/api/v1/auth/password/reset/ \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "9841234567"}'
```
Always returns 200 with the same generic message, whether or not the
number has an account, to avoid leaking registered numbers.

### 8. Confirm password reset — `POST /auth/password/reset/confirm/`
```bash
curl -X POST http://localhost:8000/api/v1/auth/password/reset/confirm/ \
  -H "Content-Type: application/json" \
  -d '{
        "phone_number": "9841234567",
        "code": "123456",
        "new_password": "BrandNewPass123!",
        "new_password_confirm": "BrandNewPass123!"
      }'
```

### 9. Current user — `GET /auth/me/`
```bash
curl http://localhost:8000/api/v1/auth/me/ \
  -H "Authorization: Bearer <access_token>"
```

## Design decisions & assumptions worth flagging to the client

1. **Password is captured at signup, not at profile completion.** The
   design document's sequence diagram sets the password during Page 2
   profile completion (the `profiles` app). Since that app is out of
   scope here, `password`/`password_confirm` were moved into
   `POST /auth/signup/` so the auth flow is independently testable.
   Nothing about this needs to change when `profiles` is built — profile
   completion just becomes a second, separately-gated step after login.
2. **Login is by phone number, not the auto-generated `username`.**
   `username` (e.g. `PB5605`) is only assigned once profile completion
   runs. `USERNAME_FIELD = "phone_number"` on the `User` model means
   switching the login serializer to accept `username` later is a
   one-line change, not a redesign.
3. **Only Student and Instructor can self-register.** Admin and Editor
   accounts are provisioned via `createsuperuser` / Django admin, per the
   RBAC model — there's no public signup path for those roles.
4. **OTP codes are hashed at rest** (`django.contrib.auth.hashers`) and
   never logged or returned in any API response — only the Celery task
   that hands off to the SMS gateway ever sees the raw code.
5. **SMS gateway is provider-agnostic by design**, per design-doc §7.3:
   `apps/accounts/services/sms/base.py` defines the interface;
   `sparrow.py` / `aakash.py` implement it; `factory.py` tries the primary
   provider and automatically falls back to the secondary one on failure.
   A `console` provider is included for local development.

## What's next (not built in this phase)

`profiles`, `academics`, `notes`, `blogs`, `qna`, `quizzes`, `progress`,
`planner`, `live_classes`, `video_lectures`, `ai_tutor`, `marketplace`,
`payments`, `points`, `ads`, `moderation`, `notifications`, `analytics` —
per the app breakdown in the design document's §3. The `IsAdmin` /
`IsStudent` / `IsInstructor` / `IsEditor` / `IsOwner` permission classes in
`apps/accounts/permissions.py` are written to be imported directly into
every one of those apps' views without modification.
