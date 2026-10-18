from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.core.security import decode_access_token
from app.models.user import UserResponse, UserRole

# Standard OAuth2 scheme pointing to login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> UserResponse:
    """
    Validates JWT Bearer token and resolves current authenticated user from MongoDB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    username: Optional[str] = payload.get("sub")
    if not username:
        raise credentials_exception

    user_doc = await db.users.find_one({"username": username})
    if not user_doc:
        # Development fallback: if user is admin or token was signed for seed admin
        if username == "admin":
            return UserResponse(
                username="admin",
                email="admin@projectcore.com",
                full_name="Project CORE Administrator",
                role=UserRole.ADMIN,
                is_active=True
            )
        raise credentials_exception

    user = UserResponse(**user_doc)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )
    return user


async def get_current_active_admin(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """Ensures user has admin privileges."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user
