import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from backend.app.models.models import Inventory, Product, Warehouse, Supplier, SupplierProduct, SalesHistory
from sqlalchemy import func

# Simple in-memory cache for 30 seconds
RISK_CACHE: Dict[str, Any] = {"timestamp": 0, "data": []}

class InventoryRiskEngine:
    def __init__(self, db: Session):
        self.db = db

    def get_all_inventory_risks(self, warehouse_id: Optional[int] = None, risk_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        global RISK_CACHE
        now = time.time()
        
        # Return cached risks if valid within 30 seconds and no filters applied
        if not warehouse_id and not risk_filter and (now - RISK_CACHE["timestamp"]) < 30 and RISK_CACHE["data"]:
            return RISK_CACHE["data"]

        # 1. Fast joined query to avoid N+1 queries
        query = self.db.query(Inventory).options(
            joinedload(Inventory.product),
            joinedload(Inventory.warehouse)
        )
        if warehouse_id:
            query = query.filter(Inventory.warehouse_id == warehouse_id)

        inventory_items = query.all()
        
        # 2. Pre-fetch average daily demand per product in 1 single bulk aggregate query
        sales_data = self.db.query(
            SalesHistory.product_id,
            func.avg(SalesHistory.quantity_sold).label("avg_daily")
        ).group_by(SalesHistory.product_id).all()
        
        avg_demand_map = {s[0]: float(s[1] or 5.0) for s in sales_data}

        # 3. Pre-fetch supplier names in 1 query
        sup_data = self.db.query(SupplierProduct.product_id, Supplier.name)\
            .join(Supplier, SupplierProduct.supplier_id == Supplier.id).all()
        supplier_map = {sp[0]: sp[1] for sp in sup_data}

        results = []
        for inv in inventory_items:
            prod = inv.product
            wh = inv.warehouse
            if not prod or not wh:
                continue

            product_id = prod.id
            sku = prod.sku
            product_name = prod.name
            wh_id = wh.id
            wh_name = wh.name
            current_stock = inv.current_stock
            allocated_stock = inv.allocated_stock
            available_stock = inv.available_stock
            
            avg_daily_demand = max(avg_demand_map.get(product_id, 5.0), 0.1)
            forecast_7d = round(avg_daily_demand * 7, 1)
            lead_time = prod.lead_time_days or 7
            safety_stock = prod.safety_stock_min or 15
            rop = prod.reorder_point or 25
            doi = round(current_stock / avg_daily_demand, 1)
            rec_order_qty = max(0, (rop * 2) - current_stock)
            supplier_name = supplier_map.get(product_id, "Primary Vendor")

            # Classification Logic
            if current_stock < safety_stock or doi < lead_time:
                risk_level = "CRITICAL"
                reason = f"CRITICAL STOCKOUT RISK! Stock ({current_stock}) below safety buffer ({safety_stock}) or DOI ({doi}d) < Lead Time ({lead_time}d)."
            elif current_stock <= rop or doi <= (lead_time + 3):
                risk_level = "HIGH"
                reason = f"High stockout risk. Stock ({current_stock}) at/below reorder point ({rop}). DOI is {doi} days."
            elif doi > 60.0 or current_stock > (rop * 4):
                risk_level = "LOW"
                reason = f"Excess stock level ({current_stock} units, {doi} days supply)."
            else:
                risk_level = "MEDIUM"
                reason = f"Stable inventory level ({current_stock} units, {doi} days of supply)."

            item_res = {
                "product_id": product_id,
                "sku": sku,
                "product_name": product_name,
                "warehouse_id": wh_id,
                "warehouse_name": wh_name,
                "current_stock": current_stock,
                "allocated_stock": allocated_stock,
                "available_stock": available_stock,
                "avg_daily_demand": round(avg_daily_demand, 2),
                "forecast_7d_demand": forecast_7d,
                "lead_time_days": lead_time,
                "safety_stock": safety_stock,
                "reorder_point": rop,
                "days_of_inventory": doi,
                "stockout_risk_level": risk_level,
                "reasoning": reason,
                "recommended_order_quantity": rec_order_qty,
                "supplier_name": supplier_name
            }

            if risk_filter:
                if risk_level == risk_filter.upper():
                    results.append(item_res)
            else:
                results.append(item_res)

        # Sort by risk severity (CRITICAL > HIGH > MEDIUM > LOW)
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        results.sort(key=lambda x: severity_order.get(x["stockout_risk_level"], 99))

        if not warehouse_id and not risk_filter:
            RISK_CACHE["timestamp"] = now
            RISK_CACHE["data"] = results

        return results
