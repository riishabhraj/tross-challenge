import secrets
from urllib.parse import urlencode

import httpx

from app.config import settings

AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
ACCESS_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


def build_authorization_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "scope": settings.linkedin_scopes,
        "state": state,
    }
    return f"{AUTHORIZATION_URL}?{urlencode(params)}"


def generate_state() -> str:
    return secrets.token_urlsafe(32)


async def exchange_code_for_token(code: str) -> str:
    """Exchange an authorization code for an access token.

    Returns the access token belonging to the user who just completed the
    LinkedIn consent screen - this is the only credential the rest of the
    app is allowed to fetch profile data with.
    """
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.linkedin_redirect_uri,
        "client_id": settings.linkedin_client_id,
        "client_secret": settings.linkedin_client_secret,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            ACCESS_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        payload = resp.json()

    return payload["access_token"]
