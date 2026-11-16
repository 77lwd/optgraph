# -*- coding: utf-8 -*-
"""
LangGraph Hello World - 带调试输出的版本
用于理解完整的执行流程
"""

from langgraph.graph import StateGraph, MessagesState, END
from langgraph.config import get_config
from langchain_core.messages import HumanMessage, AIMessage
from typing import Literal
import json


# ============= 1. 定义工具 =============
def calculator(expression: str) -> str:
    """计算器工具"""
    try:
        result = eval(expression)
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


# ============= 2. 定义节点（加调试输出）=============
def agent_node(state: MessagesState) -> MessagesState:
    """Agent节点：模拟LLM的决策"""
    config = get_config()
    step = config.get("metadata", {}).get("langgraph_step", 0)
    node_name = config.get("metadata", {}).get("langgraph_node", "unknown")

    print("\n" + "="*60)
    print(f"[Node] [Step {step}] [{node_name}] 开始执行")
    print("="*60)

    messages = state["messages"]
    print(f"[Input] 输入state['messages']: {len(messages)} 条消息")
    for i, msg in enumerate(messages):
        print(f"   [{i}] {type(msg).__name__}: {msg.content[:50]}...")

    last_message = messages[-1].content
    print(f"\n[Thinking] 最后一条消息: {last_message}")

    # 简单的规则：如果包含数字和运算符，就调用工具
    if any(op in last_message for op in ["+", "-", "*", "/"]):
        print(f"[Decision] 决策: 需要调用计算器工具")
        result = {"messages": [AIMessage(content="需要计算")]}
    else:
        print(f"[Decision] 决策: 直接回答")
        result = {"messages": [AIMessage(content="你好！我是计算助手，发送数学表达式给我吧，比如: 123+456")]}

    print(f"[Output] 输出: {result['messages'][0].content}")
    print("="*60)

    return result


def tool_node(state: MessagesState) -> MessagesState:
    """Tool节点：执行工具"""
    config = get_config()
    step = config.get("metadata", {}).get("langgraph_step", 0)
    node_name = config.get("metadata", {}).get("langgraph_node", "unknown")

    print("\n" + "="*60)
    print(f"[Node] [Step {step}] [{node_name}] 开始执行")
    print("="*60)

    messages = state["messages"]
    print(f"[Input] 输入state['messages']: {len(messages)} 条消息")
    for i, msg in enumerate(messages):
        print(f"   [{i}] {type(msg).__name__}: {msg.content[:50]}...")

    # 从第一条消息（用户输入）里提取计算表达式
    user_input = messages[0].content

    print(f"\n[Tool] 执行计算: {user_input}")
    result = calculator(user_input)
    print(f"[Result] 计算结果: {result}")

    output = {"messages": [AIMessage(content=result)]}
    print(f"[Output] 输出: {output['messages'][0].content}")
    print("="*60)

    return output


# ============= 3. 路由函数 =============
def route_decision(state: dict) -> Literal["tool", "__end__"]:
    """决定下一步去哪个节点"""
    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1].content

    if "需要计算" in last_message:
        print("\n[Route] 路由决策: 去 tool 节点")
        return "tool"
    else:
        print("\n[Route] 路由决策: 结束")
        return END


# ============= 4. 构建Graph =============
def create_graph():
    """创建LangGraph应用"""
    workflow = StateGraph(MessagesState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tool", tool_node)

    workflow.set_entry_point("agent")

    workflow.add_conditional_edges(
        "agent",
        route_decision,
        {
            "tool": "tool",
            END: END
        }
    )

    workflow.add_edge("tool", END)

    return workflow.compile()


# ============= 5. 运行 =============
def main():
    print("\n" + "="*60)
    print("LangGraph Hello World - 调试版")
    print("="*60)

    app = create_graph()

    print("\n" + "="*60)
    print("【测试1】普通对话")
    print("="*60)

    result1 = app.invoke({
        "messages": [HumanMessage(content="你好")]
    })

    print("\n" + "-"*60)
    print("最终结果:")
    print(f"messages数量: {len(result1['messages'])}")
    print(f"最后一条: {result1['messages'][-1].content}")
    print("-"*60)

    print("\n\n" + "="*60)
    print("【测试2】数学计算")
    print("="*60)

    result2 = app.invoke({
        "messages": [HumanMessage(content="123 + 456")]
    })

    print("\n" + "-"*60)
    print("最终结果:")
    print(f"messages数量: {len(result2['messages'])}")
    print(f"最后一条: {result2['messages'][-1].content}")
    print("-"*60)


if __name__ == "__main__":
    main()
