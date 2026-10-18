import csv
import io
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

# Check if pandas is available in the environment; if not, fallback seamlessly to csv/io
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


EXPORT_COLUMNS = [
    ("salesman_id", "Salesman ID"),
    ("salesman_name", "Salesman Name"),
    ("supervisor", "Supervisor"),
    ("province", "Province"),
    ("district", "District"),
    ("commune", "Commune"),
    ("status", "Status"),
    ("target_achieved_pct", "Target Achieved (%)"),
    ("strike_rate_pct", "Strike Rate (%)"),
    ("coverage_execution_pct", "Coverage Execution (%)"),
    ("route_discipline", "Route Discipline"),
    ("mom_growth", "MoM Growth"),
    ("in_store_merchandising_score", "In-Store Merchandising Score"),
    ("credit_health", "Credit Health"),
    ("achievement_status", "Achievement Status"),
    ("performance_grade", "Performance Grade"),
    ("action_status", "Action Status"),
    ("updated_at", "Last Updated"),
]


class ExportService:
    @staticmethod
    def format_row_value(key: str, val: Any) -> Any:
        """Helper to format fields nicely for CSV output."""
        if val is None:
            return ""
        if isinstance(val, float):
            return f"{val:.2f}"
        if isinstance(val, datetime):
            return val.strftime("%Y-%m-%d %H:%M:%S UTC")
        return str(val)

    @classmethod
    def generate_salesmen_csv(cls, records: List[Dict[str, Any]]) -> str:
        """
        Generates RFC-4180 compliant CSV string from list of salesman dictionaries.
        Uses pandas if installed, or high-performance io.StringIO / csv.writer fallback.
        """
        if HAS_PANDAS and len(records) > 0:
            # Prepare rows matching EXPORT_COLUMNS
            formatted_data = []
            for r in records:
                row = {}
                for key, label in EXPORT_COLUMNS:
                    row[label] = cls.format_row_value(key, r.get(key))
                formatted_data.append(row)
            df = pd.DataFrame(formatted_data)
            return df.to_csv(index=False)

        # Standard library io.StringIO / csv.writer
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")

        # Write header
        headers = [col_label for _, col_label in EXPORT_COLUMNS]
        writer.writerow(headers)

        # Write data rows
        for r in records:
            row = [cls.format_row_value(key, r.get(key)) for key, _ in EXPORT_COLUMNS]
            writer.writerow(row)

        return output.getvalue()

    @classmethod
    async def export_salesmen_from_db(
        cls,
        db: AsyncIOMotorDatabase,
        filter_query: Optional[Dict[str, Any]] = None,
        sort_by: str = "salesman_id",
        sort_order: int = 1
    ) -> Tuple[str, str, int]:
        """
        Queries MongoDB salesmen collection with filters, formats to CSV,
        and generates a timestamped filename.
        """
        query = filter_query or {}
        cursor = db.salesmen.find(query).sort(sort_by, sort_order)
        records = []
        async for doc in cursor:
            records.append(doc)

        csv_content = cls.generate_salesmen_csv(records)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"sales_performance_roster_{timestamp}.csv"
        return csv_content, filename, len(records)
