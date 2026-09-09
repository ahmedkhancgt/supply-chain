# Model Context Protocol (MCP) Tools Documentation

## Overview

The MCP Server provides a controlled interface allowing LLM models (Claude) and ReAct Agents to retrieve application state without direct database access.

## Tool Definitions

1. `get_products`: Retrieves product metadata, SKUs, and lead times.
2. `get_warehouses`: Retrieves warehouse facilities and capacities.
3. `get_inventory`: Retrieves stock levels across warehouses.
4. `get_sales_history`: Retrieves historical daily sales transactions.
5. `get_suppliers`: Retrieves vendor profiles and ratings.
6. `get_demand_forecast`: Invokes AI/ML forecasting engine for specified horizon.
7. `get_inventory_risk`: Invokes Inventory Risk Engine to classify stockout risks.
8. `get_inventory_recommendations`: Returns automated replenishment reorder quantities.
9. `get_control_tower_summary`: Returns high-level executive KPIs.

## Security Controls

- **Read-Only Access**: MCP tools strictly invoke application read services.
- **No Direct SQL Execution**: Arbitrary `SELECT`, `UPDATE`, `DELETE`, or `DROP` statements are prohibited.
- **Audit Logging**: Every tool execution is tracked in memory and system logs.
