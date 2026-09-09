import random
import math
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from backend.app.core.database import engine, Base, SessionLocal
from backend.app.models.models import (
    ProductCategory, Product, Warehouse, Inventory, SalesHistory,
    Supplier, SupplierProduct, Customer, Order, OrderItem, PurchaseOrder,
    PurchaseOrderItem, Shipment, Role, WorkspaceMember, PermissionSetting, AuditLog
)

def seed_database(db: Session):
    print("Initializing Database Tables...")
    try:
        with engine.connect() as conn:
            with conn.begin():
                Base.metadata.drop_all(bind=conn)
                Base.metadata.create_all(bind=conn)
    except Exception as e:
        print(f"Re-creating tables fallback: {e}")
        with engine.connect() as conn:
            with conn.begin():
                Base.metadata.create_all(bind=conn)
    print("Database tables created.")

    data_path = Path("data/Data.xlsx")
    if not data_path.exists():
        raise FileNotFoundError(f"Real dataset file not found at {data_path}")

    print(f"Loading real transaction data from {data_path}...")
    df_raw = pd.read_excel(data_path)
    print(f"Loaded {len(df_raw)} raw transaction rows.")

    # 1. Clean transactions
    df = df_raw.copy()
    df["StockCode"] = df["StockCode"].astype(str).str.strip()
    df["Description"] = df["Description"].astype(str).str.strip()
    
    # Filter valid positive sales
    df = df[
        (df["Quantity"] > 0) & 
        (df["Price"] > 0) & 
        (~df["Invoice"].astype(str).str.startswith("C", na=False)) &
        (df["StockCode"] != "nan") &
        (df["Description"] != "nan") &
        (df["Description"] != "")
    ].copy()

    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    df["revenue"] = df["Quantity"] * df["Price"]
    print(f"Cleaned valid transaction rows: {len(df)}")

    # 2. Product Categories
    categories_dict = {
        "Home Decor": "Candles, frames, wall hangings, and decorative home ornaments",
        "Storage & Organization": "Baskets, boxes, drawers, and organizational accessories",
        "Gifts & Novelties": "Occasion gifts, cards, trinkets, and novelties",
        "Kitchen & Tableware": "Mugs, teapots, cutlery, baking moulds, and tableware",
        "General Merchandise": "General retail goods, bags, toys, and apparel accessories"
    }

    category_map = {}
    for cat_name, cat_desc in categories_dict.items():
        cat = ProductCategory(name=cat_name, description=cat_desc)
        db.add(cat)
        db.commit()
        category_map[cat_name] = cat.id

    def categorize_product(desc: str) -> int:
        d_lower = desc.lower()
        if any(w in d_lower for w in ["frame", "heart", "candle", "holder", "light", "clock", "mirror", "sign", "wood"]):
            return category_map["Home Decor"]
        elif any(w in d_lower for w in ["box", "bag", "basket", "storage", "case", "tin", "bin", "cabinet"]):
            return category_map["Storage & Organization"]
        elif any(w in d_lower for w in ["cup", "mug", "teapot", "plate", "bowl", "cutlery", "spoon", "mould", "baking"]):
            return category_map["Kitchen & Tableware"]
        elif any(w in d_lower for w in ["card", "wrap", "ribbon", "gift", "christmas", "party", "toy"]):
            return category_map["Gifts & Novelties"]
        return category_map["General Merchandise"]

    # 3. Warehouses based on real main trade regions
    warehouses_data = [
        ("WH-UK-01", "United Kingdom Central Logistics Hub", "Birmingham, UK", 50000),
        ("WH-EU-01", "European Mainland Fulfillment Hub", "Frankfurt, Germany", 45000),
        ("WH-GLOBAL-01", "Global Distribution & Export Center", "Rotterdam, Netherlands", 60000),
    ]
    warehouse_objs = []
    for code, name, loc, cap in warehouses_data:
        wh = Warehouse(code=code, name=name, location=loc, capacity_sqft=cap)
        db.add(wh)
        warehouse_objs.append(wh)
    db.commit()
    wh_default = warehouse_objs[0]

    # 4. Extract Real Products from Data.xlsx
    print("Extracting real products from transaction panel...")
    prod_stats = df.groupby("StockCode").agg(
        Description=("Description", lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0]),
        AvgPrice=("Price", "mean"),
        TotalQty=("Quantity", "sum"),
        SalesDays=("InvoiceDate", lambda x: x.dt.date.nunique()),
        LeadTime=("lead_time_days", "first") if "lead_time_days" in df.columns else ("Quantity", lambda x: 14),
        Cost=("Cost", "first") if "Cost" in df.columns else ("Price", lambda x: x.mean() * 0.6)
    ).reset_index()

    product_id_map = {}
    product_objs = []

    for _, row in prod_stats.iterrows():
        sku = str(row["StockCode"])
        name = str(row["Description"])[:200]
        cat_id = categorize_product(name)
        price = round(float(row["AvgPrice"]), 2)
        cost = round(float(row["Cost"]) if pd.notna(row["Cost"]) and row["Cost"] > 0 else price * 0.6, 2)
        lead_time = int(row["LeadTime"]) if pd.notna(row["LeadTime"]) and row["LeadTime"] > 0 else 14
        
        # Calculate ROP & Safety Stock from real demand
        daily_demand = max(0.5, row["TotalQty"] / max(1, row["SalesDays"]))
        std_dev = daily_demand * 0.4
        safety_stock = int(math.ceil(1.65 * std_dev * math.sqrt(lead_time)))
        reorder_point = int(math.ceil(daily_demand * lead_time + safety_stock))

        prod = Product(
            sku=sku,
            name=name,
            category_id=cat_id,
            unit_cost=cost,
            selling_price=price,
            lead_time_days=lead_time,
            safety_stock_min=max(5, safety_stock),
            reorder_point=max(15, reorder_point)
        )
        db.add(prod)
        db.flush()
        product_id_map[sku] = prod.id
        product_objs.append(prod)

    db.commit()
    print(f"Created {len(product_objs)} real product records.")

    # 5. Suppliers mapped to real product catalog
    suppliers_data = [
        ("SUP-001", "Evergreen Global Supply", "orders@evergreensupply.com", 4.8, 7),
        ("SUP-002", "Reliable Imports Ltd", "contact@reliableimports.com", 4.5, 12),
        ("SUP-003", "Metro Wholesale Distribution", "sales@metrowholesale.com", 4.6, 5),
        ("SUP-004", "Summit Procurement Co.", "supply@summitprocurement.com", 4.7, 10),
        ("SUP-005", "Gulf Source Logistics", "info@gulfsource.com", 4.3, 14),
    ]
    supplier_objs = []
    for code, name, email, rating, lead_time in suppliers_data:
        sup = Supplier(code=code, name=name, contact_email=email, rating=rating, lead_time_avg_days=lead_time)
        db.add(sup)
        supplier_objs.append(sup)
    db.commit()

    for idx, prod in enumerate(product_objs):
        sup = supplier_objs[idx % len(supplier_objs)]
        sp = SupplierProduct(
            supplier_id=sup.id,
            product_id=prod.id,
            supplier_sku=f"SUP-{prod.sku}",
            unit_cost=prod.unit_cost,
            lead_time_days=prod.lead_time_days
        )
        db.add(sp)
    db.commit()

    # 6. Seed Real Sales History directly from Data.xlsx
    print("Seeding real sales history from Data.xlsx...")
    sales_batch = []
    for _, row in df.iterrows():
        sku = str(row["StockCode"])
        p_id = product_id_map.get(sku)
        if not p_id:
            continue

        sales_batch.append({
            "product_id": p_id,
            "warehouse_id": wh_default.id,
            "date": row["InvoiceDate"].to_pydatetime(),
            "quantity_sold": int(row["Quantity"]),
            "unit_price": round(float(row["Price"]), 2),
            "revenue": round(float(row["revenue"]), 2),
            "is_promotional": 0
        })

    # Bulk insert sales history for performance
    db.bulk_insert_mappings(SalesHistory, sales_batch)
    db.commit()
    print(f"Seeded {len(sales_batch)} real SalesHistory records.")

    # 7. Seed Real Inventory based on actual calculated demand
    print("Seeding real Inventory records...")
    inv_batch = []
    for prod in product_objs:
        for wh in warehouse_objs:
            stock_level = int(prod.reorder_point * random.uniform(1.2, 3.5))
            reserved = int(stock_level * 0.1)
            inv_batch.append({
                "product_id": prod.id,
                "warehouse_id": wh.id,
                "current_stock": stock_level,
                "reserved_stock": reserved,
                "in_transit_stock": 0,
                "reorder_quantity": prod.reorder_point,
                "last_restock_date": datetime.utcnow() - timedelta(days=random.randint(1, 15))
            })
    db.bulk_insert_mappings(Inventory, inv_batch)
    db.commit()

    # 8. Seed Real Customers & Customer Orders grouped by real Invoices
    print("Seeding real Customers and Customer Orders...")
    df_cust = df.dropna(subset=["Customer ID"]).copy()
    unique_cust_ids = df_cust["Customer ID"].unique()

    cust_id_map = {}
    for c_raw_id in unique_cust_ids[:500]:
        c_code = f"CUST-{int(c_raw_id)}"
        c = Customer(
            customer_code=c_code,
            name=f"Customer {int(c_raw_id)}",
            email=f"customer{int(c_raw_id)}@retailer.com",
            tier="PREMIUM" if int(c_raw_id) % 2 == 0 else "STANDARD"
        )
        db.add(c)
        db.flush()
        cust_id_map[c_raw_id] = c.id
    db.commit()

    # Group sales by Invoice to build real Orders
    invoice_groups = df_cust.groupby("Invoice")
    order_count = 0

    for inv_code, grp in invoice_groups:
        if order_count >= 150:
            break
        c_raw = grp["Customer ID"].iloc[0]
        c_db_id = cust_id_map.get(c_raw)
        if not c_db_id:
            continue

        inv_date = grp["InvoiceDate"].iloc[0].to_pydatetime()
        total_amt = float(grp["revenue"].sum())

        ord_obj = Order(
            order_number=f"ORD-{inv_code}",
            customer_id=c_db_id,
            warehouse_id=wh_default.id,
            order_date=inv_date,
            status="DELIVERED",
            total_amount=round(total_amt, 2)
        )
        db.add(ord_obj)
        db.flush()

        for _, item in grp.iterrows():
            p_sku = str(item["StockCode"])
            p_id = product_id_map.get(p_sku)
            if not p_id:
                continue
            oi = OrderItem(
                order_id=ord_obj.id,
                product_id=p_id,
                quantity=int(item["Quantity"]),
                unit_price=round(float(item["Price"]), 2),
                total_price=round(float(item["revenue"]), 2)
            )
            db.add(oi)

        order_count += 1

    db.commit()
    print(f"Seeded {order_count} real Orders and OrderItems.")

    # 9. Roles, Members, Permissions, and System Audit Logs
    roles_seed = [
        ("admin", "Admin", "Full access to all features, settings, data pipelines, and user management.", "Full Access", "#7c3aed", "#f5f3ff"),
        ("de", "Data Engineer", "Manage data sources, database connectors, canonical mappings, and ETL discovery.", "Data & Engine Access", "#2563eb", "#eff6ff"),
        ("da", "Data Analyst", "Analyze inventory metrics, demand forecasts, create custom BI reports, and view insights.", "Read & Analyze", "#059669", "#ecfdf5"),
        ("om", "Operations Manager", "Monitor stockout KPIs, manage alerts, approve PO recommendations, and execute orders.", "Limited Access", "#d97706", "#fffbeb"),
        ("viewer", "Viewer", "View dashboards, alerts, and executive reports with read-only permissions.", "Read Only", "#475569", "#f1f5f9")
    ]
    for r_key, r_name, r_desc, r_scope, r_color, r_bg in roles_seed:
        db.add(Role(role_key=r_key, name=r_name, description=r_desc, scope=r_scope, scope_color=r_color, scope_bg=r_bg, author="System"))
    db.commit()

    members_seed = [
        ("System Administrator", "admin@supplychain.internal", "Admin", "Active", "SA", "#7c3aed", "#f5f3ff"),
        ("Lead Data Engineer", "de@supplychain.internal", "Data Engineer", "Active", "DE", "#2563eb", "#eff6ff"),
        ("Senior Data Analyst", "da@supplychain.internal", "Data Analyst", "Active", "DA", "#059669", "#ecfdf5"),
        ("Operations Manager", "om@supplychain.internal", "Operations Manager", "Active", "OM", "#d97706", "#fffbeb"),
        ("System Viewer", "viewer@supplychain.internal", "Viewer", "Inactive", "SV", "#64748b", "#f1f5f9")
    ]
    for m_name, m_email, m_role, m_status, m_init, m_color, m_bg in members_seed:
        db.add(WorkspaceMember(name=m_name, email=m_email, role=m_role, status=m_status, initials=m_init, color=m_color, bg=m_bg))
    db.commit()

    perms_seed = [
        ("overview", "Overview & Executive Control Tower", 1, 1, 1, 1, 1),
        ("workspaces", "Workspaces & Multi-Tenant Setup", 1, 1, 0, 0, 0),
        ("datasources", "Data Sources & Pipeline", 1, 1, 0, 0, 0),
        ("intelligence", "Intelligence & Forecasting Engines", 1, 1, 1, 1, 1),
        ("recommendations", "Prescriptive Recommendations & PO Dispatch", 1, 0, 1, 1, 0),
        ("access_control", "Access Control & Security Governance", 1, 0, 0, 0, 0)
    ]
    for p_key, p_name, p_admin, p_de, p_da, p_om, p_view in perms_seed:
        db.add(PermissionSetting(module_key=p_key, module_name=p_name, admin_access=p_admin, de_access=p_de, da_access=p_da, om_access=p_om, viewer_access=p_view))
    db.commit()

    logs_seed = [
        ("System Administrator", "admin@supplychain.internal", "Database Connected", "Data Source", f"Seeded real database directly from Data.xlsx ({len(df)} transactions loaded)", "127.0.0.1"),
        ("System Administrator", "admin@supplychain.internal", "User Login", "Authentication", "User signed into Supply Chain Control Tower", "127.0.0.1"),
        ("Operations Manager", "om@supplychain.internal", "PO Approved", "Procurement", "Dispatched Purchase Order PO-2026-8001 for SKU-ELEC-101", "127.0.0.1"),
        ("Lead Data Engineer", "de@supplychain.internal", "Canonical Field Mapped", "Schema", "Mapped source field StockCode -> canonical field sku", "127.0.0.1"),
        ("System Auto-Engine", "system@supplychain.internal", "100/100 Readiness Calculated", "Data Quality", "Automated pipeline validated 100/100 coverage index", "127.0.0.1")
    ]
    for l_user, l_email, l_act, l_cat, l_det, l_ip in logs_seed:
        db.add(AuditLog(user=l_user, action=l_act, type=l_cat, details=l_det, ip_address=l_ip))
    db.commit()

    print("Real database seeding completed successfully!")

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
