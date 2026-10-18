import asyncio
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_database
from app.core.rules import (
    evaluate_salesman_performance,
    calculate_achievement_and_tier,
    calculate_action_status,
    AchievementStatus,
    PerformanceGrade,
    ActionStatus,
    CreditHealth,
)
from app.models.salesman import (
    SalesmanCreate,
    SalesmanUpdate,
    SalesmanResponse,
    SalesmanStatus,
    RouteDiscipline,
    MomGrowth,
    MerchandisingScore,
)
from app.models.audit import AuditLog
from app.services.salesman_service import SalesmanService


# ============================================================================
# 1. Decision Engine Unit Tests
# ============================================================================

class TestDecisionEngine:
    def test_tier_and_achievement_logic(self):
        # Target >= 100% -> Achieved, Tier 1 (High)
        ach, tier = calculate_achievement_and_tier(100.0)
        assert ach == AchievementStatus.ACHIEVED
        assert tier == PerformanceGrade.TIER_1

        ach, tier = calculate_achievement_and_tier(125.5)
        assert ach == AchievementStatus.ACHIEVED
        assert tier == PerformanceGrade.TIER_1

        # 85% <= Target < 100% -> On Track, Tier 2 (Medium)
        ach, tier = calculate_achievement_and_tier(99.9)
        assert ach == AchievementStatus.ON_TRACK
        assert tier == PerformanceGrade.TIER_2

        ach, tier = calculate_achievement_and_tier(85.0)
        assert ach == AchievementStatus.ON_TRACK
        assert tier == PerformanceGrade.TIER_2

        # Target < 85% -> Underperforming, Tier 3 (Low)
        ach, tier = calculate_achievement_and_tier(84.9)
        assert ach == AchievementStatus.UNDERPERFORMING
        assert tier == PerformanceGrade.TIER_3

        ach, tier = calculate_achievement_and_tier(0.0)
        assert ach == AchievementStatus.UNDERPERFORMING
        assert tier == PerformanceGrade.TIER_3

    def test_action_status_logic(self):
        # PIP Warning if credit_health == "Overdue Notice" (even with high target)
        assert calculate_action_status(110.0, "Overdue Notice") == ActionStatus.PIP_WARNING
        assert calculate_action_status(95.0, "Overdue Notice") == ActionStatus.PIP_WARNING
        assert calculate_action_status(80.0, "Overdue Notice") == ActionStatus.PIP_WARNING

        # PIP Warning if target < 85% (even with healthy credit)
        assert calculate_action_status(84.9, "Healthy") == ActionStatus.PIP_WARNING
        assert calculate_action_status(50.0, CreditHealth.HEALTHY) == ActionStatus.PIP_WARNING

        # Top Incentive if target >= 100% and credit_health == "Healthy"
        assert calculate_action_status(100.0, "Healthy") == ActionStatus.TOP_INCENTIVE
        assert calculate_action_status(150.0, CreditHealth.HEALTHY) == ActionStatus.TOP_INCENTIVE

        # Standard Bonus if target >= 90% and credit_health == "Healthy" (and < 100%)
        assert calculate_action_status(90.0, "Healthy") == ActionStatus.STANDARD_BONUS
        assert calculate_action_status(99.9, CreditHealth.HEALTHY) == ActionStatus.STANDARD_BONUS

        # Otherwise Retraining (85% <= target < 90% and credit_health == "Healthy")
        assert calculate_action_status(85.0, "Healthy") == ActionStatus.RETRAINING
        assert calculate_action_status(89.9, CreditHealth.HEALTHY) == ActionStatus.RETRAINING

    def test_complete_decision_engine_function(self):
        res1 = evaluate_salesman_performance(105.0, "Healthy")
        assert res1 == {
            "achievement_status": "Achieved",
            "performance_grade": "Tier 1 (High)",
            "action_status": "Top Incentive",
        }

        res2 = evaluate_salesman_performance(92.0, "Healthy")
        assert res2 == {
            "achievement_status": "On Track",
            "performance_grade": "Tier 2 (Medium)",
            "action_status": "Standard Bonus",
        }

        res3 = evaluate_salesman_performance(87.0, "Healthy")
        assert res3 == {
            "achievement_status": "On Track",
            "performance_grade": "Tier 2 (Medium)",
            "action_status": "Retraining",
        }

        res4 = evaluate_salesman_performance(80.0, "Healthy")
        assert res4 == {
            "achievement_status": "Underperforming",
            "performance_grade": "Tier 3 (Low)",
            "action_status": "PIP Warning",
        }

        res5 = evaluate_salesman_performance(115.0, "Overdue Notice")
        assert res5 == {
            "achievement_status": "Achieved",
            "performance_grade": "Tier 1 (High)",
            "action_status": "PIP Warning",
        }


