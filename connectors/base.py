from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
from datetime import datetime

class DataValidationError(Exception):
    pass

class BaseConnector(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logs: List[Dict[str, Any]] = []

    def log_event(self, level: str, message: str, details: Any = None):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "connector": self.name,
            "level": level,
            "message": message,
            "details": details
        }
        self.logs.append(entry)
        print(f"[{entry['timestamp']}] [{level}] [{self.name}] {message}")

    def validate_record(self, record: Dict[str, Any], required_fields: List[str]) -> Tuple[bool, List[str]]:
        errors = []
        for field in required_fields:
            if field not in record or record[field] is None or record[field] == "":
                errors.append(f"Missing required field: '{field}'")
        
        if "quantity" in record:
            try:
                qty = float(record["quantity"])
                if qty < 0:
                    errors.append("Quantity cannot be negative")
            except (ValueError, TypeError):
                errors.append("Quantity must be a valid number")

        if "unit_cost" in record:
            try:
                cost = float(record["unit_cost"])
                if cost < 0:
                    errors.append("Unit cost cannot be negative")
            except (ValueError, TypeError):
                errors.append("Unit cost must be a valid number")

        return len(errors) == 0, errors

    @abstractmethod
    def ingest(self, source_data: Any, db_session: Any) -> Dict[str, Any]:
        pass
