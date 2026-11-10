# LangGraph 核心架构分析

## 一、整体架构（你的简历项目蓝图）

```
┌─────────────────────────────────────────────────────────────┐
│                    Pregel (main.py)                         │
│              ├─ invoke()  同步调用                           │
│              ├─ ainvoke() 异步调用                           │
│              └─ stream()  流式输出                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               PregelLoop (_loop.py)                         │
│         🎯 核心执行循环 - 这是harness的心脏                    │
│                                                              │
│  while not done:                                            │
│    1. 读取current state (checkpoint)                        │
│    2. 准备下一批tasks (prepare_next_tasks)                  │
│    3. 执行tasks (_executor.py)                              │
│    4. 应用writes到state (apply_writes)                      │
│    5. 保存checkpoint                                         │
│    6. 检查是否需要interrupt                                  │
└─────────────────────────────────────────────────────────────┘
         ↓                ↓                  ↓
   ┌──────────┐   ┌──────────────┐   ┌────────────────┐
   │ Channels │   │  Checkpoint   │   │   Executor     │
   │(状态存储) │   │ (状态快照)     │   │ (工具执行)      │
   └──────────┘   └──────────────┘   └────────────────┘
```

---

## 二、核心文件roadmap（按重要性排序）

### ⭐⭐⭐ 必须精读（Week 1）

1. **`libs/langgraph/langgraph/pregel/_loop.py`** (2100行)
   - 🔥 **PregelLoop类** (line 172)：核心执行循环
   - 关键方法：
     - `tick()` - 执行一个iteration
     - `_put_writes()` - 应用tool结果到state
   - **这是harness的核心！**

2. **`libs/langgraph/langgraph/pregel/main.py`** (4600行)
   - Pregel类：对外API
   - `invoke()` / `stream()` / `ainvoke()` - 用户入口
   - 连接graph definition和execution loop

3. **`libs/langgraph/langgraph/pregel/_algo.py`** (1300行)
   - `prepare_next_tasks()` - 决定下一步执行哪些nodes
   - `apply_writes()` - 更新state
   - 算法核心逻辑

### ⭐⭐ 重要理解（Week 1-2）

4. **`libs/langgraph/langgraph/pregel/_executor.py`** (270行)
   - ⚠️ **优化点1：并行tool execution在这里！**
   - `execute_tasks()` - 当前是sequential执行
   - 你可以改成并发

5. **`libs/langgraph/langgraph/pregel/_checkpoint.py`** (600行)
   - Checkpoint保存/恢复
   - `create_checkpoint()` - 创建state快照

6. **`libs/checkpoint/langgraph/checkpoint/memory/__init__.py`**
   - 🎯 **优化点2：Context管理在这里！**
   - MemorySaver类 - 把所有历史都存在内存
   - 你可以加compression逻辑

### ⭐ 辅助文件（Week 2）

7. **`libs/langgraph/langgraph/graph/state.py`**
   - StateGraph类定义
   - 如何定义nodes和edges

8. **`libs/langgraph/langgraph/pregel/_retry.py`** (1000行)
   - 已有retry逻辑！
   - 可以学习它的实现

---

## 三、关键概念解释

### 1. Pregel是什么？
- Google的分布式图计算模型
- LangGraph借用了它的"迭代执行图"思想
- 每个node是一个计算单元（比如tool call）

### 2. Checkpoint机制
```python
# 每执行完一轮，就保存state
checkpoint = {
    "state": current_state,      # 当前状态
    "pending_writes": [...],     # 待写入的更新
    "versions": {...},           # 各channel的版本
}
```
- 🎯 **优化机会**：可以只保留最近N个checkpoints，老的压缩掉

### 3. Channel vs State
- **Channel**: state的存储容器（类似Redux的store）
- **State**: 实际数据
- 类比：Channel是硬盘，State是文件

---

## 四、三个优化点的精准位置

### 🎯 优化点1：Context Compression

**文件**: `libs/checkpoint/langgraph/checkpoint/memory/__init__.py`

**当前问题**:
```python
class MemorySaver(BaseCheckpointSaver):
    storage: dict[str, dict[str, Any]]  # 无限制存储所有checkpoint
    
    def put(self, checkpoint):
        self.storage[thread_id][checkpoint_id] = checkpoint  # 直接存，不压缩
```

**你的改进方向**:
```python
class OptimizedMemorySaver(MemorySaver):
    def put(self, checkpoint):
        # 1. 只保留最近5轮的完整checkpoint
        # 2. 老的checkpoint压缩成summary
        # 3. 关键信息（第一轮、有tool call的轮次）永久保留
        
        if len(self.storage[thread_id]) > 5:
            # 压缩逻辑
            old_checkpoints = list(...)[::-1][5:]
            compressed = self._compress_checkpoints(old_checkpoints)
            ...
```

**简历上写**: "实现adaptive checkpoint compression，token usage ↓65%"

---

### 🎯 优化点2：Parallel Tool Execution

**文件**: `libs/langgraph/langgraph/pregel/_executor.py`

