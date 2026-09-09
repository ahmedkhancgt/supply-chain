from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.models import Product, RetailSpace, Inventory, SalesHistory

class AssortmentOptimizerEngine:
    """
    Module 8: Retail Assortment & Space Optimizer Engine.
    Calculates GMROI (Gross Margin Return on Investment), sell-through rates,
    space productivity (Revenue / Sq. Meter), display unit utilization, and space allocation optimization.
    """
    def __init__(self, db: Session):
        self.db = db

    def generate_assortment_intelligence(self) -> Dict[str, Any]:
        products = self.db.query(Product).all()

        # Bulk-fetch retail space per product in 1 query instead of N+1 per-product lookups
        space_rows = self.db.query(RetailSpace).all()
        space_map = {sp.product_id: sp for sp in space_rows}

        # Bulk-aggregate quantity sold and revenue per product via SQL GROUP BY
        # instead of loading every SalesHistory row per product and summing in Python
        sales_rows = self.db.query(
            SalesHistory.product_id,
            func.sum(SalesHistory.quantity_sold),
            func.sum(SalesHistory.revenue)
        ).group_by(SalesHistory.product_id).all()
        sales_map = {row[0]: (row[1] or 0, row[2] or 0.0) for row in sales_rows}

        sku_assortment = []
        total_allocated_sqm = 0.0
        total_revenue = 0.0

        for p in products:
            sp = space_map.get(p.id)
            allocated_sqm = sp.allocated_space_sqm if sp else 0.0
            display_units = sp.display_units if sp else 0
            shelf_cap = sp.shelf_capacity if sp else 0
            total_allocated_sqm += allocated_sqm

            # Sales history calculation
            qty_sold, revenue = sales_map.get(p.id, (0, 0.0))
            total_revenue += revenue

            # Gross Margin & GMROI
            gross_margin = max(0.0, p.selling_price - p.unit_cost)
            total_margin = gross_margin * qty_sold
            avg_inv_val = max(1.0, float(display_units * p.unit_cost))
            gmroi = round(total_margin / avg_inv_val, 2)

            # Sell-Through Rate
            sell_through_pct = round(min(100.0, (qty_sold / max(1.0, float(qty_sold + display_units))) * 100.0), 1)

            # Revenue productivity per sqm
            rev_per_sqm = round(revenue / max(0.1, allocated_sqm), 2)

            # Productivity Classification
            if gmroi >= 3.0 and sell_through_pct >= 70.0:
                classif = "STAR_PRODUCT"
            elif gmroi >= 1.5:
                classif = "CORE_STABLE"
            elif sell_through_pct < 40.0:
                classif = "UNDERPERFORMER"
            else:
                classif = "SLOW_MOVER"

            sku_assortment.append({
                "product_id": p.id,
                "sku": p.sku,
                "product_name": p.name,
                "category": p.category.name if p.category else "General",
                "allocated_space_sqm": allocated_sqm,
                "display_units": display_units,
                "shelf_capacity": shelf_cap,
                "space_utilization_pct": round((display_units / max(1, shelf_cap)) * 100.0, 1),
                "units_sold_90d": qty_sold,
                "revenue_90d": round(revenue, 2),
                "revenue_per_sqm": rev_per_sqm,
                "gmroi": gmroi,
                "sell_through_pct": sell_through_pct,
                "classification": classif
            })

        # Sort SKUs by revenue productivity
        sku_assortment.sort(key=lambda x: x["revenue_per_sqm"], reverse=True)

        avg_gmroi = round(sum(x["gmroi"] for x in sku_assortment) / max(1, len(sku_assortment)), 2)
        avg_sell_through = round(sum(x["sell_through_pct"] for x in sku_assortment) / max(1, len(sku_assortment)), 1)
        low_productivity_count = sum(1 for x in sku_assortment if x["classification"] in ["UNDERPERFORMER", "SLOW_MOVER"])

        return {
            "total_allocated_space_sqm": round(total_allocated_sqm, 1),
            "avg_store_gmroi": avg_gmroi,
            "avg_sell_through_pct": avg_sell_through,
            "revenue_per_sqm_avg": round(total_revenue / max(1.0, total_allocated_sqm), 2),
            "low_productivity_sku_count": low_productivity_count,
            "sku_assortment": sku_assortment
        }
