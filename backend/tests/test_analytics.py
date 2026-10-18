import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_database
from app.services.analytics_service import AnalyticsService


# ============================================================================
# 1. Analytics Service Aggregation Pipeline Tests
# ============================================================================

class TestAnalyticsService:
    def test_executive_overview_aggregation(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection

            expected_overview = {
                "total_reps": 10,
                "avg_target_realization": 98.5,
                "avg_strike_rate": 84.2,
                "coverage_saturation_pct": 80.0,
                "compliant_reps": 8,
                "field_risk_count": 2,
            }

            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[expected_overview])
            mock_collection.aggregate.return_value = mock_cursor

            service = AnalyticsService(mock_db)
            result = await service.get_executive_overview(province="Phnom Penh")

            assert result == expected_overview
            mock_collection.aggregate.assert_called_once()
            pipeline = mock_collection.aggregate.call_args[0][0]
            assert pipeline[0]["$match"] == {"province": "Phnom Penh"}
            assert "$group" in pipeline[1]

        asyncio.run(run())

    def test_executive_overview_empty_result_defaults(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection

            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[])
            mock_collection.aggregate.return_value = mock_cursor

            service = AnalyticsService(mock_db)
            result = await service.get_executive_overview()

            assert result["total_reps"] == 0
            assert result["avg_target_realization"] == 0.0
            assert result["coverage_saturation_pct"] == 0.0
            assert result["field_risk_count"] == 0

        asyncio.run(run())

    def test_route_fidelity_scatter_pipeline(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection

            sample_scatter_data = [
                {
                    "salesman_id": "W001401",
                    "salesman_name": "Rep 1",
                    "coverage_execution_pct": 95.0,
                    "strike_rate_pct": 90.0,
                    "quadrant": "Q1",
                    "quadrant_label": "Optimal (High Coverage, High Strike)",
                },
                {
                    "salesman_id": "W001402",
                    "salesman_name": "Rep 2",
                    "coverage_execution_pct": 85.0,
                    "strike_rate_pct": 88.0,
                    "quadrant": "Q2",
                    "quadrant_label": "Effective But Diverted (Low Coverage, High Strike)",
                },
                {
                    "salesman_id": "W001403",
                    "salesman_name": "Rep 3",
                    "coverage_execution_pct": 80.0,
                    "strike_rate_pct": 75.0,
                    "quadrant": "Q3",
                    "quadrant_label": "Critical Risk (Low Coverage, Low Strike)",
                },
                {
                    "salesman_id": "W001404",
                    "salesman_name": "Rep 4",
                    "coverage_execution_pct": 92.0,
                    "strike_rate_pct": 80.0,
                    "quadrant": "Q4",
                    "quadrant_label": "Disciplined Ineffective (High Coverage, Low Strike)",
                },
            ]

            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=sample_scatter_data)
            mock_collection.aggregate.return_value = mock_cursor

            service = AnalyticsService(mock_db)
            result = await service.get_route_fidelity_scatter(status="Active")

            assert len(result) == 4
            assert result[0]["quadrant"] == "Q1"
            assert result[1]["quadrant"] == "Q2"
            assert result[2]["quadrant"] == "Q3"
            assert result[3]["quadrant"] == "Q4"

        asyncio.run(run())

    def test_supervisor_leaderboard_pipeline(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection

            raw_leaderboard = [
                {
                    "supervisor": "Keo Piseth",
                    "total_reps": 4,
                    "tier1_count": 3,
                    "tier2_count": 1,
                    "tier3_count": 0,
                    "tier1_ratio": 0.75,
                    "tier1_percentage": 75.0,
                    "avg_target_achieved": 104.5,
                },
                {
                    "supervisor": "Chan Vanna",
                    "total_reps": 5,
                    "tier1_count": 2,
                    "tier2_count": 2,
                    "tier3_count": 1,
                    "tier1_ratio": 0.40,
                    "tier1_percentage": 40.0,
                    "avg_target_achieved": 92.0,
                },
            ]

            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=raw_leaderboard)
            mock_collection.aggregate.return_value = mock_cursor

            service = AnalyticsService(mock_db)
            result = await service.get_supervisor_leaderboard()

            assert len(result) == 2
            assert result[0]["rank"] == 1
            assert result[0]["supervisor"] == "Keo Piseth"
            assert result[0]["tier1_percentage"] == 75.0
            assert result[1]["rank"] == 2
            assert result[1]["supervisor"] == "Chan Vanna"

        asyncio.run(run())

    def test_tier_distribution_pipeline(self):
        async def run():
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_db.__getitem__.return_value = mock_collection

            sample_groups = [
                {"_id": "Tier 1 (High)", "count": 5},
                {"_id": "Tier 2 (Medium)", "count": 3},
                {"_id": "Tier 3 (Low)", "count": 2},
            ]

            async def mock_aiter(self):
                for g in sample_groups:
                    yield g

            mock_cursor = MagicMock()
            mock_cursor.__aiter__ = mock_aiter
            mock_collection.aggregate.return_value = mock_cursor

            service = AnalyticsService(mock_db)
            result = await service.get_tier_distribution()

            assert result["total"] == 10
            assert result["tier1_count"] == 5
            assert result["tier2_count"] == 3
            assert result["tier3_count"] == 2
            assert len(result["distribution"]) == 3
            assert result["distribution"][0]["percentage"] == 50.0
            assert result["distribution"][0]["color"] == "#10B981"
            assert result["distribution"][1]["percentage"] == 30.0
            assert result["distribution"][1]["color"] == "#F59E0B"
            assert result["distribution"][2]["percentage"] == 20.0
            assert result["distribution"][2]["color"] == "#EF4444"

        asyncio.run(run())


