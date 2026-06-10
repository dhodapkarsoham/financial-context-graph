"""Financial Services AI Agent — PydanticAI implementation."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass

from app.config import settings


# Ensure ANTHROPIC_API_KEY env var is set before PydanticAI creates the provider.
# pydantic-settings may load an empty value from the shell env, overriding .env.
if not os.environ.get("ANTHROPIC_API_KEY"):
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    else:
        from dotenv import dotenv_values
        _key = dotenv_values("../.env").get("ANTHROPIC_API_KEY", "")
        if _key:
            os.environ["ANTHROPIC_API_KEY"] = _key

from pydantic_ai import Agent, RunContext

from app.context_graph_client import execute_cypher, get_schema
from app.memory import store_message, get_context, resolve_session_id


SYSTEM_PROMPT = """You are an AI financial intelligence assistant with access to a comprehensive
knowledge graph of financial data. You help financial advisors, compliance
officers, and portfolio managers analyze accounts, transactions, decisions,
and policies.

Your capabilities include:
- Searching and analyzing client portfolios and transaction history
- Reviewing compliance status and policy adherence
- Tracing decision provenance and causal chains
- Identifying patterns and anomalies in financial data
- Finding similar past decisions to inform current choices

Always provide accurate, data-driven responses. When making recommendations,
cite the specific data points and reasoning from the knowledge graph.


IMPORTANT: You MUST use the available tools to query the knowledge graph before answering any question about the data. Never guess or make up information — always use tools to look up actual data from the graph. If a user asks a question, identify which tool(s) can help answer it and call them.

CRITICAL: Call tools DIRECTLY without any introductory text. Do NOT say "I'll search for..." or "Let me look up..." before calling a tool — just call the tool immediately. Only generate text AFTER you have received the tool results and are ready to provide your final answer.

When writing Cypher queries with run_cypher:
- Never combine ORDER BY with DISTINCT or aggregation in the same RETURN clause — use a WITH clause first
- Always LIMIT results (default LIMIT 25) to avoid overwhelming responses
- Use toLower() for case-insensitive matching
- If a query fails, try a simpler approach rather than repeating the same pattern"""



@dataclass
class AgentDeps:
    """Dependencies injected into the agent."""
    session_id: str


agent = Agent(
    "anthropic:claude-sonnet-4-20250514",
    system_prompt=SYSTEM_PROMPT,
    deps_type=AgentDeps,
    retries=2,
)

# ---------------------------------------------------------------------------
# Agent tools — domain-specific for Financial Services
# ---------------------------------------------------------------------------

@agent.tool
async def search_customer(ctx: RunContext[AgentDeps], query: str) -> str:
    """Search for clients, advisors, or other people by name or role"""
    cypher = """MATCH (p:Person)
    WHERE toLower(p.name) CONTAINS toLower($query)
       OR toLower(coalesce(p.role, '')) CONTAINS toLower($query)
    OPTIONAL MATCH (p)-[r]-(related)
    RETURN p, type(r) AS rel_type, related
    LIMIT 20
"""
    params = {
        "query": query,
    }
    result = await execute_cypher(cypher, params, tool_name="search_customer")
    return json.dumps(result, default=str)

@agent.tool
async def get_customer_decisions(ctx: RunContext[AgentDeps], name: str) -> str:
    """Get all decisions related to a specific client"""
    cypher = """MATCH (p:Person {name: $name})-[:OWNS|MANAGES]->(a:Account)
    OPTIONAL MATCH (d:Decision)-[:CAUSED]->(t:Transaction)-[:TRANSFERRED_TO|TRANSFERRED_FROM]->(a)
    RETURN p, a, d, t
    ORDER BY d.date DESC
    LIMIT 20
"""
    params = {
        "name": name,
    }
    result = await execute_cypher(cypher, params, tool_name="get_customer_decisions")
    return json.dumps(result, default=str)

@agent.tool
async def find_similar_decisions(ctx: RunContext[AgentDeps], decision_id: str) -> str:
    """Find decisions similar to a given decision using vector similarity"""
    cypher = """MATCH (d:Decision {decision_id: $decision_id})
    CALL db.index.vector.queryNodes('decision_embeddings', 5, d.embedding)
    YIELD node, score
    WHERE node.decision_id <> $decision_id
    RETURN node AS similar_decision, score
    ORDER BY score DESC
"""
    params = {
        "decision_id": decision_id,
    }
    result = await execute_cypher(cypher, params, tool_name="find_similar_decisions")
    return json.dumps(result, default=str)

@agent.tool
async def get_causal_chain(ctx: RunContext[AgentDeps], decision_id: str) -> str:
    """Trace the causal chain of events from a decision"""
    cypher = """MATCH path = (d:Decision {decision_id: $decision_id})-[:CAUSED|PRECEDED_BY*1..5]-(related)
    RETURN path
"""
    params = {
        "decision_id": decision_id,
    }
    result = await execute_cypher(cypher, params, tool_name="get_causal_chain")
    return json.dumps(result, default=str)

@agent.tool
async def detect_fraud_patterns(ctx: RunContext[AgentDeps]) -> str:
    """Detect unusual transaction patterns that may indicate fraud"""
    cypher = """MATCH (a:Account)<-[:TRANSFERRED_TO]-(t:Transaction)
    WHERE t.date > datetime() - duration('P30D')
    WITH a, count(t) AS tx_count, sum(t.amount) AS total_amount
    WHERE tx_count > 10 OR total_amount > 100000
    RETURN a.account_id, a.name, tx_count, total_amount
    ORDER BY total_amount DESC
