from typing import Dict, Any, List
from sqlalchemy.orm import Session
from connectors.base import BaseConnector
from backend.app.models.models import Product, Supplier, SupplierProduct, ProductCategory

class MockERPConnector(BaseConnector):
    def __init__(self):
        super().__init__("MockERPConnector")

    def sync_erp_data(self, erp_payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Consumes payload structure simulating external ERP (SAP / Oracle).
        Payload contains: products, suppliers, purchase_orders
        """
        processed_products = 0
        processed_suppliers = 0
        errors: List[str] = []

        products_data = erp_payload.get("products", [])
        suppliers_data = erp_payload.get("suppliers", [])

        default_cat = db.query(ProductCategory).first()
        if not default_cat:
            default_cat = ProductCategory(name="ERP Synced Category")
            db.add(default_cat)
            db.commit()

        # Process Suppliers
        for sup_data in suppliers_data:
            code = sup_data.get("code")
            name = sup_data.get("name")
            if not code or not name:
                errors.append("Invalid ERP supplier record: missing code or name")
                continue
            
            supplier = db.query(Supplier).filter(Supplier.code == code).first()
            if not supplier:
                supplier = Supplier(
                    code=code,
                    name=name,
                    contact_email=sup_data.get("contact_email"),
                    rating=float(sup_data.get("rating", 4.5)),
                    lead_time_avg_days=int(sup_data.get("lead_time_days", 7))
                )
                db.add(supplier)
                processed_suppliers += 1
        db.commit()

        # Process Products
        for prod_data in products_data:
            sku = prod_data.get("sku")
            name = prod_data.get("name")
            cost = prod_data.get("unit_cost")

            if not sku or not name or cost is None:
                errors.append(f"Invalid ERP product record for SKU: {sku}")
                continue

            product = db.query(Product).filter(Product.sku == sku).first()
            if not product:
                product = Product(
                    sku=sku,
                    name=name,
                    category_id=default_cat.id,
                    unit_cost=float(cost),
                    selling_price=float(prod_data.get("selling_price", float(cost) * 1.6)),
                    lead_time_days=int(prod_data.get("lead_time_days", 7)),
                    safety_stock_min=int(prod_data.get("safety_stock", 15)),
                    reorder_point=int(prod_data.get("reorder_point", 30))
                )
                db.add(product)
            else:
                product.unit_cost = float(cost)
                product.selling_price = float(prod_data.get("selling_price", product.selling_price))

            processed_products += 1

        db.commit()

        self.log_event("INFO", f"Synced ERP data: {processed_products} products, {processed_suppliers} suppliers")
        return {
            "status": "SUCCESS" if not errors else "PARTIAL_SUCCESS",
            "synced_products": processed_products,
            "synced_suppliers": processed_suppliers,
            "errors": errors
        }

    def ingest(self, source_data: Any, db_session: Session) -> Dict[str, Any]:
        return self.sync_erp_data(source_data, db_session)
