# ReAct Agent & LLM Provider Architecture

## ReAct Orchestration Flow

```
User Query
   │
   ▼
ReAct Agent (agents/react_agent.py)
   │
   ├── 1. Parse intent & determine necessary tools
   ├── 2. Execute read-only MCP Tools against FastAPI Services
   ├── 3. Collect DB observations & ML calculation outputs
   └── 4. Pass reasoning evidence to GenAI Provider
   │
   ▼
Claude / GenAI Provider
   │
   ▼
Formatted Response with Evidence & Metrics
```

## Provider Abstraction

- `GenAIProvider`: Abstract interface for LLM provider implementations.
- `ClaudeProvider`: Integrates with Anthropic API (`claude-3-5-sonnet`) using function/tool calling.
- `MockGenAIProvider`: Local deterministic fallback provider for zero-token offline testing.
