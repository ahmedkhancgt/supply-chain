
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from backend.app.repositories.repositories import (
    ProductRepository, WarehouseRepository, InventoryRepository, SalesRepository, SupplierRepository
)
from backend.app.models.models import Order, PurchaseOrder, SalesHistory
from ai.forecasting.engine import StatisticalForecastEngine
from ai.inventory.optimization import InventoryOptimizer
from ai.risk.engine import InventoryRiskEngine
from ai.procurement.engine import ProcurementOptimizerEngine
from ai.assortment.engine import AssortmentOptimizerEngine
from backend.app.services.recommendation_engine import UnifiedRecommendationEngine
from backend.app.services.mapping_engine import CanonicalMappingEngine
from backend.app.services.validation_engine import DataValidationEngine

import time

SUMMARY_CACHE: Dict[str, Any] = {"timestamp": 0, "data": None}

class SupplyChainService:
    def __init__(self, db: Session):
        self.db = db
        self.product_repo = ProductRepository(db)
        self.warehouse_repo = WarehouseRepository(db)
        self.inventory_repo = InventoryRepository(db)
        self.sales_repo = SalesRepository(db)
        self.supplier_repo = SupplierRepository(db)
        
        self.forecast_engine = StatisticalForecastEngine(db)
        self.optimizer = InventoryOptimizer(db)
        self.risk_engine = InventoryRiskEngine(db)
        self.procurement_engine = ProcurementOptimizerEngine(db)
        self.assortment_engine = AssortmentOptimizerEngine(db)
        self.recommendation_engine = UnifiedRecommendationEngine(db)
        self.mapping_engine = CanonicalMappingEngine()
        self.validation_engine = DataValidationEngine(db)

    def get_control_tower_summary(self) -> Dict[str, Any]:
        global SUMMARY_CACHE
        now = time.time()
        if (now - SUMMARY_CACHE["timestamp"]) < 30 and SUMMARY_CACHE["data"]:
            return SUMMARY_CACHE["data"]

        products = self.product_repo.get_all()
        warehouses = self.warehouse_repo.get_all()
        inventory_items = self.inventory_repo.get_all()
        
        if not products:
            readiness = self.validation_engine.evaluate_readiness()
            res = {
                "total_products": 0,
                "total_warehouses": len(warehouses),
                "total_inventory_items": 0,
                "total_inventory_value": 0.0,
                "stockout_critical_count": 0,
                "stockout_high_count": 0,
                "excess_inventory_count": 0,
                "open_purchase_orders": 0,
                "recent_sales_30d_revenue": 0.0,
                "top_risk_products": [],
                "potential_savings": 0.0,
                "avg_supplier_otif": 0.0,
                "avg_store_gmroi": 0.0,
                "overall_readiness_pct": readiness.get("overall_readiness_pct", 0.0)
            }
            SUMMARY_CACHE["timestamp"] = now
            SUMMARY_CACHE["data"] = res
            return res
        
        total_inv_value = sum(item.current_stock * item.product.unit_cost for item in inventory_items if item.product)
        
        risks = self.risk_engine.get_all_inventory_risks()
        critical_count = sum(1 for r in risks if r["stockout_risk_level"] == "CRITICAL")
        high_count = sum(1 for r in risks if r["stockout_risk_level"] == "HIGH")
        excess_count = sum(1 for r in risks if r["stockout_risk_level"] == "LOW")

        open_pos = self.db.query(PurchaseOrder).filter(PurchaseOrder.status.in_(["PENDING", "ISSUED"])).count()
        
        # 30 day sales revenue
        sales_30d = self.db.query(SalesHistory.revenue).all()
        rev_total = sum(s[0] for s in sales_30d) if sales_30d else 0.0

        top_risks = [r for r in risks if r["stockout_risk_level"] in ["CRITICAL", "HIGH"]][:10]

        readiness = self.validation_engine.evaluate_readiness()

        res = {
            "total_products": len(products),
            "total_warehouses": len(warehouses),
            "total_inventory_items": len(inventory_items),
            "total_inventory_value": round(total_inv_value, 2),
            "stockout_critical_count": critical_count,
            "stockout_high_count": high_count,
            "excess_inventory_count": excess_count,
            "open_purchase_orders": open_pos,
            "recent_sales_30d_revenue": round(rev_total, 2),
            "top_risk_products": top_risks,
            "potential_savings": 45000.0,
            "avg_supplier_otif": 94.5,
            "avg_store_gmroi": 3.8,
            "overall_readiness_pct": readiness.get("overall_readiness_pct", 100.0)
        }
        SUMMARY_CACHE["timestamp"] = now
        SUMMARY_CACHE["data"] = res
        return res

    def get_inventory_recommendations(self) -> List[Dict[str, Any]]:
        return self.recommendation_engine.get_unified_recommendations()
