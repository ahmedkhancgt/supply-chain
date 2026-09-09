# Supply Chain AI Decision-Intelligence — Development Plan

## Phase 1 Execution Roadmap (20 Steps)

1. **Step 1: Workspace & Repository Setup**: Inspect directory and set up architecture documentation.
2. **Step 2: Database Schema & Migration Setup**: Define SQLAlchemy ORM models and migrations for PostgreSQL/SQLite.
3. **Step 3: Realistic Seed Data**: Create `database/seeds/seed_db.py` to seed 50+ products, 3 warehouses, suppliers, sales history, overstock, and stockout risk scenarios.
4. **Step 4: CSV Connector**: Implement CSV ingestion pipeline with data validation logs.
5. **Step 5: Mock ERP & WMS Connectors**: Implement mock REST endpoints and data ingestion pipelines for ERP and WMS sources.
6. **Step 6: FastAPI Backend Layer**: Build clean API layer with repositories, services, and schemas.
7. **Step 7: Demand Forecasting Engine**: Build time-series forecasting service with metrics (MAE, RMSE).
8. **Step 8: Inventory Optimization Engine**: Implement formulas for Safety Stock, Reorder Point, and Recommended Order Quantity.
9. **Step 9: Inventory Risk Engine**: Build risk classification engine (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
10. **Step 10: Control Tower APIs**: Create endpoints for dashboard metrics, risk matrix, and recommendations.
11. **Step 11: MCP Tools Implementation**: Build pure Python MCP tools wrapping application services.
12. **Step 12: ReAct Agent Implementation**: Implement agentic loop for dynamic tool invocation and evidence assembly.
13. **Step 13: Claude / GenAI Integration**: Build provider abstraction with Anthropic SDK and offline mock fallback.
14. **Step 14: Control Tower UI Development**: Create React / Vite dashboard with glassmorphism styling, KPI cards, tables, charts, and recommendations.
15. **Step 15: AI Chat Integration**: Connect UI chat drawer to backend `/api/ai/chat` endpoint.
16. **Step 16: BI Integration Adapter**: Implement export adapters for PowerBI / Tableau integration.
17. **Step 17: Comprehensive Testing**: Create unit and E2E tests using `pytest`.
18. **Step 18: Docker & Local Deployment**: Create `docker-compose.yml`, `Dockerfile`, and `.env.example`.
19. **Step 19: End-to-End Verification**: Validate full flow from data ingestion to UI recommendation & AI chat.
20. **Step 20: Documentation & Handover**: Complete all documentation files and operational guides.
