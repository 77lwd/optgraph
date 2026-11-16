# -*- coding: utf-8 -*-
"""
Week 2 Day 1: Test Context Compression
验证AdaptiveCheckpointSaver的压缩效果
"""

from langgraph.graph import StateGraph, MessagesState, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optgraph.checkpointer import AdaptiveCheckpointSaver


# ============= 定义简单的Agent =============
def simple_agent(state: MessagesState) -> MessagesState:
    """简单的回声agent"""
    messages = state["messages"]
    last_message = messages[-1].content

    # 简单回应
    response = f"收到: {last_message}"

    return {"messages": [AIMessage(content=response)]}


# ============= 创建Graph =============
def create_test_graph(checkpointer):
    """创建测试用的graph"""
    workflow = StateGraph(MessagesState)

    workflow.add_node("agent", simple_agent)
    workflow.set_entry_point("agent")
    workflow.add_edge("agent", END)

    return workflow.compile(checkpointer=checkpointer)


# ============= 测试1: 基础压缩 =============
def test_basic_compression():
    """测试基础压缩功能"""
    print("\n" + "="*60)
    print("测试1: 基础压缩（threshold=200, keep_recent=3）")
    print("="*60)

    # 创建checkpointer（设置很低的threshold便于触发）
    checkpointer = AdaptiveCheckpointSaver(
        threshold=200,      # 低阈值，容易触发
        keep_recent=3       # 只保留最近3条
    )

    # 创建graph
    app = create_test_graph(checkpointer)

    # 发送10条消息
    thread_id = {"configurable": {"thread_id": "test-1"}}

    for i in range(1, 11):
        print(f"\n--- Round {i} ---")
        # 创建更长的消息内容
        long_content = f"这是第{i}条消息。" + "这是填充内容让token数增加。" * 10
        result = app.invoke(
            {"messages": [HumanMessage(content=long_content)]},
            config=thread_id
        )
        print(f"当前messages数量: {len(result['messages'])}")

    # 输出统计
    print("\n" + "="*60)
    print("压缩统计:")
    print("="*60)
    stats = checkpointer.get_compression_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")


# ============= 测试2: 重要性保留 =============
def test_importance_retention():
    """测试重要消息保留"""
    print("\n" + "="*60)
    print("测试2: 重要性保留")
    print("="*60)

    checkpointer = AdaptiveCheckpointSaver(
        threshold=150,
        keep_recent=2
    )

    app = create_test_graph(checkpointer)
    thread_id = {"configurable": {"thread_id": "test-2"}}

    # 发送不同类型的消息
    messages_to_send = [
        SystemMessage(content="你是一个助手"),  # 重要：system消息
        HumanMessage(content="普通消息1"),
        AIMessage(content="普通回复1"),
        HumanMessage(content="普通消息2"),
        AIMessage(content="Error: 发生了错误"),  # 重要：包含error
        HumanMessage(content="普通消息3"),
        AIMessage(content="普通回复3"),
        HumanMessage(content="普通消息4"),
        AIMessage(content="普通回复4"),
        HumanMessage(content="最后一条消息"),  # 重要：最近的
    ]

    state = {"messages": []}
    for i, msg in enumerate(messages_to_send):
        print(f"\n--- 发送第{i+1}条消息 ---")
        print(f"类型: {type(msg).__name__}, 内容: {msg.content[:30]}...")

        state = app.invoke(
            {"messages": state["messages"] + [msg]},
            config=thread_id
        )
        print(f"当前messages数量: {len(state['messages'])}")

    # 检查最终保留的消息
    print("\n" + "="*60)
    print("最终保留的消息:")
    print("="*60)
    for i, msg in enumerate(state['messages']):
        print(f"{i+1}. {type(msg).__name__}: {msg.content[:50]}")

    # 统计
    print("\n" + "="*60)
    print("压缩统计:")
    print("="*60)
    stats = checkpointer.get_compression_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")


# ============= 测试3: 不同参数对比 =============
def test_parameter_comparison():
    """对比不同参数的效果"""
    print("\n" + "="*60)
    print("测试3: 参数对比")
    print("="*60)

    configs = [
        {"threshold": 200, "keep_recent": 3},
        {"threshold": 200, "keep_recent": 5},
        {"threshold": 200, "keep_recent": 10},
    ]

    for config in configs:
        print(f"\n--- 配置: threshold={config['threshold']}, keep_recent={config['keep_recent']} ---")

        checkpointer = AdaptiveCheckpointSaver(**config)
        app = create_test_graph(checkpointer)
        thread_id = {"configurable": {"thread_id": f"test-{config['keep_recent']}"}}

        # 发送20条消息
        for i in range(1, 21):
            app.invoke(
                {"messages": [HumanMessage(content=f"消息{i}，添加一些内容增加token数量")]},
                config=thread_id
            )

        # 输出统计
        stats = checkpointer.get_compression_stats()
        print(f"总压缩次数: {stats['total_compressions']}")
        print(f"Token减少: {stats['avg_token_reduction_percent']}%")
        print(f"Messages: {stats['total_messages_before']} → {stats['total_messages_after']}")


# ============= 主函数 =============
def main():
    print("\n" + "="*60)
    print("Week 2 Day 1: Context Compression 测试")
    print("="*60)

    # 运行测试
    test_basic_compression()

    print("\n\n")
    test_importance_retention()

    print("\n\n")
    test_parameter_comparison()

    print("\n" + "="*60)
    print("所有测试完成！")
    print("="*60)


if __name__ == "__main__":
    main()
