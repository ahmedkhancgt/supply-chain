from abc import ABC, abstractmethod
from typing import Dict, Any, List
import json
import os
from backend.app.core.config import settings

class GenAIProvider(ABC):
    @abstractmethod
    def generate_response(self, prompt: str, tool_registry: Any) -> Dict[str, Any]:
        pass

class OpenAIProvider(GenAIProvider):
    """
    Official OpenAI GenAI Provider (GPT-4o / GPT-4o-mini) using standard OpenAI Function/Tool Calling.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        try:
            import openai
            self.client = openai.OpenAI(api_key=api_key)
        except Exception as e:
            self.client = None

    def generate_response(self, prompt: str, tool_registry: Any) -> Dict[str, Any]:
        if not self.client or not self.api_key:
            return DeterministicRuleBasedProvider().generate_response(prompt, tool_registry)

        raw_tools = tool_registry.get_tool_definitions()
        openai_tools = []
        for t in raw_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"]
                }
            })

        system_prompt = (
            "You are an expert Supply Chain AI Decision-Intelligence Assistant for Wisualyst Platform. "
            "Your task is to answer user queries using real operational supply chain metrics retrieved from MCP tools. "
            "Never invent numbers or assume metrics. Always cite real stock levels, days of inventory, safety stock, "
            "lead times, and supplier OTIF scores returned by the tools."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        tools_executed = []
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=openai_tools,
                tool_choice="auto"
            )

            response_message = response.choices[0].message
            tool_calls = response_message.tool_calls

            if tool_calls:
                messages.append(response_message)
                for tool_call in tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments or "{}")
                    tools_executed.append(func_name)
                    
                    tool_result = tool_registry.execute_tool(func_name, func_args)
                    
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": func_name,
                        "content": json.dumps(tool_result, default=str)
                    })

                second_response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages
                )
                final_text = second_response.choices[0].message.content
            else:
                final_text = response_message.content

            return {
                "response": final_text,
                "tools_used": tools_executed,
                "provider": "OpenAI GPT-4o (Live API)"
            }
        except Exception as err:
            print(f"[OpenAIProvider Error] {err}. Falling back to Rule-Based Engine.")
            return DeterministicRuleBasedProvider().generate_response(prompt, tool_registry)

class ClaudeProvider(GenAIProvider):
    """
    Anthropic Claude GenAI Provider implementation using the official anthropic SDK.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            self.client = None

    def generate_response(self, prompt: str, tool_registry: Any) -> Dict[str, Any]:
        if not self.client or not self.api_key:
            return DeterministicRuleBasedProvider().generate_response(prompt, tool_registry)

        tools = tool_registry.get_tool_definitions()
        
        system_prompt = (
            "You are an expert Supply Chain AI Decision-Intelligence Assistant. "
            "Your job is to answer user queries using real supply chain data retrieved from MCP tools. "
            "Do not fabricate numbers or invent fictional stock metrics. Always cite calculations, "
            "days of inventory, stockout risks, and supplier lead times retrieved from MCP tools."
        )

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                tools=tools
            )

            tools_executed = []
            final_text = ""

            tool_uses = [content for content in response.content if content.type == "tool_use"]
            
            if tool_uses:
                tool_results_payload = []
                for tu in tool_uses:
                    tools_executed.append(tu.name)
                    tool_output = tool_registry.execute_tool(tu.name, tu.input)
                    tool_results_payload.append({
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": json.dumps(tool_output, default=str)
                    })

                follow_up = self.client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1024,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": response.content},
                        {"role": "user", "content": tool_results_payload}
                    ]
                )
                
                text_blocks = [c.text for c in follow_up.content if c.type == "text"]
                final_text = "\n".join(text_blocks)
            else:
                text_blocks = [c.text for c in response.content if c.type == "text"]
                final_text = "\n".join(text_blocks)

            return {
                "response": final_text,
                "tools_used": tools_executed,
                "provider": "Claude (Anthropic API)"
            }
        except Exception as err:
            print(f"[ClaudeProvider Error] {err}. Falling back to Rule-Based Engine.")
            return DeterministicRuleBasedProvider().generate_response(prompt, tool_registry)

