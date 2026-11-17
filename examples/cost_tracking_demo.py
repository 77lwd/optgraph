# -*- coding: utf-8 -*-
"""
Cost Tracking Demo - 完整的成本追踪使用示例

展示如何在LangGraph workflow中追踪LLM调用成本
"""

import asyncio
from typing import Literal
from langgraph.graph import StateGraph, MessagesState, END
from langchain_core.messages import HumanMessage, AIMessage


# ============= Mock LLM for Demo =============
# 在实际使用中，替换为：from langchain_openai import ChatOpenAI

class MockLLM:
    """模拟LLM（避免实际API调用）"""

    def __init__(self, model: str = "gpt-4"):
        self.model_name = model
        self.callbacks = []

    def invoke(self, input_text):
        """模拟LLM调用"""
        # 模拟token使用
        input_tokens = len(str(input_text).split()) * 10
        output_tokens = 50

        # 创建mock响应
        response = type('obj', (object,), {
            'llm_output': {
                'model_name': self.model_name,
                'token_usage': {
                    'prompt_tokens': input_tokens,
                    'completion_tokens': output_tokens,
                }
            }
        })()

        # 触发callbacks
        for callback in self.callbacks:
            if hasattr(callback, 'on_llm_end'):
                callback.on_llm_end(response)

        return AIMessage(content=f"Response from {self.model_name}")


# ============= Demo 1: 独立使用CostTracker =============

def demo_1_standalone():
    """Demo 1: 独立使用CostTracker（不使用OptGraph）"""

    print("=" * 70)
    print("Demo 1: 独立使用CostTracker")
    print("=" * 70)

    from optgraph import CostTracker, enable_cost_tracking

    # 方法1: 手动创建tracker和callback
    print("\n[方法1] 手动创建tracker和callback")
    tracker = CostTracker(db_path=":memory:")
    tracker.set_budget(limit=10.0)

    llm = MockLLM(model="gpt-4")

    # 使用便捷函数包装LLM
    llm = enable_cost_tracking(llm, cost_tracker=tracker)

    # 调用LLM
    for i in range(3):
        response = llm.invoke(f"Hello {i}")
        print(f"  Call {i+1}: {response.content}")

    # 查询统计
    stats = tracker.get_stats()
    print(f"\n[统计]")
    print(f"  总调用次数: {stats['total_calls']}")
    print(f"  总成本: ${stats['total_cost']:.4f}")
    print(f"  总tokens: {stats['total_tokens']}")

    # 检查预算
    budget = tracker.check_budget()
    print(f"\n[预算]")
    print(f"  已使用: ${budget['current_spend']:.4f}")
    print(f"  限制: ${budget['budget_limit']:.2f}")
    print(f"  使用率: {budget['usage_percent']:.1f}%")
    print(f"  是否超限: {'否' if budget['within_budget'] else '是'}")


# ============= Demo 2: 与OptGraph集成 =============

def demo_2_optgraph_integration():
    """Demo 2: 与OptGraph.compile()集成（推荐方式）"""

    print("\n\n" + "=" * 70)
    print("Demo 2: 与OptGraph集成（推荐方式）")
    print("=" * 70)

    from optgraph import OptGraph, enable_cost_tracking

    # 定义workflow节点
    def agent_node(state: MessagesState) -> MessagesState:
        """Agent节点 - 关键：需要手动wrap LLM"""

        # 创建LLM
        llm = MockLLM(model="gpt-4")

        # 重要！使用app.cost_tracker来wrap LLM
        # 这样才能追踪成本
        llm = enable_cost_tracking(
            llm,
            cost_tracker=app.cost_tracker,  # 使用app的tracker
            thread_id="conversation_123"     # 可选：指定thread_id
        )

        # 调用LLM
        response = llm.invoke(state["messages"])

        return {"messages": [response]}

    def tools_node(state: MessagesState) -> MessagesState:
        """工具节点"""
        return {"messages": [AIMessage(content="Tool result")]}

    def route_decision(state: dict) -> Literal["tools", "__end__"]:
        """路由决策"""
        # 简单示例：直接结束
        return END

    # 构建graph
    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route_decision, {"tools": "tools", END: END})
    graph.add_edge("tools", END)

    # 编译时启用cost tracking
    print("\n[编译] 启用cost tracking")
    app = OptGraph.compile(
        graph,
        enable_cost_tracking=True,
        cost_tracker_config={
            "db_path": ":memory:",
            "budget_limit": 5.0,  # $5预算
        }
    )

    # 验证tracker已创建
    print(f"  Tracker: {app.cost_tracker}")
    print(f"  Callback: {app.cost_tracking_callback}")

    # 运行workflow（多次）
    print("\n[运行] 执行3次workflow")
    for i in range(3):
        result = app.invoke({
            "messages": [HumanMessage(content=f"Query {i+1}")]
        })
        print(f"  Run {i+1}: {result['messages'][-1].content}")

    # 查询统计
    stats = app.cost_tracker.get_stats()
    print(f"\n[全局统计]")
    print(f"  总调用: {stats['total_calls']}")
    print(f"  总成本: ${stats['total_cost']:.4f}")

    # 按thread查询
    thread_stats = app.cost_tracker.get_stats(thread_id="conversation_123")
    print(f"\n[Thread 'conversation_123' 统计]")
    print(f"  调用次数: {thread_stats['total_calls']}")
    print(f"  成本: ${thread_stats['total_cost']:.4f}")


