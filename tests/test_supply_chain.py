import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import json

from backend.app.core.database import Base
from database.seeds.seed_db import seed_database
from backend.app.models.models import Product, Warehouse, Inventory, SalesHistory
from connectors.csv_connector import CSVIngestionConnector
from connectors.mock_erp_connector import MockERPConnector
from connectors.mock_wms_connector import MockWMSConnector
from ai.forecasting.engine import StatisticalForecastEngine
from ai.inventory.optimization import InventoryOptimizer
from ai.risk.engine import InventoryRiskEngine
from mcp.tools import MCPToolRegistry
from agents.react_agent import ReActAgent
from backend.app.services.services import SupplyChainService

@pytest.fixture(scope="module")
def test_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    # Seed database for testing
    seed_database(db)
    yield db
    db.close()

def test_database_and_seeds(test_db):
    product_count = test_db.query(Product).count()
    warehouse_count = test_db.query(Warehouse).count()
    inventory_count = test_db.query(Inventory).count()

    assert product_count >= 50
    assert warehouse_count == 3
    assert inventory_count >= 50

def test_csv_ingestion_connector(test_db):
    csv_data = """sku,name,unit_cost,quantity,selling_price
SKU-TEST-001,Test Pneumatic Cylinder,45.0,100,85.0
SKU-TEST-002,Test Sensor Module,15.0,50,30.0"""
    
    connector = CSVIngestionConnector()
    res = connector.ingest_csv_content(csv_data, test_db)
    
    assert res["status"] == "SUCCESS"
    assert res["processed_count"] == 2

    # Verify product in DB
    p = test_db.query(Product).filter(Product.sku == "SKU-TEST-001").first()
    assert p is not None
    assert p.unit_cost == 45.0

def test_mock_erp_connector(test_db):
    erp_payload = {
        "products": [
            {"sku": "SKU-ERP-TEST", "name": "ERP Test Valve", "unit_cost": 75.0, "selling_price": 140.0}
        ],
        "suppliers": [
            {"code": "SUP-ERP-TEST", "name": "ERP Vendor", "lead_time_days": 10}
        ]
    }
    connector = MockERPConnector()
    res = connector.sync_erp_data(erp_payload, test_db)
    assert res["synced_products"] == 1
    assert res["synced_suppliers"] == 1

def test_mock_wms_connector(test_db):
    wh = test_db.query(Warehouse).first()
    prod = test_db.query(Product).first()
    wms_payload = {
        "warehouse_code": wh.code,
        "inventory_levels": [
            {"sku": prod.sku, "current_stock": 15, "allocated_stock": 2}
        ]
    }
    connector = MockWMSConnector()
    res = connector.sync_wms_inventory(wms_payload, test_db)
    assert res["status"] == "SUCCESS"
    assert res["items_updated"] == 1

def test_demand_forecasting_engine(test_db):
    product = test_db.query(Product).first()
    engine = StatisticalForecastEngine(test_db)
    fc = engine.generate_forecast(product.id, horizon_days=14)

    assert fc["product_id"] == product.id
    assert fc["horizon_days"] == 14
    assert len(fc["forecast_data"]) == 14
    assert fc["total_forecasted_demand"] > 0

def test_inventory_optimization(test_db):
    product = test_db.query(Product).first()
    wh = test_db.query(Warehouse).first()
    optimizer = InventoryOptimizer(test_db)
    metrics = optimizer.calculate_inventory_metrics(product.id, wh.id)

    assert "safety_stock_calculated" in metrics
    assert "reorder_point_calculated" in metrics
    assert metrics["days_of_inventory"] >= 0

def test_inventory_risk_engine(test_db):
    risk_engine = InventoryRiskEngine(test_db)
    risks = risk_engine.get_all_inventory_risks()

    assert len(risks) > 0
    # Must have at least one critical or high risk from seed setup
    risk_levels = set(r["stockout_risk_level"] for r in risks)
    assert "CRITICAL" in risk_levels or "HIGH" in risk_levels

def test_mcp_tools(test_db):
    registry = MCPToolRegistry(test_db)
    defs = registry.get_tool_definitions()
    assert len(defs) >= 9

    summary = registry.execute_tool("get_control_tower_summary", {})
    assert summary["total_products"] >= 50

    risks = registry.execute_tool("get_inventory_risk", {"risk_level": "CRITICAL"})
    assert isinstance(risks, list)

def test_react_agent_and_chat(test_db):
    agent = ReActAgent(test_db)
    res = agent.process_query("Which products are at risk of stockout in the next 7 days?")

    assert "response" in res
    assert len(res["tools_used"]) > 0
    assert "CRITICAL" in res["response"] or "stockout" in res["response"].lower() or "risk" in res["response"].lower()

def test_end_to_end_flow(test_db):
    """
    End-to-End Test Verification:
    Query -> Agent -> MCP -> DB -> Forecast/Optimization -> AI Response
    """
    service = SupplyChainService(test_db)
    summary = service.get_control_tower_summary()
    assert summary["total_inventory_value"] > 0

    agent = ReActAgent(test_db)
    res = agent.process_query("Why is SKU-ELEC-101 at risk?")
    assert len(res["response"]) > 0
    assert res["reasoning_summary"] is not None
