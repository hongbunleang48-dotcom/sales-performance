import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_database
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.services.export_service import ExportService


# ============================================================================
# 1. Security Unit Tests
# ============================================================================

class TestSecurity:
    def test_password_hashing_and_verification(self):
        password = "SecurePassword123!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_jwt_token_flow(self):
        data = {"sub": "testuser", "role": "admin"}
        token = create_access_token(data)
        assert isinstance(token, str)

        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_invalid_jwt_token(self):
        payload = decode_access_token("invalid.token.string")
        assert payload is None


# ============================================================================
# 2. Export Service Tests
# ============================================================================

class TestExportService:
    def test_generate_salesmen_csv(self):
        records = [
            {
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
                "achievement_status": "Achieved",
                "performance_grade": "Tier 1 (High)",
                "action_status": "Top Incentive",
            }
        ]
        csv_str = ExportService.generate_salesmen_csv(records)
        lines = csv_str.strip().split("\n")
        assert len(lines) == 2
        assert "Salesman ID" in lines[0]
        assert "W001406" in lines[1]
        assert "Top Incentive" in lines[1]


# ============================================================================
# 3. Auth and Reports API Tests
# ============================================================================

class TestAuthAndReportsAPI:
    def test_login_and_me_endpoints(self):
        mock_db = MagicMock()
        mock_users = MagicMock()
        mock_db.users = mock_users
        mock_db.__getitem__.return_value = mock_users

        # No user yet -> triggers auto-seed admin
        mock_users.find_one = AsyncMock(return_value=None)
        mock_users.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=ObjectId())
        )

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        # Login
        login_res = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["user"]["username"] == "admin"

        # Call /me with Bearer token
        token = token_data["access_token"]
        # Mock find_one to return the created admin
        mock_users.find_one = AsyncMock(
            return_value={
                "username": "admin",
                "email": "admin@projectcore.com",
                "full_name": "Project CORE Administrator",
                "role": "admin",
                "is_active": True,
            }
        )

        me_res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["username"] == "admin"
        assert me_data["role"] == "admin"

        app.dependency_overrides.clear()

    def test_reports_export_csv_endpoint(self):
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.salesmen = mock_collection

        sample_record = {
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

        mock_cursor = MagicMock()

        async def async_iter(self):
            yield sample_record

        mock_cursor.__aiter__ = async_iter
        mock_cursor.sort.return_value = mock_cursor
        mock_collection.find.return_value = mock_cursor

        app.dependency_overrides[get_database] = lambda: mock_db
        client = TestClient(app)

        res = client.get("/api/v1/reports/export/csv?province=Phnom Penh")
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/csv")
        assert "attachment; filename=" in res.headers["content-disposition"]
        content = res.text
        assert "Salesman ID" in content
        assert "W001406" in content

        app.dependency_overrides.clear()
