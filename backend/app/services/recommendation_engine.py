from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.models.models import Product, Inventory, Supplier, PurchaseOrder
from ai.risk.engine import InventoryRiskEngine
from ai.procurement.engine import ProcurementOptimizerEngine
from ai.assortment.engine import AssortmentOptimizerEngine

class UnifiedRecommendationEngine:
    """
    Standardized Recommendation Engine for Wisualyst Platform.
    Aggregates and standardizes intelligence insights across Inventory AI, Demand AI, Procurement AI, and Assortment AI.
    """
    def __init__(self, db: Session):
        self.db = db
        self.risk_engine = InventoryRiskEngine(db)
        self.procurement_engine = ProcurementOptimizerEngine(db)
        self.assortment_engine = AssortmentOptimizerEngine(db)

    def get_unified_recommendations(self) -> List[Dict[str, Any]]:
        recommendations = []
        rec_counter = 1

        # 1. Inventory & Stockout Risk Recommendations
        risks = self.risk_engine.get_all_inventory_risks()
        for r in risks:
            if r["stockout_risk_level"] in ["CRITICAL", "HIGH"]:
                impact = round(float(r["current_stock"] * r.get("unit_cost", 0.0) * 3.5), 2)
                recommendations.append({
                    "recommendation_id": f"REC_INV_{rec_counter:03d}",
                    "module": "inventory",
                    "entity_type": "sku",
                    "entity_id": r["sku"],
                    "severity": "critical" if r["stockout_risk_level"] == "CRITICAL" else "high",
                    "title": f"Stockout Risk: {r['product_name']}",
                    "summary": f"Product {r['sku']} has only {r.get('days_of_inventory', 0)} days of stock remaining at {r['warehouse_name']}",
                    "reason": f"Available stock ({r['current_stock']}) is below safety threshold ({r.get('safety_stock', 0)}) with lead time of {r['lead_time_days']} days.",
                    "financial_impact": impact,
                    "confidence": 0.94,
                    "recommended_action": f"Issue emergency purchase order for {r['reorder_point'] * 2} units immediately.",
                    "alternative_action": "Reallocate 50% safety stock from central hub warehouse.",
                    "status": "open"
                })
                rec_counter += 1

        # 2. Procurement & EOQ Savings Recommendations
        proc_intel = self.procurement_engine.generate_procurement_intelligence()
        for po_rec in proc_intel.get("order_recommendations", []):
            recommendations.append({
                "recommendation_id": f"REC_PROC_{rec_counter:03d}",
                "module": "procurement",
                "entity_type": "sku",
                "entity_id": po_rec["sku"],
                "severity": po_rec["urgency"].lower(),
                "title": f"EOQ Purchase Order Recommendation for {po_rec['product_name']}",
                "summary": f"Place PO of {po_rec['recommended_po_qty']} units with supplier {po_rec['supplier_name']}",
                "reason": f"Current stock is {po_rec['current_stock']} units (Reorder threshold: {po_rec['reorder_point']}). Supplier OTIF is {po_rec['supplier_otif']}%.",
                "financial_impact": po_rec["potential_savings"],
                "confidence": 0.91,
                "recommended_action": f"Issue purchase order for {po_rec['recommended_po_qty']} units (Est. cost AED {po_rec['estimated_order_cost']}).",
                "alternative_action": "Split order across two regional vendors to mitigate lead time risk.",
                "status": "open"
            })
            rec_counter += 1

        # 3. Retail Assortment & Space Recommendations
        assort_intel = self.assortment_engine.generate_assortment_intelligence()
        for item in assort_intel.get("sku_assortment", []):
            if item["classification"] in ["UNDERPERFORMER", "SLOW_MOVER"]:
                recommendations.append({
                    "recommendation_id": f"REC_ASST_{rec_counter:03d}",
                    "module": "assortment",
                    "entity_type": "sku",
                    "entity_id": item["sku"],
                    "severity": "medium",
                    "title": f"Reallocate Shelf Space for {item['product_name']}",
                    "summary": f"Product {item['sku']} is generating low revenue per sqm (AED {item['revenue_per_sqm']}/sqm, GMROI {item['gmroi']})",
                    "reason": f"Occupying {item['allocated_space_sqm']} sqm with sell-through of only {item['sell_through_pct']}%.",
                    "financial_impact": round(item["revenue_90d"] * 0.25, 2),
                    "confidence": 0.88,
                    "recommended_action": f"Reduce shelf facing by 50% and allocate space to star products.",
                    "alternative_action": "Apply 15% promotional discount to increase sell-through velocity.",
                    "status": "open"
                })
                rec_counter += 1

        return recommendations
