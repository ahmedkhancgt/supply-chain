import csv
import io
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from connectors.base import BaseConnector
from backend.app.models.models import Product, Warehouse, Inventory, ProductCategory

class CSVIngestionConnector(BaseConnector):
    def __init__(self):
        super().__init__("CSVIngestionConnector")

    def ingest_csv_content(self, csv_string: str, db: Session) -> Dict[str, Any]:
        reader = csv.DictReader(io.StringIO(csv_string))
        processed = 0
        errors: List[str] = []

        # Get default category and warehouse
        default_cat = db.query(ProductCategory).first()
        if not default_cat:
            default_cat = ProductCategory(name="General Ingested Category")
            db.add(default_cat)
            db.commit()

        default_wh = db.query(Warehouse).first()
        if not default_wh:
            default_wh = Warehouse(code="WH-CSV-DEFAULT", name="CSV Import Warehouse", location="Default Location")
            db.add(default_wh)
            db.commit()

        # Load existing products into memory once, instead of querying per row
        existing_products = {p.sku: p for p in db.query(Product).all()}
        existing_inventory = {
            (inv.product_id, inv.warehouse_id): inv
            for inv in db.query(Inventory).filter(Inventory.warehouse_id == default_wh.id).all()
        }

        for idx, row in enumerate(reader, start=1):
            valid, errs = self.validate_record(row, ["sku", "name", "unit_cost", "quantity"])
            if not valid:
                err_msg = f"Row {idx} rejected: {', '.join(errs)}"
                self.log_event("ERROR", err_msg, row)
                errors.append(err_msg)
                continue

            sku = None
            product = None
            created_new_product = False
            created_new_inv = False
            try:
                sku = row["sku"].strip().upper()
                name = row["name"].strip()
                unit_cost = float(row["unit_cost"])
                selling_price = float(row.get("selling_price", unit_cost * 1.5))
                quantity = int(float(row["quantity"]))

                # Check if product exists (in-memory lookup instead of a query per row)
                product = existing_products.get(sku)
                if not product:
                    product = Product(
                        sku=sku,
                        name=name,
                        category_id=default_cat.id,
                        unit_cost=unit_cost,
                        selling_price=selling_price,
                        lead_time_days=int(row.get("lead_time_days", 7)),
                        safety_stock_min=int(row.get("safety_stock", 10)),
                        reorder_point=int(row.get("reorder_point", 25))
                    )
                    db.add(product)
                    db.flush()  # assigns product.id without a full commit round-trip
                    existing_products[sku] = product
                    created_new_product = True

                # Upsert Inventory (in-memory lookup instead of a query per row)
                inv = existing_inventory.get((product.id, default_wh.id))

                if inv:
                    inv.current_stock += quantity
                    inv.available_stock = max(0, inv.current_stock - inv.allocated_stock)
                else:
                    inv = Inventory(
                        product_id=product.id,
                        warehouse_id=default_wh.id,
                        current_stock=quantity,
                        allocated_stock=0,
                        available_stock=quantity,
                        safety_stock=product.safety_stock_min
                    )
                    db.add(inv)
                    existing_inventory[(product.id, default_wh.id)] = inv
                    created_new_inv = True

                # One commit per row (not per lookup): each row previously cost up to 5
                # DB round-trips (2 existence-check SELECTs, an INSERT+COMMIT+REFRESH for
                # new products, plus the inventory COMMIT). The SELECTs are now in-memory
                # dict lookups and the REFRESH is unnecessary since flush() above already
                # populates product.id, so this is down to a single round-trip per row.
                db.commit()
                processed += 1
                self.log_event("INFO", f"Ingested SKU '{sku}' with quantity {quantity}")
            except Exception as e:
                db.rollback()
                # Drop anything this failed row added to the caches: the rollback
                # discarded it from the DB, so a later row with the same SKU must
                # not treat it as already existing.
                if created_new_product and sku:
                    existing_products.pop(sku, None)
                if created_new_inv and product:
                    existing_inventory.pop((product.id, default_wh.id), None)
                err_msg = f"Row {idx} DB Error: {str(e)}"
                self.log_event("ERROR", err_msg)
                errors.append(err_msg)

        return {
            "status": "SUCCESS" if len(errors) == 0 else "PARTIAL_SUCCESS",
            "processed_count": processed,
            "error_count": len(errors),
            "errors": errors,
            "logs": self.logs
        }

    def ingest(self, source_data: Any, db_session: Session) -> Dict[str, Any]:
        if isinstance(source_data, str):
            return self.ingest_csv_content(source_data, db_session)
        raise ValueError("Source data for CSV connector must be a string")
