from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/overview", response_model=Dict[str, Any])
@router.get("/executive-summary", response_model=Dict[str, Any])
async def get_executive_overview(
    province: Optional[str] = Query(None, description="Filter by territory province"),
    district: Optional[str] = Query(None, description="Filter by territory district"),
    commune: Optional[str] = Query(None, description="Filter by territory commune"),
    supervisor: Optional[str] = Query(None, description="Filter by supervisor"),
    status: Optional[str] = Query(None, description="Filter by status (Active/Inactive)"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """
    Executive Overview Pipeline:
    - Average target realization %
    - Average strike rate %
    - Coverage saturation % (ratio of Compliant reps)
    - Field Risk Count (count of reps on PIP Warning or Overdue Notice)
    """
    service = AnalyticsService(db)
    return await service.get_executive_overview(
        province=province,
        district=district,
        commune=commune,
        supervisor=supervisor,
        status=status,
    )


@router.get("/scatter", response_model=List[Dict[str, Any]])
@router.get("/route-fidelity", response_model=List[Dict[str, Any]])
async def get_route_fidelity_scatter(
    province: Optional[str] = Query(None, description="Filter by territory province"),
    district: Optional[str] = Query(None, description="Filter by territory district"),
    commune: Optional[str] = Query(None, description="Filter by territory commune"),
    supervisor: Optional[str] = Query(None, description="Filter by supervisor"),
    status: Optional[str] = Query(None, description="Filter by status (Active/Inactive)"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[Dict[str, Any]]:
    """
    Route Fidelity Scatter Pipeline:
    Rep-level array containing salesman_id, salesman_name, coverage_execution_pct,
    strike_rate_pct, and quadrant classification (X=90%, Y=85% thresholds).
    """
    service = AnalyticsService(db)
    return await service.get_route_fidelity_scatter(
        province=province,
        district=district,
        commune=commune,
        supervisor=supervisor,
        status=status,
    )


@router.get("/supervisors", response_model=List[Dict[str, Any]])
@router.get("/supervisor-leaderboard", response_model=List[Dict[str, Any]])
async def get_supervisor_leaderboard(
    province: Optional[str] = Query(None, description="Filter by territory province"),
    status: Optional[str] = Query(None, description="Filter by status (Active/Inactive)"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> List[Dict[str, Any]]:
    """
    Supervisor Leaderboard Pipeline:
    Ranking of supervisors grouped by count and proportion of Tier 1 reps under their management.
    """
    service = AnalyticsService(db)
    return await service.get_supervisor_leaderboard(
        province=province,
        status=status,
    )


@router.get("/tier-distribution", response_model=Dict[str, Any])
@router.get("/tiers", response_model=Dict[str, Any])
async def get_tier_distribution(
    province: Optional[str] = Query(None, description="Filter by territory province"),
    district: Optional[str] = Query(None, description="Filter by territory district"),
    supervisor: Optional[str] = Query(None, description="Filter by supervisor"),
    status: Optional[str] = Query(None, description="Filter by status (Active/Inactive)"),
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> Dict[str, Any]:
    """
    Tier Distribution Pipeline:
    Count of reps in Tier 1 (High), Tier 2 (Medium), Tier 3 (Low) with percentages and UI colors.
    """
    service = AnalyticsService(db)
    return await service.get_tier_distribution(
        province=province,
        district=district,
        supervisor=supervisor,
        status=status,
    )