"""
    params = {
    }
    result = await execute_cypher(cypher, params, tool_name="detect_fraud_patterns")
    return json.dumps(result, default=str)

@agent.tool
async def list_accounts(ctx: RunContext[AgentDeps], limit: str) -> str:
    """List Account records with optional limit"""
    cypher = """MATCH (n:Account)
    RETURN n
    ORDER BY n.name
    LIMIT toInteger($limit)
"""
    params = {
        "limit": limit,
    }
    result = await execute_cypher(cypher, params, tool_name="list_accounts")
    return json.dumps(result, default=str)

@agent.tool
async def get_account_by_id(ctx: RunContext[AgentDeps], id: str) -> str:
    """Get a specific Account by ID with all connections"""
    cypher = """MATCH (n:Account {account_id: $id})
    OPTIONAL MATCH (n)-[r]-(related)
    RETURN n, type(r) AS relationship, labels(related) AS related_labels, related.name AS related_name
    LIMIT 50
"""
    params = {
        "id": id,
    }
    result = await execute_cypher(cypher, params, tool_name="get_account_by_id")
    return json.dumps(result, default=str)



@agent.tool
async def run_cypher(ctx: RunContext[AgentDeps], query: str, parameters: str = "{}") -> str:
    """Execute a read-only Cypher query against the knowledge graph."""
    try:
        params = json.loads(parameters) if parameters else {}
    except json.JSONDecodeError:
        return json.dumps([{"error": "Invalid JSON parameters"}])
    params.setdefault("domain", settings.domain_id)
    try:
        result = await execute_cypher(query, params, tool_name="run_cypher")
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps([{"error": f"Cypher query failed: {e}"}])


@agent.tool
async def get_graph_schema(ctx: RunContext[AgentDeps]) -> str:
    """Get the knowledge graph schema (node labels and relationship types)."""
    result = await get_schema()
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------


async def handle_message(message: str, session_id: str | None = None) -> dict:
    """Handle an incoming chat message."""
    session_id = resolve_session_id(session_id)

    # Store user message (triggers entity extraction + preference detection)
    await store_message(session_id, "user", message)

    # Get rich context (messages + entities + preferences + traces)
    context = await get_context(session_id, query=message)
    history = context.get("messages", [])

    # Convert history to PydanticAI message format
    from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart
    message_history = []
    for msg in history:
        if msg["role"] == "user":
            message_history.append(
                ModelRequest(parts=[UserPromptPart(content=msg["content"])])
            )
        elif msg["role"] == "assistant":
            message_history.append(
                ModelResponse(parts=[TextPart(content=msg["content"])])
            )

    deps = AgentDeps(session_id=session_id)
    result = await agent.run(
        message, deps=deps, message_history=message_history
    )

    response_text = result.output or ""
    if not response_text.strip():
        response_text = "I searched the knowledge graph but couldn't find relevant results for your query. Could you try rephrasing your question?"
    assistant_result = await store_message(session_id, "assistant", response_text)

    return {
        "response": response_text,
        "session_id": session_id,
        "graph_data": None,
        "entities_extracted": (assistant_result or {}).get("entities", []),
        "preferences_detected": (assistant_result or {}).get("preferences", []),
    }


async def handle_message_stream(message: str, session_id: str | None = None) -> dict:
    """Handle a chat message with streaming text deltas via the collector event queue."""
    from app.context_graph_client import get_collector

    session_id = resolve_session_id(session_id)

    collector = get_collector()
    await store_message(session_id, "user", message)

    # Get rich context (messages + entities + preferences + traces)
    context = await get_context(session_id, query=message)
    history = context.get("messages", [])

    # Convert history to PydanticAI message format
    from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart
    message_history = []
    for msg in history:
        if msg["role"] == "user":
            message_history.append(
                ModelRequest(parts=[UserPromptPart(content=msg["content"])])
            )
        elif msg["role"] == "assistant":
            message_history.append(
                ModelResponse(parts=[TextPart(content=msg["content"])])
            )

    deps = AgentDeps(session_id=session_id)
    # Use agent.run() (not run_stream) so the full agent loop completes —
    # including all tool calls — before we emit the final text.
    # run_stream stops at the first text part, so it cuts off before tool
    # results are incorporated when Claude generates "I'll search..." + a tool
    # call in the same response.  Tool events (tool_start / tool_end) are still
    # pushed to the SSE queue by execute_cypher during the run.
    result = await agent.run(
        message, deps=deps, message_history=message_history
    )

    response_text = result.output or ""
    if not response_text.strip():
        response_text = "I searched the knowledge graph but couldn't find relevant results for your query. Could you try rephrasing your question?"

    collector.emit_text_delta(response_text)
    assistant_result = await store_message(session_id, "assistant", response_text)
    if assistant_result:
        collector.emit_entities_extracted(assistant_result.get("entities", []))
        collector.emit_preferences_detected(assistant_result.get("preferences", []))
    collector.emit_done(response_text, session_id)

    return {
        "response": response_text,
        "session_id": session_id,
        "graph_data": None,
    }
