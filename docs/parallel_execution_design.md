# Parallel Tool Execution 设计文档

**创建日期**: 2025-01-16  
**状态**: 设计中  
**目标**: 多工具调用并发执行，降低latency 50%+

---

## 1. 问题定义

### 1.1 当前痛点

**场景**：Agent需要调用多个独立的工具

```python
# 例如：用户问"帮我查一下北京和上海的天气，顺便搜索附近的餐厅"
tools_to_call = [
    {"tool": "weather", "args": {"city": "北京"}},
    {"tool": "weather", "args": {"city": "上海"}},
    {"tool": "search", "args": {"query": "restaurants nearby"}}
]
```

**LangGraph默认行为**：串行执行
```
weather(北京)  →  weather(上海)  →  search(餐厅)
  2s              2s               3s
总耗时: 7s
```

**问题**：
- 三个工具调用完全独立，没有数据依赖
- 串行执行浪费了大量等待时间
- 用户体验差（等7秒才看到结果）

### 1.2 理想效果

**并发执行**：
```
weather(北京)  ┐
weather(上海)  ├─ 并发执行
search(餐厅)   ┘

总耗时: 3s (最慢的那个)
```

**收益**：
- Latency降低 57% (7s → 3s)
- 用户体验提升
- 资源利用率提高

---

## 2. 技术方案

### 2.1 核心思路

```
┌─────────────────────────────────────┐
│ 1. 依赖检测                          │
│    分析哪些任务可以并发               │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 2. 拓扑排序                          │
│    按依赖层级分组                     │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 3. 分层并发执行                      │
│    每层内部并发，层间串行             │
└─────────────────────────────────────┘
```

### 2.2 依赖检测

**问题**：如何判断两个任务是否有依赖关系？

#### 方案A：基于Channel读写分析（LangGraph原生）

LangGraph的Task有这些属性：
- `writes`: 任务会写入哪些channel
- `triggers`: 任务会读取哪些channel

**依赖判断规则**：
```python
def has_dependency(task_a, task_b):
    """
    task_b依赖task_a的条件：
    task_b读取的channel ∩ task_a写入的channel ≠ ∅
    """
    return bool(task_b.triggers & task_a.writes)
```

**示例**：
```python
# Task 1: weather tool
task1.writes = {"weather_result"}
task1.triggers = {"messages"}

# Task 2: summarize (依赖weather结果)
task2.writes = {"summary"}
task2.triggers = {"weather_result"}

# 判断：task2.triggers ∩ task1.writes = {"weather_result"} ≠ ∅
# 结论：task2 依赖 task1，不能并发
```

#### 方案B：基于工具调用分析（简化版）

如果LangGraph的Task结构不够清晰，可以退回到简化方案：

**假设**：同一轮内的所有工具调用都是独立的（Agent已经做了规划）

```python
# 直接并发执行所有工具调用
async def execute_tools(tool_calls):
    results = await asyncio.gather(*[
        call_tool(tc) for tc in tool_calls
    ])
    return results
```

**权衡**：
- 优点：实现简单，适合大部分场景
- 缺点：无法处理工具间有依赖的情况（如：先查数据库，再用结果调API）

**初步决定**：先实现方案A（准确），如果太复杂再退到方案B

### 2.3 拓扑排序

**目标**：将有依赖关系的任务分成多个层级

**算法**：Kahn's Algorithm（经典拓扑排序）

```python
def topological_sort(tasks, dep_graph):
    """
    输入：
        tasks: [task1, task2, task3, task4]
        dep_graph: {
            task1: [],           # 无依赖
            task2: [],           # 无依赖
            task3: [task1],      # 依赖task1
            task4: [task1, task2] # 依赖task1和task2
        }
    
    输出：
        [
            [task1, task2],      # Level 0: 可以并发
            [task3, task4]       # Level 1: 等Level 0完成后并发
        ]
    """
    levels = []
    in_degree = {t: len(deps) for t, deps in dep_graph.items()}
    
    while in_degree:
        # 找出所有入度为0的任务（无依赖）
        current_level = [t for t, deg in in_degree.items() if deg == 0]
        
        if not current_level:
            raise Exception("检测到循环依赖！")
        
        levels.append(current_level)
        
        # 移除这层任务，更新其他任务的入度
        for task in current_level:
            del in_degree[task]
            for other_task, deps in dep_graph.items():
                if task in deps and other_task in in_degree:
                    in_degree[other_task] -= 1
    
    return levels
```

**示例**：
```
依赖图:
task1 (weather北京) ──┐
                      ├─→ task3 (汇总)
task2 (weather上海) ──┘

分层结果:
Level 0: [task1, task2]  # 并发
Level 1: [task3]         # 等Level 0完成
```

### 2.4 并发执行

**核心实现**：

