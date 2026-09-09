import os
import csv
import random
from datetime import datetime, timedelta
import psycopg2

# Target AWS RDS PostgreSQL connection credentials
HOST = "database-2.c90s8acs6gvg.eu-west-2.rds.amazonaws.com"
PORT = 5432
DATABASE = "postgres"
USER = "postgres"
PASSWORD = "StrongPassword123!"

# Output directory for CSV exports
OUTPUT_DIR = "./exported_supply_chain_data"

def create_tables_and_seed():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"🔌 Connecting to AWS RDS PostgreSQL: {HOST}:{PORT}/{DATABASE}...")

    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=DATABASE,
        user=USER,
        password=PASSWORD,
        connect_timeout=15
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("🛠️ Re-creating expanded Supply Chain schema...")
    cur.execute("""
        DROP TABLE IF EXISTS sales_history CASCADE;
        DROP TABLE IF EXISTS inventory CASCADE;
        DROP TABLE IF EXISTS products CASCADE;
        DROP TABLE IF EXISTS warehouses CASCADE;
        DROP TABLE IF EXISTS suppliers CASCADE;
        DROP TABLE IF EXISTS categories CASCADE;

        CREATE TABLE categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT
        );

        CREATE TABLE products (
            id SERIAL PRIMARY KEY,
            sku VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            category_id INT REFERENCES categories(id),
            unit VARCHAR(20) DEFAULT 'units',
            unit_cost NUMERIC(10,2) NOT NULL,
            selling_price NUMERIC(10,2) NOT NULL,
            lead_time_days INT DEFAULT 7,
            safety_stock_min INT DEFAULT 15,
            reorder_point INT DEFAULT 30,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE warehouses (
            id SERIAL PRIMARY KEY,
            code VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            location VARCHAR(100) NOT NULL,
            capacity_sqft INT DEFAULT 50000
        );

        CREATE TABLE inventory (
            id SERIAL PRIMARY KEY,
            product_id INT REFERENCES products(id),
            warehouse_id INT REFERENCES warehouses(id),
            current_stock INT NOT NULL DEFAULT 0,
            allocated_stock INT NOT NULL DEFAULT 0,
            available_stock INT NOT NULL DEFAULT 0,
            safety_stock INT NOT NULL DEFAULT 15,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_product_warehouse UNIQUE (product_id, warehouse_id)
        );

        CREATE TABLE suppliers (
            id SERIAL PRIMARY KEY,
            code VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            contact_email VARCHAR(100),
            rating NUMERIC(3,2) DEFAULT 4.5,
            lead_time_avg_days INT DEFAULT 7
        );

        CREATE TABLE sales_history (
            id SERIAL PRIMARY KEY,
            product_id INT REFERENCES products(id),
            warehouse_id INT REFERENCES warehouses(id),
            sale_date DATE NOT NULL,
            quantity_sold INT NOT NULL,
            unit_price NUMERIC(10,2) NOT NULL,
            revenue NUMERIC(12,2) NOT NULL
        );
    """)

    print("🌱 Populating 25+ Products, 5 Warehouses, 8 Suppliers, and 500 Sales Transactions...")

    # 1. Categories
    categories_data = [
        ("Pharmaceuticals & Healthcare", "Essential medicines, vaccines and medical equipment"),
        ("Consumer Electronics", "Smartphones, laptops, accessories and audio gear"),
        ("FMCG & Groceries", "Packaged foods, beverages and household essentials"),
        ("Apparel & Footwear", "Fashion apparel, footwear and accessories"),
        ("Industrial Components", "Precision tools, mechanical spares and hardware")
    ]
    cur.executemany("INSERT INTO categories (name, description) VALUES (%s, %s);", categories_data)

    # 2. Warehouses
    warehouses_data = [
        ("WH-LON-01", "London Logistics Hub", "London, UK", 85000),
        ("WH-DXB-01", "Dubai Gateway Logistics", "Dubai, UAE", 150000),
        ("WH-SIN-01", "Singapore Distribution Center", "Singapore", 110000),
        ("WH-NYC-01", "New York Fulfillment Center", "New York, USA", 140000),
        ("WH-FRA-01", "Frankfurt Air Hub", "Frankfurt, Germany", 90000)
    ]
    cur.executemany("INSERT INTO warehouses (code, name, location, capacity_sqft) VALUES (%s, %s, %s, %s);", warehouses_data)

    # 3. Suppliers
    suppliers_data = [
        ("SUP-MED-01", "Astra Pharma Global", "orders@astrapharma.com", 4.85, 4),
        ("SUP-MED-02", "Pfizer Health Supplies", "supply@pfizerhealth.com", 4.90, 5),
        ("SUP-ELEC-01", "TechTronix Asia Ltd", "sales@techtronix.io", 4.65, 8),
        ("SUP-ELEC-02", "Samsung Electro Components", "b2b@samsungcomponents.com", 4.78, 7),
        ("SUP-FMCG-01", "Unilever FMCG Supply", "distribution@unilever.com", 4.92, 3),
        ("SUP-FMCG-02", "Nestlé Logistics EMEA", "orders@nestlelogistics.com", 4.88, 3),
        ("SUP-APP-01", "Nike Supply Chain Co", "orders@nikesupply.com", 4.70, 6),
        ("SUP-IND-01", "Bosch Industrial Spares", "support@boschspares.com", 4.82, 10)
    ]
    cur.executemany("INSERT INTO suppliers (code, name, contact_email, rating, lead_time_avg_days) VALUES (%s, %s, %s, %s, %s);", suppliers_data)

    # 4. Products (20 SKUs)
    products_data = [
        ("SKU-PHA-501", "Paracetamol 500mg Tablets (100s)", 1, "pack", 4.50, 12.00, 5, 100, 250),
        ("SKU-PHA-502", "Amoxicillin 250mg Antibiotic", 1, "box", 8.20, 24.50, 7, 50, 120),
        ("SKU-PHA-503", "Ibuprofen 400mg Anti-inflammatory", 1, "pack", 3.80, 9.99, 4, 80, 200),
        ("SKU-PHA-504", "Vitamin C 1000mg Effervescent", 1, "tube", 2.90, 7.50, 5, 120, 300),
        ("SKU-PHA-505", "Digital Infrared Thermometer", 1, "unit", 14.50, 39.99, 8, 30, 75),

        ("SKU-ELEC-601", "Wireless Active Noise-Canceling Headphones", 2, "unit", 45.00, 129.99, 9, 20, 50),
        ("SKU-ELEC-602", "Smart USB-C Fast Charger 65W", 2, "unit", 12.50, 34.99, 7, 40, 100),
        ("SKU-ELEC-603", "Bluetooth Portable Speaker 20W", 2, "unit", 22.00, 59.99, 8, 25, 60),
        ("SKU-ELEC-604", "Ultra-Wide 27-inch 4K Monitor", 2, "unit", 180.00, 349.99, 12, 10, 25),
        ("SKU-ELEC-605", "Mechanical Gaming Keyboard RGB", 2, "unit", 35.00, 89.99, 8, 15, 40),

        ("SKU-FMCG-701", "Organic Almond Milk 1L", 3, "carton", 1.80, 4.50, 3, 150, 400),
        ("SKU-FMCG-702", "Premium Arabica Coffee Beans 500g", 3, "bag", 6.50, 16.99, 5, 80, 200),
        ("SKU-FMCG-703", "Extra Virgin Olive Oil 750ml", 3, "bottle", 5.20, 13.50, 6, 60, 150),
        ("SKU-FMCG-704", "Gluten-Free Oats 1kg", 3, "bag", 2.10, 5.25, 4, 100, 250),
        ("SKU-FMCG-705", "Dark Chocolate 85% Cocoa 100g", 3, "bar", 1.20, 3.49, 4, 200, 500),

        ("SKU-APP-801", "Performance Running Shoes Men Size 10", 4, "pair", 38.00, 110.00, 8, 25, 60),
        ("SKU-APP-802", "Breathable Athletic Socks (3-Pack)", 4, "pack", 3.50, 12.99, 5, 100, 250),
        ("SKU-APP-803", "Waterproof Outdoor Jacket XL", 4, "unit", 42.00, 125.00, 10, 15, 40),

        ("SKU-IND-901", "High-Precision Ball Bearing Set", 5, "set", 18.50, 45.00, 10, 40, 90),
        ("SKU-IND-902", "Industrial Hydraulic Pressure Valve", 5, "unit", 85.00, 210.00, 14, 8, 20)
    ]
    
    prod_id_map = {}
    prod_cost_map = {}

    for p in products_data:
        cur.execute("""
            INSERT INTO products (sku, name, category_id, unit, unit_cost, selling_price, lead_time_days, safety_stock_min, reorder_point)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, sku, unit_cost, selling_price;
        """, p)
        row = cur.fetchone()
        prod_id_map[row[1]] = row[0]
        prod_cost_map[row[0]] = (float(row[2]), float(row[3]))

    cur.execute("SELECT id, code FROM warehouses;")
    whs = cur.fetchall()
    wh_ids = [r[0] for r in whs]
    wh_id_map = {row[1]: row[0] for row in whs}

    # 5. Inventory Items (Product x Warehouse cross product with realistic stock)
    inventory_data = []
    for prod_sku, prod_id in prod_id_map.items():
        for wh_code, wh_id in wh_id_map.items():
            current = random.choice([12, 18, 45, 85, 140, 280, 520, 1200])
            alloc = random.randint(2, min(20, current))
            avail = max(0, current - alloc)
            safety = random.choice([15, 30, 50, 100])
            inventory_data.append((prod_id, wh_id, current, alloc, avail, safety))

    cur.executemany("""
        INSERT INTO inventory (product_id, warehouse_id, current_stock, allocated_stock, available_stock, safety_stock)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, inventory_data)

    # 6. Sales History (500+ records over past 30 days)
    sales_data = []
    base_date = datetime.now().date()
    for day in range(30):
        s_date = base_date - timedelta(days=day)
        for prod_id, (cost, price) in prod_cost_map.items():
            wh_id = random.choice(wh_ids)
            qty = random.randint(5, 45)
            rev = round(qty * price, 2)
            sales_data.append((prod_id, wh_id, s_date, qty, price, rev))

    cur.executemany("""
        INSERT INTO sales_history (product_id, warehouse_id, sale_date, quantity_sold, unit_price, revenue)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, sales_data)

    print(f"📄 Exporting 5 CSV files to {OUTPUT_DIR}...")
    
    # 1. products.csv
    cur.execute("SELECT p.id, p.sku, p.name, c.name as category, p.unit, p.unit_cost, p.selling_price, p.lead_time_days, p.safety_stock_min, p.reorder_point FROM products p JOIN categories c ON p.category_id = c.id;")
    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    with open(f"{OUTPUT_DIR}/products.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        writer.writerows(rows)

    # 2. inventory.csv
    cur.execute("SELECT i.id, p.sku, p.name as product_name, w.code as warehouse_code, w.name as warehouse_name, i.current_stock, i.available_stock, i.safety_stock FROM inventory i JOIN products p ON i.product_id = p.id JOIN warehouses w ON i.warehouse_id = w.id;")
    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    with open(f"{OUTPUT_DIR}/inventory.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        writer.writerows(rows)

    # 3. suppliers.csv
    cur.execute("SELECT id, code, name, contact_email, rating, lead_time_avg_days FROM suppliers;")
    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    with open(f"{OUTPUT_DIR}/suppliers.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        writer.writerows(rows)

    # 4. sales_history.csv
    cur.execute("SELECT s.id, p.sku, p.name as product_name, w.code as warehouse_code, s.sale_date, s.quantity_sold, s.unit_price, s.revenue FROM sales_history s JOIN products p ON s.product_id = p.id JOIN warehouses w ON s.warehouse_id = w.id;")
    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    with open(f"{OUTPUT_DIR}/sales_history.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        writer.writerows(rows)

    # 5. warehouses.csv
    cur.execute("SELECT id, code, name, location, capacity_sqft FROM warehouses;")
    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    with open(f"{OUTPUT_DIR}/warehouses.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        writer.writerows(rows)

    print("🎉 SUCCESS! AWS RDS PostgreSQL database expanded with 20 Products, 5 Warehouses, 8 Suppliers, and 600 Sales Transactions. All 5 CSV files exported successfully!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    try:
        create_tables_and_seed()
    except Exception as e:
        print(f"❌ Error seeding RDS database: {e}")
