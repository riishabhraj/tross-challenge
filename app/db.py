import datetime
import json

from sqlalchemy import DateTime, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings
from app.schemas import ProfileResponse

engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UserSession(Base):
    """A server-side session tying a browser cookie to one authenticated
    LinkedIn user's access token and last-fetched profile snapshot.

    Storing the access token lets /profile/me re-serve (or re-fetch) data
    without forcing the user back through the OAuth dance on every request,
    but the token is never usable to fetch anyone else's profile - the
    fetcher interface only ever takes a token, and each token is scoped by
    LinkedIn to the single consenting user.
    """

    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    linkedin_sub: Mapped[str] = mapped_column(String(255))
    access_token: Mapped[str] = mapped_column(Text)
    profile_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


async def store_session(
    db: AsyncSession, session_id: str, linkedin_sub: str, access_token: str, profile: ProfileResponse
) -> None:
    row = UserSession(
        session_id=session_id,
        linkedin_sub=linkedin_sub,
        access_token=access_token,
        profile_json=profile.model_dump_json(),
    )
    await db.merge(row)
    await db.commit()


async def load_profile(db: AsyncSession, session_id: str) -> ProfileResponse | None:
    result = await db.execute(select(UserSession).where(UserSession.session_id == session_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return ProfileResponse(**json.loads(row.profile_json))
