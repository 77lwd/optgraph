# -*- coding: utf-8 -*-
"""
Parallel Tool Execution Demo with LangGraph

Demonstrates how to execute multiple tool calls in parallel within LangGraph
"""

import asyncio
import time
from typing import Literal
from langgraph.graph import StateGraph, MessagesState, END
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from optgraph.parallel_executor import ParallelExecutor, Task


# ============= Mock Tools =============

async def weather_tool(city: str) -> str:
    """Fetch weather for a city (simulated 2s delay)"""
    print(f"  [Tool] Fetching weather for {city}...")
    await asyncio.sleep(2)
    return f"{city}: 25C, Sunny"


async def news_tool(topic: str) -> str:
    """Fetch news for a topic (simulated 3s delay)"""
    print(f"  [Tool] Fetching news about {topic}...")
    await asyncio.sleep(3)
    return f"Latest {topic} news: AI breakthroughs continue"


async def stock_tool(symbol: str) -> str:
    """Fetch stock price (simulated 2s delay)"""
    print(f"  [Tool] Fetching stock price for {symbol}...")
    await asyncio.sleep(2)
    return f"{symbol}: $150.25 (+2.5%)"


# ============= Nodes =============

def agent_node(state: MessagesState) -> MessagesState:
    """
    Agent decides which tools to call

    In a real implementation, this would use an LLM to analyze the user's
    request and generate tool calls. Here we use simple rules.
    """
    messages = state["messages"]
    last_message = messages[-1].content.lower()

    print(f"\n[Agent] Analyzing request: '{last_message}'")

    # Parse request to determine tool calls
    tool_calls = []

    if "weather" in last_message:
        # Extract cities
        if "beijing" in last_message:
            tool_calls.append(("weather", "Beijing"))
        if "shanghai" in last_message:
            tool_calls.append(("weather", "Shanghai"))
        if "shenzhen" in last_message:
            tool_calls.append(("weather", "Shenzhen"))

    if "news" in last_message:
        if "tech" in last_message:
            tool_calls.append(("news", "Tech"))
        if "ai" in last_message:
            tool_calls.append(("news", "AI"))

    if "stock" in last_message:
        if "aapl" in last_message or "apple" in last_message:
            tool_calls.append(("stock", "AAPL"))
        if "tsla" in last_message or "tesla" in last_message:
            tool_calls.append(("stock", "TSLA"))

    if not tool_calls:
        # No tools needed, direct response
        print("[Agent] No tools needed")
        return {"messages": [AIMessage(content="I can help with weather, news, and stock queries!")]}

    print(f"[Agent] Planning to call {len(tool_calls)} tools: {tool_calls}")

    # Store tool calls in state for the tool node
    # In real LangGraph with real LLMs, this would be structured as tool_calls
    return {
        "messages": [AIMessage(content=f"TOOL_CALLS:{tool_calls}")]
    }


async def parallel_tool_node(state: MessagesState) -> MessagesState:
    """
    Execute multiple tool calls in parallel

    This is the key innovation: instead of calling tools one by one,
    we detect which tools can run concurrently and execute them together.
    """
    messages = state["messages"]
    last_message = messages[-1].content

    # Parse tool calls from agent's message
    if not last_message.startswith("TOOL_CALLS:"):
        return {"messages": [AIMessage(content="No tools to execute")]}

    tool_calls_str = last_message.replace("TOOL_CALLS:", "")
    tool_calls = eval(tool_calls_str)  # In production, use proper parsing

    print(f"\n[Tool Node] Received {len(tool_calls)} tool calls")
    print(f"[Tool Node] Starting parallel execution...")

    start_time = time.time()

    # Create tasks for parallel executor
    tasks = []
    for idx, (tool_name, arg) in enumerate(tool_calls):
        task_id = f"{tool_name}_{arg}_{idx}"

        if tool_name == "weather":
            func = lambda a=arg: weather_tool(a)
        elif tool_name == "news":
            func = lambda a=arg: news_tool(a)
        elif tool_name == "stock":
            func = lambda a=arg: stock_tool(a)
        else:
            continue

        # All tool calls are independent (no dependencies)
        # In a more sophisticated system, we'd analyze dependencies
        task = Task(
            task_id=task_id,
            func=func,
            reads=set(),  # No dependencies
            writes={task_id}  # Each writes its own result
        )
        tasks.append(task)

    # Execute in parallel
    executor = ParallelExecutor()
    results = await executor.execute_batch(tasks)

    elapsed = time.time() - start_time

    # Format results
    results_text = "\n".join([f"- {k}: {v}" for k, v in results.items()])

    print(f"\n[Tool Node] All tools completed in {elapsed:.2f}s")
    print(f"[Tool Node] Results:\n{results_text}")

    return {
        "messages": [AIMessage(content=f"Tool Results:\n{results_text}\n(Completed in {elapsed:.2f}s)")]
    }


def route_decision(state: dict) -> Literal["tools", "__end__"]:
    """Route to tools or end"""
    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1].content

    if "TOOL_CALLS:" in last_message:
        return "tools"
    else:
        return END


# ============= Build Graph =============

def create_parallel_graph():
    """Create LangGraph with parallel tool execution"""

    workflow = StateGraph(MessagesState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", parallel_tool_node)

    # Entry point
    workflow.set_entry_point("agent")

    # Routing
    workflow.add_conditional_edges(
        "agent",
        route_decision,
        {
            "tools": "tools",
            END: END
        }
    )

    workflow.add_edge("tools", END)

    return workflow.compile()


# ============= Demo =============

async def demo():
    """Run demo scenarios"""

    app = create_parallel_graph()

    print("=" * 70)
    print("Parallel Tool Execution Demo")
    print("=" * 70)

    # Scenario 1: Multiple independent weather queries
    print("\n" + "="*70)
    print("Scenario 1: Check weather for 3 cities (parallel)")
    print("="*70)

    start = time.time()
    result = await app.ainvoke({
        "messages": [HumanMessage(content="What's the weather in Beijing, Shanghai, and Shenzhen?")]
    })
    total_time = time.time() - start

    print(f"\n[FINAL RESULT]")
    print(result["messages"][-1].content)
    print(f"\nTotal time: {total_time:.2f}s")
    print("Note: Serial would take ~6s, parallel takes ~2s (3x speedup)")

    # Scenario 2: Mixed tool calls
    print("\n\n" + "="*70)
    print("Scenario 2: Weather + News + Stock (parallel)")
    print("="*70)

    start = time.time()
    result = await app.ainvoke({
        "messages": [HumanMessage(content="Check weather in Beijing, tech news, and AAPL stock")]
    })
    total_time = time.time() - start

    print(f"\n[FINAL RESULT]")
    print(result["messages"][-1].content)
    print(f"\nTotal time: {total_time:.2f}s")
    print("Note: Serial would take ~7s (2+3+2), parallel takes ~3s (max of all)")


if __name__ == "__main__":
    asyncio.run(demo())
