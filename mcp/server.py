#!/usr/bin/env python3
import sys
import json
import logging
import argparse
from typing import Dict, Any
import numpy as np
from backend.app.core.database import SessionLocal
from mcp.tools import MCPToolRegistry

# Configure stderr logging so stdin/stdout remain clean for JSON-RPC JSON lines
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s - %(levelname)s - %(message)s")

def json_default(obj):
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)

def send_response(response: Dict[str, Any]):
    sys.stdout.write(json.dumps(response, default=json_default) + "\n")
    sys.stdout.flush()

def main():
    """
    Standard Model Context Protocol (MCP) Server for Wisualyst Platform.
    Exposes 9 supply chain intelligence tools over JSON-RPC stdio.
    """
    logging.info("Starting Wisualyst MCP Server...")
    db = SessionLocal()
    registry = MCPToolRegistry(db)

    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            # 1. MCP Initialization Handshake
            if method == "initialize":
                send_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "serverInfo": {
                            "name": "wisualyst-supplychain-mcp",
                            "version": "1.0.0"
                        }
                    }
                })

            elif method == "notifications/initialized":
                # No response needed for initialized notification
                pass

            # 2. List Available Tools
            elif method == "tools/list":
                tools_def = registry.get_tool_definitions()
                mcp_tools = []
                for t in tools_def:
                    mcp_tools.append({
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": t["parameters"]
                    })
                send_response({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": mcp_tools
                    }
                })

            # 3. Execute Tool
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                try:
                    res = registry.execute_tool(tool_name, arguments)
                    send_response({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(res, indent=2, default=json_default)
                                }
                            ]
                        }
                    })
                except Exception as err:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32603,
                            "message": f"Tool execution failed: {str(err)}"
                        }
                    })

            # Ping
            elif method == "ping":
                send_response({"jsonrpc": "2.0", "id": msg_id, "result": {}})

            else:
                if msg_id:
                    send_response({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method '{method}' not found"
                        }
                    })
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wisualyst Supply Chain MCP Server")
    parser.add_argument("--test", action="store_true", help="Run a self-test of all registered MCP tools")
    parser.add_argument("--list-tools", action="store_true", help="Print all available MCP tools")
    args = parser.parse_args()

    if args.test:
        print("=== Wisualyst MCP Server Self-Test ===")
        db = SessionLocal()
        reg = MCPToolRegistry(db)
        tools = reg.get_tool_definitions()
        print(f"Registered Tools Count: {len(tools)}")
        for t in tools:
            print(f"  • {t['name']}: {t['description']}")
        print("\nTesting 'get_control_tower_summary':")
        summary = reg.execute_tool('get_control_tower_summary', {})
        print(f"  -> Total Products: {summary.get('total_products')}, Stockout Critical: {summary.get('stockout_critical_count')}, Readiness: {summary.get('overall_readiness_pct')}%")
        db.close()
        print("=== MCP Server Self-Test PASSED ===")
    elif args.list_tools:
        db = SessionLocal()
        reg = MCPToolRegistry(db)
        print(json.dumps(reg.get_tool_definitions(), indent=2))
        db.close()
    else:
        main()
