import math
import numpy as np
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.app.models.models import Inventory, Product, Warehouse, SalesHistory

class InventoryOptimizer:
    """
    Implements deterministic supply chain optimization formulas:
    - Daily Demand (D_avg) & Standard Deviation (sigma_d)
    - Safety Stock SS = Z * sigma_d * sqrt(L)
    - Reorder Point ROP = (D_avg * L) + SS
    - Recommended Order Quantity ROQ = max(0, ROP + SS - Current_Stock)
    """
    def __init__(self, db: Session, service_level_z: float = 1.65):
        self.db = db
        self.z = service_level_z  # 1.65 corresponds to 95% service level

    def calculate_inventory_metrics(self, product_id: int, warehouse_id: int) -> Dict[str, Any]:
        product = self.db.query(Product).filter(Product.id == product_id).first()
        warehouse = self.db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        inv = self.db.query(Inventory).filter(
            Inventory.product_id == product_id,
            Inventory.warehouse_id == warehouse_id
        ).first()

        if not product or not warehouse or not inv:
            raise ValueError("Invalid product, warehouse, or inventory record")

        # Get historical daily sales for last 60 days to estimate demand variability
        sales = self.db.query(SalesHistory.quantity_sold).filter(
            SalesHistory.product_id == product_id,
            SalesHistory.warehouse_id == warehouse_id
        ).order_by(SalesHistory.date.desc()).limit(60).all()

        if sales:
            qty_list = [s[0] for s in sales]
            d_avg = float(np.mean(qty_list))
            d_std = float(np.std(qty_list)) if len(qty_list) > 1 else d_avg * 0.25
        else:
            d_avg = float(product.reorder_point) / max(1, product.lead_time_days)
            d_std = d_avg * 0.3

        lead_time = max(1, product.lead_time_days)
        
        # Formulas
        # 1. Safety Stock
        safety_stock_calc = int(math.ceil(self.z * d_std * math.sqrt(lead_time)))
        safety_stock = max(product.safety_stock_min, safety_stock_calc)

        # 2. Reorder Point (Expected demand during lead time + Safety stock)
        expected_lead_time_demand = d_avg * lead_time
        reorder_point = int(math.ceil(expected_lead_time_demand + safety_stock))

        # 3. Days of Inventory (DOI)
        doi = float(inv.current_stock / d_avg) if d_avg > 0 else 999.0

        # 4. Recommended Order Quantity (ROQ)
        # ROQ = max(0, Reorder Point + Safety Stock - Current Stock)
        if inv.current_stock <= reorder_point:
            # Target stock is max capacity or ROP + Safety Stock
            target_stock = reorder_point + safety_stock * 2
            roq = max(0, target_stock - inv.current_stock)
        else:
            roq = 0

        # 5. Stockout & Excess Assessment
        is_stockout_risk = inv.current_stock <= reorder_point
        is_excess_stock = inv.current_stock > (reorder_point * 4)

        return {
            "product_id": product.id,
            "sku": product.sku,
            "product_name": product.name,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "current_stock": inv.current_stock,
            "allocated_stock": inv.allocated_stock,
            "available_stock": inv.available_stock,
            "avg_daily_demand": round(d_avg, 2),
            "demand_std_dev": round(d_std, 2),
            "lead_time_days": lead_time,
            "safety_stock_calculated": safety_stock,
            "reorder_point_calculated": reorder_point,
            "days_of_inventory": round(doi, 1),
            "is_stockout_risk": is_stockout_risk,
            "is_excess_stock": is_excess_stock,
            "recommended_order_quantity": int(roq)
        }
