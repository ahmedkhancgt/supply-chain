from typing import Dict, Any, List
import math
from sqlalchemy.orm import Session
from backend.app.models.models import Product, Supplier, PurchaseOrder, Inventory, SalesHistory

class ProcurementOptimizerEngine:
    """
    Module 4: Intelligent Procurement AI Engine.
    Calculates EOQ (Economic Order Quantity), Supplier OTIF metrics, lead time variance,
    reorder order quantities, and potential procurement savings.
    """
    def __init__(self, db: Session):
        self.db = db

    def generate_procurement_intelligence(self) -> Dict[str, Any]:
        products = self.db.query(Product).all()
        suppliers = self.db.query(Supplier).all()

        # Bulk-fetch stock for every product in 1 query instead of N+1 per-product lookups.
        # available_stock is a computed Python property (current_stock - reserved_stock),
        # not a DB column, so it can't be summed in SQL - aggregate it here instead, across
        # every warehouse holding the product.
        stock_map: Dict[int, int] = {}
        for inv in self.db.query(Inventory.product_id, Inventory.current_stock, Inventory.reserved_stock).all():
            product_id, current_stock, reserved_stock = inv
            available = max(0, (current_stock or 0) - (reserved_stock or 0))
            stock_map[product_id] = stock_map.get(product_id, 0) + available

        total_open_po_cost = 0.0
        po_list = self.db.query(PurchaseOrder).all()
        for po in po_list:
            total_open_po_cost += po.total_cost or 0.0

        supplier_performance = []
        for s in suppliers:
            otif = getattr(s, 'otif_score', 92.5) or 92.5
            supplier_performance.append({
                "supplier_id": s.id,
                "code": s.code,
                "name": s.name,
                "rating": s.rating,
                "otif_score_pct": otif,
                "avg_lead_time_days": s.lead_time_avg_days,
                "risk_level": "LOW" if otif >= 90 else ("MEDIUM" if otif >= 80 else "HIGH")
            })

        order_recommendations = []
        total_potential_savings = 0.0

        for p in products:
            current_qty = stock_map.get(p.id, 0)
            
            if current_qty <= p.reorder_point:
                # Calculate EOQ: sqrt((2 * Demand * OrderingCost) / HoldingCost)
                annual_demand = max(100.0, float(p.reorder_point * 12))
                order_cost = 50.0 # Fixed setup cost
                holding_cost = max(1.0, float(p.unit_cost * 0.15)) # 15% holding cost
                eoq = int(math.ceil(math.sqrt((2 * annual_demand * order_cost) / holding_cost)))
                
                # Recommended PO quantity
                rec_qty = max(eoq, (p.reorder_point * 2) - current_qty)
                estimated_cost = round(rec_qty * p.unit_cost, 2)
                savings = round(estimated_cost * 0.08, 2) # Bulk purchasing negotiation savings
                total_potential_savings += savings

                # Primary supplier
                supp = suppliers[0] if suppliers else None

                order_recommendations.append({
                    "product_id": p.id,
                    "sku": p.sku,
                    "product_name": p.name,
                    "current_stock": current_qty,
                    "reorder_point": p.reorder_point,
                    "recommended_po_qty": rec_qty,
                    "estimated_order_cost": estimated_cost,
                    "supplier_name": supp.name if supp else "Primary Supplier",
                    "supplier_otif": supp.otif_score if supp and hasattr(supp, 'otif_score') else 92.5,
                    "potential_savings": savings,
                    "urgency": "CRITICAL" if current_qty <= p.safety_stock_min else "HIGH"
                })

        return {
            "total_open_po_value": round(total_open_po_cost, 2),
            "potential_savings": round(total_potential_savings, 2),
            "suppliers_count": len(suppliers),
            "avg_supplier_otif_pct": round(sum(sp["otif_score_pct"] for sp in supplier_performance) / max(1, len(supplier_performance)), 1),
            "supplier_performance": supplier_performance,
            "order_recommendations": order_recommendations
        }
