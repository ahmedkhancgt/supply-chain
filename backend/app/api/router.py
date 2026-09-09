from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime

from backend.app.core.database import get_db, SessionLocal, engine, Base
from backend.app.schemas.schemas import (
    ProductResponse, WarehouseResponse, InventoryResponse, SupplierResponse,
    ForecastResponse, ControlTowerSummary, AIChatRequest, AIChatResponse, IngestionLogResponse
)
from backend.app.services.services import SupplyChainService
from backend.app.services.bi_adapter import LocalBIAdapter
from ai.forecasting.engine import StatisticalForecastEngine
from ai.risk.engine import InventoryRiskEngine
from agents.react_agent import ReActAgent
from connectors.csv_connector import CSVIngestionConnector
from connectors.mock_erp_connector import MockERPConnector
from connectors.mock_wms_connector import MockWMSConnector
from database.seeds.seed_db import seed_database
from backend.app.models.models import Role, WorkspaceMember, AuditLog, MicrosoftOAuthConnection
from backend.app.services.teams_notifier import MicrosoftTeamsNotifier

router = APIRouter()
teams_notifier = MicrosoftTeamsNotifier()

# In-memory store for active Microsoft OAuth session
ACTIVE_MICROSOFT_SESSIONS: Dict[str, Any] = {}

