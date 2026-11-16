# LangGraph 完整拆解：从用户代码到底层执行

> **目标读者**：需要深入理解 LangGraph 内部机制的开发者  
> **阅读时间**：30-40 分钟  
> **知识水平**：熟悉 Python，了解基本的 Agent 概念

---

## 📋 目录

1. [概览：LangGraph 是什么](#1-概览langgraph-是什么)
2. [用户视角：如何使用 LangGraph](#2-用户视角如何使用-langgraph)
3. [编译阶段：从 Graph 到 Pregel](#3-编译阶段从-graph-到-pregel)
4. [执行引擎：PregelLoop 核心流程](#4-执行引擎pregelloop-核心流程)
5. [State 管理：Channel 机制](#5-state-管理channel-机制)
6. [Checkpoint：持久化与恢复](#6-checkpoint持久化与恢复)
7. [完整示例：逐步 Trace](#7-完整示例逐步-trace)
8. [高级特性](#8-高级特性)
9. [核心概念总结](#9-核心概念总结)

---

## 1. 概览：LangGraph 是什么

### 1.1 一句话定义

**LangGraph = 状态机 + 执行引擎 + 持久化**

它让你用"流程图"的方式定义 Agent 的执行逻辑，框架负责：
- 按照流程图执行节点
- 管理节点间的状态传递
- 处理持久化和恢复

### 1.2 核心设计理念

**灵感来源**：Google Pregel（图计算框架）

**核心思想**：
- **图结构定义**：用户定义 Nodes（节点）和 Edges（边）
- **迭代执行**：类似 Pregel 的 "超步"（superstep），每个 tick 执行一批节点
- **状态驱动**：节点通过 State 通信，而非直接调用

### 1.3 与传统编程的区别

```python
# 传统编程：直接调用
def workflow():
    result1 = step1()
    result2 = step2(result1)
    return step3(result2)

# LangGraph：声明式定义
graph = StateGraph(State)
graph.add_node("step1", step1)
graph.add_node("step2", step2)
graph.add_node("step3", step3)
graph.add_edge("step1", "step2")
graph.add_edge("step2", "step3")
```

---

## 2. 用户视角：如何使用 LangGraph

### 2.1 最小示例

```python
from langgraph.graph import StateGraph, MessagesState, START, END

# 1. 定义节点函数
def chatbot(state: MessagesState):
    # 节点逻辑：调用 LLM
    return {"messages": [llm.invoke(state["messages"])]}

# 2. 创建 Graph
workflow = StateGraph(MessagesState)

# 3. 添加节点
workflow.add_node("chatbot", chatbot)

# 4. 添加边
workflow.add_edge(START, "chatbot")
workflow.add_edge("chatbot", END)

# 5. 编译
app = workflow.compile()

# 6. 运行
result = app.invoke({"messages": [("user", "Hello")]})
```

### 2.2 关键概念

#### State（状态）

```python
from typing import Annotated
from langgraph.graph import MessagesState

# MessagesState 是内置的，包含一个 messages 字段
class MessagesState(TypedDict):
    messages: Annotated[list, add_messages]  # 特殊的 reducer

# 自定义 State
class MyState(TypedDict):
    user_input: str
    agent_response: str
    counter: int
```

**State 的作用**：
- 节点间唯一的通信方式
- 每个节点读取 State，返回 State 的部分更新
- 框架自动合并更新（通过 reducer）

#### Node（节点）

```python
# 节点就是一个函数
def my_node(state: MyState) -> dict:
    # 读取 state
    user_input = state["user_input"]
    
    # 执行逻辑
    response = process(user_input)
    
    # 返回部分更新
    return {"agent_response": response}
```

**节点的约定**：
- 输入：完整的 State
- 输出：State 的部分更新（dict）
- 框架会自动合并返回值到 State

#### Edge（边）

```python
# 普通边：固定连接
workflow.add_edge("node1", "node2")

# 条件边：根据 state 动态决定
def should_continue(state):
    if state["counter"] < 10:
        return "continue"
    else:
        return "end"

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "agent",  # 循环
        "end": END
    }
)
```

---

## 3. 编译阶段：从 Graph 到 Pregel

### 3.1 编译做了什么

```python
app = workflow.compile()
```

这一步发生了什么？

#### 步骤 1：创建 Channel

```python
# 伪代码
channels = {}
for field_name, field_type in State.__annotations__.items():
    # 为每个 State 字段创建一个 Channel
    channels[field_name] = create_channel(field_type)
```

**Channel 是什么？**
- State 的存储容器
- 每个 State 字段对应一个 Channel
- Channel 知道如何合并更新（通过 reducer）

#### 步骤 2：构建执行图

```python
# 伪代码
nodes = {}
for node_name, node_func in user_nodes:
    nodes[node_name] = PregelNode(
        func=node_func,
        input_channels=all_channels,   # 读取所有 channels
        output_channels=all_channels   # 写入所有 channels
    )
```

#### 步骤 3：构建边的映射

```python
# 伪代码
edges_map = {
    "node1": ["node2"],           # node1 → node2
    "node2": ["node3", "node4"],  # node2 → node3 和 node4
}
```

#### 步骤 4：创建 Pregel 对象

```python
pregel = Pregel(
    nodes=nodes,
    channels=channels,
    input_channels=["messages"],
    output_channels=["messages"],
    stream_channels=["messages"],
)
```

### 3.2 Pregel 对象

**Pregel 是编译后的可执行对象**，包含：
- `nodes`: 所有节点的映射
- `channels`: State 的存储
- `edges`: 边的关系
- `checkpointer`: 持久化配置（可选）

---

## 4. 执行引擎：PregelLoop 核心流程

### 4.1 执行入口

```python
result = app.invoke({"messages": [("user", "Hello")]})
```

实际调用链：
```
app.invoke() 
  → Pregel.invoke() 
    → PregelLoop.tick() [循环]
```

### 4.2 PregelLoop：核心循环

```python
# 简化的伪代码
class PregelLoop:
    def run(self, input_data):
        # 1. 初始化
        self.checkpoint = self.load_checkpoint()
        self.channels.update(input_data)
        
        # 2. 主循环
        while True:
            # 2.1 准备下一批任务
            tasks = self.prepare_next_tasks()
            
            if not tasks:
                break  # 没有任务了，结束
            
            # 2.2 执行任务
            results = self.execute_tasks(tasks)
            
            # 2.3 更新 channels
            self.apply_writes(results)
            
            # 2.4 保存 checkpoint
            self.save_checkpoint()
        
        # 3. 返回最终 state
        return self.read_channels()
```

### 4.3 关键函数详解

#### 4.3.1 `prepare_next_tasks()`

**作用**：决定下一个 tick 要执行哪些节点

```python
def prepare_next_tasks(self):
    # 情况 1：第一次执行，找入口节点
    if self.step == 0:
        return [Task(name=START)]
    
    # 情况 2：根据上一个 tick 的节点输出，找下一批节点
    next_nodes = []
    for completed_node in self.last_completed:
        # 查找边
        next_nodes.extend(self.edges[completed_node])
    
    # 情况 3：条件边，需要执行路由函数
    for node in next_nodes:
        if node.is_conditional:
            state = self.read_channels()
            route = node.route_func(state)
            next_nodes.append(self.edges[node][route])
    
    return [Task(name=n) for n in next_nodes]
```

**Task 对象**：
```python
class Task:
    name: str           # 节点名称
    input: dict         # 输入（从 channels 读取）
    writes: list        # 执行后的输出
```

#### 4.3.2 `execute_tasks(tasks)`

**作用**：并行执行一批节点

```python
def execute_tasks(self, tasks):
    results = []
    for task in tasks:
        # 1. 准备输入：从 channels 读取
        input_state = self.read_channels()
        
        # 2. 执行节点函数
        node_func = self.nodes[task.name]
        output = node_func(input_state)
        
        # 3. 记录输出
        task.writes = output
        results.append(task)
    
    return results
```

#### 4.3.3 `apply_writes(results)`

**作用**：将节点输出写入 channels

```python
def apply_writes(self, results):
    for task in results:
        for key, value in task.writes.items():
            # 调用 channel 的 update 方法
            self.channels[key].update(value)
```

### 4.4 执行示例

假设有这样的图：
```
START → agent → tools → agent → END
```

**Tick 0**:
- `prepare_next_tasks()` → [agent]
- `execute_tasks()` → agent 返回 tool_call
- `apply_writes()` → 更新 messages

**Tick 1**:
- `prepare_next_tasks()` → [tools]（条件边决定）
- `execute_tasks()` → tools 返回结果
- `apply_writes()` → 更新 messages

**Tick 2**:
- `prepare_next_tasks()` → [agent]
- `execute_tasks()` → agent 返回最终答案
- `apply_writes()` → 更新 messages

**Tick 3**:
- `prepare_next_tasks()` → [END]
- 循环结束

---

## 5. State 管理：Channel 机制

### 5.1 Channel 是什么

**Channel = State 字段的存储 + 更新逻辑**

```python
class Channel:
    def __init__(self, reducer=None):
        self.value = None
        self.reducer = reducer or replace
    
    def update(self, new_value):
        if self.reducer:
            self.value = self.reducer(self.value, new_value)
        else:
            self.value = new_value
    
    def get(self):
        return self.value
```

### 5.2 Reducer：合并策略

**内置的 reducer**：

```python
# 1. replace（默认）：直接替换
def replace(old, new):
    return new

# 2. add_messages：合并消息列表
def add_messages(old, new):
    # 智能合并：
    # - 新消息追加
    # - 相同 id 的消息替换
    # - 支持 RemoveMessage
    result = old.copy()
    for msg in new:
        if isinstance(msg, RemoveMessage):
            result = [m for m in result if m.id != msg.id]
        else:
            result.append(msg)
    return result
```

**自定义 reducer**：

```python
from typing import Annotated

def add_numbers(old: int, new: int) -> int:
    return old + new

class MyState(TypedDict):
    counter: Annotated[int, add_numbers]  # 使用自定义 reducer
```

### 5.3 Channel 的类型

```python
# 1. LastValue - 保留最后一个值
channels["user_input"] = LastValue(str)

# 2. Topic - 消息队列（用于 messages）
channels["messages"] = Topic(list, reducer=add_messages)

# 3. BinaryOperator - 自定义合并
channels["counter"] = BinaryOperator(int, operator=add)
```

---

## 6. Checkpoint：持久化与恢复

### 6.1 Checkpoint 是什么

**Checkpoint = 某个时刻的完整 State 快照**

```python
class Checkpoint:
    id: str                    # checkpoint_id
    channel_values: dict       # 所有 channels 的值
    pending_writes: list       # 尚未应用的写入
    metadata: dict             # 元数据（step, run_id 等）
```

### 6.2 MemorySaver：内存持久化

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# 使用 thread_id 区分不同的对话
config = {"configurable": {"thread_id": "conversation-1"}}

# 第一次调用
app.invoke({"messages": [("user", "Hello")]}, config)

# 第二次调用，自动加载上一次的 state
app.invoke({"messages": [("user", "Goodbye")]}, config)
```

### 6.3 Checkpoint 的生命周期

```python
# PregelLoop 中的使用
class PregelLoop:
    def run(self, input_data, config):
        # 1. 加载 checkpoint
        checkpoint = self.checkpointer.get(config["thread_id"])
        if checkpoint:
            self.channels.from_checkpoint(checkpoint)
        
        # 2. 执行循环
        while True:
            tasks = self.prepare_next_tasks()
            results = self.execute_tasks(tasks)
            self.apply_writes(results)
            
            # 3. 每个 tick 后保存
            self.checkpointer.put(
                thread_id=config["thread_id"],
                checkpoint=self.create_checkpoint()
            )
        
        return self.read_channels()
```

### 6.4 Checkpoint 的高级用法

#### 恢复到历史状态

```python
# 获取历史 checkpoints
history = app.get_state_history(config)

for state in history:
    print(f"Step {state.metadata['step']}: {state.values}")

# 恢复到特定 checkpoint
old_state = history[2]  # 第 2 步
app.update_state(config, old_state.values)
```

#### 人工干预

```python
# 1. 运行到某个点
app.invoke(input_data, config)

# 2. 检查当前 state
current_state = app.get_state(config)

# 3. 修改 state
app.update_state(config, {"messages": [修改后的消息]})

# 4. 继续运行
app.invoke(None, config)  # 从当前 state 继续
```

---

## 7. 完整示例：逐步 Trace

### 7.1 示例代码

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langchain_core.messages import HumanMessage, AIMessage

def agent(state: MessagesState):
    messages = state["messages"]
    # 模拟 LLM 返回 tool_call
    return {
        "messages": [AIMessage(content="", tool_calls=[
            {"name": "search", "args": {"query": "weather"}}
        ])]
    }

def tools(state: MessagesState):
    # 执行工具
    return {
        "messages": [AIMessage(content="Tool result: Sunny")]
    }

def should_continue(state: MessagesState):
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"

# 构建图
workflow = StateGraph(MessagesState)
workflow.add_node("agent", agent)
workflow.add_node("tools", tools)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {
    "tools": "tools",
    "end": END
})
workflow.add_edge("tools", "agent")

app = workflow.compile()
```

### 7.2 执行 Trace

#### 初始输入
```python
input_data = {"messages": [HumanMessage(content="What's the weather?")]}
```

#### Tick 0

**1. prepare_next_tasks()**
```python
step = 0
→ 返回 [Task(name="agent")]
```

**2. execute_tasks()**
```python
# 读取 channels
state = {"messages": [HumanMessage(content="What's the weather?")]}

# 执行 agent
output = agent(state)
→ {"messages": [AIMessage(tool_calls=[...])]}

# 记录 task
task.writes = output
```

**3. apply_writes()**
```python
# 合并到 channels["messages"]
old_messages = [HumanMessage(...)]
new_messages = [AIMessage(tool_calls=[...])]
→ messages = [HumanMessage(...), AIMessage(tool_calls=[...])]
```

**4. save_checkpoint()**
```python
checkpoint = {
    "channel_values": {"messages": [HumanMessage(...), AIMessage(...)]},
    "metadata": {"step": 0}
}
```

#### Tick 1

**1. prepare_next_tasks()**
```python
# 上一个节点：agent
# 查找条件边
state = read_channels()
route = should_continue(state)  → "tools"
→ 返回 [Task(name="tools")]
```

**2. execute_tasks()**
```python
state = {"messages": [HumanMessage(...), AIMessage(tool_calls=[...])]}
output = tools(state)
→ {"messages": [AIMessage(content="Tool result: Sunny")]}
```

**3. apply_writes()**
```python
messages = [
    HumanMessage(...),
    AIMessage(tool_calls=[...]),
    AIMessage(content="Tool result: Sunny")
]
```

#### Tick 2

**1. prepare_next_tasks()**
```python
# tools → agent
→ 返回 [Task(name="agent")]
```

**2. execute_tasks()**
```python
state = {"messages": [HumanMessage(...), AIMessage(...), AIMessage(...)]}
output = agent(state)
→ {"messages": [AIMessage(content="It's sunny!")]}
```

**3. apply_writes()**
```python
messages = [
    HumanMessage(...),
    AIMessage(tool_calls=[...]),
    AIMessage(content="Tool result: Sunny"),
    AIMessage(content="It's sunny!")
]
```

#### Tick 3

**1. prepare_next_tasks()**
```python
route = should_continue(state)  → "end"
→ 返回 [Task(name=END)]
```

**2. 循环结束**

---

## 8. 高级特性

### 8.1 并发执行

```python
# 同一个 tick 内，多个节点可以并行执行
workflow.add_edge("node1", "node2")
workflow.add_edge("node1", "node3")  # node2 和 node3 并行

# PregelLoop 会在同一个 tick 内执行 [node2, node3]
```

### 8.2 子图（Subgraph）

```python
# 创建子图
sub_workflow = StateGraph(SubState)
sub_workflow.add_node("sub_node1", sub_node1)
sub_workflow.add_node("sub_node2", sub_node2)
sub_workflow.add_edge("sub_node1", "sub_node2")
sub_app = sub_workflow.compile()

# 在主图中使用子图
main_workflow = StateGraph(MainState)
main_workflow.add_node("main_node1", main_node1)
main_workflow.add_node("subgraph", sub_app)  # 子图作为一个节点
main_workflow.add_edge("main_node1", "subgraph")
```

### 8.3 中断（Interrupt）

```python
# 在某个节点前中断
app = workflow.compile(interrupt_before=["human_review"])

# 运行到中断点
app.invoke(input_data, config)

# 人工审核后继续
app.update_state(config, {"approved": True})
app.invoke(None, config)
```

### 8.4 流式输出

```python
# 流式返回每个节点的输出
for chunk in app.stream(input_data, config):
    print(chunk)
# 输出：
# {"agent": {"messages": [...]}}
# {"tools": {"messages": [...]}}
# {"agent": {"messages": [...]}}
```

### 8.5 访问执行上下文

```python
from langgraph.prebuilt import get_config

def my_node(state: MyState):
    # 在节点内访问 config
    config = get_config()
    
    # 获取元数据
    thread_id = config["configurable"]["thread_id"]
    step = config["metadata"]["step"]
    
    print(f"Thread {thread_id}, Step {step}")
    
    return {"result": "done"}
```

---

## 9. 核心概念总结

### 9.1 概念映射表

| 用户概念 | 底层实现 | 作用 |
|---------|---------|------|
| State | Channel + Reducer | 存储和合并状态 |
| Node | PregelNode + 用户函数 | 执行逻辑 |
| Edge | edges 映射表 | 控制流 |
| Graph | Pregel 对象 | 编译后的可执行对象 |
| Checkpoint | Checkpoint 对象 | 持久化快照 |
| invoke() | PregelLoop.run() | 执行引擎 |

### 9.2 数据流图

```
用户输入
    ↓
[加载 Checkpoint]
    ↓
[初始化 Channels]
    ↓
┌─────────────────┐
│  PregelLoop     │
│                 │
│  while True:    │
│    ↓            │
│  prepare_tasks  │ ← 根据 edges 决定下一批节点
│    ↓            │
│  execute_tasks  │ ← 并行执行节点函数
│    ↓            │
│  apply_writes   │ ← 更新 channels
│    ↓            │
│  save_checkpoint│ ← 持久化
│    ↓            │
│  (循环继续)     │
└─────────────────┘
    ↓
[读取 Channels]
    ↓
返回最终 State
```

### 9.3 关键设计决策

#### 为什么需要 Channel？
- **解耦**：节点不直接依赖，通过 Channel 通信
- **合并策略**：不同字段有不同的更新逻辑（replace vs add）
- **可观测**：所有状态变化都经过 Channel，便于调试

#### 为什么需要 Checkpoint？
- **容错**：进程崩溃后可以恢复
- **人工干预**：可以在任意点修改 state
- **时间旅行**：可以回到历史状态

#### 为什么是 tick 模型？
- **并发**：同一个 tick 内的节点可以并行执行
- **控制流**：清晰的执行边界，便于理解
- **可测试**：每个 tick 是独立的单元

---

## 10. 与 OptGraph 的关系

### 10.1 LangGraph 的局限

1. **Context 管理**：Checkpoint 保存完整历史，长对话成本高
2. **性能优化**：没有内置的 token 追踪和成本控制
3. **调试工具**：需要依赖 LangSmith（商业产品）

### 10.2 OptGraph 的优化方向

1. **Adaptive Checkpoint**：在 Checkpoint 层加入压缩逻辑
2. **Token Tracker**：在 Channel 层统计 token 使用
3. **Cost Control**：在 PregelLoop 层加入预算控制

### 10.3 保持兼容性

OptGraph 不修改核心流程，只在关键位置插入优化：
- `MemorySaver` → `AdaptiveCheckpointSaver`
- `MessagesState` → `MemoryState`（添加 summary 和 profile）
- 保持 API 兼容，现有代码无需修改

---

## 附录

### A. 关键源码位置

```
langgraph/
├── graph/
│   ├── graph.py              # StateGraph 定义
│   └── state.py              # State 和 Channel
├── pregel/
│   ├── __init__.py           # Pregel 类
│   ├── loop.py               # PregelLoop 执行引擎
│   └── algo.py               # prepare_next_tasks 算法
├── checkpoint/
│   ├── base.py               # Checkpoint 接口
│   └── memory.py             # MemorySaver 实现
└── prebuilt/
    ├── tool_node.py          # 内置工具节点
    └── chat_agent_executor.py # 内置 Agent
```

### B. 推荐阅读

1. **官方文档**：https://langchain-ai.github.io/langgraph/
2. **Pregel 论文**：Google Pregel (2010)
3. **源码**：https://github.com/langchain-ai/langgraph

### C. 调试技巧

```python
# 1. 打印每个节点的输入输出
def debug_node(state):
    print(f"Input: {state}")
    result = my_node(state)
    print(f"Output: {result}")
    return result

# 2. 查看 checkpoint 历史
for state in app.get_state_history(config):
    print(f"Step {state.metadata['step']}: {state.values}")

# 3. 流式输出查看执行过程
for chunk in app.stream(input_data, config, stream_mode="updates"):
    print(chunk)
```

---

**文档版本**：v1.0  
**最后更新**：2024-11-15  
**作者**：OptGraph Team
