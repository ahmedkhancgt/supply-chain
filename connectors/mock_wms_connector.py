from typing import Dict, Any, List
from sqlalchemy.orm import Session
from connectors.base import BaseConnector
from backend.app.models.models import Product, Warehouse, Inventory, InventoryTransaction

class MockWMSConnector(BaseConnector):
    def __init__(self):
        super().__init__("MockWMSConnector")

    def sync_wms_inventory(self, wms_payload: Dict[str, Any], db: Session) -> Dict[str, Any]:
        """
        Consumes payload simulating external WMS (Manhattan / HighJump / BlueYonder).
        Payload contains: warehouse_code, inventory_levels [{sku, current_stock, allocated_stock}]
        """
        wh_code = wms_payload.get("warehouse_code")
        inventory_levels = wms_payload.get("inventory_levels", [])

        if not wh_code:
            return {"status": "ERROR", "message": "Missing warehouse_code in WMS payload"}

        warehouse = db.query(Warehouse).filter(Warehouse.code == wh_code).first()
        if not warehouse:
            return {"status": "ERROR", "message": f"Warehouse with code '{wh_code}' not found"}

        updated_count = 0
        errors: List[str] = []

        for item in inventory_levels:
            sku = item.get("sku")
            stock = item.get("current_stock")
            allocated = item.get("allocated_stock", 0)

            if not sku or stock is None:
                errors.append(f"Invalid item format for SKU: {sku}")
                continue

            product = db.query(Product).filter(Product.sku == sku).first()
            if not product:
                errors.append(f"Product SKU '{sku}' not found in database")
                continue

            inv = db.query(Inventory).filter(
                Inventory.product_id == product.id,
                Inventory.warehouse_id == warehouse.id
            ).first()

            old_stock = inv.current_stock if inv else 0
            new_stock = int(stock)
            qty_delta = new_stock - old_stock

            if inv:
                inv.current_stock = new_stock
                inv.allocated_stock = int(allocated)
                inv.available_stock = max(0, new_stock - int(allocated))
            else:
                inv = Inventory(
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    current_stock=new_stock,
                    allocated_stock=int(allocated),
                    available_stock=max(0, new_stock - int(allocated)),
                    safety_stock=product.safety_stock_min
                )
                db.add(inv)

            # Record Inventory Transaction
            if qty_delta != 0:
                tx_type = "INBOUND" if qty_delta > 0 else "OUTBOUND"
                tx = InventoryTransaction(
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    transaction_type=tx_type,
                    quantity=abs(qty_delta),
                    reference_id=f"WMS-SYNC-{warehouse.code}"
                )
                db.add(tx)

            updated_count += 1

        db.commit()

        self.log_event("INFO", f"Synced WMS inventory for warehouse '{wh_code}': {updated_count} items updated")
        return {
            "status": "SUCCESS" if not errors else "PARTIAL_SUCCESS",
            "warehouse": wh_code,
            "items_updated": updated_count,
            "errors": errors
        }

    def ingest(self, source_data: Any, db_session: Session) -> Dict[str, Any]:
        return self.sync_wms_inventory(source_data, db_session)