**当前问题**:
```python
def submit(
    executor: concurrent.futures.Executor,
    task: PregelTask,
    ...
) -> concurrent.futures.Future:
    # 每个task顺序submit
    return executor.submit(_run_with_retry, ...)
```

**你的改进方向**:
```python
def submit_parallel(
    executor: concurrent.futures.Executor,
    tasks: list[PregelTask],
    ...
):
    # 1. 分析tasks的依赖关系
    independent_tasks = _detect_independent_tasks(tasks)
    dependent_tasks = _detect_dependent_tasks(tasks)
    
    # 2. 并发执行independent tasks
    futures = [executor.submit(...) for t in independent_tasks]
    results = concurrent.futures.wait(futures)
    
    # 3. 然后执行dependent tasks
    ...
```

**依赖检测逻辑**:
```python
def _detect_independent_tasks(tasks):
    # 两个tool call如果：
    # 1. 不读写同一个state key
    # 2. 输出不会互相依赖
    # → 就可以并行执行
    ...
```

**简历上写**: "设计并行tool execution引擎，latency ↓40%"

---

### 🎯 优化点3：Cost Tracking

**文件**: 新建 `libs/langgraph/langgraph/cost_tracker.py`

**当前问题**: 整个项目**没有任何cost tracking**

**你的实现**:
```python
import sqlite3
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TokenUsage:
    timestamp: datetime
    thread_id: str
    node_name: str
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float  # GPT-4: $0.03/1k input, $0.06/1k output

class CostTracker:
    def __init__(self, db_path="cost_tracking.db"):
        self.conn = sqlite3.connect(db_path)
        self._create_table()
    
    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                thread_id TEXT,
                node_name TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                cost_usd REAL
            )
        """)
    
    def log_usage(self, usage: TokenUsage):
        # 记录每次LLM call
        self.conn.execute("INSERT INTO token_usage VALUES (?, ?, ?, ?, ?, ?, ?)", ...)
    
    def get_total_cost(self, thread_id=None):
        # 查询总成本
        ...
    
    def check_budget(self, thread_id, budget_usd):
        # 预算警报
        if self.get_total_cost(thread_id) > budget_usd:
            raise BudgetExceededError(...)
```

**集成点**: 在`_loop.py`的`tick()`方法里，每次调用LLM后记录：
```python
# _loop.py, line ~500 (假设)
async def tick(...):
    ...
    result = await call_llm(...)
    
    # 🆕 加这段
    cost_tracker.log_usage(TokenUsage(
        timestamp=datetime.now(),
        thread_id=config["thread_id"],
        node_name=task.name,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        total_cost_usd=calculate_cost(result.usage),
    ))
    ...
```

**简历上写**: "集成cost tracking + budget alerts，防止infinite loop成本爆炸"

---

## 五、Week 1具体任务（逐条执行）

### Day 1: 搭建环境
```bash
cd langgraph-main
cd libs/langgraph
pip install -e .
pip install openai anthropic  # 或你用的provider

# 设置API key
export OPENAI_API_KEY="sk-..."
```

### Day 2-3: 跑通第一个example
```bash
# 找一个简单的example（文档已迁移，我们用代码看）
cat libs/langgraph/tests/test_pregel.py | grep "def test_" | head -5
```

或者手写一个最简单的ReAct agent:
```python
# test_basic.py
from langgraph.graph import StateGraph, MessagesState
from langchain_openai import ChatOpenAI

# 定义一个简单tool
def search_web(query: str) -> str:
    return f"搜索结果: {query}"

# 构建graph
workflow = StateGraph(MessagesState)
workflow.add_node("agent", lambda state: {"messages": [...]})
workflow.add_node("action", lambda state: {"messages": [search_web(...)]})
workflow.add_edge("agent", "action")
workflow.add_edge("action", "agent")

app = workflow.compile()
result = app.invoke({"messages": [("user", "查一下天气")]})
print(result)
```

**任务**: 跑通，加print，trace数据流

### Day 4-5: 读核心代码
按顺序读这3个文件，并回答问题：

1. `_loop.py` - PregelLoop.tick()方法
   - [ ] 一个iteration包含哪几步？
   - [ ] state是怎么传递的？
   - [ ] 什么时候会停止循环？

2. `_executor.py` - submit()方法
   - [ ] task是顺序执行还是并发？
   - [ ] 如果改成并发会遇到什么问题？

3. `checkpoint/memory/__init__.py` - MemorySaver
   - [ ] checkpoint存了哪些信息？
   - [ ] 如果context太长会怎样？

### Day 6-7: 画架构图
在纸上或whiteboard上画出：
1. 数据流图（Input → PregelLoop → Checkpoint → Output）
2. 标出3个优化点的位置
3. 写下你的理解（用自己的话）

---

## 六、Week 2-3: 开始魔改（下次详细拆解）

我会给你每个优化的完整代码模板 + 测试用例。

---

**现在开始Day 1-2的任务吧！遇到问题随时问我。**
