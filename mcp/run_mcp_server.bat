@echo off
:: Wisualyst Supply Chain MCP Server Launcher
:: Used by Claude Desktop and any MCP-compatible AI client
cd /d "D:\supplychain"
set DATABASE_URL=sqlite:///./supply_chain.db
"C:\Users\user\AppData\Local\Programs\Python\Python311\python.exe" -m mcp.server