# ============= Demo 3: 预算控制 =============

def demo_3_budget_enforcement():
    """Demo 3: 预算超限自动停止"""

    print("\n\n" + "=" * 70)
    print("Demo 3: 预算控制（超限自动停止）")
    print("=" * 70)

    from optgraph import CostTracker, enable_cost_tracking, BudgetExceededError

    # 创建低预算tracker
    tracker = CostTracker(db_path=":memory:")
    tracker.set_budget(limit=0.01)  # 仅$0.01预算

    print(f"\n[设置] 预算限制: $0.01")

    # 使用便宜的模型
    llm = MockLLM(model="gpt-3.5-turbo")
    llm = enable_cost_tracking(llm, cost_tracker=tracker)

    # 持续调用直到预算耗尽
    print("\n[执行] 持续调用LLM直到预算耗尽...")
    call_count = 0

    try:
        for i in range(100):
            llm.invoke(f"Call {i} with some text to generate tokens")
            call_count += 1

            # 显示进度
            if (i + 1) % 10 == 0:
                budget = tracker.check_budget()
                print(f"  {i+1} calls: ${budget['current_spend']:.6f} / ${budget['budget_limit']:.2f}")

    except BudgetExceededError as e:
        print(f"\n[预算超限] {e}")
        print(f"  成功调用次数: {call_count}")

        # 最终统计
        stats = tracker.get_stats()
        budget = tracker.check_budget()
        print(f"\n[最终统计]")
        print(f"  总调用: {stats['total_calls']}")
        print(f"  总成本: ${stats['total_cost']:.6f}")
        print(f"  预算限制: ${budget['budget_limit']:.2f}")
        print(f"  超限金额: ${budget['current_spend'] - budget['budget_limit']:.6f}")


# ============= Demo 4: 多用户/多线程统计 =============

def demo_4_multi_user_stats():
    """Demo 4: 按用户/线程分别统计成本"""

    print("\n\n" + "=" * 70)
    print("Demo 4: 多用户/多线程成本追踪")
    print("=" * 70)

    from optgraph import CostTracker, enable_cost_tracking

    tracker = CostTracker(db_path=":memory:")

    # 模拟3个用户，每个用户2个会话
    users = ["alice", "bob", "charlie"]
    threads_per_user = 2

    print("\n[模拟] 3个用户，每个用户2个会话")

    for user in users:
        for thread_num in range(threads_per_user):
            thread_id = f"{user}_thread_{thread_num}"

            # 为每个会话创建LLM
            llm = MockLLM(model="gpt-4")
            llm = enable_cost_tracking(
                llm,
                cost_tracker=tracker,
                user_id=user,
                thread_id=thread_id
            )

            # 每个会话调用2次
            for i in range(2):
                llm.invoke(f"Message {i} from {user}")

    # 全局统计
    global_stats = tracker.get_stats()
    print(f"\n[全局统计]")
    print(f"  总调用: {global_stats['total_calls']}")
    print(f"  总成本: ${global_stats['total_cost']:.4f}")

    # 按用户统计
    print(f"\n[按用户统计]")
    for user in users:
        user_stats = tracker.get_stats(user_id=user)
        print(f"  {user:8s}: {user_stats['total_calls']} calls, ${user_stats['total_cost']:.4f}")

    # 按线程统计（示例）
    print(f"\n[按线程统计（部分）]")
    for user in ["alice", "bob"]:
        thread_id = f"{user}_thread_0"
        thread_stats = tracker.get_stats(thread_id=thread_id)
        print(f"  {thread_id:20s}: {thread_stats['total_calls']} calls, ${thread_stats['total_cost']:.4f}")


# ============= Demo 5: 实际使用模式 =============

