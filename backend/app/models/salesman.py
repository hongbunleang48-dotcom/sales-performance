from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from app.core.rules import (
    AchievementStatus,
    PerformanceGrade,
    ActionStatus,
    CreditHealth,
)


class SalesmanStatus(str, Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"


class RouteDiscipline(str, Enum):
    COMPLIANT = "Compliant"
    ROUTE_DIVERTED = "Route Diverted"


class MomGrowth(str, Enum):
    POSITIVE_GROWTH = "Positive Growth"
    FLAT = "Flat"
    DECLINING = "Declining"


class MerchandisingScore(str, Enum):
    EXCELLENT = "Excellent"
    GOOD = "Good"
    FAIR = "Fair"
    POOR = "Poor"


class SalesmanBase(BaseModel):
    salesman_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Full name of salesman",
        examples=["Chhay Sophal"]
    )
    supervisor: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Direct supervisor name",
        examples=["Keo Piseth"]
    )
    province: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Territory Province",
        examples=["Phnom Penh"]
    )
    district: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Territory District",
        examples=["Pur SenChey"]
    )
    commune: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Territory Commune",
        examples=["Kakab 1"]
    )
    status: SalesmanStatus = Field(
        default=SalesmanStatus.ACTIVE,
        description="Salesman operational status",
        examples=["Active"]
    )
    target_achieved_pct: float = Field(
        ...,
        ge=0.0,
        description="Sales target achieved percentage (e.g. 102.5 for 102.5%)",
        examples=[105.0]
    )
    strike_rate_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Sales visit strike rate percentage (0-100%)",
        examples=[85.0]
    )
    coverage_execution_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Coverage route execution percentage (0-100%)",
        examples=[92.0]
    )
    route_discipline: RouteDiscipline = Field(
        default=RouteDiscipline.COMPLIANT,
        description="Route discipline compliance status",
        examples=["Compliant"]
    )
    mom_growth: MomGrowth = Field(
        default=MomGrowth.POSITIVE_GROWTH,
        description="Month-over-month performance growth trend",
        examples=["Positive Growth"]
    )
    in_store_merchandising_score: MerchandisingScore = Field(
        default=MerchandisingScore.GOOD,
        description="In-store merchandising audit score",
        examples=["Good"]
    )
    credit_health: CreditHealth = Field(
        default=CreditHealth.HEALTHY,
        description="Customer credit and payment compliance health",
        examples=["Healthy"]
    )

    @field_validator(
        "salesman_name",
        "supervisor",
        "province",
        "district",
        "commune",
        mode="before"
    )
    @classmethod
    def strip_and_validate_non_empty(cls, v: Any) -> str:
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("String field cannot be empty or only whitespace")
            return v_stripped
        return v

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="ignore"
    )


class SalesmanCreate(SalesmanBase):
    salesman_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique salesman identification code (e.g. W001406)",
        examples=["W001406"]
    )

    # Optional rule-derived fields on create; if not provided or provided,
    # the backend service layer will evaluate and populate these using the decision engine.
    achievement_status: Optional[AchievementStatus] = Field(
        None,
        description="Computed achievement status ('Achieved', 'On Track', 'Underperforming')"
    )
    performance_grade: Optional[PerformanceGrade] = Field(
        None,
        description="Computed performance tier ('Tier 1 (High)', 'Tier 2 (Medium)', 'Tier 3 (Low)')"
    )
    action_status: Optional[ActionStatus] = Field(
        None,
        description="Computed recommendation ('Top Incentive', 'Standard Bonus', 'Retraining', 'PIP Warning')"
    )

    @field_validator("salesman_id", mode="before")
    @classmethod
    def validate_salesman_id(cls, v: Any) -> str:
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("salesman_id cannot be blank")
            return v_stripped
        return v


class SalesmanUpdate(BaseModel):
    salesman_name: Optional[str] = Field(None, min_length=1, max_length=150)
    supervisor: Optional[str] = Field(None, min_length=1, max_length=150)
    province: Optional[str] = Field(None, min_length=1, max_length=100)
    district: Optional[str] = Field(None, min_length=1, max_length=100)
    commune: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[SalesmanStatus] = None
    target_achieved_pct: Optional[float] = Field(None, ge=0.0)
    strike_rate_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    coverage_execution_pct: Optional[float] = Field(None, ge=0.0, le=100.0)
    route_discipline: Optional[RouteDiscipline] = None
    mom_growth: Optional[MomGrowth] = None
    in_store_merchandising_score: Optional[MerchandisingScore] = None
    merchandising_score: Optional[MerchandisingScore] = None
    credit_health: Optional[CreditHealth] = None
    achievement_status: Optional[AchievementStatus] = None
    performance_grade: Optional[PerformanceGrade] = None
    action_status: Optional[ActionStatus] = None

    @model_validator(mode="after")
    def sync_merchandising_score(self) -> "SalesmanUpdate":
        if self.merchandising_score is not None and self.in_store_merchandising_score is None:
            self.in_store_merchandising_score = self.merchandising_score
        return self

    @field_validator(
        "salesman_name",
        "supervisor",
        "province",
        "district",
        "commune",
        mode="before"
    )
    @classmethod
    def strip_and_validate_non_empty(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("String field cannot be empty or only whitespace")
            return v_stripped
        return v

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="ignore"
    )


class SalesmanResponse(SalesmanBase):
    salesman_id: str = Field(..., description="Unique salesman identifier")
    achievement_status: AchievementStatus = Field(
        ...,
        description="Computed achievement status"
    )
    performance_grade: PerformanceGrade = Field(
        ...,
        description="Computed performance grade tier"
    )
    action_status: ActionStatus = Field(
        ...,
        description="Computed action recommendation status"
    )
    id: Optional[str] = Field(
        default=None,
        alias="_id",
        description="MongoDB ObjectId as hex string"
    )
    created_at: Optional[datetime] = Field(None, description="Creation timestamp (UTC)")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp (UTC)")

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


class SalesmanListResponse(BaseModel):
    total: int = Field(..., description="Total count of records matching filters")
    count: int = Field(..., description="Number of items in the current page")
    page: int = Field(1, description="Current page number (1-indexed)")
    limit: int = Field(100, description="Items per page limit")
    data: list[SalesmanResponse] = Field(..., description="List of salesman records")
