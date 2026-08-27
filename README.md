# Tross LinkedIn Profile API

A hosted HTTP API that returns structured LinkedIn profile data for a user
who has authenticated via LinkedIn's official "Sign In with LinkedIn using
OpenID Connect" OAuth flow. Built with FastAPI + PostgreSQL.

## Approach

LinkedIn does not offer any consent-based API that returns an arbitrary
third party's profile data given only a profile URL. The only legitimate,
ToS-compliant way to get profile data from LinkedIn as a standard developer
app is to have the profile's owner authenticate through LinkedIn's OAuth
consent screen and read back *their own* data via the OpenID Connect
`/userinfo` endpoint.

So instead of "paste a LinkedIn URL, get JSON back," this API is structured
as **"sign in with LinkedIn, get your own profile back."** Concretely:

- A `ProfileFetcher` protocol (`app/fetcher.py`) defines the fetching
  contract as `fetch_profile(access_token: str) -> ProfileResponse`. It
  takes an OAuth access token, never a URL or a member ID - which makes "you
  can only ever fetch the consenting user's own data" an architectural
  property of the interface, not just a policy someone has to remember to
  enforce in a route handler.
- `OAuthProfileFetcher` is the one concrete implementation, calling
  LinkedIn's OpenID Connect `/userinfo` endpoint with the token obtained
  from the OAuth callback.
- There is no code path anywhere in the project that accepts a raw LinkedIn
  profile URL. Nothing scrapes linkedin.com, logs in with stored
  credentials, or drives a headless browser against LinkedIn's site.

## Architecture

```
GET /auth/linkedin/login     -> redirects to LinkedIn's OAuth authorize URL
GET /auth/linkedin/callback  -> exchanges code for token, fetches profile,
                                 stores a session, returns the profile JSON
GET /profile/me              -> returns the signed-in user's stored profile
GET /health                  -> liveness check (no auth, no profile data)
```

Sessions are stored server-side in Postgres (`user_sessions`: session id,
LinkedIn `sub`, access token, and the last-fetched profile JSON), keyed by an
opaque, httponly session cookie. No unauthenticated endpoint returns real
profile data - `/health` is the only route reachable without a valid
session, and it returns nothing but a status string.

## Response schema

```python
class ProfileResponse(BaseModel):
    name: str | None
    headline: str | None
    location: str | None
    about: str | None
    email: str | None
    profile_image_url: str | None
    experience: list[ExperienceItem] = []
    education: list[EducationItem] = []
    skills: list[str] = []
    certifications: list[CertificationItem] = []
    languages: list[str] = []
    data_source: str  # "linkedin_oauth"
    fields_unavailable: list[str]  # what couldn't be fetched, and why
```

## Setup

### Environment variables

Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `LINKEDIN_CLIENT_ID` / `LINKEDIN_CLIENT_SECRET` | From a LinkedIn app at [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) with the **"Sign In with LinkedIn using OpenID Connect"** product enabled |
| `LINKEDIN_REDIRECT_URI` | Must exactly match a redirect URL registered on the LinkedIn app |
| `DATABASE_URL` | Async Postgres URL, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| `SESSION_SECRET` | Random secret (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |

`.env` is git-ignored; never commit real credentials.

### Run locally with Docker (recommended)

```bash
docker compose up --build
```

This starts the API on `http://localhost:8000` and a local Postgres
instance. The API creates its own tables on startup.

### Run locally without Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# point DATABASE_URL in .env at a Postgres instance you already have running
uvicorn app.main:app --reload
```

## API documentation

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### `GET /auth/linkedin/login`

Open in a browser (not curl - it's an interactive OAuth redirect):

```
http://localhost:8000/auth/linkedin/login
```

Redirects to LinkedIn's consent screen, then back to
`/auth/linkedin/callback`.

### `GET /auth/linkedin/callback`

Handled automatically by the redirect above. Exchanges the authorization
code for an access token, fetches the profile, stores a session, sets a
session cookie, and returns the profile JSON directly:

```json
{
  "linkedin_sub": "abc123",
  "name": "Jane Doe",
  "headline": null,
  "location": null,
  "about": null,
  "email": "jane@example.com",
  "profile_image_url": "https://media.licdn.com/...",
  "experience": [],
  "education": [],
  "skills": [],
  "certifications": [],
  "languages": [],
  "data_source": "linkedin_oauth",
  "fields_unavailable": [
    "headline: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
    "..."
  ]
}
```

### `GET /profile/me`

Returns the same JSON as above, read back from the stored session (needs
the session cookie set by the callback):

```bash
curl -b cookies.txt http://localhost:8000/profile/me
```

Returns `401` if there's no valid session.

## Known limitations

- **This implementation only returns data for the authenticated user, not
  arbitrary third-party profile URLs**, and does not scrape or
  reverse-engineer LinkedIn's private endpoints. Scraping LinkedIn or
  reverse-engineering its internal APIs to fetch other users' data without
  their consent violates LinkedIn's Terms of Service and raises real
  privacy concerns for the people whose data would be exposed - LinkedIn
  has taken legal action against companies doing exactly this
  (e.g. its suits against scraping/data-harvesting operators).
- **Fields unavailable via consented OAuth scopes**: LinkedIn's standard
  "Sign In with LinkedIn using OpenID Connect" product only exposes basic
  identity claims - name, email, profile picture, locale. It does **not**
  expose headline, summary/about text, geographic location, detailed work
  experience, education history, skills, certifications, or languages. Those
  fields were available via the legacy `r_liteprofile`/`r_basicprofile` v2
  People API, which LinkedIn has since restricted to Partner Program
  members. Every response explicitly lists which fields are missing and why
  in `fields_unavailable`, rather than silently omitting them or
  fabricating placeholder data.
- **What a fuller version would require**: to genuinely pull full profile
  histories (experience, education, skills, etc.) at scale, an application
  needs a formal [LinkedIn Partner Program](https://learn.microsoft.com/en-us/linkedin/)
  agreement (e.g. Talent Solutions or Marketing Developer Platform
  partnership) - a business relationship with LinkedIn, not something a
  standard developer app can unlock through more OAuth scopes.
- Sessions are stored in plaintext (access token + profile JSON) in Postgres
  for simplicity; a production system would encrypt tokens at rest and add
  expiry/refresh handling.

## Deployment

Any container host that can run a Docker image plus provision a Postgres
database works (Railway, Render, Fly.io, a small VPS behind Caddy/Nginx for
TLS). The general steps:

1. Provision a managed Postgres instance and set `DATABASE_URL`.
2. Set `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `SESSION_SECRET`, and
   `LINKEDIN_REDIRECT_URI` (pointing at your deployed HTTPS domain, e.g.
   `https://your-app.example.com/auth/linkedin/callback`) as environment
   variables on the host.
3. Register that same redirect URL on the LinkedIn app's OAuth settings
   page.
4. Deploy the `Dockerfile` image; the app listens on `$PORT` via the
   platform's standard mechanism (most PaaS providers set `PORT` and expect
   the container to bind to it - adjust the `uvicorn` command's `--port` or
   rely on the platform's Docker `EXPOSE`/proxy handling as needed).
5. Confirm the deployed instance requires OAuth: `GET /profile/me` on a
   fresh session should return `401`, and only `/health` should respond
   without authentication.