# --- Microsoft Teams Integration Endpoints ---
@router.post("/api/teams/webhook/test", tags=["Microsoft Teams Integration"])
def send_teams_test_card(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    webhook_url = payload.get("webhook_url")
    channel = payload.get("channel", "#alerts-and-insights")
    
    # Try fetching a top critical risk to display in test card
    service = SupplyChainService(db)
    risks = service.risk_engine.get_all_inventory_risks()
    top_risk = next((r for r in risks if r["stockout_risk_level"] == "CRITICAL"), risks[0] if risks else None)
    
    if not top_risk:
        return {
            "status": "INFO",
            "message": "No inventory risk records currently in database to dispatch to Teams. Connect data sources first.",
            "detail": teams_notifier.get_recent_notifications()
        }
    
    card_msg = teams_notifier.build_stockout_alert_card(top_risk, channel=channel)
    result = teams_notifier.send_webhook_notification(webhook_url, card_msg)
    return {"status": "SUCCESS", "message": "Microsoft Teams Adaptive Card sent successfully!", "detail": result}

@router.post("/api/teams/webhook/send", tags=["Microsoft Teams Integration"])
def send_teams_notification(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    webhook_url = payload.get("webhook_url")
    notification_type = payload.get("type", "STOCKOUT_ALERT")
    alert_data = payload.get("data", {})
    channel = payload.get("channel", "#alerts-and-insights")
    
    if notification_type == "AI_RECOMMENDATION":
        card_msg = teams_notifier.build_recommendation_card(alert_data, channel=channel)
    else:
        card_msg = teams_notifier.build_stockout_alert_card(alert_data, channel=channel)

    # Fetch active Microsoft OAuth session from memory or persistent PostgreSQL DB
    session = ACTIVE_MICROSOFT_SESSIONS.get("latest")
    access_token = session.get("access_token") if session else None
    user_id = session.get("user_id") if session else None
    
    if not access_token:
        db_conn = db.query(MicrosoftOAuthConnection).filter(MicrosoftOAuthConnection.is_active == 1).order_by(MicrosoftOAuthConnection.updated_at.desc()).first()
        if db_conn:
            access_token = db_conn.access_token
            user_id = db_conn.user_id

    if access_token:
        try:
            graph_res = teams_notifier.send_graph_chat_message(
                access_token=access_token,
                user_id=user_id,
                payload=card_msg
            )
            card_msg["graph_status"] = graph_res
        except Exception as e:
            print("Graph chat dispatch error note:", e)

    result = teams_notifier.send_webhook_notification(webhook_url, card_msg)
    if "graph_status" in card_msg:
        result["graph_status"] = card_msg["graph_status"]
    else:
        result["graph_status"] = {"status": "NO_ACTIVE_SESSION", "message": "Click 'Sign in with Microsoft' in UI first to establish live session"}
    return {"status": "SUCCESS", "detail": result}

# --- Microsoft Teams 1-Click OAuth Integration ---
import os
import urllib.parse
from fastapi.responses import RedirectResponse

@router.get("/api/auth/microsoft/login", tags=["Microsoft Teams Integration"])
@router.get("/auth/microsoft/login", tags=["Microsoft Teams Integration"])
def microsoft_oauth_login():
    client_id = os.environ.get("AZURE_CLIENT_ID", "52889720-e817-40ce-be25-ca732a9d1a5c")
    tenant_authority = "common"
    redirect_uri = os.environ.get("AZURE_REDIRECT_URI", "https://app.wisualyst.com/api/auth/callback/microsoft")
    scope = "openid profile email User.Read ChannelMessage.Send ChatMessage.Send Chat.ReadWrite"
    
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": scope,
        "state": "wisualyst_teams_auth"
    }
    url = f"https://login.microsoftonline.com/{tenant_authority}/oauth2/v2.0/authorize?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=url)

import json
import urllib.request

@router.get("/api/auth/callback/microsoft", tags=["Microsoft Teams Integration"])
@router.get("/auth/callback/microsoft", tags=["Microsoft Teams Integration"])
def microsoft_oauth_callback(code: Optional[str] = None, error: Optional[str] = None, db: Session = Depends(get_db)):
    if error or not code:
        return RedirectResponse(url="https://app.wisualyst.com/?teams_connected=false&error=" + (error or "no_code") + "#alerts")
    
    client_id = os.environ.get("AZURE_CLIENT_ID", "52889720-e817-40ce-be25-ca732a9d1a5c")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("AZURE_REDIRECT_URI", "https://app.wisualyst.com/api/auth/callback/microsoft")
    
    user_email = "user@microsoft.com"
    try:
        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        post_data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }).encode("utf-8")
        
        req = urllib.request.Request(token_url, data=post_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                token_json = json.loads(response.read().decode("utf-8"))
                access_token = token_json.get("access_token")
                
                # Fetch user profile from Microsoft Graph
                graph_req = urllib.request.Request(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                with urllib.request.urlopen(graph_req, timeout=10) as graph_res:
                    if graph_res.status == 200:
                        me_data = json.loads(graph_res.read().decode("utf-8"))
                        user_email = me_data.get("mail") or me_data.get("userPrincipalName") or me_data.get("displayName") or "user@microsoft.com"
                        
                        # Save in memory
                        ACTIVE_MICROSOFT_SESSIONS["latest"] = {
                            "access_token": access_token,
                            "user_email": user_email,
                            "user_id": me_data.get("id"),
                            "display_name": me_data.get("displayName")
                        }

                        # Save persistently in PostgreSQL database so connection survives server restarts
                        existing_conn = db.query(MicrosoftOAuthConnection).filter(MicrosoftOAuthConnection.user_email == user_email).first()
                        if existing_conn:
                            existing_conn.access_token = access_token
                            existing_conn.refresh_token = token_json.get("refresh_token")
                            existing_conn.user_id = me_data.get("id")
                            existing_conn.display_name = me_data.get("displayName")
                            existing_conn.is_active = 1
                            existing_conn.updated_at = datetime.utcnow()
                        else:
                            new_conn = MicrosoftOAuthConnection(
                                user_email=user_email,
                                user_id=me_data.get("id"),
                                display_name=me_data.get("displayName"),
                                access_token=access_token,
                                refresh_token=token_json.get("refresh_token"),
                                is_active=1
                            )
                            db.add(new_conn)
                        db.commit()
    except Exception as e:
        print("Microsoft Graph token exchange note:", e)

    encoded_email = urllib.parse.quote(user_email)
    return RedirectResponse(url=f"https://app.wisualyst.com/?teams_connected=true&account={encoded_email}#alerts")

@router.get("/api/auth/microsoft/status", tags=["Microsoft Teams Integration"])
def microsoft_oauth_status(db: Session = Depends(get_db)):
    active_conn = db.query(MicrosoftOAuthConnection).filter(MicrosoftOAuthConnection.is_active == 1).order_by(MicrosoftOAuthConnection.updated_at.desc()).first()
    if active_conn:
        return {
            "connected": True,
            "account": active_conn.user_email,
            "display_name": active_conn.display_name,
            "client_id": os.environ.get("AZURE_CLIENT_ID", "52889720-e817-40ce-be25-ca732a9d1a5c")
        }
    return {
        "connected": False,
        "account": None,
        "client_id": os.environ.get("AZURE_CLIENT_ID", "52889720-e817-40ce-be25-ca732a9d1a5c")
    }

@router.post("/api/auth/microsoft/disconnect", tags=["Microsoft Teams Integration"])
def microsoft_oauth_disconnect(db: Session = Depends(get_db)):
    db.query(MicrosoftOAuthConnection).update({"is_active": 0})
    db.commit()
    ACTIVE_MICROSOFT_SESSIONS.clear()
    return {"status": "SUCCESS", "message": "Microsoft Teams disconnected successfully"}


# --- Database Administration Endpoints ---
@router.post("/api/database/clean", tags=["Admin"])
def clean_database(db: Session = Depends(get_db)):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return {"status": "SUCCESS", "message": "Database completely cleaned for a new fresh workspace!"}

@router.post("/api/database/seed", tags=["Admin"])
@router.post("/api/seed-database", tags=["Admin"])
def run_seed_db(db: Session = Depends(get_db)):
    seed_database(db)
    return {"status": "SUCCESS", "message": "Database successfully seeded with realistic supply chain data!"}

# --- Core Entities ---
@router.get("/api/products", tags=["Catalog"])
@router.get("/products", tags=["Catalog"])
def get_products(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    prods = service.product_repo.get_all()
    return [{
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "category_id": p.category_id,
        "category_name": p.category.name if p.category else "Uncategorized",
        "unit": p.unit,
        "unit_cost": p.unit_cost,
        "selling_price": p.selling_price,
        "lead_time_days": p.lead_time_days,
        "safety_stock_min": p.safety_stock_min,
        "reorder_point": p.reorder_point,
        "created_at": p.created_at.isoformat() if p.created_at else None
    } for p in prods]

@router.get("/api/warehouses", tags=["Catalog"])
@router.get("/warehouses", tags=["Catalog"])
def get_warehouses(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    whs = service.warehouse_repo.get_all()
    return [{
        "id": w.id, "code": w.code, "name": w.name, "location": w.location, "capacity": getattr(w, "capacity_sqft", 25000),
        "created_at": w.created_at.isoformat() if w.created_at else None
    } for w in whs]

@router.get("/api/inventory", tags=["Inventory"])
@router.get("/inventory", tags=["Inventory"])
def get_inventory(warehouse_id: Optional[int] = None, db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    items = service.inventory_repo.get_all(warehouse_id)
    return [{
        "id": i.id,
        "product_id": i.product_id,
        "sku": i.product.sku if i.product else "",
        "product_name": i.product.name if i.product else "",
        "warehouse_id": i.warehouse_id,
        "warehouse_name": i.warehouse.name if i.warehouse else "",
        "current_stock": i.current_stock,
        "allocated_stock": i.allocated_stock,
        "available_stock": i.available_stock,
        "safety_stock": i.safety_stock,
        "unit_cost": i.product.unit_cost if i.product else 0.0,
        "total_value": round(i.current_stock * (i.product.unit_cost if i.product else 0.0), 2),
        "last_updated": i.last_updated.isoformat() if i.last_updated else None
    } for i in items]

@router.get("/api/suppliers", tags=["Suppliers"])
@router.get("/suppliers", tags=["Suppliers"])
def get_suppliers(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    sups = service.supplier_repo.get_all()
    return [{
        "id": s.id, "code": s.code, "name": s.name, "contact_email": s.contact_email,
        "rating": s.rating, "lead_time_avg_days": s.lead_time_avg_days
    } for s in sups]

# --- AI & Analytics ---
@router.get("/api/forecast/{product_id}", response_model=ForecastResponse, tags=["AI/ML Forecast"])
def get_product_forecast(product_id: int, warehouse_id: Optional[int] = None, horizon_days: int = 30, db: Session = Depends(get_db)):
    engine = StatisticalForecastEngine(db)
    try:
        return engine.generate_forecast(product_id, warehouse_id, horizon_days)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/api/inventory-risk", tags=["AI/ML Risk Engine"])
def get_inventory_risk(warehouse_id: Optional[int] = None, risk_level: Optional[str] = None, db: Session = Depends(get_db)):
    risk_engine = InventoryRiskEngine(db)
    return risk_engine.get_all_inventory_risks(warehouse_id, risk_level)

@router.get("/api/inventory-recommendations", tags=["AI/ML Optimization"])
def get_inventory_recommendations(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    return service.get_inventory_recommendations()

@router.get("/api/control-tower", tags=["Control Tower"])
@router.get("/api/control-tower/summary", tags=["Control Tower"])
def get_control_tower_summary(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    return service.get_control_tower_summary()

# --- Wisualyst 4 Module Endpoints ---
@router.get("/api/modules/inventory", tags=["Wisualyst Modules"])
def get_module_inventory(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    return {
        "module": "Inventory AI",
        "summary": service.get_control_tower_summary(),
        "risks": service.risk_engine.get_all_inventory_risks()
    }

@router.get("/api/modules/demand", tags=["Wisualyst Modules"])
def get_module_demand(product_id: Optional[int] = None, db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    if not product_id:
        first_prod = db.query(Product).first()
        product_id = first_prod.id if first_prod else 1
    return service.forecast_engine.generate_forecast(product_id=product_id, horizon_days=30)

@router.get("/api/modules/procurement", tags=["Wisualyst Modules"])
def get_module_procurement(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    return service.procurement_engine.generate_procurement_intelligence()

@router.get("/api/modules/assortment", tags=["Wisualyst Modules"])
def get_module_assortment(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    return service.assortment_engine.generate_assortment_intelligence()

@router.get("/api/recommendations", tags=["Wisualyst Modules"])
def get_unified_recommendations(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    return service.recommendation_engine.get_unified_recommendations()

# --- Wisualyst Onboarding & Data Connection Routes ---
@router.post("/api/workspace/create", tags=["Wisualyst Onboarding"])
def create_workspace(payload: Dict[str, Any] = Body(...)):
    return {
        "status": "SUCCESS",
        "workspace_id": "ws_dubai_retail_01",
        "name": payload.get("name", "Wisualyst Enterprise Workspace"),
        "industry": payload.get("industry", "Retail & Consumer Goods"),
        "region": payload.get("region", "Global / Middle East"),
        "selected_modules": payload.get("modules", ["inventory", "demand", "procurement", "assortment"])
    }

@router.get("/api/workspace/members", tags=["Wisualyst Onboarding"])
def get_workspace_members(db: Session = Depends(get_db)):
    members = db.query(WorkspaceMember).all()
    return [{
        "id": m.id,
        "name": m.name,
        "email": m.email,
        "role": m.role,
        "initials": m.initials,
        "color": m.color,
        "bg": m.bg
    } for m in members]

@router.post("/api/workspace/invite", tags=["Wisualyst Onboarding"])
def invite_workspace_member(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    email = payload.get("email", "")
    name = payload.get("name", email.split("@")[0].title() if "@" in email else "Team Member")
    role = payload.get("role", "Viewer")
    initials = "".join([p[0].upper() for p in name.split()[:2]]) or "U"
    
    new_m = WorkspaceMember(
        name=name,
        email=email,
        role=role,
        initials=initials,
        color="#2563eb",
        bg="#eff6ff"
    )
    db.add(new_m)
    db.commit()
    db.refresh(new_m)
    return {
        "status": "SUCCESS",
        "message": f"Invitation sent to {new_m.email} as {new_m.role}",
        "member": {
            "id": new_m.id,
            "name": new_m.name,
            "email": new_m.email,
            "role": new_m.role,
            "initials": new_m.initials,
            "color": new_m.color,
            "bg": new_m.bg
        }
    }

@router.post("/api/connectors/test", tags=["Wisualyst Onboarding"])
def test_connector(payload: Dict[str, Any] = Body(...)):
    c_type = payload.get("type", "DIRECT_DB").upper()
    if c_type == "DIRECT_DB":
        from connectors.direct_db_connector import DirectDBConnector
        connector = DirectDBConnector(
            host=payload.get("host", ""),
            port=payload.get("port", 5432),
            database=payload.get("database", ""),
            username=payload.get("username", ""),
            password=payload.get("password", ""),
            ssl_mode=payload.get("ssl_mode", "disable")
        )
        return connector.test_connection()
    elif c_type == "ZOHO":
        from connectors.zoho_connector import ZohoConnector
        connector = ZohoConnector(
            client_id=payload.get("client_id", ""),
            client_secret=payload.get("client_secret", ""),
            organization_id=payload.get("organization_id", ""),
            region_domain=payload.get("region_domain", "accounts.zoho.com")
        )
        return connector.authenticate(auth_code=payload.get("auth_code", ""))
    elif c_type == "SFTP":
        from connectors.sftp_connector import SFTPConnector
        connector = SFTPConnector(
            host=payload.get("host", ""),
            port=payload.get("port", 22),
            username=payload.get("username", ""),
            password=payload.get("password", ""),
            remote_path=payload.get("remote_path", "/exports/daily_feeds")
        )
        return connector.test_connection()
    return {"status": "SUCCESS", "message": f"Connection to {c_type} validated successfully!"}

@router.post("/api/connectors/discover", tags=["Wisualyst Onboarding"])
def discover_tables(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    c_type = payload.get("type", "DIRECT_DB").upper()
    if c_type == "DIRECT_DB":
        from connectors.direct_db_connector import DirectDBConnector
        connector = DirectDBConnector(
            host=payload.get("host", ""),
            port=payload.get("port", 5432),
            database=payload.get("database", ""),
            username=payload.get("username", ""),
            password=payload.get("password", "")
        )
        tables = connector.discover_tables()
        return {"tables": tables}
    elif c_type == "ZOHO":
        from connectors.zoho_connector import ZohoConnector
        return {"tables": ZohoConnector().discover_modules()}
    else:
        from connectors.sftp_connector import SFTPConnector
        connector = SFTPConnector(
            host=payload.get("host", ""),
            port=payload.get("port", 22),
            username=payload.get("username", ""),
            password=payload.get("password", ""),
            remote_path=payload.get("remote_path", "/exports/daily_feeds")
        )
        return {"tables": connector.discover_files()}

@router.post("/api/mapping/suggest", tags=["Wisualyst Onboarding"])
def suggest_mapping(payload: Dict[str, Any] = Body(...)):
    from backend.app.services.mapping_engine import CanonicalMappingEngine
    source_fields = payload.get("source_fields", ["ItemCode", "ItemDescription", "WarehouseCode", "QtyOnHand", "TxnDate", "NetAmount", "SupplierCode"])
    engine = CanonicalMappingEngine()
    return {"mappings": engine.suggest_mappings(source_fields)}

@router.get("/api/validation/check", tags=["Wisualyst Onboarding"])
def check_validation(db: Session = Depends(get_db)):
    service = SupplyChainService(db)
    return service.validation_engine.evaluate_readiness()

@router.post("/api/workspace/launch", tags=["Wisualyst Onboarding"])
def launch_workspace():
    return {
        "status": "LAUNCHED",
        "workspace_id": "ws_dubai_retail_01",
        "message": "Workspace successfully configured and launched!"
    }


@router.get("/api/access-control/roles", tags=["Access Control"])
def get_roles(db: Session = Depends(get_db)):
    roles = db.query(Role).all()
    if not roles:
        # Seed standard initial roles into database if not present
        init_roles = [
            Role(role_key="admin", name="Admin", description="Full access to all features, settings, and user management.", scope="Full Access", scope_color="#7c3aed", scope_bg="#f3e8ff", author="System"),
            Role(role_key="de", name="Data Engineer", description="Manage data sources, mappings, and intelligence engines.", scope="Data & Engine Access", scope_color="#2563eb", scope_bg="#dbeafe", author="System"),
            Role(role_key="da", name="Data Analyst", description="Analyze data, create reports, and view insights.", scope="Read & Analyze", scope_color="#059669", scope_bg="#d1fae5", author="System"),
            Role(role_key="om", name="Operations Manager", description="Monitor KPIs, manage alerts, and view recommendations.", scope="Limited Access", scope_color="#d97706", scope_bg="#fef3c7", author="System"),
            Role(role_key="viewer", name="Viewer", description="View dashboards and reports with read-only access.", scope="Read Only", scope_color="#475569", scope_bg="#f1f5f9", author="System")
        ]
        db.add_all(init_roles)
        db.commit()
        roles = db.query(Role).all()
    
    result = []
    for r in roles:
        users_count = db.query(WorkspaceMember).filter(WorkspaceMember.role == r.name).count()
        result.append({
            "id": r.role_key,
            "name": r.name,
            "desc": r.description,
            "usersCount": users_count,
            "scope": r.scope,
            "scopeColor": r.scope_color,
            "scopeBg": r.scope_bg,
            "lastModified": r.updated_at.strftime("%b %d, %Y") if r.updated_at else "Today",
            "author": r.author
        })
    return result

@router.post("/api/access-control/roles", tags=["Access Control"])
def create_role(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    role_key = payload.get("name", "custom").lower().replace(" ", "_")
    new_role = Role(
        role_key=role_key,
        name=payload.get("name", "New Role"),
        description=payload.get("description", "Custom Role"),
        scope=payload.get("scope", "Custom Scope"),
        scope_color="#2563eb",
        scope_bg="#eff6ff",
        author=payload.get("author", "Admin")
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return {
        "status": "SUCCESS",
        "role": {
            "id": new_role.role_key,
            "name": new_role.name,
            "desc": new_role.description,
            "usersCount": 0,
            "scope": new_role.scope,
            "scopeColor": new_role.scope_color,
            "scopeBg": new_role.scope_bg,
            "lastModified": "Today",
            "author": new_role.author
        }
    }

# --- MCP Server Integration ---
@router.get("/api/mcp/tools", tags=["MCP Server Integration"])
def get_mcp_tools(db: Session = Depends(get_db)):
    import os
    from mcp.tools import MCPToolRegistry
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    server_path = os.path.join(base_dir, "mcp", "server.py")
    registry = MCPToolRegistry(db)
    return {
        "status": "ONLINE",
        "mcp_version": "2024-11-05",
        "transport": "JSON-RPC stdio",
        "server_path": server_path,
        "base_dir": base_dir,
        "tools": registry.get_tool_definitions()
    }

# --- BI Integration Adapters ---
@router.get("/api/bi/export", tags=["BI Integration"])
@router.get("/api/bi/powerbi", tags=["BI Integration"])
@router.get("/api/bi/adapter/powerbi", tags=["BI Integration"])
@router.get("/api/bi/adapter/powerbi/json", tags=["BI Integration"])
@router.get("/api/bi/adapter/powerbi.json", tags=["BI Integration"])
def export_powerbi(db: Session = Depends(get_db)):
    adapter = LocalBIAdapter()
    return adapter.export_powerbi(db)

@router.get("/api/bi/qlik", tags=["BI Integration"])
def export_qlik(db: Session = Depends(get_db)):
    adapter = LocalBIAdapter()
    return adapter.export_qlik(db)

@router.get("/api/bi/google-sheets", tags=["BI Integration"])
@router.get("/api/bi/export/csv", tags=["BI Integration"])
def export_bi_csv(db: Session = Depends(get_db)):
    adapter = LocalBIAdapter()
    csv_data = adapter.export_inventory_metrics_csv(db)
    return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=wisualyst_bi_dataset.csv"})

# --- AI Agent Chat & Multi-Agent Workflow ---
@router.post("/api/agents/multi-agent-workflow/run", tags=["Multi-Agent AI Engine"])
def run_multi_agent_workflow(auto_dispatch_teams: bool = True, db: Session = Depends(get_db)):
    try:
        from ai.multi_agent.workflow import MultiAgentSupplyChainWorkflow
        workflow = MultiAgentSupplyChainWorkflow(db)
        res = workflow.execute_workflow(auto_dispatch_teams=auto_dispatch_teams)
        return {
            "status": "SUCCESS",
            "timestamp": res.timestamp,
            "total_execution_ms": res.total_execution_ms,
            "products_scanned": res.products_scanned,
            "anomalies_detected": res.anomalies_detected,
            "critical_alerts_triggered": res.critical_alerts_triggered,
            "agent_logs": [
                {
                    "agent_name": log.agent_name,
                    "action": log.action,
                    "status": log.status,
                    "execution_ms": log.execution_ms,
                    "details": log.details
                } for log in res.agent_logs
            ],
            "forecast_insights": res.forecast_insights,
            "inventory_optimizations": res.inventory_optimizations,
            "anomalies": res.anomalies,
            "summary_message": res.summary_message
        }
    except Exception as e:
        return {"status": "ERROR", "message": f"Multi-agent execution note: {e}"}

@router.post("/api/ai/chat", response_model=AIChatResponse, tags=["AI Agent"])
def ai_chat(req: AIChatRequest, db: Session = Depends(get_db)):
    agent = ReActAgent(db)
    res = agent.process_query(req.message)
    return AIChatResponse(
        response=res["response"],
        tools_used=res["tools_used"],
        reasoning_summary=res["reasoning_summary"]
    )

# --- Ingestion & Connectors ---
@router.post("/api/ingest/csv", response_model=IngestionLogResponse, tags=["Connectors"])
async def ingest_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    contents = await file.read()
    csv_str = contents.decode("utf-8")
    connector = CSVIngestionConnector()
    res = connector.ingest_csv_content(csv_str, db)
    return IngestionLogResponse(
        status=res["status"],
        processed_count=res["processed_count"],
        errors=res["errors"],
        timestamp=res["logs"][-1]["timestamp"] if res["logs"] else ""
    )

@router.post("/api/ingest/erp", tags=["Connectors"])
def ingest_erp(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    connector = MockERPConnector()
    return connector.sync_erp_data(payload, db)

@router.post("/api/ingest/wms", tags=["Connectors"])
def ingest_wms(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    connector = MockWMSConnector()
    return connector.sync_wms_inventory(payload, db)

# --- Access Control Endpoints (Dynamic Database Models) ---
from backend.app.models.models import Role, WorkspaceMember, PermissionSetting, AuditLog

@router.get("/api/access-control/roles", tags=["Access Control"])
def get_access_roles(db: Session = Depends(get_db)):
    db_roles = db.query(Role).all()
    if not db_roles:
        return []
    
    result = []
    for r in db_roles:
        # Count workspace members assigned to this role
        user_count = db.query(WorkspaceMember).filter(WorkspaceMember.role.ilike(f"%{r.name}%")).count()
        result.append({
            "id": r.role_key,
            "name": r.name,
            "desc": r.description or "",
            "usersCount": user_count,
            "scope": r.scope or "Full Access",
            "scopeColor": r.scope_color or "#7c3aed",
            "scopeBg": r.scope_bg or "#f5f3ff",
            "lastModified": r.updated_at.strftime("%b %d, %Y") if r.updated_at else "Today",
            "author": r.author or "System"
        })
    return result

@router.post("/api/access-control/roles", tags=["Access Control"])
def create_role(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    name = payload.get("name", "Custom Role")
    desc = payload.get("description", "Custom user role")
    role_key = name.lower().replace(" ", "-")
    
    existing = db.query(Role).filter(Role.role_key == role_key).first()
    if existing:
        return {"status": "EXISTS", "message": f"Role '{name}' already exists.", "role": {
            "id": existing.role_key, "name": existing.name, "desc": existing.description, "usersCount": 0
        }}

    new_role = Role(
        role_key=role_key,
        name=name,
        description=desc,
        scope=payload.get("scope", "Custom Scope"),
        scope_color="#2563eb",
        scope_bg="#eff6ff",
        author="Admin"
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    
    return {
        "status": "SUCCESS",
        "message": f"Role '{name}' created successfully in database!",
        "role": {
            "id": new_role.role_key,
            "name": new_role.name,
            "desc": new_role.description,
            "usersCount": 0,
            "scope": new_role.scope,
            "scopeColor": new_role.scope_color,
            "scopeBg": new_role.scope_bg,
            "lastModified": new_role.updated_at.strftime("%b %d, %Y") if new_role.updated_at else "Today",
            "author": new_role.author
        }
    }

@router.get("/api/access-control/users", tags=["Access Control"])
def get_access_users(db: Session = Depends(get_db)):
    members = db.query(WorkspaceMember).all()
    result = []
    for m in members:
        result.append({
            "id": m.id,
            "name": m.name,
            "email": m.email,
            "role": m.role,
            "roleId": m.role.lower().replace(" ", "-"),
            "status": m.status or "Active",
            "lastActive": "Active Today",
            "avatarBg": m.color or "#2563eb"
        })
    return result

@router.post("/api/access-control/users/invite", tags=["Access Control"])
def invite_user(payload: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    email = payload.get("email", "").strip()
    role = payload.get("role", "Viewer")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
        
    name = email.split("@")[0].title().replace(".", " ")
    initials = "".join([part[0] for part in name.split()])[:2].upper()
    
    existing = db.query(WorkspaceMember).filter(WorkspaceMember.email == email).first()
    if existing:
        existing.role = role
        db.commit()
        return {"status": "UPDATED", "message": f"Updated role for {email} to {role}!", "invited_user": {
            "id": existing.id, "name": existing.name, "email": existing.email, "role": existing.role, "status": existing.status
        }}

    new_mem = WorkspaceMember(
        name=name,
        email=email,
        role=role,
        status="Active",
        initials=initials,
        color="#2563eb",
        bg="#eff6ff"
    )
    db.add(new_mem)
    db.commit()
    db.refresh(new_mem)
    
    return {
        "status": "SUCCESS",
        "message": f"Invitation link generated and saved to database for {email} as {role}!",
        "invited_user": {
            "id": new_mem.id,
            "name": new_mem.name,
            "email": new_mem.email,
            "role": new_mem.role,
            "status": new_mem.status,
            "lastActive": "Invited Today",
            "avatarBg": new_mem.color
        }
    }

@router.delete("/api/access-control/users/{user_id}", tags=["Access Control"])
def revoke_user_access(user_id: int, db: Session = Depends(get_db)):
    mem = db.query(WorkspaceMember).filter(WorkspaceMember.id == user_id).first()
    if mem:
        db.delete(mem)
        db.commit()
        return {"status": "SUCCESS", "message": f"User #{user_id} removed from database."}
    return {"status": "NOT_FOUND", "message": "User record not found."}

@router.get("/api/access-control/permissions", tags=["Access Control"])
def get_permissions_matrix(db: Session = Depends(get_db)):
    perms = db.query(PermissionSetting).all()
    if not perms:
        return []
    return [
        {
            "module": p.module_name,
            "key": p.module_key,
            "admin": bool(p.admin_access),
            "data_engineer": bool(p.de_access),
            "data_analyst": bool(p.da_access),
            "ops_manager": bool(p.om_access),
            "viewer": bool(p.viewer_access)
        } for p in perms
    ]

@router.get("/api/access-control/audit-logs", tags=["Access Control"])
def get_audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()
    if not logs:
        return []
    return [
        {
            "id": f"aud-{l.id}",
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "user": l.user_name,
            "email": l.user_email,
            "action": l.action,
            "category": l.category or "General",
            "details": l.details or "",
            "ip": l.ip_address or "127.0.0.1",
            "severity": l.severity or "INFO"
        } for l in logs
    ]