# ============================================================================
# 2. Pydantic v2 Schema Tests
# ============================================================================

class TestSalesmanSchemas:
    def test_valid_salesman_create(self):
        data = {
            "salesman_id": "W001406",
            "salesman_name": "  Sophal Chea  ",
            "supervisor": "Keo Piseth",
            "province": "Phnom Penh",
            "district": "Pur SenChey",
            "commune": "Kakab 1",
            "status": "Active",
            "target_achieved_pct": 105.0,
            "strike_rate_pct": 82.5,
            "coverage_execution_pct": 94.0,
            "route_discipline": "Compliant",
            "mom_growth": "Positive Growth",
            "in_store_merchandising_score": "Good",
            "credit_health": "Healthy",
        }
        sm = SalesmanCreate(**data)
        assert sm.salesman_id == "W001406"
        assert sm.salesman_name == "Sophal Chea"  # Stripped whitespace
        assert sm.target_achieved_pct == 105.0
        assert sm.status == SalesmanStatus.ACTIVE

    def test_field_validations(self):
        base_data = {
            "salesman_id": "W001406",
            "salesman_name": "Sophal Chea",
            "supervisor": "Keo Piseth",
            "province": "Phnom Penh",
            "district": "Pur SenChey",
            "commune": "Kakab 1",
            "target_achieved_pct": 100.0,
            "strike_rate_pct": 80.0,
            "coverage_execution_pct": 90.0,
        }

        # Empty or whitespace-only salesman_id
        with pytest.raises(ValidationError):
            SalesmanCreate(**{**base_data, "salesman_id": "   "})

        # Negative target
        with pytest.raises(ValidationError):
            SalesmanCreate(**{**base_data, "target_achieved_pct": -10.0})

        # Strike rate > 100
        with pytest.raises(ValidationError):
            SalesmanCreate(**{**base_data, "strike_rate_pct": 105.0})

        # Coverage execution < 0
        with pytest.raises(ValidationError):
            SalesmanCreate(**{**base_data, "coverage_execution_pct": -1.0})

        # Blank string for required fields
        with pytest.raises(ValidationError):
            SalesmanCreate(**{**base_data, "province": "   "})

    def test_salesman_response_serialization(self):
        mongo_oid = ObjectId()
        doc = {
            "_id": mongo_oid,
            "salesman_id": "W001406",
            "salesman_name": "Sophal Chea",
            "supervisor": "Keo Piseth",
            "province": "Phnom Penh",
            "district": "Pur SenChey",
            "commune": "Kakab 1",
            "status": "Active",
            "target_achieved_pct": 105.0,
            "strike_rate_pct": 85.0,
            "coverage_execution_pct": 92.0,
            "route_discipline": "Compliant",
            "mom_growth": "Positive Growth",
            "in_store_merchandising_score": "Good",
            "credit_health": "Healthy",
            "achievement_status": "Achieved",
            "performance_grade": "Tier 1 (High)",
            "action_status": "Top Incentive",
        }
        resp = SalesmanResponse(**doc)
        dumped = resp.model_dump(by_alias=True)
        assert dumped["_id"] == str(mongo_oid)
        assert dumped["achievement_status"] == "Achieved"
        assert dumped["action_status"] == "Top Incentive"

    def test_salesman_update_schema(self):
        up = SalesmanUpdate(
            target_achieved_pct=110.0,
            credit_health=CreditHealth.HEALTHY,
            merchandising_score=MerchandisingScore.EXCELLENT
        )
        d = up.model_dump(exclude_unset=True)
        assert d["target_achieved_pct"] == 110.0
        assert d["credit_health"] == "Healthy"
        assert d["in_store_merchandising_score"] == "Excellent"


