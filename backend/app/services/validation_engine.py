from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.models.models import Product, Inventory, SalesHistory, Supplier, RetailSpace

class DataValidationEngine:
    """
    Data Quality & Readiness Validation Engine for Wisualyst Platform.
    Evaluates dataset health and calculates readiness scores (%) dynamically for all 4 intelligence modules.
    """
    def __init__(self, db: Session):
        self.db = db

    def evaluate_readiness(self) -> Dict[str, Any]:
        product_count = self.db.query(Product).count()
        inventory_count = self.db.query(Inventory).count()
        sales_count = self.db.query(SalesHistory).count()
        supplier_count = self.db.query(Supplier).count()
        space_count = self.db.query(RetailSpace).count()

        # Dynamic Module Readiness Calculations
        if product_count > 0 and inventory_count > 0:
            inv_readiness = min(100.0, round((inventory_count / float(product_count * 3)) * 100.0, 1))
        else:
            inv_readiness = 0.0

        if sales_count > 0:
            demand_readiness = min(100.0, round((sales_count / 100.0) * 100.0, 1))
        else:
            demand_readiness = 0.0

        if supplier_count > 0:
            proc_readiness = min(100.0, round((supplier_count / 5.0) * 100.0, 1))
        else:
            proc_readiness = 0.0

        if product_count > 0 and space_count > 0:
            assort_readiness = min(100.0, round((space_count / float(product_count)) * 100.0, 1))
        else:
            assort_readiness = 0.0

        overall_score = round((inv_readiness + demand_readiness + proc_readiness + assort_readiness) / 4.0, 1)

        quality_checks = []
        if product_count > 0:
            quality_checks.append({"check": "Product Catalog Schema Mapped", "status": "PASSED", "severity": "NONE", "affected_records": 0})
        else:
            quality_checks.append({"check": "Product Catalog Schema Mapped", "status": "PENDING", "severity": "HIGH", "affected_records": 0})

        if sales_count > 0:
            quality_checks.append({"check": "Historical Sales Coverage", "status": "PASSED", "severity": "NONE", "affected_records": 0})
        else:
            quality_checks.append({"check": "Historical Sales Coverage", "status": "PENDING", "severity": "MEDIUM", "affected_records": 0})

        return {
            "overall_readiness_pct": overall_score,
            "can_launch_workspace": overall_score >= 50.0,
            "modules": {
                "inventory_ai": {"readiness_pct": inv_readiness, "status": "READY" if inv_readiness >= 50 else "PENDING_DATA"},
                "demand_ai": {"readiness_pct": demand_readiness, "status": "READY" if demand_readiness >= 50 else "PENDING_DATA"},
                "procurement_ai": {"readiness_pct": proc_readiness, "status": "READY" if proc_readiness >= 50 else "PENDING_DATA"},
                "assortment_ai": {"readiness_pct": assort_readiness, "status": "READY" if assort_readiness >= 50 else "PENDING_DATA"}
            },
            "dataset_summary": {
                "products_mapped": product_count,
                "inventory_items_mapped": inventory_count,
                "sales_history_records": sales_count,
                "suppliers_connected": supplier_count,
                "retail_store_spaces": space_count
            },
            "quality_checks": quality_checks
        }
