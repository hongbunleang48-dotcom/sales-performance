from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple, Union
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.rules import evaluate_salesman_performance, CreditHealth
from app.models.salesman import (
    SalesmanCreate,
    SalesmanUpdate,
    SalesmanResponse,
)


def _format_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Helper to convert MongoDB ObjectId to string for JSON/Pydantic serialization."""
    if not doc:
        return None
    d = dict(doc)
    if "_id" in d and d["_id"] is not None:
        d["_id"] = str(d["_id"])
    return d


class SalesmanService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["salesmen"]
        self.audit_collection = db["audit_logs"]

    async def record_audit_log(
        self,
        salesman_id: str,
        changes: Dict[str, Dict[str, Any]],
        previous_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        action: str = "UPDATE",
        actor: str = "system"
    ) -> Dict[str, Any]:
        """
        Records an entry in MongoDB 'audit_logs' collection.
        """
        log_entry = {
            "salesman_id": salesman_id,
            "action": action,
            "changes": changes,
            "previous_values": previous_values or {},
            "new_values": new_values or {},
            "actor": actor,
            "timestamp": datetime.now(timezone.utc),
        }
        res = await self.audit_collection.insert_one(log_entry)
        log_entry["_id"] = str(res.inserted_id)
        return log_entry

    async def create_salesman(self, salesman_in: SalesmanCreate) -> Dict[str, Any]:
        """
        Creates a new salesman document.
        Calls the decision engine rules to compute achievement_status,
        performance_grade, and action_status before persisting into MongoDB.
        """
        # Validate that salesman_id is unique
        existing = await self.collection.find_one({"salesman_id": salesman_in.salesman_id})
        if existing:
            raise ValueError(f"Salesman with ID '{salesman_in.salesman_id}' already exists.")

        # Prepare document dictionary
        data = salesman_in.model_dump(exclude_unset=False)

        # Call decision engine rules
        rules = evaluate_salesman_performance(
            target_achieved_pct=data["target_achieved_pct"],
            credit_health=data["credit_health"]
        )

        # Enforce computed business fields from the decision engine
        data["achievement_status"] = rules["achievement_status"]
        data["performance_grade"] = rules["performance_grade"]
        data["action_status"] = rules["action_status"]

        # Timestamping
        now = datetime.now(timezone.utc)
        data["created_at"] = now
        data["updated_at"] = now

        # Persist into MongoDB
        result = await self.collection.insert_one(data)
        data["_id"] = str(result.inserted_id)
        return data

    async def update_salesman(
        self,
        salesman_id: str,
        salesman_in: SalesmanUpdate,
        actor: str = "system"
    ) -> Optional[Dict[str, Any]]:
        """
        Updates an existing salesman document.
        Evaluates the decision engine rules before saving changes, ensuring
        achievement_status, performance_grade, and action_status are consistently synchronized.
        Records any changed fields in the 'audit_logs' collection.
        """
        existing = await self.collection.find_one({"salesman_id": salesman_id})
        if not existing:
            return None

        update_dict = salesman_in.model_dump(exclude_unset=True)
        if not update_dict:
            return _format_doc(existing)

        # Determine target achievement and credit health for decision rules
        target = update_dict.get("target_achieved_pct")
        if target is None:
            target = existing.get("target_achieved_pct", 0.0)

        credit = update_dict.get("credit_health")
        if credit is None:
            credit = existing.get("credit_health", CreditHealth.HEALTHY.value)

        # Re-evaluate business rules
        rules = evaluate_salesman_performance(
            target_achieved_pct=target,
            credit_health=credit
        )

        # Update computed fields and timestamp
        update_dict["achievement_status"] = rules["achievement_status"]
        update_dict["performance_grade"] = rules["performance_grade"]
        update_dict["action_status"] = rules["action_status"]
        now = datetime.now(timezone.utc)
        update_dict["updated_at"] = now

        # Calculate delta for audit log
        changes: Dict[str, Dict[str, Any]] = {}
        previous_values: Dict[str, Any] = {}
        new_values: Dict[str, Any] = {}

        for key, new_val in update_dict.items():
            if key == "updated_at":
                continue
            old_val = existing.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
                previous_values[key] = old_val
                new_values[key] = new_val

        # Persist update
        updated_doc = await self.collection.find_one_and_update(
            {"salesman_id": salesman_id},
            {"$set": update_dict},
            return_document=ReturnDocument.AFTER
        )

        # Write to audit_logs if any fields changed
        if changes:
            await self.record_audit_log(
                salesman_id=salesman_id,
                changes=changes,
                previous_values=previous_values,
                new_values=new_values,
                action="UPDATE",
                actor=actor
            )

        return _format_doc(updated_doc)

    async def toggle_salesman_status(
        self, salesman_id: str, actor: str = "system"
    ) -> Optional[Dict[str, Any]]:
        """
        Soft deletion logic: toggles salesman status between 'Active' and 'Inactive',
        records the status change in 'audit_logs', and returns the updated document.
        """
        existing = await self.collection.find_one({"salesman_id": salesman_id})
        if not existing:
            return None

        current_status = existing.get("status", "Active")
        new_status = "Inactive" if current_status == "Active" else "Active"
        now = datetime.now(timezone.utc)

        updated_doc = await self.collection.find_one_and_update(
            {"salesman_id": salesman_id},
            {"$set": {"status": new_status, "updated_at": now}},
            return_document=ReturnDocument.AFTER
        )

        # Record audit log
        changes = {"status": {"old": current_status, "new": new_status}}
        await self.record_audit_log(
            salesman_id=salesman_id,
            changes=changes,
            previous_values={"status": current_status},
            new_values={"status": new_status},
            action="STATUS_TOGGLE",
            actor=actor
        )

        return _format_doc(updated_doc)

    async def get_salesman_by_id(self, salesman_id: str) -> Optional[Dict[str, Any]]:
        """Finds a single salesman by salesman_id."""
        doc = await self.collection.find_one({"salesman_id": salesman_id})
        return _format_doc(doc)

    async def get_all_salesmen(
        self,
        skip: int = 0,
        limit: int = 100,
        query: Optional[Dict[str, Any]] = None,
        sort_by: str = "salesman_id",
        sort_order: Union[int, str] = 1
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieves a paginated list of salesmen matching the query criteria, along with total count.
        """
        filter_query = query or {}
        total = await self.collection.count_documents(filter_query)

        # Normalize sort order
        if isinstance(sort_order, str):
            direction = -1 if sort_order.lower() in ("desc", "-1") else 1
        else:
            direction = -1 if sort_order == -1 else 1

        cursor = self.collection.find(filter_query).sort(sort_by, direction).skip(skip).limit(limit)

        records = []
        async for doc in cursor:
            records.append(_format_doc(doc))

        return records, total

    async def delete_salesman(self, salesman_id: str) -> bool:
        """Deletes a salesman document by salesman_id."""
        result = await self.collection.delete_one({"salesman_id": salesman_id})
        return result.deleted_count > 0

    async def bulk_upsert_salesmen(
        self, salesmen_list: List[SalesmanCreate]
    ) -> Dict[str, int]:
        """
        Bulk upserts salesman documents, evaluating the decision engine rules
        for each salesman before persisting.
        """
        inserted_count = 0
        updated_count = 0

        for sm in salesmen_list:
            data = sm.model_dump(exclude_unset=False)
            rules = evaluate_salesman_performance(
                target_achieved_pct=data["target_achieved_pct"],
                credit_health=data["credit_health"]
            )
            data["achievement_status"] = rules["achievement_status"]
            data["performance_grade"] = rules["performance_grade"]
            data["action_status"] = rules["action_status"]

            now = datetime.now(timezone.utc)
            data["updated_at"] = now

            res = await self.collection.update_one(
                {"salesman_id": sm.salesman_id},
                {
                    "$set": data,
                    "$setOnInsert": {"created_at": now}
                },
                upsert=True
            )
            if res.upserted_id:
                inserted_count += 1
            elif res.modified_count > 0:
                updated_count += 1

        return {"inserted": inserted_count, "updated": updated_count}

    async def get_audit_logs(
        self, salesman_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieves audit log entries, optionally filtered by salesman_id."""
        query = {"salesman_id": salesman_id} if salesman_id else {}
        cursor = self.audit_collection.find(query).sort("timestamp", -1).limit(limit)
        logs = []
        async for doc in cursor:
            logs.append(_format_doc(doc))
        return logs


# Functional helpers for module-level usage
async def create_salesman(db: AsyncIOMotorDatabase, salesman_in: SalesmanCreate) -> Dict[str, Any]:
    service = SalesmanService(db)
    return await service.create_salesman(salesman_in)


async def update_salesman(
    db: AsyncIOMotorDatabase, salesman_id: str, salesman_in: SalesmanUpdate, actor: str = "system"
) -> Optional[Dict[str, Any]]:
    service = SalesmanService(db)
    return await service.update_salesman(salesman_id, salesman_in, actor=actor)


async def toggle_salesman_status(
    db: AsyncIOMotorDatabase, salesman_id: str, actor: str = "system"
) -> Optional[Dict[str, Any]]:
    service = SalesmanService(db)
    return await service.toggle_salesman_status(salesman_id, actor=actor)


async def get_salesman_by_id(db: AsyncIOMotorDatabase, salesman_id: str) -> Optional[Dict[str, Any]]:
    service = SalesmanService(db)
    return await service.get_salesman_by_id(salesman_id)


async def get_all_salesmen(
    db: AsyncIOMotorDatabase,
    skip: int = 0,
    limit: int = 100,
    query: Optional[Dict[str, Any]] = None,
    sort_by: str = "salesman_id",
    sort_order: Union[int, str] = 1
) -> Tuple[List[Dict[str, Any]], int]:
    service = SalesmanService(db)
    return await service.get_all_salesmen(skip=skip, limit=limit, query=query, sort_by=sort_by, sort_order=sort_order)


async def delete_salesman(db: AsyncIOMotorDatabase, salesman_id: str) -> bool:
    service = SalesmanService(db)
    return await service.delete_salesman(salesman_id)


async def bulk_upsert_salesmen(
    db: AsyncIOMotorDatabase, salesmen_list: List[SalesmanCreate]
) -> Dict[str, int]:
    service = SalesmanService(db)
    return await service.bulk_upsert_salesmen(salesmen_list)
