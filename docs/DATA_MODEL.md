# Supply Chain Data Model Specification

## Entity-Relationship Diagram Overview

The database schema models a multi-echelon retail/industrial supply chain with 14 normalized entities:

```
[ ProductCategory ] 1 ──── N [ Product ] 1 ──── N [ Inventory ] N ──── 1 [ Warehouse ]
                                 │                      │                      │
                                 ├── 1 ── N [ Sales ]   ├── 1 ── N [ Orders ] ─┼─ 1 ── 1 [ Shipment ]
                                 │                      │            │         │
                                 ├── N ── N [ Supplier ]┼────────────┼─────────┘
                                 │                      │            │
                                 └── 1 ── N [ PO Items ]┘            └── 1 ── N [ Order Items ]
```

## Entity Schema Specifications

### 1. `product_categories`
- `id` (PK, Int): Primary key.
- `name` (String 100, Unique): Category title.
- `description` (Text): Details.

### 2. `products`
- `id` (PK, Int): Primary key.
- `sku` (String 50, Unique, Indexed): Stock keeping unit identifier.
- `name` (String 200): Product name.
- `category_id` (FK -> product_categories.id): Category reference.
- `unit_cost` (Float): Cost per unit.
- `selling_price` (Float): Retail price per unit.
- `lead_time_days` (Int): Supplier procurement lead time in days.
- `safety_stock_min` (Int): Baseline min safety stock threshold.
- `reorder_point` (Int): Reorder point trigger level.

### 3. `warehouses`
- `id` (PK, Int): Primary key.
- `code` (String 50, Unique, Indexed): Hub code (e.g. `WH-BLR-01`).
- `name` (String 150): Warehouse title.
- `location` (String 200): Geographic location.
- `capacity` (Int): Storage unit capacity.

### 4. `inventory`
- `id` (PK, Int): Primary key.
- `product_id` (FK -> products.id, Indexed)
- `warehouse_id` (FK -> warehouses.id, Indexed)
- `current_stock` (Int): Total physical units present.
- `allocated_stock` (Int): Reserved units for pending orders.
- `available_stock` (Int): `current_stock - allocated_stock`.
- `safety_stock` (Int): Target safety stock.

### 5. `sales_history`
- `id` (PK, Int): Primary key.
- `product_id` (FK -> products.id, Indexed)
- `warehouse_id` (FK -> warehouses.id, Indexed)
- `date` (DateTime, Indexed): Transaction date.
- `quantity_sold` (Int): Units sold.
- `revenue` (Float): Revenue total.

### 6–14. Additional Entities
- `inventory_transactions`: Audit log of inbound/outbound stock movements.
- `suppliers`: Vendor metadata & rating.
- `supplier_products`: Contracted vendor pricing & lead times.
- `customers`: Buyer details & region.
- `orders` & `order_items`: Sales order headers & line items.
- `purchase_orders` & `purchase_order_items`: Replenishment POs.
- `shipments`: Tracking status & carrier delivery schedules.
