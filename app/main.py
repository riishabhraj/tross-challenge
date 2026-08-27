import secrets
from contextlib import asynccontextmanager

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session, init_db, load_profile, store_session
from app.fetcher import OAuthProfileFetcher
from app.oauth import build_authorization_url, exchange_code_for_token, generate_state
from app.schemas import ProfileResponse

STATE_COOKIE_NAME = "tross_oauth_state"

profile_fetcher = OAuthProfileFetcher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Tross LinkedIn Profile API",
    description=(
        "Returns structured profile data for the user who has authenticated via "
        "LinkedIn's OAuth 'Sign In with LinkedIn' flow. Only ever returns data for "
        "the authenticated user - never for an arbitrary third-party profile URL."
    ),
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/auth/linkedin/login")
async def linkedin_login():
    state = generate_state()
    auth_url = build_authorization_url(state)
    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        STATE_COOKIE_NAME,
        state,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=600,
    )
    return response


@app.get("/auth/linkedin/callback")
async def linkedin_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    if error:
        raise HTTPException(status_code=400, detail=f"LinkedIn OAuth error: {error} - {error_description}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state from LinkedIn redirect")

    expected_state = request.cookies.get(STATE_COOKIE_NAME)
    if not expected_state or not secrets.compare_digest(expected_state, state):
        raise HTTPException(status_code=400, detail="Invalid or missing OAuth state (possible CSRF)")

    access_token = await exchange_code_for_token(code)
    profile: ProfileResponse = await profile_fetcher.fetch_profile(access_token)

    session_id = secrets.token_urlsafe(32)
    await store_session(db, session_id, profile.linkedin_sub or session_id, access_token, profile)

    response = JSONResponse(content=profile.model_dump())
    response.delete_cookie(STATE_COOKIE_NAME)
    response.set_cookie(
        settings.session_cookie_name,
        session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@app.get("/profile/me", response_model=ProfileResponse)
async def profile_me(
    db: AsyncSession = Depends(get_session),
    session_id: str | None = Cookie(default=None, alias=settings.session_cookie_name),
):
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated. Visit /auth/linkedin/login first.")

    profile = await load_profile(db, session_id)
    if profile is None:
        raise HTTPException(status_code=401, detail="No stored profile for this session. Re-authenticate.")

    return profile
