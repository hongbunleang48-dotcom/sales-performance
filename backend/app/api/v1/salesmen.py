from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.models.salesman import (
    SalesmanCreate,
    SalesmanUpdate,
    SalesmanResponse,
    SalesmanStatus,
)
from app.services.salesman_service import SalesmanService

router = APIRouter()


@router.get("", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any])
async def list_salesmen(
    page: Optional[int] = Query(None, ge=1, description="Page number (1-indexed)"),
    skip: int = Query(0, ge=0, description="Record offset for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Items per page"),
    search: Optional[str] = Query(
        None,
        description="Multi-field search across salesman_name, supervisor, commune, and salesman_id"
    ),
    province: Optional[str] = Query(None, description="Faceted filter: Province"),
    district: Optional[str] = Query(None, description="Faceted filter: District"),
    commune: Optional[str] = Query(None, description="Faceted filter: Commune"),
    performance_grade: Optional[str] = Query(None, description="Faceted filter: Performance Grade (Tier 1/2/3)"),
    action_status: Optional[str] = Query(None, description="Faceted filter: Action Status"),
    status_filter: Optional[SalesmanStatus] = Query(
        None,
        alias="status",
        description="Faceted filter: Status ('Active' / 'Inactive')"
    ),
    min_target: Optional[float] = Query(None, ge=0.0, description="Range filter: Min Target Achieved %"),
    max_target: Optional[float] = Query(None, ge=0.0, description="Range filter: Max Target Achieved %"),
    min_strike: Optional[float] = Query(None, ge=0.0, le=100.0, description="Range filter: Min Strike Rate %"),
    max_strike: Optional[float] = Query(None, ge=0.0, le=100.0, description="Range filter: Max Strike Rate %"),
    sort_by: str = Query("salesman_id", description="Field to sort by"),
    sort_order: str = Query("asc", description="Sort order: 'asc' or 'desc'"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Paginated list of sales representatives with:
    - Multi-field search (salesman_name, supervisor, commune, salesman_id)
    - Faceted filters (province, district, commune, performance_grade, action_status, status)
    - Range filters (min_target, max_target, min_strike, max_strike)
    - Configurable sorting and pagination.
    """
    service = SalesmanService(db)
    filter_query: Dict[str, Any] = {}

    # Multi-field search
    if search and search.strip():
        term = search.strip()
        regex_pattern = {"$regex": term, "$options": "i"}
        filter_query["$or"] = [
            {"salesman_name": regex_pattern},
            {"supervisor": regex_pattern},
            {"commune": regex_pattern},
            {"salesman_id": regex_pattern},
            {"district": regex_pattern},
            {"province": regex_pattern},
        ]

    # Faceted filters
    if province:
        filter_query["province"] = province
    if district:
        filter_query["district"] = district
    if commune:
        filter_query["commune"] = commune
    if performance_grade:
        filter_query["performance_grade"] = performance_grade
    if action_status:
        filter_query["action_status"] = action_status
    if status_filter:
        filter_query["status"] = (
            status_filter.value if hasattr(status_filter, "value") else str(status_filter)
        )

    # Range filters for target achieved percentage
    if min_target is not None or max_target is not None:
        target_cond: Dict[str, float] = {}
        if min_target is not None:
            target_cond["$gte"] = min_target
        if max_target is not None:
            target_cond["$lte"] = max_target
        filter_query["target_achieved_pct"] = target_cond

    # Range filters for strike rate percentage
    if min_strike is not None or max_strike is not None:
        strike_cond: Dict[str, float] = {}
        if min_strike is not None:
            strike_cond["$gte"] = min_strike
        if max_strike is not None:
            strike_cond["$lte"] = max_strike
        filter_query["strike_rate_pct"] = strike_cond

    # Compute pagination offset
    effective_skip = skip
    if page is not None and skip == 0:
        effective_skip = (page - 1) * limit

    records, total = await service.get_all_salesmen(
        skip=effective_skip,
        limit=limit,
        query=filter_query,
        sort_by=sort_by,
        sort_order=sort_order
    )

    current_page = (effective_skip // limit) + 1 if limit > 0 else 1
    return {
        "total": total,
        "count": len(records),
        "page": current_page,
        "limit": limit,
        "data": records
    }


@router.post("", response_model=SalesmanResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SalesmanResponse, status_code=status.HTTP_201_CREATED)
async def create_salesman(
    salesman_in: SalesmanCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Onboard a new sales representative.
    Automatically evaluates their achievement status, tier, and action status via rules.py.
    """
    service = SalesmanService(db)
    try:
        created = await service.create_salesman(salesman_in)
        return created
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{salesman_id}", response_model=SalesmanResponse)
async def get_salesman(
    salesman_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a salesman by unique salesman_id."""
    service = SalesmanService(db)
    doc = await service.get_salesman_by_id(salesman_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salesman '{salesman_id}' not found."
        )
    return doc


@router.patch("/{salesman_id}", response_model=SalesmanResponse)
@router.put("/{salesman_id}", response_model=SalesmanResponse)
async def update_salesman(
    salesman_id: str,
    salesman_in: SalesmanUpdate,
    actor: str = Query("system", description="Identifier of user or service making the change"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Support inline updates for route_discipline, merchandising_score,
    target_achieved_pct, strike_rate_pct, credit_health, etc.
    Re-evaluates action_status / tier and records the modification in the 'audit_logs' collection.
    """
    service = SalesmanService(db)
    updated = await service.update_salesman(salesman_id, salesman_in, actor=actor)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salesman '{salesman_id}' not found."
        )
    return updated


@router.delete("/{salesman_id}", response_model=SalesmanResponse)
async def delete_salesman(
    salesman_id: str,
    actor: str = Query("system", description="Identifier of user or service initiating soft deletion"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Soft deletion endpoint: toggles status between 'Active' and 'Inactive',
    records the change in 'audit_logs', and returns the updated document.
    """
    service = SalesmanService(db)
    updated = await service.toggle_salesman_status(salesman_id, actor=actor)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Salesman '{salesman_id}' not found."
        )
    return updated


@router.get("/{salesman_id}/audit-logs", response_model=List[Dict[str, Any]])
async def get_salesman_audit_logs(
    salesman_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Retrieve audit history for a specific salesman."""
    service = SalesmanService(db)
    return await service.get_audit_logs(salesman_id=salesman_id, limit=limit)


@router.post("/bulk", response_model=Dict[str, int])
async def bulk_upsert_salesmen(
    salesmen_list: List[SalesmanCreate],
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Bulk upsert salesmen with rules evaluation."""
    service = SalesmanService(db)
    return await service.bulk_upsert_salesmen(salesmen_list)
