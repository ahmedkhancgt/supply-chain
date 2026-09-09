from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.models.models import (
    Product, Warehouse, Inventory, SalesHistory, Supplier, Order, PurchaseOrder, ProductCategory
)

class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Product]:
        return self.db.query(Product).offset(skip).limit(limit).all()

    def get_by_id(self, product_id: int) -> Optional[Product]:
        return self.db.query(Product).filter(Product.id == product_id).first()

    def get_by_sku(self, sku: str) -> Optional[Product]:
        return self.db.query(Product).filter(Product.sku == sku.upper()).first()

class WarehouseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[Warehouse]:
        return self.db.query(Warehouse).all()

    def get_by_id(self, warehouse_id: int) -> Optional[Warehouse]:
        return self.db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()

class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, warehouse_id: Optional[int] = None) -> List[Inventory]:
        query = self.db.query(Inventory)
        if warehouse_id:
            query = query.filter(Inventory.warehouse_id == warehouse_id)
        return query.all()

    def get_by_product_and_warehouse(self, product_id: int, warehouse_id: int) -> Optional[Inventory]:
        return self.db.query(Inventory).filter(
            Inventory.product_id == product_id,
            Inventory.warehouse_id == warehouse_id
        ).first()

class SalesRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_product(self, product_id: int, warehouse_id: Optional[int] = None, days: int = 90) -> List[SalesHistory]:
        query = self.db.query(SalesHistory).filter(SalesHistory.product_id == product_id)
        if warehouse_id:
            query = query.filter(SalesHistory.warehouse_id == warehouse_id)
        return query.order_by(SalesHistory.date.desc()).limit(days).all()

class SupplierRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[Supplier]:
        return self.db.query(Supplier).all()

    def get_by_id(self, supplier_id: int) -> Optional[Supplier]:
        return self.db.query(Supplier).filter(Supplier.id == supplier_id).first()
