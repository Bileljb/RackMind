from fastapi import APIRouter, HTTPException, status

from app.deps import Admin, DbSession, Operator
from app.models import User
from app.schemas.user import UserBrief, UserCreate, UserOut, UserUpdate
from app.services import users as users_service
from app.services.users import EmailTakenError, SelfLockoutError

# Admins only, except the directory. Accounts are never deleted (comments and audit entries
# point at them): set `is_active: false` instead, which blocks login and every request at once.
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/directory")
async def directory(db: DbSession, _: Operator) -> list[UserBrief]:
    """Names and roles for every logged-in user: who commented, who is assigned, etc."""
    return [UserBrief.model_validate(user) for user in await users_service.list_users(db)]


@router.get("")
async def list_users(db: DbSession, _: Admin) -> list[UserOut]:
    return [UserOut.model_validate(user) for user in await users_service.list_users(db)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, db: DbSession, actor: Admin) -> UserOut:
    try:
        user = await users_service.create_user(db, body, actor)
    except EmailTakenError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use") from error
    return UserOut.model_validate(user)


@router.patch("/{user_id}")
async def update_user(user_id: int, body: UserUpdate, db: DbSession, actor: Admin) -> UserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        user = await users_service.update_user(db, user, body, actor)
    except SelfLockoutError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You can't demote or deactivate your own account"
        ) from error
    return UserOut.model_validate(user)
