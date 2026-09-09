# Supply Chain AI Decision-Intelligence — Phase-1 POC Scope

## 1. Scope Objectives

The Phase-1 POC establishes a working decision-intelligence system for Supply Chain control, focusing on:
1. **Demand Forecasting**: Predicting SKU-level demand per warehouse from historical sales.
2. **Inventory Optimization**: Calculating Safety Stock, Reorder Points, and Stockout Risks.
3. **Control Tower**: Providing unified visibility and AI Chat capabilities.

## 2. In-Scope Modules & Features

- **Database**: PostgreSQL / SQLite with 14 key tables & 50+ realistic products, multi-warehouse seed data.
- **Connectors**:
  - CSV file ingestion pipeline with validation log
  - Mock ERP REST API connector
  - Mock WMS REST API connector
- **FastAPI Backend**:
  - Core domain APIs for Products, Warehouses, Inventory, Orders, Suppliers, Sales
  - ML Forecast & Optimization endpoints
  - AI Agent chat endpoint (`/api/ai/chat`)
- **AI/ML Engine**:
  - Time-series demand forecasting engine
  - Formulaic safety stock & reorder point calculator
  - Multi-dimensional inventory risk categorizer (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`)
- **MCP Server**:
  - Python MCP server exposing 12 read-only tools
- **ReAct Agent & GenAI Integration**:
  - Tool selection & reasoning loop
  - Claude provider + local fallback mock provider
- **Control Tower UI**:
  - Modern React dashboard with KPI cards, risk matrix, forecast graphs, recommendations, AI Chat drawer.
- **BI Integration**:
  - PowerBI / Tableau export adapter.
- **Testing & Deployment**:
  - Pytest test suite (unit + E2E)
  - Docker Compose setup (`docker-compose.yml`)

## 3. Out-of-Scope (Future Phases)

- Live enterprise SAP/Oracle connectors (mock adapters provided).
- Multi-echelon dynamic network optimization (placeholder interfaces provided).
- Real-time IoT sensor telemetry streams.
