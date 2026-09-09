from typing import Dict, Any, List
from sqlalchemy.orm import Session
from mcp.tools import MCPToolRegistry
from backend.app.core.ai_provider import get_ai_provider

class ReActAgent:
    """
    ReAct (Reasoning + Acting) Agent for Supply Chain Intelligence.
    Workflow:
    1. Receive user query
    2. Identify required data context & select MCP tools
    3. Execute read-only tools against backend services
    4. Pass observations & calculations to GenAI provider
    5. Format evidence-backed executive summary
    """
    def __init__(self, db: Session):
        self.db = db
        self.tool_registry = MCPToolRegistry(db)
        self.provider = get_ai_provider()

    def process_query(self, user_query: str) -> Dict[str, Any]:
        result = self.provider.generate_response(user_query, self.tool_registry)
        
        reasoning_summary = f"Selected and executed MCP tools [{', '.join(result['tools_used'])}] to fetch live database state and calculate safety stock metrics."
        
        return {
            "response": result["response"],
            "tools_used": result["tools_used"],
            "reasoning_summary": reasoning_summary,
            "provider": result.get("provider", "GenAI Engine")
        }
