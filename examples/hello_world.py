# -*- coding: utf-8 -*-
"""
LangGraph Hello World - 最简单的例子
任务：一个能做加法的AI助手

运行：python hello_world.py
"""

from langgraph.graph import StateGraph, MessagesState, END
from langchain_core.messages import HumanMessage, AIMessage
from typing import Literal

# ============= 1. 定义工具 =============
def calculator(expression: str) -> str:
    """计算器工具"""
    try:
        result = eval(expression)  # 生产环境别这么干，这里只是演示
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"


# ============= 2. 定义节点 =============
def agent_node(state: MessagesState) -> MessagesState:
    """Agent节点：模拟LLM的决策"""
    messages = state["messages"]
    last_message = messages[-1].content

    print(f"\n[Agent节点] 收到消息: {last_message}")

    # 简单的规则：如果包含数字和运算符，就调用工具
    if any(op in last_message for op in ["+", "-", "*", "/"]):
        print("[Agent节点] 决策: 需要调用计算器工具")
        return {"messages": [AIMessage(content="需要计算")]}
    else:
        print("[Agent节点] 决策: 直接回答")
        return {"messages": [AIMessage(content="你好！我是计算助手，发送数学表达式给我吧，比如: 123+456")]}


def tool_node(state: MessagesState) -> MessagesState:
    """Tool节点：执行工具"""
    messages = state["messages"]
    # 从第一条消息（用户输入）里提取计算表达式
    user_input = messages[0].content

    print(f"[Tool节点] 执行计算: {user_input}")
    result = calculator(user_input)
    print(f"[Tool节点] 计算结果: {result}")

    return {"messages": [AIMessage(content=result)]}


# ============= 3. 路由函数 =============
def route_decision(state: dict) -> Literal["tool", "__end__"]:
    """决定下一步去哪个节点"""
    # 检查是否需要调用工具
    messages = state.get("messages", [])
    if not messages:
        return END

    last_message = messages[-1].content

    # 如果最后一条消息是"需要计算"，就去tool节点
    if "需要计算" in last_message:
        return "tool"
    else:
        return END


# ============= 4. 构建Graph =============
def create_graph():
    """创建LangGraph应用"""

    # 定义state schema
    workflow = StateGraph(MessagesState)

    # 添加节点
    workflow.add_node("agent", agent_node)
    workflow.add_node("tool", tool_node)

    # 设置入口
    workflow.set_entry_point("agent")

    # 添加条件边（根据agent的决策，决定去tool还是结束）
    workflow.add_conditional_edges(
        "agent",
        route_decision,
        {
            "tool": "tool",
            END: END
        }
    )

    # tool执行完后，直接结束（不回到agent）
    workflow.add_edge("tool", END)

    return workflow.compile()


# ============= 5. 运行 =============
def main():
    print("=" * 60)
    print("LangGraph Hello World - 计算助手")
    print("=" * 60)

    # 创建app
    app = create_graph()

    # 可视化graph（可选）
    try:
        print("\n流程图（Mermaid格式）:")
        print(app.get_graph().draw_mermaid())
    except:
        pass

    print("\n" + "=" * 60)

    # 测试1：不需要工具
    print("\n【测试1】普通对话")
    result = app.invoke({
        "messages": [HumanMessage(content="你好")]
    })
    print(f"\n最终输出: {result['messages'][-1].content}")

    print("\n" + "=" * 60)

    # 测试2：需要工具
    print("\n【测试2】数学计算")
    result = app.invoke({
        "messages": [HumanMessage(content="123 + 456")]
    })
    print(f"\n最终输出: {result['messages'][-1].content}")

    print("\n" + "=" * 60)
    print("[SUCCESS] Done!")
    print("\nWhat you just saw:")
    print("1. [Agent node] decision making")
    print("2. [Tool node] execution")
    print("3. State flowing between nodes")
    print("\nThis is LangGraph core: Nodes + State + Routing")


if __name__ == "__main__":
    main()