# ============================================================================
# 2. Analytics FastAPI Endpoints Integration Tests
# ============================================================================

class TestAnalyticsAPI:
    def test_overview_endpoint(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(
            return_value=[
                {
                    "total_reps": 7,
                    "avg_target_realization": 102.3,
                    "avg_strike_rate": 86.5,
                    "coverage_saturation_pct": 85.71,
                    "compliant_reps": 6,
                    "field_risk_count": 1,
                }
            ]
        )
        mock_collection.aggregate.return_value = mock_cursor

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        res = client.get("/api/v1/analytics/overview?province=Phnom Penh")
        assert res.status_code == 200
        data = res.json()
        assert data["total_reps"] == 7
        assert data["avg_target_realization"] == 102.3
        assert data["coverage_saturation_pct"] == 85.71
        assert data["field_risk_count"] == 1

        app.dependency_overrides.clear()

    def test_scatter_endpoint(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(
            return_value=[
                {
                    "salesman_id": "W001406",
                    "salesman_name": "Sophal Chea",
                    "coverage_execution_pct": 95.0,
                    "strike_rate_pct": 90.0,
                    "quadrant": "Q1",
                    "quadrant_label": "Optimal (High Coverage, High Strike)",
                }
            ]
        )
        mock_collection.aggregate.return_value = mock_cursor

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        res = client.get("/api/v1/analytics/scatter")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["quadrant"] == "Q1"

        app.dependency_overrides.clear()

    def test_supervisors_endpoint(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(
            return_value=[
                {
                    "rank": 1,
                    "supervisor": "Keo Piseth",
                    "total_reps": 5,
                    "tier1_count": 4,
                    "tier1_ratio": 0.8,
                    "tier1_percentage": 80.0,
                    "avg_target_achieved": 105.0,
                }
            ]
        )
        mock_collection.aggregate.return_value = mock_cursor

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        res = client.get("/api/v1/analytics/supervisors")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["rank"] == 1
        assert data[0]["supervisor"] == "Keo Piseth"
        assert data[0]["tier1_percentage"] == 80.0

        app.dependency_overrides.clear()

    def test_tier_distribution_endpoint(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        async def mock_aiter(self):
            yield {"_id": "Tier 1 (High)", "count": 4}
            yield {"_id": "Tier 2 (Medium)", "count": 2}
            yield {"_id": "Tier 3 (Low)", "count": 1}

        mock_cursor = MagicMock()
        mock_cursor.__aiter__ = mock_aiter
        mock_collection.aggregate.return_value = mock_cursor

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        res = client.get("/api/v1/analytics/tier-distribution")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 7
        assert data["tier1_count"] == 4
        assert len(data["distribution"]) == 3

        app.dependency_overrides.clear()
