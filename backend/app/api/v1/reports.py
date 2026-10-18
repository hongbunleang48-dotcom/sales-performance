from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.database import get_database
from app.services.export_service import ExportService

router = APIRouter()


@router.get("/export/csv")
@router.get("/csv")
async def export_salesmen_csv(
    province: Optional[str] = Query(None, description="Filter export by province"),
    district: Optional[str] = Query(None, description="Filter export by district"),
    commune: Optional[str] = Query(None, description="Filter export by commune"),
    supervisor: Optional[str] = Query(None, description="Filter export by supervisor"),
    performance_grade: Optional[str] = Query(None, description="Filter export by tier"),
    action_status: Optional[str] = Query(None, description="Filter export by action recommendation"),
    status: Optional[str] = Query(None, description="Filter export by active/inactive status"),
    search: Optional[str] = Query(None, description="Search term for names or codes"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """
    Exports filtered sales representative roster as a standardized CSV file.
    Returns text/csv with attachment Content-Disposition header.
    """
    filter_query: Dict[str, Any] = {}

    if search and search.strip():
        term = search.strip()
        filter_query["$or"] = [
            {"salesman_name": {"$regex": term, "$options": "i"}},
            {"supervisor": {"$regex": term, "$options": "i"}},
            {"commune": {"$regex": term, "$options": "i"}},
            {"salesman_id": {"$regex": term, "$options": "i"}},
        ]

    if province:
        filter_query["province"] = province
    if district:
        filter_query["district"] = district
    if commune:
        filter_query["commune"] = commune
    if supervisor:
        filter_query["supervisor"] = supervisor
    if performance_grade:
        filter_query["performance_grade"] = performance_grade
    if action_status:
        filter_query["action_status"] = action_status
    if status:
        filter_query["status"] = status

    csv_content, filename, total_records = await ExportService.export_salesmen_from_db(
        db=db,
        filter_query=filter_query,
        sort_by="salesman_id",
        sort_order=1,
    )

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Total-Count": str(total_records),
    }

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers=headers,
    )