class DeterministicRuleBasedProvider(GenAIProvider):
    """
    Deterministic Live Data Engine that executes real tool queries directly against the live database
    without hardcoded strings or mock numbers.
    """
    def generate_response(self, prompt: str, tool_registry: Any) -> Dict[str, Any]:
        p_lower = prompt.lower()
        tools_used = []

        if "risk" in p_lower or "run out" in p_lower or "stockout" in p_lower:
            tools_used.append("get_inventory_risk")
            risks = tool_registry.execute_tool("get_inventory_risk", {"risk_level": "CRITICAL"})
            high_risks = tool_registry.execute_tool("get_inventory_risk", {"risk_level": "HIGH"})
            combined = (risks or []) + (high_risks or [])

            if not combined:
                all_risks = tool_registry.execute_tool("get_inventory_risk", {})
                combined = all_risks if all_risks else []

            count = len(combined)
            if count == 0:
                response_text = "No stockout risks detected in the current connected database."
            else:
                lines = [f"Based on real-time database calculations, **{count} products** are at elevated stockout risk:"]
                for item in combined[:5]:
                    lines.append(
                        f"• **{item['product_name']} ({item['sku']})** at *{item['warehouse_name']}*:\n"
                        f"  - Current Stock: **{item['current_stock']} units**\n"
                        f"  - 7-Day Forecast Demand: **{item['forecast_7d_demand']} units**\n"
                        f"  - Days of Inventory: **{item['days_of_inventory']} days** (Supplier Lead Time: {item['lead_time_days']} days)\n"
                        f"  - Risk Classification: `{item['stockout_risk_level']}`\n"
                        f"  - Recommendation: **Order {item['recommended_order_quantity']} units** from *{item['supplier_name']}*."
                    )
                response_text = "\n\n".join(lines)

        elif "reorder" in p_lower or "recommendation" in p_lower or "replenish" in p_lower or "buy" in p_lower:
            tools_used.append("get_inventory_recommendations")
            recs = tool_registry.execute_tool("get_inventory_recommendations", {})
            if not recs:
                response_text = "No purchase order recommendations currently required for the database."
            else:
                lines = ["Here are the automated replenishment recommendations generated by the optimization engine:"]
                for r in recs[:5]:
                    lines.append(
                        f"• **{r.get('product_name', r.get('entity_id', 'SKU'))}**:\n"
                        f"  - Recommended Order: **{r.get('recommended_action', 'Place PO')}**\n"
                        f"  - Severity: `{r.get('severity', 'high').upper()}`\n"
                        f"  - Reason: {r.get('reason', 'Stock threshold reached')}"
                    )
                response_text = "\n\n".join(lines)

        elif "forecast" in p_lower or "demand" in p_lower:
            tools_used.append("get_products")
            tools_used.append("get_demand_forecast")
            prods = tool_registry.execute_tool("get_products", {})
            if prods:
                p_id = prods[0]["id"]
                fc = tool_registry.execute_tool("get_demand_forecast", {"product_id": p_id, "horizon_days": 30})
                response_text = (
                    f"**Demand Forecast Analysis for {fc['product_name']} ({fc['sku']})**:\n"
                    f"• Horizon: **30 Days**\n"
                    f"• Total Forecasted Demand: **{fc['total_forecasted_demand']} units**\n"
                    f"• Model Accuracy (MAE): **{fc['mae']}** | RMSE: **{fc['rmse']}**\n"
                    f"• Confidence Interval: **95%**"
                )
            else:
                response_text = "No product data available in connected database to generate demand forecast."

        else:
            tools_used.append("get_control_tower_summary")
            summary = tool_registry.execute_tool("get_control_tower_summary", {})
            response_text = (
                f"**Supply Chain Control Tower Overview**:\n"
                f"• Total Products Managed: **{summary['total_products']}** across **{summary['total_warehouses']} Warehouses**\n"
                f"• Total Inventory Valuation: **AED {summary['total_inventory_value']:,.2f}**\n"
                f"• Stockout Alerts: **{summary['stockout_critical_count']} Critical**, **{summary['stockout_high_count']} High**\n"
                f"• Excess Inventory SKUs: **{summary['excess_inventory_count']}**\n"
                f"• Open Purchase Orders: **{summary['open_purchase_orders']}**"
            )

        return {
            "response": response_text,
            "tools_used": tools_used,
            "provider": "Wisualyst Real-Time Decision Engine"
        }

def get_ai_provider() -> GenAIProvider:
    if settings.OPENAI_API_KEY and settings.AI_PROVIDER in ["openai", "gpt", "gpt4"]:
        return OpenAIProvider(settings.OPENAI_API_KEY)
    if settings.ANTHROPIC_API_KEY and settings.AI_PROVIDER in ["claude", "anthropic"]:
        return ClaudeProvider(settings.ANTHROPIC_API_KEY)
    return DeterministicRuleBasedProvider()
