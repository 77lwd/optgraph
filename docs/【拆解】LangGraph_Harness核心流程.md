# LangGraph Harness 核心执行流程拆解

## 🎯 文件定位

```
langgraph-main/
└── libs/langgraph/langgraph/pregel/
    ├── main.py           # 对外API (Pregel类)
    ├── _loop.py          # ⭐ 核心执行循环 (PregelLoop)
    ├── _algo.py          # 任务准备和写入应用
    ├── _executor.py      # 工具执行器
    ├── _checkpoint.py    # Checkpoint管理
    └── _io.py            # 输入输出映射
```

---

## 🔄 核心循环：PregelLoop.tick()

### 代码位置
`libs/langgraph/langgraph/pregel/_loop.py:652`

### 伪代码
```python
def tick(self) -> bool:
    """执行一次Pregel循环迭代
    
    Returns:
        True = 需要继续执行
        False = 任务完成/中断
    """
    
    # ============ 第1步：检查循环限制 ============
    if self.step > self.stop:
        self.status = "out_of_steps"
        return False
    
    # ============ 第2步：准备任务并发射checkpoint ============
    self._prepare_tasks_and_emit_checkpoint()
    
    # ============ 第3步：检查是否还有任务 ============
    if not self.tasks:
        self.status = "done"
        return False
    
    # ============ 第4步：重新应用pending writes ============
    if self._reapplies_pending_writes and self.checkpoint_pending_writes:
        self._reapply_writes_to_succeeded_nodes(self.tasks)
    
    # ============ 第5步：检查是否需要在执行前中断 ============
    if self.interrupt_before and should_interrupt(...):
        self.status = "interrupt_before"
        raise GraphInterrupt()
    
    # ============ 第6步：检查drain请求 ============
    if self.control.drain_requested:
        self.status = "draining"
        return False
    
    # ============ 第7步：输出debug信息 ============
    self._emit("tasks", map_debug_tasks, self.tasks.values())
    
    return True  # 继续执行
```

---

## 📊 完整执行流程图

```
用户调用 app.invoke(input)
    ↓
┌──────────────────────────────────────┐
│   Pregel.invoke() (main.py)          │
│   - 初始化PregelLoop                  │
│   - 准备配置和checkpoint               │
└──────────────────────────────────────┘
    ↓
┌──────────────────────────────────────┐
│   PregelLoop.__enter__()              │
│   - 加载checkpoint                    │
│   - 初始化channels                    │
│   - 准备第一批tasks                   │
└──────────────────────────────────────┘
    ↓
┌──────────────────────────────────────────────────────┐
│   主循环: while loop.tick():                          │
│                                                       │
│   ┌─────────────────────────────────────┐           │
│   │  PregelLoop.tick()                  │           │
│   │  1. 检查step限制                     │           │
│   │  2. _prepare_tasks_and_emit_checkpoint()  │      │
│   │  3. 检查任务队列                     │           │
│   │  4. 应用pending writes               │           │
│   │  5. 检查interrupt_before             │           │
│   │  6. 发射debug events                 │           │
│   └─────────────────────────────────────┘           │
│       ↓                                              │
│   ┌─────────────────────────────────────┐           │
│   │  Executor执行任务 (_executor.py)     │           │
│   │  - 并发执行node函数                  │           │
│   │  - 收集writes                        │           │
│   └─────────────────────────────────────┘           │
│       ↓                                              │
│   ┌─────────────────────────────────────┐           │
│   │  PregelLoop.after_tick()            │           │
│   │  1. apply_writes(更新channels)       │           │
│   │  2. 发射values output                │           │
│   │  3. _put_checkpoint(保存状态)        │           │
│   │  4. 检查interrupt_after              │           │
│   │  5. step += 1                        │           │
│   └─────────────────────────────────────┘           │
│       ↓                                              │
│   返回顶部继续循环 (tick返回True)                     │
└──────────────────────────────────────────────────────┘
    ↓
┌──────────────────────────────────────┐
│   PregelLoop.__exit__()               │
│   - 最终checkpoint                    │
│   - 清理资源                          │
└──────────────────────────────────────┘
    ↓
返回最终结果给用户
```

---

## 🔑 关键组件详解

### 1. **PregelLoop类** (_loop.py:172)

**核心属性**：
```python
class PregelLoop:
    step: int                    # 当前步数
    stop: int                    # 最大步数限制
    tasks: dict[str, Task]       # 当前要执行的任务
    channels: dict[str, Channel] # State存储
    checkpoint: Checkpoint       # 当前检查点
    checkpoint_pending_writes: list  # 待写入的数据
    nodes: dict[str, PregelNode] # 所有节点定义
    
    # Interruption控制
    interrupt_before: list[str]
    interrupt_after: list[str]
    
    # 执行器
    executor: Executor
    checkpointer: BaseCheckpointSaver
```

---

### 2. **_prepare_tasks_and_emit_checkpoint()** (_loop.py:780)

**作用**：决定下一步要执行哪些node