```python
import asyncio
from typing import List, Dict

class ParallelExecutor:
    """并发执行器"""
    
    async def execute_batch(self, tasks: List[Task]) -> Dict:
        """
        并发执行一批任务
        
        Args:
            tasks: 任务列表
            
        Returns:
            {task_id: result}
        """
        # 1. 构建依赖图
        dep_graph = self._build_dependency_graph(tasks)
        
        # 2. 拓扑排序
        levels = self._topological_sort(tasks, dep_graph)
        
        # 3. 逐层执行
        all_results = {}
        
        for level in levels:
            # 每层内部并发
            level_futures = [self._execute_task(task) for task in level]
            level_results = await asyncio.gather(*level_futures)
            
            # 合并结果
            for task, result in zip(level, level_results):
                all_results[task.id] = result
        
        return all_results
    
    def _build_dependency_graph(self, tasks: List[Task]) -> Dict[Task, List[Task]]:
        """构建依赖图"""
        graph = {task: [] for task in tasks}
        
        for task in tasks:
            for other in tasks:
                if task != other and self._has_dependency(task, other):
                    graph[task].append(other)
        
        return graph
    
    def _has_dependency(self, task_a: Task, task_b: Task) -> bool:
        """
        判断task_a是否依赖task_b
        规则：task_a读取的channel ∩ task_b写入的channel ≠ ∅
        """
        return bool(task_a.triggers & task_b.writes)
    
    async def _execute_task(self, task: Task):
        """执行单个任务（异步）"""
        # TODO: 调用LangGraph的task执行逻辑
        pass
```

---

## 3. 集成到LangGraph

### 3.1 LangGraph的执行流程

**当前流程**（串行）：
```python
# langgraph/pregel/__init__.py
class Pregel:
    def stream(self, input):
        for step in range(max_steps):
            # 1. 准备下一批任务
            tasks = prepare_next_tasks(...)
            
            # 2. 串行执行
            for task in tasks:
                result = task.proc.invoke(...)
            
            # 3. 更新state
            state = apply_writes(...)
```

**优化后流程**（并发）：
```python
class Pregel:
    def stream(self, input):
        for step in range(max_steps):
            # 1. 准备下一批任务
            tasks = prepare_next_tasks(...)
            
            # 2. 并发执行（新增）
            executor = ParallelExecutor()
            results = await executor.execute_batch(tasks)
            
            # 3. 更新state
            state = apply_writes(...)
```

### 3.2 实现路径

**选项1：Fork LangGraph（不推荐）**
- 直接修改langgraph源码
- 缺点：维护成本高，升级困难

**选项2：Wrapper模式（推荐）**
- 创建`OptGraph`类，包装`Pregel`
- 重写关键方法，注入并发逻辑
- 保持对外API兼容

```python
from langgraph.pregel import Pregel

class OptGraph(Pregel):
    """
    LangGraph的优化版本，支持并发执行
    """
    
    def __init__(self, *args, enable_parallel=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_parallel = enable_parallel
        self.executor = ParallelExecutor() if enable_parallel else None
    
    async def _execute_tasks(self, tasks):
        """重写任务执行逻辑"""
        if self.enable_parallel and len(tasks) > 1:
            # 并发执行
            return await self.executor.execute_batch(tasks)
        else:
            # 串行执行（fallback）
            return await super()._execute_tasks(tasks)
```

**选项3：Executor替换（最简单）**
- LangGraph已有`BackgroundExecutor`接口
- 继承并实现自己的Executor

```python
from langgraph.pregel._executor import BackgroundExecutor

class DependencyAwareExecutor(BackgroundExecutor):
    """支持依赖检测的并发执行器"""
    
    def submit_batch(self, tasks):
        """重写批量提交逻辑"""
        # 依赖检测 + 拓扑排序 + 并发执行
        pass
```

**初步决定**：先尝试选项3（最轻量），不行再用选项2

---

## 4. 测试方案

### 4.1 测试场景

**Scenario 1: 多个独立工具调用**
```python
# 用户输入："查询北京、上海、深圳的天气"
# 预期：3个weather调用并发执行

tools = [
    weather("北京"),   # 2s
    weather("上海"),   # 2s
    weather("深圳")    # 2s
]

# 串行：6s
# 并发：2s
# 加速：3x
```

**Scenario 2: 有依赖关系的工具链**
```python
# 用户输入："查询北京天气，然后根据天气推荐活动"
# 预期：串行执行（有依赖）

tools = [
    weather("北京"),        # 2s
    recommend(weather)      # 依赖weather结果，3s
]

# 串行：5s
# 并发：5s（检测到依赖，自动串行）
# 加速：1x（无加速，但不会出错）
```

**Scenario 3: 混合场景**
```python
# 多个独立 + 有依赖
tools = [
    weather("北京"),    # 独立，2s
    weather("上海"),    # 独立，2s
    news("科技"),       # 独立，3s
    summarize([weather, news])  # 依赖前3个，2s
]

# 串行：2+2+3+2=9s
# 并发：max(2,2,3)+2=5s
# 加速：1.8x
```

