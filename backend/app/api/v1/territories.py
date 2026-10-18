from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database

router = APIRouter()


@router.get("/provinces", response_model=List[str])
async def get_provinces(
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> List[str]:
    """
    Returns distinct, sorted list of provinces derived from MongoDB 'salesmen' collection.
    """
    filter_query: Dict[str, Any] = {"province": {"$nin": [None, ""]}}
    raw_results = await db.salesmen.distinct("province", filter_query)
    cleaned = [p.strip() for p in raw_results if isinstance(p, str) and p.strip()]
    return sorted(list(set(cleaned)))


@router.get("/districts", response_model=List[str])
async def get_districts(
    province: Optional[str] = Query(None, description="Filter districts cascading by province"),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> List[str]:
    """
    Returns distinct, sorted list of districts derived from MongoDB 'salesmen' collection,
    cascading on province if supplied.
    """
    filter_query: Dict[str, Any] = {"district": {"$nin": [None, ""]}}
    if province and province.strip():
        filter_query["province"] = province.strip()

    raw_results = await db.salesmen.distinct("district", filter_query)
    cleaned = [d.strip() for d in raw_results if isinstance(d, str) and d.strip()]
    return sorted(list(set(cleaned)))


@router.get("/communes", response_model=List[str])
async def get_communes(
    district: Optional[str] = Query(None, description="Filter communes cascading by district"),
    province: Optional[str] = Query(None, description="Filter communes cascading by province"),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> List[str]:
    """
    Returns distinct, sorted list of communes derived from MongoDB 'salesmen' collection,
    cascading on district and/or province if supplied.
    """
    filter_query: Dict[str, Any] = {"commune": {"$nin": [None, ""]}}
    if district and district.strip():
        filter_query["district"] = district.strip()
    if province and province.strip():
        filter_query["province"] = province.strip()

    raw_results = await db.salesmen.distinct("commune", filter_query)
    cleaned = [c.strip() for c in raw_results if isinstance(c, str) and c.strip()]
    return sorted(list(set(cleaned)))
