from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class AuditLog(BaseModel):
    salesman_id: str = Field(..., description="Target salesman identifier")
    action: str = Field("UPDATE", description="Action performed, e.g. UPDATE, STATUS_TOGGLE")
    changes: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Dictionary of field-level changes: {field: {'old': ..., 'new': ...}}"
    )
    previous_values: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Snapshot of changed fields prior to the operation"
    )
    new_values: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Snapshot of changed fields after the operation"
    )
    actor: Optional[str] = Field(
        "system",
        description="User or system role initiating the modification"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the change occurred"
    )
    id: Optional[str] = Field(
        None,
        alias="_id",
        description="MongoDB ObjectId string representation"
    )

    @field_validator("id", mode="before")
    @classmethod
    def serialize_mongo_id(cls, v: Any) -> Optional[str]:
        if v is not None:
            return str(v)
        return None

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        extra="ignore"
    )
