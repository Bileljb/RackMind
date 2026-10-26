from fastapi import APIRouter, HTTPException, Response, status

from app.core.config import get_settings
from app.core.security import SESSION_COOKIE, create_access_token
from app.deps import CurrentUser, DbSession
from app.schemas.user import LoginIn, UserOut
from app.services import users as users_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginIn, response: Response, db: DbSession) -> UserOut:
    """Check the credentials and set the session cookie.

    The token goes in an httpOnly cookie, not the response body: JavaScript on the page
    (including injected scripts) can't read it, and the browser sends it automatically.
    SameSite=Lax stops other websites from making the browser send it with their POSTs.
    """
    user = await users_service.authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_access_token(user.id),
        max_age=settings.session_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    """Remove the cookie. The token itself stays valid until it expires (it is stateless)."""
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, secure=settings.cookie_secure, samesite="lax"
    )


@router.get("/me")
async def me(user: CurrentUser) -> UserOut:
    """Who is logged in. The web app calls this to show the name and pick which buttons to show."""
    return UserOut.model_validate(user)
