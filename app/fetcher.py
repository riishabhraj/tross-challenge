"""
Profile-fetching abstraction.

IMPORTANT ARCHITECTURAL BOUNDARY:
Every ProfileFetcher implementation takes an authenticated user's OAuth access
token, never a LinkedIn profile URL or a member ID supplied by a caller. This
is intentional: LinkedIn's consumer OAuth ("Sign In with LinkedIn using OpenID
Connect") only ever authorizes an app to read the data of the person who just
completed the consent screen. There is no code path anywhere in this project
that accepts an arbitrary LinkedIn URL and returns another person's data -
that would require either scraping (against LinkedIn's ToS and legally
contested, see e.g. hiQ v. LinkedIn / LinkedIn's suits against scraping
operators) or a formal LinkedIn Partner Program integration, neither of which
is in scope here.
"""

from typing import Protocol

import httpx

from app.schemas import ProfileResponse

LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"


class ProfileFetcher(Protocol):
    async def fetch_profile(self, access_token: str) -> ProfileResponse:
        """Fetch the profile of the user who owns `access_token`.

        Implementations must not accept a profile URL, member ID, or any
        other identifier for a *different* user - the access token itself
        is the only permitted input, since it is what LinkedIn ties consent
        to.
        """
        ...


class OAuthProfileFetcher:
    """
    Fetches the authenticated user's own profile via LinkedIn's OpenID
    Connect /userinfo endpoint.

    Field availability note:
    LinkedIn's current "Sign In with LinkedIn using OpenID Connect" product
    (the `openid profile email` scopes) exposes only basic identity claims:
    sub, name, given_name, family_name, picture, locale, email,
    email_verified. It does NOT expose headline, summary/about, geographic
    location, work experience, education history, skills, certifications, or
    language list - those fields were previously available via the legacy
    `r_liteprofile` / `r_basicprofile` v2 People API, which LinkedIn has
    locked behind its Partner Program (Marketing Developer Platform /
    Talent/Compliance partnerships) and no longer grants to standard
    developer apps. Most developer apps - including this one - genuinely
    cannot obtain those fields through any consent-based API today.

    This implementation therefore returns `None` for every field LinkedIn's
    standard OIDC scopes don't provide, and lists them explicitly in
    `fields_unavailable` rather than guessing, scraping, or leaving the
    caller to wonder why a field is empty.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None):
        self._client = http_client

    async def fetch_profile(self, access_token: str) -> ProfileResponse:
        headers = {"Authorization": f"Bearer {access_token}"}

        client = self._client
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(timeout=10.0)

        try:
            resp = await client.get(LINKEDIN_USERINFO_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        finally:
            if owns_client:
                await client.aclose()

        name = data.get("name") or " ".join(
            filter(None, [data.get("given_name"), data.get("family_name")])
        ) or None

        fields_unavailable = [
            "headline: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
            "location: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
            "about: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
            "experience: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
            "education: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
            "skills: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
            "certifications: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
            "languages: not exposed by LinkedIn's OpenID Connect scopes (requires Partner Program access)",
        ]

        return ProfileResponse(
            linkedin_sub=data.get("sub"),
            name=name,
            headline=None,
            location=None,
            about=None,
            email=data.get("email"),
            profile_image_url=data.get("picture"),
            experience=[],
            education=[],
            skills=[],
            certifications=[],
            languages=[],
            data_source="linkedin_oauth",
            fields_unavailable=fields_unavailable,
        )