# ============================================================================
# 3. Salesman Service Layer Tests (Motor Async Mocks)
# ============================================================================

class TestSalesmanService:
    def test_create_salesman_calls_rules_engine(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_audit = MagicMock()
            mock_db.__getitem__.side_effect = lambda k: mock_audit if k == "audit_logs" else mock_collection

            # No duplicate
            mock_collection.find_one = AsyncMock(return_value=None)
            inserted_id = ObjectId()
            mock_collection.insert_one = AsyncMock(
                return_value=MagicMock(inserted_id=inserted_id)
            )

            service = SalesmanService(mock_db)
            sm_in = SalesmanCreate(
                salesman_id="W001406",
                salesman_name="Sophal Chea",
                supervisor="Keo Piseth",
                province="Phnom Penh",
                district="Pur SenChey",
                commune="Kakab 1",
                target_achieved_pct=105.0,
                strike_rate_pct=85.0,
                coverage_execution_pct=90.0,
                credit_health=CreditHealth.HEALTHY,
            )

            result = await service.create_salesman(sm_in)

            # Verify decision engine output was applied
            assert result["achievement_status"] == "Achieved"
            assert result["performance_grade"] == "Tier 1 (High)"
            assert result["action_status"] == "Top Incentive"
            assert result["_id"] == str(inserted_id)
            assert "created_at" in result
            assert "updated_at" in result
            mock_collection.insert_one.assert_called_once()

        asyncio.run(run())

    def test_create_salesman_duplicate_raises_error(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection

            # Duplicate exists
            mock_collection.find_one = AsyncMock(return_value={"salesman_id": "W001406"})

            service = SalesmanService(mock_db)
            sm_in = SalesmanCreate(
                salesman_id="W001406",
                salesman_name="Sophal Chea",
                supervisor="Keo Piseth",
                province="Phnom Penh",
                district="Pur SenChey",
                commune="Kakab 1",
                target_achieved_pct=105.0,
                strike_rate_pct=85.0,
                coverage_execution_pct=90.0,
            )

            with pytest.raises(ValueError) as exc:
                await service.create_salesman(sm_in)
            assert "already exists" in str(exc.value)

        asyncio.run(run())

    def test_update_salesman_recomputes_rules_and_audits(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_audit = MagicMock()
            mock_db.__getitem__.side_effect = lambda k: mock_audit if k == "audit_logs" else mock_collection

            existing_doc = {
                "_id": ObjectId(),
                "salesman_id": "W001406",
                "target_achieved_pct": 105.0,
                "credit_health": "Healthy",
                "achievement_status": "Achieved",
                "performance_grade": "Tier 1 (High)",
                "action_status": "Top Incentive",
            }
            mock_collection.find_one = AsyncMock(return_value=existing_doc)
            mock_audit.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

            def side_effect(filter_dict, update_dict, return_document):
                updated = dict(existing_doc)
                updated.update(update_dict["$set"])
                return updated

            mock_collection.find_one_and_update = AsyncMock(side_effect=side_effect)

            service = SalesmanService(mock_db)
            # Update target to 80% (which should trigger PIP Warning and Underperforming)
            update_in = SalesmanUpdate(target_achieved_pct=80.0)
            res = await service.update_salesman("W001406", update_in, actor="test_user")

            assert res["achievement_status"] == "Underperforming"
            assert res["performance_grade"] == "Tier 3 (Low)"
            assert res["action_status"] == "PIP Warning"
            assert res["target_achieved_pct"] == 80.0

            # Verify audit log was recorded
            mock_audit.insert_one.assert_called_once()
            audit_call_args = mock_audit.insert_one.call_args[0][0]
            assert audit_call_args["salesman_id"] == "W001406"
            assert audit_call_args["action"] == "UPDATE"
            assert audit_call_args["actor"] == "test_user"
            assert "target_achieved_pct" in audit_call_args["changes"]
            assert audit_call_args["changes"]["target_achieved_pct"] == {"old": 105.0, "new": 80.0}

        asyncio.run(run())

    def test_toggle_salesman_status_soft_deletion(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_audit = MagicMock()
            mock_db.__getitem__.side_effect = lambda k: mock_audit if k == "audit_logs" else mock_collection

            existing_doc = {
                "_id": ObjectId(),
                "salesman_id": "W001406",
                "status": "Active",
            }
            mock_collection.find_one = AsyncMock(return_value=existing_doc)
            mock_audit.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

            def side_effect(filter_dict, update_dict, return_document):
                updated = dict(existing_doc)
                updated.update(update_dict["$set"])
                return updated

            mock_collection.find_one_and_update = AsyncMock(side_effect=side_effect)

            service = SalesmanService(mock_db)
            # Toggle Active -> Inactive
            res = await service.toggle_salesman_status("W001406", actor="admin")
            assert res["status"] == "Inactive"
            mock_audit.insert_one.assert_called_once()
            audit_call = mock_audit.insert_one.call_args[0][0]
            assert audit_call["changes"]["status"] == {"old": "Active", "new": "Inactive"}

            # Toggle Inactive -> Active
            existing_doc["status"] = "Inactive"
            mock_collection.find_one = AsyncMock(return_value=existing_doc)
            res2 = await service.toggle_salesman_status("W001406", actor="admin")
            assert res2["status"] == "Active"

        asyncio.run(run())

    def test_bulk_upsert_salesmen_evaluates_rules(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection

            mock_collection.update_one = AsyncMock(
                return_value=MagicMock(upserted_id=ObjectId(), modified_count=0)
            )

            service = SalesmanService(mock_db)
            sm_list = [
                SalesmanCreate(
                    salesman_id="W001401",
                    salesman_name="Salesman 1",
                    supervisor="Supervisor",
                    province="Phnom Penh",
                    district="Pur SenChey",
                    commune="Kakab 1",
                    target_achieved_pct=92.0,
                    strike_rate_pct=80.0,
                    coverage_execution_pct=90.0,
                    credit_health=CreditHealth.HEALTHY,
                ),
                SalesmanCreate(
                    salesman_id="W001402",
                    salesman_name="Salesman 2",
                    supervisor="Supervisor",
                    province="Phnom Penh",
                    district="Pur SenChey",
                    commune="Kakab 1",
                    target_achieved_pct=75.0,
                    strike_rate_pct=60.0,
                    coverage_execution_pct=70.0,
                    credit_health=CreditHealth.OVERDUE_NOTICE,
                ),
            ]

            result = await service.bulk_upsert_salesmen(sm_list)
            assert result["inserted"] == 2
            assert mock_collection.update_one.call_count == 2

            call_args_list = mock_collection.update_one.call_args_list
            first_call_set = call_args_list[0][0][1]["$set"]
            assert first_call_set["achievement_status"] == "On Track"
            assert first_call_set["performance_grade"] == "Tier 2 (Medium)"
            assert first_call_set["action_status"] == "Standard Bonus"

            second_call_set = call_args_list[1][0][1]["$set"]
            assert second_call_set["achievement_status"] == "Underperforming"
            assert second_call_set["performance_grade"] == "Tier 3 (Low)"
            assert second_call_set["action_status"] == "PIP Warning"

        asyncio.run(run())


# ============================================================================
# 4. FastAPI Endpoints Integration Tests
# ============================================================================

class TestSalesmenAndTerritoriesAPI:
    def test_post_salesman_api(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_audit = MagicMock()
        mock_db.__getitem__.side_effect = lambda k: mock_audit if k == "audit_logs" else mock_collection

        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId("507f1f77bcf86cd799439011"))
        )

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        payload = {
            "salesman_id": "W001406",
            "salesman_name": "Sophal Chea",
            "supervisor": "Keo Piseth",
            "province": "Phnom Penh",
            "district": "Pur SenChey",
            "commune": "Kakab 1",
            "status": "Active",
            "target_achieved_pct": 105.0,
            "strike_rate_pct": 82.5,
            "coverage_execution_pct": 94.0,
            "route_discipline": "Compliant",
            "mom_growth": "Positive Growth",
            "in_store_merchandising_score": "Good",
            "credit_health": "Healthy",
        }
        res = client.post("/api/v1/salesmen", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["salesman_id"] == "W001406"
        assert data["achievement_status"] == "Achieved"
        assert data["performance_grade"] == "Tier 1 (High)"
        assert data["action_status"] == "Top Incentive"

        app.dependency_overrides.clear()

    def test_get_salesmen_with_search_and_filters_api(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        mock_collection.count_documents = AsyncMock(return_value=1)
        mock_cursor = MagicMock()

        sample_record = {
            "_id": ObjectId(),
            "salesman_id": "W001406",
            "salesman_name": "Sophal Chea",
            "supervisor": "Keo Piseth",
            "province": "Phnom Penh",
            "district": "Pur SenChey",
            "commune": "Kakab 1",
            "status": "Active",
            "target_achieved_pct": 105.0,
            "strike_rate_pct": 85.0,
            "coverage_execution_pct": 92.0,
            "route_discipline": "Compliant",
            "mom_growth": "Positive Growth",
            "in_store_merchandising_score": "Good",
            "credit_health": "Healthy",
            "achievement_status": "Achieved",
            "performance_grade": "Tier 1 (High)",
            "action_status": "Top Incentive",
        }

        async def async_iter(self):
            yield sample_record

        mock_cursor.__aiter__ = async_iter
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_collection.find.return_value = mock_cursor

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        # Call with search, faceted filters, range filters, and sort
        res = client.get(
            "/api/v1/salesmen?search=Sophal&province=Phnom Penh&min_target=90&max_target=120&min_strike=80&max_strike=100&sort_by=target_achieved_pct&sort_order=desc"
        )
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["count"] == 1
        assert len(body["data"]) == 1
        assert body["data"][0]["salesman_id"] == "W001406"

        # Verify query criteria passed to find()
        find_call_query = mock_collection.find.call_args[0][0]
        assert "$or" in find_call_query
        assert find_call_query["province"] == "Phnom Penh"
        assert find_call_query["target_achieved_pct"] == {"$gte": 90.0, "$lte": 120.0}
        assert find_call_query["strike_rate_pct"] == {"$gte": 80.0, "$lte": 100.0}

        app.dependency_overrides.clear()

    def test_patch_salesman_inline_update_api(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_audit = MagicMock()
        mock_db.__getitem__.side_effect = lambda k: mock_audit if k == "audit_logs" else mock_collection

        existing_doc = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "salesman_id": "W001406",
            "salesman_name": "Sophal Chea",
            "supervisor": "Keo Piseth",
            "province": "Phnom Penh",
            "district": "Pur SenChey",
            "commune": "Kakab 1",
            "status": "Active",
            "target_achieved_pct": 105.0,
            "strike_rate_pct": 85.0,
            "coverage_execution_pct": 92.0,
            "route_discipline": "Compliant",
            "mom_growth": "Positive Growth",
            "in_store_merchandising_score": "Good",
            "credit_health": "Healthy",
            "achievement_status": "Achieved",
            "performance_grade": "Tier 1 (High)",
            "action_status": "Top Incentive",
        }
        mock_collection.find_one = AsyncMock(return_value=existing_doc)
        mock_audit.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

        def side_effect(filter_dict, update_dict, return_document):
            updated = dict(existing_doc)
            updated.update(update_dict["$set"])
            return updated

        mock_collection.find_one_and_update = AsyncMock(side_effect=side_effect)

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        patch_payload = {
            "route_discipline": "Route Diverted",
            "merchandising_score": "Fair",
            "target_achieved_pct": 82.0,
            "credit_health": "Overdue Notice",
        }

        res = client.patch("/api/v1/salesmen/W001406?actor=supervisor_sam", json=patch_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["salesman_id"] == "W001406"
        assert data["route_discipline"] == "Route Diverted"
        assert data["in_store_merchandising_score"] == "Fair"
        assert data["target_achieved_pct"] == 82.0
        assert data["credit_health"] == "Overdue Notice"
        # Re-evaluated decision rules:
        assert data["achievement_status"] == "Underperforming"
        assert data["performance_grade"] == "Tier 3 (Low)"
        assert data["action_status"] == "PIP Warning"

        # Verify audit log was recorded
        mock_audit.insert_one.assert_called_once()
        audit_call = mock_audit.insert_one.call_args[0][0]
        assert audit_call["salesman_id"] == "W001406"
        assert audit_call["actor"] == "supervisor_sam"
        assert "route_discipline" in audit_call["changes"]

        app.dependency_overrides.clear()

    def test_delete_salesman_soft_deletion_api(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_audit = MagicMock()
        mock_db.__getitem__.side_effect = lambda k: mock_audit if k == "audit_logs" else mock_collection

        existing_doc = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "salesman_id": "W001406",
            "salesman_name": "Sophal Chea",
            "supervisor": "Keo Piseth",
            "province": "Phnom Penh",
            "district": "Pur SenChey",
            "commune": "Kakab 1",
            "status": "Active",
            "target_achieved_pct": 105.0,
            "strike_rate_pct": 85.0,
            "coverage_execution_pct": 92.0,
            "route_discipline": "Compliant",
            "mom_growth": "Positive Growth",
            "in_store_merchandising_score": "Good",
            "credit_health": "Healthy",
            "achievement_status": "Achieved",
            "performance_grade": "Tier 1 (High)",
            "action_status": "Top Incentive",
        }
        mock_collection.find_one = AsyncMock(return_value=existing_doc)
        mock_audit.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

        def side_effect(filter_dict, update_dict, return_document):
            updated = dict(existing_doc)
            updated.update(update_dict["$set"])
            return updated

        mock_collection.find_one_and_update = AsyncMock(side_effect=side_effect)

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        res = client.delete("/api/v1/salesmen/W001406?actor=admin_jane")
        assert res.status_code == 200
        data = res.json()
        assert data["salesman_id"] == "W001406"
        assert data["status"] == "Inactive"

        # Verify audit log
        mock_audit.insert_one.assert_called_once()
        audit_call = mock_audit.insert_one.call_args[0][0]
        assert audit_call["action"] == "STATUS_TOGGLE"
        assert audit_call["changes"]["status"] == {"old": "Active", "new": "Inactive"}

        app.dependency_overrides.clear()

    def test_territories_cascading_endpoints_api(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.salesmen = mock_collection

        # Distinct calls
        async def mock_distinct(field, filter_query):
            if field == "province":
                return ["Siem Reap", "Phnom Penh", "Battambang"]
            elif field == "district":
                if filter_query.get("province") == "Phnom Penh":
                    return ["Pur SenChey", "Chamkar Mon"]
                return ["Pur SenChey", "Chamkar Mon", "Svay Por"]
            elif field == "commune":
                if filter_query.get("district") == "Pur SenChey":
                    return ["Kakab 1", "Chaom Chau 3"]
                return ["Kakab 1", "Chaom Chau 3", "Boeng Keng Kang 1"]
            return []

        mock_collection.distinct = AsyncMock(side_effect=mock_distinct)

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        # 1. Provinces
        res1 = client.get("/api/v1/territories/provinces")
        assert res1.status_code == 200
        assert res1.json() == ["Battambang", "Phnom Penh", "Siem Reap"]

        # 2. Districts with province filter
        res2 = client.get("/api/v1/territories/districts?province=Phnom Penh")
        assert res2.status_code == 200
        assert res2.json() == ["Chamkar Mon", "Pur SenChey"]

        # 3. Communes with district filter
        res3 = client.get("/api/v1/territories/communes?district=Pur SenChey")
        assert res3.status_code == 200
        assert res3.json() == ["Chaom Chau 3", "Kakab 1"]

        # Also verify direct cascading path /api/v1/provinces
        res4 = client.get("/api/v1/provinces")
        assert res4.status_code == 200
        assert res4.json() == ["Battambang", "Phnom Penh", "Siem Reap"]

        app.dependency_overrides.clear()