def demo_5_real_world_pattern():
    """Demo 5: 实际生产环境使用模式"""

    print("\n\n" + "=" * 70)
    print("Demo 5: 生产环境使用模式")
    print("=" * 70)

    from optgraph import OptGraph, enable_cost_tracking

    print("\n[场景] 多轮对话Agent，追踪每个会话的成本")

    # 定义workflow
    # 注意：为了传递thread_id/user_id，需要使用闭包或其他方式
    # 这里我们使用一个简单的字典来模拟context
    current_context = {}

    def agent_node(state: MessagesState) -> MessagesState:
        # 从context获取当前的thread_id和user_id
        thread_id = current_context.get("thread_id", "default")
        user_id = current_context.get("user_id", "anonymous")

        # 创建并包装LLM
        llm = MockLLM(model="gpt-4")
        llm = enable_cost_tracking(
            llm,
            cost_tracker=app.cost_tracker,
            thread_id=thread_id,
            user_id=user_id
        )

        # 调用LLM
        messages = state["messages"]
        response = llm.invoke(messages)

        return {"messages": [response]}

    # 构建graph
    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)

    # 编译
    app = OptGraph.compile(
        graph,
        enable_cost_tracking=True,
        cost_tracker_config={
            "db_path": "production_costs.db",  # 持久化数据库
            "budget_limit": 1000.0,            # $1000/月预算
        }
    )

    print(f"  Database: production_costs.db")
    print(f"  Budget: $1000.00")

    # 模拟多个会话
    print("\n[运行] 模拟3个用户的多轮对话")

    conversations = [
        {"user": "alice", "thread": "alice_chat_001", "turns": 3},
        {"user": "bob", "thread": "bob_chat_001", "turns": 2},
        {"user": "alice", "thread": "alice_chat_002", "turns": 4},
    ]

    for conv in conversations:
        print(f"\n  {conv['user']}/{conv['thread']}: {conv['turns']} turns")

        # 设置当前context（在实际应用中，可以使用contextvars或其他方式）
        current_context["thread_id"] = conv["thread"]
        current_context["user_id"] = conv["user"]

        for turn in range(conv["turns"]):
            result = app.invoke({
                "messages": [HumanMessage(content=f"Turn {turn+1}")]
            })

    # 汇总统计
    print("\n[成本报告]")
    print("-" * 70)

    # 总成本
    total_stats = app.cost_tracker.get_stats()
    print(f"总成本: ${total_stats['total_cost']:.4f} / $1000.00")
    print(f"总调用: {total_stats['total_calls']}")

    # 按用户
    print(f"\n按用户:")
    for user in ["alice", "bob"]:
        user_stats = app.cost_tracker.get_stats(user_id=user)
        print(f"  {user:8s}: ${user_stats['total_cost']:.4f} ({user_stats['total_calls']} calls)")

    # 按会话
    print(f"\n按会话:")
    for conv in conversations:
        thread_stats = app.cost_tracker.get_stats(thread_id=conv["thread"])
        print(f"  {conv['thread']:20s}: ${thread_stats['total_cost']:.4f} ({thread_stats['total_calls']} calls)")

    print("\n" + "=" * 70)


# ============= 主函数 =============

def main():
    """运行所有demo"""

    print("\n")
    print("=" * 70)
    print("OptGraph Cost Tracking Demo")
    print("=" * 70)
    print()
    print("本Demo展示如何在LangGraph workflow中追踪LLM API成本")
    print()

    # Demo 1: 独立使用
    demo_1_standalone()

    # Demo 2: 与OptGraph集成
    demo_2_optgraph_integration()

    # Demo 3: 预算控制
    demo_3_budget_enforcement()

    # Demo 4: 多用户统计
    demo_4_multi_user_stats()

    # Demo 5: 实际使用模式
    demo_5_real_world_pattern()

    # 总结
    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)
    print()
    print("关键要点:")
    print("1. 使用 OptGraph.compile(enable_cost_tracking=True) 创建tracker")
    print("2. 在agent_node中，用 enable_cost_tracking(llm, app.cost_tracker) 包装LLM")
    print("3. 可选：指定 thread_id 和 user_id 进行细粒度追踪")
    print("4. 使用 app.cost_tracker.get_stats() 查询成本统计")
    print("5. 设置 budget_limit 实现预算控制")
    print()
    print("实际使用时，替换 MockLLM 为真实LLM:")
    print("  from langchain_openai import ChatOpenAI")
    print("  llm = ChatOpenAI(model='gpt-4')")
    print()


if __name__ == "__main__":
    main()
