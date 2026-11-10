# Week 1 Task 1: 深入理解 get_config()

## 📖 Config的完整结构

`get_config()`返回的是一个包含执行上下文的字典，主要有3个部分：

```python
{
  "configurable": {...},  # LangGraph内部状态
  "metadata": {...},      # 执行元数据（这里有step!）
  "callbacks": {...}      # LangChain callbacks
}
```

---

## 🎯 关键字段详解

### 1. metadata（最重要！）

```python
"metadata": {
  "langgraph_step": 1,           # ⭐ 这就是step数字！
  "langgraph_node": "agent",     # 当前执行的node名字
  "langgraph_triggers": [        # 触发这个node的channel
    "branch:to:agent"
  ],
  "langgraph_path": [            # 执行路径
    "__pregel_pull",
    "agent"
  ],
  "langgraph_checkpoint_ns": "agent:187974d3-eb37-3125-055c-6468120ebbd1"
}
```

**关键发现**：
- ✅ `langgraph_step` 就是我们要的step数字（从1开始）
- ✅ `langgraph_node` 是当前node的名字
- ✅ `langgraph_checkpoint_ns` 是node的唯一标识（node_name:uuid）

---

### 2. configurable（内部状态）

```python
"configurable": {
  "__pregel_scratchpad": "PregelScratchpad(step=1, stop=10007, ...)",
  "__pregel_task_id": "187974d3-eb37-3125-055c-6468120ebbd1",
  "__pregel_runtime": "Runtime(...)",
  "checkpoint_ns": "agent:187974d3-eb37-3125-055c-6468120ebbd1",
  ...
}
```

**关键发现**：
- `__pregel_scratchpad` 里也有step信息（字符串形式）
- `checkpoint_ns` 和 metadata里的 `langgraph_checkpoint_ns` 一样
- 很多字段是LangGraph内部使用的，我们通常不需要直接访问

---

### 3. PregelScratchpad的秘密

在`__pregel_scratchpad`和`__pregel_read`里看到：

```python
PregelScratchpad(
  step=1,              # 当前step
  stop=10007,          # 最大step限制（默认很大）
  call_counter=...,    # 调用计数器
  interrupt_counter=...,  # 中断计数器
  ...
)
```

这就是PregelLoop内部的状态！

---

## ✅ 正确获取Step的方法

### 方法1：从metadata获取（推荐）

```python
from langgraph.config import get_config

def agent_node(state):
    config = get_config()
    step = config.get("metadata", {}).get("langgraph_step", 0)
    node_name = config.get("metadata", {}).get("langgraph_node", "unknown")
    
    print(f"[Step {step}] [Node: {node_name}]")
```

**为什么推荐**：
- metadata是公开API的一部分
- 数据类型是int，不是字符串
- 清晰明确

---

### 方法2：从configurable获取

```python
def agent_node(state):
    config = get_config()
    checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")
    # checkpoint_ns格式: "agent:uuid"
    node_name = checkpoint_ns.split(":")[0] if ":" in checkpoint_ns else "unknown"
    
    print(f"[Node: {node_name}]")
```

**缺点**：
- 拿不到step数字（checkpoint_ns里没有）
- 只能拿到node名字和uuid

---

## 🔬 实验：修改hello_world

现在我们用正确的方法获取step：

```python
def agent_node(state: MessagesState) -> MessagesState:
    """Agent节点：模拟LLM的决策"""
    config = get_config()
    
    # ✅ 正确方法：从metadata获取
    step = config.get("metadata", {}).get("langgraph_step", 0)
    node_name = config.get("metadata", {}).get("langgraph_node", "unknown")
    
    messages = state["messages"]
    last_message = messages[-1].content

    print(f"\n[Step {step}] [{node_name}节点] 收到消息: {last_message}")

    # 简单的规则：如果包含数字和运算符，就调用工具
    if any(op in last_message for op in ["+", "-", "*", "/"]):
        print(f"[Step {step}] [{node_name}节点] 决策: 需要调用计算器工具")
        return {"messages": [AIMessage(content="需要计算")]}
    else:
        print(f"[Step {step}] [{node_name}节点] 决策: 直接回答")
        return {"messages": [AIMessage(content="你好！我是计算助手")]}
```

---

## 📊 Step的生命周期

### 测试1：普通对话（不调用tool）
```
[Step 1] [agent节点] 收到消息: 你好
[Step 1] [agent节点] 决策: 直接回答
→ 完成，没有step 2
```

### 测试2：需要调用tool
```
[Step 1] [agent节点] 收到消息: 123 + 456
[Step 1] [agent节点] 决策: 需要调用计算器工具

[Step 2] [tool节点] 执行计算: 123 + 456
[Step 2] [tool节点] 计算结果: 579
→ 完成
```

**观察**：
- 每次PregelLoop.tick()，step会+1
- 同一个step内可能执行多个node（并发场景）
- Step从1开始（不是0）

---

## 🎓 总结

### 你学到了什么

1. **Config结构**
   - metadata: 公开API，包含step/node信息
   - configurable: 内部状态，包含PregelLoop的运行时数据
   - callbacks: LangChain的回调系统

2. **获取Step的方法**
   - ✅ 正确：`config["metadata"]["langgraph_step"]`
   - ❌ 错误：从checkpoint_ns解析（里面没有step）

3. **PregelLoop的内部状态**
   - PregelScratchpad存储了step/stop/counters
   - 通过`__pregel_scratchpad`可以窥探内部

4. **执行模型**
   - Step从1开始
   - 每个tick对应一个step
   - 同一step内的node共享相同的step数字

---

## ✅ 验证你的理解

### 问题1
为什么checkpoint_ns是"agent:uuid"格式，而不是简单的"agent"？

<details>
<summary>答案</summary>

因为同一个node可能在不同的执行路径中被多次调用（比如循环），
UUID保证了每次调用都有唯一的标识，用于checkpoint的保存和恢复。
</details>

### 问题2
如果一个step里并发执行3个tool，它们的step数字是一样的吗？

<details>
<summary>答案</summary>

是的！同一个tick内执行的所有node，step数字相同。
比如：
- [Step 2] [tool1节点] 执行
- [Step 2] [tool2节点] 执行
- [Step 2] [tool3节点] 执行
</details>

### 问题3
`stop=10007`是什么意思？

<details>
<summary>答案</summary>

这是最大step限制，防止无限循环。
默认值很大（10007），你可以在调用时设置更小的值：
```python
app.invoke(input, config={"recursion_limit": 50})
```
</details>

---

## 🚀 下一步

**Week 1 Task 1 完成！** ✅

你现在知道：
- Config的结构
- 如何获取step和node信息
- PregelLoop的内部状态

**下一个任务**：理解`prepare_next_tasks()`
- 它如何决定下一步执行哪个node？
- Task对象的结构是什么？
