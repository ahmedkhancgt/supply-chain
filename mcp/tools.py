import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.services.services import SupplyChainService
from ai.forecasting.engine import StatisticalForecastEngine
from ai.risk.engine import InventoryRiskEngine

class MCPToolRegistry:
    """
    Standard Model Context Protocol (MCP) Tool Registry.
    Exposes strictly READ-ONLY data and analytical tools.
    No direct SQL execution allowed.
    """
    def __init__(self, db: Session):
        self.db = db
        self.service = SupplyChainService(db)
        self.risk_engine = InventoryRiskEngine(db)
        self.forecast_engine = StatisticalForecastEngine(db)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_products",
                "description": "Get a list of products in the catalog with SKUs, category, unit cost, and lead times.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sku": {"type": "string", "description": "Optional SKU filter"}
                    }
                }
            },
            {
                "name": "get_warehouses",
                "description": "Get all warehouse locations, capacities, and codes.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_inventory",
                "description": "Get current stock levels, allocated stock, and safety stock across products and warehouses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "warehouse_id": {"type": "integer", "description": "Filter by warehouse ID"}
                    }
                }
            },
            {
                "name": "get_sales_history",
                "description": "Get historical daily sales quantity and revenue for a product.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"}
                    },
                    "required": ["product_id"]
                }
            },
            {
                "name": "get_suppliers",
                "description": "Get suppliers, ratings, and lead time information.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_demand_forecast",
                "description": "Calculate statistical AI demand forecast for a product over a given horizon (7, 14, 30 days).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer", "description": "Product ID"},
                        "horizon_days": {"type": "integer", "description": "Forecast horizon in days (default 30)"}
                    },
                    "required": ["product_id"]
                }
            },
            {
                "name": "get_inventory_risk",
                "description": "Calculate stockout and excess inventory risks (CRITICAL, HIGH, MEDIUM, LOW) based on lead times and demand forecasts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "warehouse_id": {"type": "integer", "description": "Filter by warehouse ID"},
                        "risk_level": {"type": "string", "description": "Filter by CRITICAL, HIGH, MEDIUM, or LOW"}
                    }
                }
            },
            {
                "name": "get_inventory_recommendations",
                "description": "Get automated replenishment recommendations and order quantities for products at risk.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": "get_control_tower_summary",
                "description": "Get executive high-level Control Tower metrics including total stock value, stockout risk counts, open POs, and top risk SKUs.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name == "get_products":
            sku = arguments.get("sku")
            if sku:
                p = self.service.product_repo.get_by_sku(sku)
                return [p.__dict__] if p else []
            prods = self.service.product_repo.get_all()
            return [{"id": p.id, "sku": p.sku, "name": p.name, "unit_cost": p.unit_cost, "lead_time_days": p.lead_time_days} for p in prods[:20]]

        elif name == "get_warehouses":
            whs = self.service.warehouse_repo.get_all()
            return [{"id": w.id, "code": w.code, "name": w.name, "location": w.location} for w in whs]

        elif name == "get_inventory":
            wh_id = arguments.get("warehouse_id")
            items = self.service.inventory_repo.get_all(wh_id)
            return [{
                "id": i.id, "sku": i.product.sku if i.product else "", 
                "product_name": i.product.name if i.product else "",
                "warehouse": i.warehouse.name if i.warehouse else "",
                "current_stock": i.current_stock, "available_stock": i.available_stock
            } for i in items[:25]]

        elif name == "get_sales_history":
            prod_id = arguments.get("product_id")
            records = self.service.sales_repo.get_by_product(prod_id, days=30)
            return [{"date": r.date.strftime("%Y-%m-%d"), "quantity_sold": r.quantity_sold, "revenue": r.revenue} for r in records]

        elif name == "get_suppliers":
            sups = self.service.supplier_repo.get_all()
            return [{"id": s.id, "code": s.code, "name": s.name, "rating": s.rating, "lead_time_days": s.lead_time_avg_days} for s in sups]

        elif name == "get_demand_forecast":
            prod_id = arguments.get("product_id")
            horizon = arguments.get("horizon_days", 30)
            return self.forecast_engine.generate_forecast(prod_id, horizon_days=horizon)

        elif name == "get_inventory_risk":
            wh_id = arguments.get("warehouse_id")
            risk_flt = arguments.get("risk_level")
            return self.risk_engine.get_all_inventory_risks(warehouse_id=wh_id, risk_filter=risk_flt)

        elif name == "get_inventory_recommendations":
            return self.service.get_inventory_recommendations()

        elif name == "get_control_tower_summary":
            return self.service.get_control_tower_summary()

        else:
            raise ValueError(f"Unknown MCP tool: {name}")