```python
def _prepare_tasks_and_emit_checkpoint(self):
    # 调用_algo.py的核心函数
    self.tasks = prepare_next_tasks(
        self.checkpoint,          # 当前状态
        self.checkpoint_pending_writes,  # 待处理写入
        self.nodes,               # 所有节点
        self.channels,            # State数据
        ...
    )
    
    # 发射checkpoint event (用于streaming)
    self._emit("debug", ...)
```

**核心逻辑** (在 `_algo.py` 里):
- 读取checkpoint，看哪些channel被更新了
- 根据graph的edges，找到应该触发的node
- 生成Task对象放入self.tasks

---

### 3. **Executor执行任务** (_executor.py)

**代码位置**: `libs/langgraph/langgraph/pregel/_executor.py`

**伪代码**：
```python
class BackgroundExecutor:
    def submit(self, task: PregelExecutableTask):
        """提交一个任务到线程池/协程池"""
        future = self.executor.submit(
            self._run_with_retry,
            task.proc,    # 节点函数
            task.input    # 输入数据
        )
        return future
    
    def _run_with_retry(self, proc, input):
        """带重试的执行"""
        for attempt in range(max_retries):
            try:
                result = proc.invoke(input)
                return result
            except Exception as e:
                if attempt < max_retries - 1:
                    sleep(backoff_time)
                else:
                    raise
```

**特点**：
- 支持并发执行（ThreadPoolExecutor / asyncio）
- 自动重试机制
- Timeout控制

---

### 4. **apply_writes()** (_algo.py)

**作用**：把任务的writes应用到channels（更新State）

```python
def apply_writes(
    checkpoint: Checkpoint,
    channels: dict[str, BaseChannel],
    tasks: list[Task],
    ...
) -> set[str]:
    """
    Returns:
        set[str] - 被更新的channel名字
    """
    updated = set()
    
    for task in tasks:
        for channel_name, value in task.writes:
            channel = channels[channel_name]
            channel.update([value])  # 更新channel
            updated.add(channel_name)
    
    return updated
```

---

### 5. **Checkpoint机制** (_checkpoint.py)

**Checkpoint结构**：
```python
@dataclass
class Checkpoint:
    v: int  # 版本号
    id: str  # UUID
    ts: str  # 时间戳
    channel_values: dict[str, Any]  # 所有channel的值
    channel_versions: dict[str, int]  # 每个channel的版本
    versions_seen: dict[str, dict[str, int]]  # 每个node看到的版本
    pending_sends: list[Send]  # 待发送的消息
```

**保存时机**：
- 每次`after_tick()`完成后
- 代码位置：`_loop.py:768` → `self._put_checkpoint({"source": "loop"})`

---

## 🎯 这就是Harness！

### 对比传统Harness

| 传统Harness (手写)           | LangGraph PregelLoop          |
|-----------------------------|-------------------------------|
| `while True: ...`           | `while loop.tick(): ...`      |
| 手动调用LLM                  | `task.proc.invoke(input)`     |
| 手动解析tool_calls           | `prepare_next_tasks()`自动路由  |
| 手动重试                     | Executor内置retry             |
| 手动管理context              | Checkpoint自动保存             |
| 手动判断是否结束              | `if not self.tasks: return`   |

---

## 💡 Week 1 任务：验证你的理解

### 任务1：找到hello_world的trace
在你刚才跑的hello_world例子里，加debug输出：

```python
# 在 agent_node 开头加
print(f"[DEBUG] PregelLoop.step = ???")  # 怎么拿到？

# 运行时应该输出：
# [DEBUG] PregelLoop.step = 0
# [Agent节点] 收到消息: 123 + 456
# [DEBUG] PregelLoop.step = 1
# [Tool节点] 执行计算...
```

**问题**：怎么在node函数里拿到当前的step数？
**提示**：看 `get_config()` 函数

---

### 任务2：找到task准备逻辑
打开 `_algo.py`，找到`prepare_next_tasks()`函数，回答：

1. 它是怎么决定"下一步执行哪个node"的？
2. `self.tasks` 是什么数据结构？
3. 一个Task对象包含哪些字段？

---

### 任务3：画出你的hello_world执行trace

**格式**：
```
Tick 0:
  - prepare_next_tasks() → [Task(node="agent", input=...)]
  - executor.submit(agent_node)
  - agent返回: {"messages": [AIMessage("需要计算")]}
  - apply_writes() → 更新channels["messages"]
  - _put_checkpoint()

Tick 1:
  - prepare_next_tasks() → [Task(node="tool", input=...)]
  - executor.submit(tool_node)
  - tool返回: {"messages": [AIMessage("结果: 579")]}
  - apply_writes()
  - _put_checkpoint()

Tick 2:
  - prepare_next_tasks() → []  (没有任务)
  - loop.tick() 返回 False
  - Done!
```

---

## 📝 下一步

完成上面3个任务后告诉我，我给你讲：
1. **如何优化context**（在checkpoint里压缩历史消息）
2. **如何优化executor**（并发执行独立的tool）
3. **如何添加cost tracking**（在哪里hook住LLM调用）

准备好了吗？
