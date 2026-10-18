from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.rules import PerformanceGrade, UI_COLOR_MAPPINGS


class AnalyticsService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["salesmen"]

    def _build_match_query(
        self,
        province: Optional[str] = None,
        district: Optional[str] = None,
        commune: Optional[str] = None,
        supervisor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Builds MongoDB $match filter for analytics queries."""
        match_query: Dict[str, Any] = {}
        if province:
            match_query["province"] = province
        if district:
            match_query["district"] = district
        if commune:
            match_query["commune"] = commune
        if supervisor:
            match_query["supervisor"] = supervisor
        if status:
            match_query["status"] = status
        return match_query

    async def get_executive_overview(
        self,
        province: Optional[str] = None,
        district: Optional[str] = None,
        commune: Optional[str] = None,
        supervisor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate pipeline for Executive Overview:
        - Average target realization %
        - Average strike rate %
        - Coverage saturation % (ratio of Compliant reps)
        - Count of reps on PIP Warning or Overdue Notice (Field Risk Count)
        """
        match_query = self._build_match_query(
            province=province,
            district=district,
            commune=commune,
            supervisor=supervisor,
            status=status,
        )

        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": None,
                    "total_reps": {"$sum": 1},
                    "avg_target_realization": {"$avg": "$target_achieved_pct"},
                    "avg_strike_rate": {"$avg": "$strike_rate_pct"},
                    "compliant_count": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$route_discipline", "Compliant"]},
                                1,
                                0,
                            ]
                        }
                    },
                    "field_risk_count": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$or": [
                                        {"$eq": ["$action_status", "PIP Warning"]},
                                        {"$eq": ["$credit_health", "Overdue Notice"]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "total_reps": 1,
                    "avg_target_realization": {
                        "$round": [{"$ifNull": ["$avg_target_realization", 0.0]}, 2]
                    },
                    "avg_strike_rate": {
                        "$round": [{"$ifNull": ["$avg_strike_rate", 0.0]}, 2]
                    },
                    "coverage_saturation_pct": {
                        "$round": [
                            {
                                "$cond": [
                                    {"$gt": ["$total_reps", 0]},
                                    {
                                        "$multiply": [
                                            {"$divide": ["$compliant_count", "$total_reps"]},
                                            100,
                                        ]
                                    },
                                    0.0,
                                ]
                            },
                            2,
                        ]
                    },
                    "compliant_reps": "$compliant_count",
                    "field_risk_count": 1,
                }
            },
        ]

        cursor = self.collection.aggregate(pipeline)
        result = await cursor.to_list(length=1)

        if result:
            return result[0]

        return {
            "total_reps": 0,
            "avg_target_realization": 0.0,
            "avg_strike_rate": 0.0,
            "coverage_saturation_pct": 0.0,
            "compliant_reps": 0,
            "field_risk_count": 0,
        }

    async def get_route_fidelity_scatter(
        self,
        province: Optional[str] = None,
        district: Optional[str] = None,
        commune: Optional[str] = None,
        supervisor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate pipeline for Route Fidelity Scatter Data:
        Returns rep-level array with:
        - salesman_id
        - salesman_name
        - coverage_execution_pct
        - strike_rate_pct
        - quadrant classification (Q1: Optimal, Q2: Diverted, Q3: Risk, Q4: Ineffective)
        """
        match_query = self._build_match_query(
            province=province,
            district=district,
            commune=commune,
            supervisor=supervisor,
            status=status,
        )

        pipeline = [
            {"$match": match_query},
            {
                "$project": {
                    "_id": 0,
                    "salesman_id": 1,
                    "salesman_name": 1,
                    "supervisor": 1,
                    "province": 1,
                    "district": 1,
                    "commune": 1,
                    "coverage_execution_pct": {"$ifNull": ["$coverage_execution_pct", 0.0]},
                    "strike_rate_pct": {"$ifNull": ["$strike_rate_pct", 0.0]},
                    "target_achieved_pct": {"$ifNull": ["$target_achieved_pct", 0.0]},
                    "route_discipline": 1,
                    "performance_grade": 1,
                    "action_status": 1,
                    "quadrant": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$gte": [{"$ifNull": ["$coverage_execution_pct", 0]}, 90.0]},
                                    {"$gte": [{"$ifNull": ["$strike_rate_pct", 0]}, 85.0]},
                                ]
                            },
                            "Q1",
                            {
                                "$cond": [
                                    {
                                        "$and": [
                                            {"$lt": [{"$ifNull": ["$coverage_execution_pct", 0]}, 90.0]},
                                            {"$gte": [{"$ifNull": ["$strike_rate_pct", 0]}, 85.0]},
                                        ]
                                    },
                                    "Q2",
                                    {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$lt": [{"$ifNull": ["$coverage_execution_pct", 0]}, 90.0]},
                                                    {"$lt": [{"$ifNull": ["$strike_rate_pct", 0]}, 85.0]},
                                                ]
                                            },
                                            "Q3",
                                            "Q4",
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                    "quadrant_label": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$gte": [{"$ifNull": ["$coverage_execution_pct", 0]}, 90.0]},
                                    {"$gte": [{"$ifNull": ["$strike_rate_pct", 0]}, 85.0]},
                                ]
                            },
                            "Optimal (High Coverage, High Strike)",
                            {
                                "$cond": [
                                    {
                                        "$and": [
                                            {"$lt": [{"$ifNull": ["$coverage_execution_pct", 0]}, 90.0]},
                                            {"$gte": [{"$ifNull": ["$strike_rate_pct", 0]}, 85.0]},
                                        ]
                                    },
                                    "Effective But Diverted (Low Coverage, High Strike)",
                                    {
                                        "$cond": [
                                            {
                                                "$and": [
                                                    {"$lt": [{"$ifNull": ["$coverage_execution_pct", 0]}, 90.0]},
                                                    {"$lt": [{"$ifNull": ["$strike_rate_pct", 0]}, 85.0]},
                                                ]
                                            },
                                            "Critical Risk (Low Coverage, Low Strike)",
                                            "Disciplined Ineffective (High Coverage, Low Strike)",
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                }
            },
            {"$sort": {"coverage_execution_pct": -1, "strike_rate_pct": -1}},
        ]

        cursor = self.collection.aggregate(pipeline)
        return await cursor.to_list(length=1000)

    async def get_supervisor_leaderboard(
        self,
        province: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Aggregate pipeline for Supervisor Leaderboard:
        Ranks supervisors grouped by the count and proportion of Tier 1 reps under their management.
        """
        match_query = self._build_match_query(province=province, status=status)
        # Ensure supervisor is not null/empty
        match_query["supervisor"] = {"$nin": [None, ""]}

        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": "$supervisor",
                    "total_reps": {"$sum": 1},
                    "tier1_count": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$performance_grade", PerformanceGrade.TIER_1.value]},
                                1,
                                0,
                            ]
                        }
                    },
                    "tier2_count": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$performance_grade", PerformanceGrade.TIER_2.value]},
                                1,
                                0,
                            ]
                        }
                    },
                    "tier3_count": {
                        "$sum": {
                            "$cond": [
                                {"$eq": ["$performance_grade", PerformanceGrade.TIER_3.value]},
                                1,
                                0,
                            ]
                        }
                    },
                    "avg_target_achieved": {"$avg": "$target_achieved_pct"},
                    "avg_strike_rate": {"$avg": "$strike_rate_pct"},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "supervisor": "$_id",
                    "total_reps": 1,
                    "tier1_count": 1,
                    "tier2_count": 1,
                    "tier3_count": 1,
                    "tier1_ratio": {
                        "$round": [
                            {
                                "$cond": [
                                    {"$gt": ["$total_reps", 0]},
                                    {"$divide": ["$tier1_count", "$total_reps"]},
                                    0.0,
                                ]
                            },
                            4,
                        ]
                    },
                    "tier1_percentage": {
                        "$round": [
                            {
                                "$cond": [
                                    {"$gt": ["$total_reps", 0]},
                                    {
                                        "$multiply": [
                                            {"$divide": ["$tier1_count", "$total_reps"]},
                                            100,
                                        ]
                                    },
                                    0.0,
                                ]
                            },
                            2,
                        ]
                    },
                    "avg_target_achieved": {
                        "$round": [{"$ifNull": ["$avg_target_achieved", 0.0]}, 2]
                    },
                    "avg_strike_rate": {
                        "$round": [{"$ifNull": ["$avg_strike_rate", 0.0]}, 2]
                    },
                }
            },
            {
                "$sort": {
                    "tier1_ratio": -1,
                    "tier1_count": -1,
                    "avg_target_achieved": -1,
                    "total_reps": -1,
                }
            },
        ]

        cursor = self.collection.aggregate(pipeline)
        raw_leaderboard = await cursor.to_list(length=100)

        # Assign 1-indexed ranks
        for idx, entry in enumerate(raw_leaderboard):
            entry["rank"] = idx + 1

        return raw_leaderboard

    async def get_tier_distribution(
        self,
        province: Optional[str] = None,
        district: Optional[str] = None,
        supervisor: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate pipeline for Tier Distribution:
        Count of reps in Tier 1 (High), Tier 2 (Medium), Tier 3 (Low).
        """
        match_query = self._build_match_query(
            province=province,
            district=district,
            supervisor=supervisor,
            status=status,
        )

        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": "$performance_grade",
                    "count": {"$sum": 1},
                }
            },
        ]

        cursor = self.collection.aggregate(pipeline)
        counts = {
            PerformanceGrade.TIER_1.value: 0,
            PerformanceGrade.TIER_2.value: 0,
            PerformanceGrade.TIER_3.value: 0,
        }

        async for doc in cursor:
            grade = doc.get("_id")
            if grade in counts:
                counts[grade] = doc.get("count", 0)

        total = sum(counts.values())

        distribution = [
            {
                "tier": PerformanceGrade.TIER_1.value,
                "label": "Tier 1 (High)",
                "count": counts[PerformanceGrade.TIER_1.value],
                "percentage": round(counts[PerformanceGrade.TIER_1.value] / total * 100, 2)
                if total > 0
                else 0.0,
                "color": UI_COLOR_MAPPINGS.get(PerformanceGrade.TIER_1.value, "#10B981"),
            },
            {
                "tier": PerformanceGrade.TIER_2.value,
                "label": "Tier 2 (Medium)",
                "count": counts[PerformanceGrade.TIER_2.value],
                "percentage": round(counts[PerformanceGrade.TIER_2.value] / total * 100, 2)
                if total > 0
                else 0.0,
                "color": UI_COLOR_MAPPINGS.get(PerformanceGrade.TIER_2.value, "#F59E0B"),
            },
            {
                "tier": PerformanceGrade.TIER_3.value,
                "label": "Tier 3 (Low)",
                "count": counts[PerformanceGrade.TIER_3.value],
                "percentage": round(counts[PerformanceGrade.TIER_3.value] / total * 100, 2)
                if total > 0
                else 0.0,
                "color": UI_COLOR_MAPPINGS.get(PerformanceGrade.TIER_3.value, "#EF4444"),
            },
        ]

        return {
            "total": total,
            "tier1_count": counts[PerformanceGrade.TIER_1.value],
            "tier2_count": counts[PerformanceGrade.TIER_2.value],
            "tier3_count": counts[PerformanceGrade.TIER_3.value],
            "distribution": distribution,
        }