### 4.2 基准测试

**指标**：
- **Latency**: 端到端耗时
- **Throughput**: 单位时间完成的任务数
- **加速比**: 并发耗时 / 串行耗时

**测试代码框架**：
```python
import time
import asyncio

async def benchmark_parallel_vs_serial():
    """对比串行和并发执行"""
    
    # 构造测试任务
    tasks = create_test_tasks(n=5)
    
    # 测试串行
    start = time.time()
    serial_results = await execute_serial(tasks)
    serial_time = time.time() - start
    
    # 测试并发
    start = time.time()
    parallel_results = await execute_parallel(tasks)
    parallel_time = time.time() - start
    
    # 计算加速比
    speedup = serial_time / parallel_time
    
    print(f"串行耗时: {serial_time:.2f}s")
    print(f"并发耗时: {parallel_time:.2f}s")
    print(f"加速比: {speedup:.2f}x")
    print(f"Latency降低: {(1 - parallel_time/serial_time)*100:.1f}%")
```

### 4.3 验收标准

**必达指标**：
- ✅ 独立任务能够并发执行
- ✅ 有依赖的任务自动串行
- ✅ 平均加速比 >2x（latency降低50%+）
- ✅ 结果正确性100%（与串行执行结果一致）

**加分项**：
- 📊 可视化依赖图
- 📈 不同场景的性能曲线
- 🔧 可配置并发度限制（如最多同时3个任务）

---

## 5. 风险和应对

### 5.1 技术风险

**风险1：LangGraph内部结构复杂，难以集成**
- 应对：先做原型验证，确认可行性
- 降级方案：实现独立的并发工具调用库（不集成到LangGraph）

**风险2：依赖检测不准确**
- 应对：保守策略（检测不到就串行）
- 降级方案：用户手动标注依赖关系

**风险3：并发执行出现race condition**
- 应对：每个任务有独立的state副本
- 降级方案：加锁保护共享状态

### 5.2 性能风险

**风险4：并发overhead超过收益（任务太小）**
- 应对：设置阈值（任务<100ms不并发）
- 降级方案：动态切换串行/并发

**风险5：并发度过高，资源耗尽**
- 应对：限制最大并发数（如max_workers=5）
- 降级方案：动态调整并发度

---

## 6. 实现计划

### Phase 1: 原型验证（1-2天）
- [ ] 研究LangGraph的Task结构
- [ ] 写一个最小demo：2个独立工具并发调用
- [ ] 验证可行性

### Phase 2: 核心实现（2-3天）
- [ ] 实现依赖检测（`_build_dependency_graph`）
- [ ] 实现拓扑排序（`_topological_sort`）
- [ ] 实现并发执行（`execute_batch`）
- [ ] 单元测试

### Phase 3: 集成和测试（2天）
- [ ] 集成到OptGraph
- [ ] 3个场景的benchmark测试
- [ ] 性能分析和优化

### Phase 4: 文档和总结（1天）
- [ ] 写使用文档
- [ ] 生成性能报告
- [ ] 更新README

**总耗时**：6-8天

---

## 7. 参考资料

### 7.1 相关技术

**拓扑排序**：
- [Kahn's Algorithm](https://en.wikipedia.org/wiki/Topological_sorting)
- 时间复杂度：O(V + E)

**并发编程**：
- Python asyncio: [官方文档](https://docs.python.org/3/library/asyncio.html)
- `asyncio.gather()`: 并发执行多个协程

**依赖分析**：
- 数据流分析（Data Flow Analysis）
- Channel-based communication

### 7.2 类似项目

**Dask**：Python并行计算框架
- 支持任务依赖图
- 自动并发调度

**Prefect**：工作流编排
- DAG-based执行
- 依赖检测

**Ray**：分布式计算框架
- Task-based并行
- 依赖追踪

---

## 8. 面试价值

**这个优化能体现什么**：

1. **系统设计能力**
   - 理解任务调度和依赖管理
   - 设计并发执行架构

2. **算法能力**
   - 拓扑排序（经典算法）
   - 依赖检测（图论）

3. **工程能力**
   - 集成到现有框架
   - 性能优化和测试

4. **实际价值**
   - 解决真实痛点（API调用慢）
   - 量化收益（latency降低50%+）

**面试时可以讲的故事**：
> "我发现LangGraph在调用多个工具时是串行的，比如查3个城市的天气需要6秒。我实现了一个依赖检测系统，用拓扑排序找出可以并发的任务，把耗时降到2秒，加速了3倍。关键技术是channel读写分析和asyncio并发执行。"

---

**文档状态**：设计完成，待审核  
**下一步**：用户审阅并确认方案
