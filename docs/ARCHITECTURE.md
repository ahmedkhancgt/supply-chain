# Supply Chain AI Decision-Intelligence Platform — Architecture

## 1. System Overview

The Supply Chain AI Decision-Intelligence Platform is a modern enterprise decision-support architecture designed to unify multi-source ERP/WMS data, apply statistical & AI/ML algorithms for demand forecasting and inventory optimization, and expose actionable insights via an interactive Control Tower UI and an LLM ReAct Agent using Model Context Protocol (MCP) tools.

```
+-----------------------------------------------------------------------+
|                             DATA SOURCES                              |
|                CSV Files  |  Mock ERP APIs  |  Mock WMS APIs          |
+-----------------------------------┬-----------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------+
|                         CONNECTORS & INGESTION                        |
|       Schema Validation | Transformation | Audit Log | Sync Engine   |
+-----------------------------------┬-----------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------+
|                              POSTGRESQL                               |
|   Products | Warehouses | Inventory | Sales History | Orders | POs    |
+-----------------------------------┬-----------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------+
|                         PYTHON FASTAPI BACKEND                        |
|       API Routes | Application Services | SQL Repositories            |
+-----------------------------------┬-----------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------+
|                            AI/ML ENGINE                               |
|   Demand Forecasting  |  Safety Stock & ROP  |  Inventory Risk Engine |
+-----------------------------------┬-----------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------+
|                            MCP TOOL SERVER                            |
|             Read-Only Standardized Model Context Protocol Tools        |
+-----------------------------------┬-----------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------+
|                         REACT AGENT & CLAUDE                          |
|         Question Parsing -> Tool Selection -> Decision Execution      |
+-----------------------------------┬-----------------------------------+
                                    │
                                    ▼
+-----------------------------------------------------------------------+
|                        CONTROL TOWER FRONTEND                         |
|   KPI Dashboard | Risk Matrix | Forecast Graphs | AI Assistant Chat   |
+-----------------------------------------------------------------------+
```

## 2. Key Component Responsibilities

### 2.1 Database & Schema
- **PostgreSQL / SQLAlchemy**: Stores normalized supply chain data across 14 entities (`products`, `product_categories`, `warehouses`, `inventory`, `inventory_transactions`, `sales_history`, `orders`, `order_items`, `suppliers`, `supplier_products`, `purchase_orders`, `purchase_order_items`, `shipments`, `customers`).
- Enforces relational constraints, timestamps (`created_at`, `updated_at`), foreign keys, and indexes on SKUs and warehouse IDs.

### 2.2 Ingestion & Connectors
- Interfaces for CSV, ERP, and WMS sources.
- Data validation engine handling bad SKUs, negative quantities, missing lead times, and writing execution audit logs.

### 2.3 AI/ML Engine
- **Demand Forecasting**: Uses Pandas, NumPy, Statsmodels, Scikit-learn for time-series forecasting (moving averages, trend decomposition, exponential smoothing).
- **Inventory Optimization**: Computes safety stock ($SS = Z \cdot \sigma \cdot \sqrt{L}$), Reorder Point ($ROP = D \cdot L + SS$), and Recommended Order Quantity ($ROQ = \max(0, ROP + SS - Stock)$).
- **Inventory Risk**: Categorizes inventory status into `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`.

### 2.4 MCP & ReAct Agent Layer
- Pure Python MCP server providing safe, read-only tools to the ReAct agent.
- Claude GenAI Provider interprets queries, chooses MCP tools, analyzes output, and returns evidence-backed recommendations to the user.

### 2.5 Control Tower Frontend
- React / Vite SPA rendering real-time KPI metrics, stockout alerts, demand trends, purchase order recommendations, and an integrated AI assistant.
