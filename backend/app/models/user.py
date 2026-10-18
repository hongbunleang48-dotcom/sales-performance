from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class UserRole(str, Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UserBase(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique system login username",
        examples=["admin"]
    )
    email: Optional[str] = Field(
        None,
        description="User email address",
        examples=["admin@projectcore.com"]
    )
    full_name: Optional[str] = Field(
        None,
        max_length=150,
        description="User full display name",
        examples=["System Administrator"]
    )
    role: UserRole = Field(
        default=UserRole.ANALYST,
        description="User permission role",
        examples=["admin"]
    )
    is_active: bool = Field(
        default=True,
        description="Account active status"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="ignore"
    )


class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Plaintext password for registration"
    )


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="ignore"
    )


class UserInDB(UserBase):
    hashed_password: str = Field(..., description="Bcrypt hashed password")
    id: Optional[str] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("id", mode="before")
    @classmethod
    def serialize_mongo_id(cls, v: Any) -> Optional[str]:
        if v is not None:
            return str(v)
        return None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        use_enum_values=True,
        extra="ignore"
    )


class UserResponse(UserBase):
    id: Optional[str] = Field(None, alias="_id")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("id", mode="before")
    @classmethod
    def serialize_mongo_id(cls, v: Any) -> Optional[str]:
        if v is not None:
            return str(v)
        return None

    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        use_enum_values=True,
        extra="ignore"
    )


class Token(BaseModel):
    access_token: str = Field(..., description="JWT bearer access token")
    token_type: str = Field("bearer", description="Token scheme")
    user: Optional[UserResponse] = Field(None, description="Current authenticated user info")


class TokenPayload(BaseModel):
    sub: Optional[str] = Field(None, description="Username / user subject")
    role: Optional[str] = Field(None, description="User role")
    exp: Optional[int] = Field(None, description="Expiry UNIX timestamp")


class LoginRequest(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
