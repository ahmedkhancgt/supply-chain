from typing import List, Dict, Any, Optional

CANONICAL_FIELDS = {
    "sku_id": ["itemcode", "item_code", "sku", "product_id", "part_number", "material_no", "mat_num", "item_no", "part_no", "article_no", "upc", "barcode", "gtin"],
    "product_name": ["itemdescription", "item_name", "product_name", "description", "title", "mat_desc", "item_desc", "product_desc"],
    "location_id": ["warehousecode", "wh", "store_id", "location_id", "site_code", "depot", "wh_code", "facility_id", "branch_id"],
    "on_hand_quantity": ["qtyonhand", "current_stock", "on_hand_qty", "quantity", "stock_qty", "qty_on_hand", "stock_on_hand", "qty_available", "stock_level"],
    "available_quantity": ["qtyavailable", "available_stock", "free_stock", "allocatable_qty", "alloc_stock"],
    "unit_cost": ["unitcost", "cost_price", "purchase_price", "unit_cost", "cogs", "purchase_rate", "buy_price", "unit_prc", "cost"],
    "selling_price": ["sellingprice", "unit_price", "rate", "retail_price", "list_price", "mrp", "sales_price"],
    "date": ["transactiondate", "txndate", "orderdate", "date", "created_at", "txn_date", "posting_date"],
    "revenue": ["netamount", "total_revenue", "sales_amount", "revenue", "net_sales", "amount", "total"],
    "supplier_id": ["suppliercode", "vendor_id", "supplier_id", "vendor_code", "contact_id", "supplier_name", "vendor_name"],
    "lead_time": ["leadtimedays", "lead_time", "delivery_days", "transit_time", "lead_days", "vendor_lead_time"],
    "allocated_space": ["allocated_space_sqm", "space_sqm", "shelf_space", "facing_width", "display_sqm"]
}

class CanonicalMappingEngine:
    """
    Automated source-to-canonical field mapping engine with alias matching and confidence scoring.
    """
    def suggest_mappings(self, source_fields: List[str]) -> List[Dict[str, Any]]:
        suggestions = []
        for s_field in source_fields:
            s_clean = s_field.lower().replace("_", "").replace(" ", "")
            matched_canonical = None
            highest_conf = 0.0

            for canonical_key, aliases in CANONICAL_FIELDS.items():
                for alias in aliases:
                    alias_clean = alias.replace("_", "")
                    if s_clean == alias_clean:
                        matched_canonical = canonical_key
                        highest_conf = 0.98
                        break
                    elif alias_clean in s_clean or s_clean in alias_clean:
                        if highest_conf < 0.85:
                            matched_canonical = canonical_key
                            highest_conf = 0.85
                if highest_conf >= 0.98:
                    break

            if not matched_canonical:
                matched_canonical = "unmapped_custom_field"
                highest_conf = 0.50

            suggestions.append({
                "source_field": s_field,
                "suggested_canonical": matched_canonical,
                "confidence_score": highest_conf,
                "status": "CONFIRMED" if highest_conf >= 0.90 else "PENDING_CONFIRMATION"
            })
        return suggestions
