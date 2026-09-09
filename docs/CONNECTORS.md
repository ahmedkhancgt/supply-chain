# Data Connectors & Ingestion Architecture

## 1. CSV Ingestion Connector (`connectors/csv_connector.py`)
- Accepts CSV data containing `sku`, `name`, `unit_cost`, `quantity`, `selling_price`.
- Performs validation checks for missing fields, negative stock, invalid numbers.
- Writes error logs for invalid rows and commits valid records to database.

## 2. Mock ERP Connector (`connectors/mock_erp_connector.py`)
- Consumes external SAP/Oracle REST payloads (`/mock-erp/...`).
- Syncs products, pricing, suppliers, and contracted lead times.

## 3. Mock WMS Connector (`connectors/mock_wms_connector.py`)
- Consumes external WMS payloads (`/mock-wms/...`).
- Syncs warehouse stock levels, allocated inventory, and logs inventory transaction movements.
