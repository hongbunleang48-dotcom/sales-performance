from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
)
from app.api.deps import get_current_user
from app.models.user import (
    UserCreate,
    UserResponse,
    UserRole,
    Token,
)

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Authenticate user and issue JWT Bearer access token.
    Accepts both standard application/json and application/x-www-form-urlencoded.
    Includes default seed admin fallback (admin / admin123) for initial deployment.
    """
    content_type = request.headers.get("content-type", "")
    username = None
    password = None

    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed JSON body",
            )
    else:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )

    username = str(username).strip()
    password = str(password)

    # Query user from MongoDB
    user_doc = await db.users.find_one({"username": username})

    # Default developer/demo seed: if users collection is empty and logging in as admin
    if not user_doc and username == "admin" and password in ("admin123", "admin"):
        # Auto-seed default admin
        now = datetime.now(timezone.utc)
        hashed_pwd = get_password_hash("admin123")
        default_admin = {
            "username": "admin",
            "email": "admin@projectcore.com",
            "full_name": "Project CORE Administrator",
            "role": UserRole.ADMIN.value,
            "is_active": True,
            "hashed_password": hashed_pwd,
            "created_at": now,
            "updated_at": now,
        }
        res = await db.users.insert_one(default_admin)
        default_admin["_id"] = str(res.inserted_id)
        user_doc = default_admin

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password hash
    if not verify_password(password, user_doc.get("hashed_password", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_doc.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    # Create JWT
    role = user_doc.get("role", UserRole.ANALYST.value)
    token = create_access_token(data={"sub": username, "role": role})
    user_resp = UserResponse(**user_doc)

    return Token(
        access_token=token,
        token_type="bearer",
        user=user_resp,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: UserResponse = Depends(get_current_user),
):
    """Returns profile and permission details of currently authenticated user."""
    return current_user


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Registers a new user account."""
    existing = await db.users.find_one({"username": user_in.username})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_in.username}' is already taken",
        )

    now = datetime.now(timezone.utc)
    hashed = get_password_hash(user_in.password)
    user_dict = user_in.model_dump()
    user_dict.pop("password", None)
    user_dict["hashed_password"] = hashed
    user_dict["created_at"] = now
    user_dict["updated_at"] = now

    res = await db.users.insert_one(user_dict)
    user_dict["_id"] = str(res.inserted_id)
    return UserResponse(**user_dict)
