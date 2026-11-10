# OptGraph 项目执行计划（B方案）

## 🎯 总体目标
生产级Agent编排框架，包含3个核心优化 + 生产级特性 + （可选）真实场景验证

**时间线**：5-6周  
**交付物**：可写入简历的完整项目 + benchmark + 文档

---

## 📅 详细计划

### Week 1: Foundation（已完成80%）

**目标**：理解LangGraph核心机制

**已完成**：
- [x] 理解LangGraph概念
- [x] 跑通hello_world.py
- [x] 拆解PregelLoop核心流程
- [x] 写完整项目方案
- [x] 创建OptGraph repo

**剩余任务**（2-3天）：
- [ ] **验证任务1**：在node里拿到step数（0.5天）
  - 修改hello_world.py，输出每个节点的step
  - 理解RunnableConfig和get_config()
  
- [ ] **验证任务2**：理解prepare_next_tasks()（1天）
  - 阅读_algo.py的prepare_next_tasks()
  - 回答：它如何决定下一步执行哪个node？
  - 回答：Task对象包含哪些字段？
  
- [ ] **验证任务3**：画执行trace（1天）
  - 手动trace hello_world的完整执行流程
  - 画出每个tick的状态变化
  - 验证理解是否正确

**Deliverable**：
- 理解PregelLoop的执行机制
- 能用自己的话讲清楚harness流程

---

### Week 2: Adaptive Context Compression

**目标**：实现并验证context压缩策略

#### Day 1-2: 实现基础压缩
- [ ] 实现`AdaptiveCheckpointSaver`
  ```python
  class AdaptiveCheckpointSaver(MemorySaver):
      def put(self, config, checkpoint, metadata, new_versions):
          # 检测token数
          messages = checkpoint["channel_values"]["messages"]
          token_count = count_tokens(messages)
          
          # 超过阈值就压缩
          if token_count > self.threshold:
              checkpoint["channel_values"]["messages"] = self._compress(messages)
          
          return super().put(config, checkpoint, metadata, new_versions)
  ```

- [ ] 实现压缩策略（滑动窗口 + 重要性保留）
  ```python
  def _compress(self, messages):
      # 1. 保留最近N条
      recent = messages[-10:]
      
      # 2. 保留重要消息（tool_calls/errors）
      important = [m for m in messages[:-10] 
                   if self._is_important(m)]
      
      # 3. 合并
      return important + recent
  ```

#### Day 3-4: 写benchmark
- [ ] 创建测试场景（50轮对话）
- [ ] 对比baseline vs 压缩版
- [ ] 记录：token数、latency、cost

#### Day 5-7: 优化策略
- [ ] 尝试不同窗口大小（5/10/15条）
- [ ] 测试不同重要性规则
- [ ] 画图：token消耗 vs 对话轮数
- [ ] 验证质量没下降

**Deliverable**：
- `optgraph/checkpointer.py` 完整实现
- `benchmarks/context_compression_benchmark.py`
- Benchmark报告（Markdown + 图表）
- Token降低 >60%

---

### Week 3: Parallel Tool Execution

**目标**：实现依赖检测和并发执行

#### Day 1-2: 分析依赖关系
- [ ] 研究`prepare_next_tasks()`的输出
- [ ] 理解Task的channel读写关系
- [ ] 实现`_build_dependency_graph()`
  ```python
  def _build_dependency_graph(self, tasks):
      graph = {}
      for task in tasks:
          deps = []
          for other in tasks:
              # 如果task读取other写入的channel
              if task.triggers.intersection(other.writes):
                  deps.append(other)
          graph[task] = deps
      return graph
  ```

#### Day 3-4: 实现并发执行
- [ ] 实现拓扑排序
- [ ] 用asyncio.gather()并发执行
  ```python
  async def submit_batch(self, tasks):
      dep_graph = self._build_dependency_graph(tasks)
      levels = self._topological_sort(dep_graph)
      
      results = {}
      for level in levels:
          # 每一层并发执行
          futures = [self._run_task(t) for t in level]
          level_results = await asyncio.gather(*futures)
          results.update(level_results)
      
      return results
  ```

#### Day 5-7: 测试和benchmark
- [ ] 构造测试用例（3个独立tool）
- [ ] 对比串行 vs 并发的latency
- [ ] 画图展示加速效果

**Deliverable**：
- `optgraph/executor.py` 完整实现
- Benchmark：latency降低 >50%

---

### Week 4: Cost Tracking + 生产级特性（关键周）

**目标**：成本监控 + 让项目"不像玩具"

#### Day 1-2: 实现Cost Tracking
- [ ] SQLite数据库设计
- [ ] 实现`CostTracker`
  ```python
  class CostTracker:
      def log_call(self, model, input_tokens, output_tokens, ...):
          cost = self._calculate_cost(...)
          self.db.insert(...)
          
          # 检查预算
          if self._get_thread_cost(thread_id) > budget:
              raise BudgetExceededError(...)
  ```

- [ ] Hook到PregelLoop
  ```python
  # 在after_tick()里记录
  for task in self.tasks.values():
      if task.metadata.get("llm_call"):
          cost_tracker.log_call(...)
  ```

#### Day 3: 生产级特性 - 错误处理
- [ ] 给3个模块加错误处理
  ```python
  # Checkpointer
  def _compress(self, messages):
      try:
          return self._smart_compress(messages)
      except Exception as e:
          logger.warning(f"Compression failed, fallback: {e}")
          return messages[-10:]  # 降级
  
  # Executor
  async def submit_batch(self, tasks):
      try:
          return await self._parallel_execute(tasks)
      except Exception as e:
          logger.warning(f"Parallel execution failed, fallback to serial")
          return self._serial_execute(tasks)
  ```

#### Day 4: 生产级特性 - 可观测性
- [ ] 加监控指标
  ```python
  class CostTracker:
      def log_call(self, ..., latency):
          # 原有逻辑
          self._log_to_db(...)
          
          # 监控
          if latency > 5.0:
              logger.warning(f"Slow LLM call: {latency}s")
          
          if cost > daily_budget * 0.8:
              self._send_alert("⚠️ 80% budget used")
  ```

- [ ] 实现简单告警（打log/Slack webhook）

#### Day 5: 生产级特性 - 配置化
- [ ] 创建`config.yaml`
  ```yaml
  compression:
    enabled: true
    threshold: 4000
    strategy: sliding_window
    keep_recent: 10
  
  parallel_execution:
    enabled: true
    max_concurrent: 5
  
  cost_tracking:
    enabled: true
    budget_per_thread: 1.0
  ```

- [ ] 实现配置加载
  ```python
  # optgraph/config.py
  import yaml
  
  def load_config(path="config.yaml"):
      with open(path) as f:
          return yaml.safe_load(f)
  ```

#### Day 6-7: Streamlit Dashboard
- [ ] 实现成本监控UI
  ```python
  # optgraph/dashboard.py
  import streamlit as st
  
  st.title("OptGraph Cost Dashboard")
  
  col1, col2, col3 = st.columns(3)
  col1.metric("Total Cost", f"${tracker.total_cost():.2f}")
  col2.metric("Total Calls", tracker.total_calls())
  col3.metric("Avg Cost", f"${tracker.avg_cost():.4f}")
  
  st.line_chart(tracker.cost_over_time())
  ```

**Deliverable**：
- `optgraph/cost_tracker.py` 完整实现
- 错误处理 + 监控 + 配置化
- Streamlit dashboard

---

### Week 5: 真实场景验证（可选/待定）

**状态**：根据Week 4结束时的情况决定是否执行

#### 执行条件（满足任意一个）：
- ✅ Week 1-4进展顺利，有余力
- ✅ Benchmark结果很好，想展示更强的效果
- ✅ 找到了合适的场景（不需要太多额外工作）

#### 不执行条件：
- ❌ Week 1-4已经很赶
- ❌ Benchmark数据已经足够说服力
- ❌ 想快速投简历

#### 如果执行（7天）：
- [ ] Day 1: 选择场景（研究助手/客服/代码助手）
- [ ] Day 2-3: 实现场景Agent
- [ ] Day 4-5: 跑benchmark（10个测试问题）
- [ ] Day 6-7: 写报告 + 画图

**Deliverable**（如果执行）：
- `examples/research_agent.py`（或其他场景）
- `benchmarks/research_agent_benchmark.py`
- Benchmark报告（真实场景验证）

---

## 🚦 决策点

### Decision Point 1: Week 4结束时
**问题**：是否执行Week 5（真实场景验证）？

**评估标准**：
1. 时间是否充裕？
2. Week 1-4的benchmark效果如何？
3. 简历是否已经足够亮眼？

**选项A**：执行Week 5
- 简历上加"validated in XX scenario"
- 面试时更有说服力

**选项B**：跳过Week 5，直接完善文档
- 节省1周时间
- 快速投简历

---

## ✅ 验收标准

### 技术指标（必达）
- [ ] Context压缩：token降低 >60%
- [ ] 并发执行：latency降低 >50%（3个独立工具）
- [ ] 成本追踪：能记录、能设预算、能告警
- [ ] 错误处理：3个模块都有降级逻辑
- [ ] 测试覆盖率：>70%

### 简历指标（必达）
- [ ] GitHub repo完整（README + docs/ + examples/）
- [ ] 至少2个benchmark（压缩 + 并发）
- [ ] 有可视化图表
- [ ] 有运行截图（dashboard）

### 加分项（Week 5完成后）
- [ ] 真实场景验证
- [ ] GitHub stars >20
- [ ] 完整的benchmark报告

---

## 📋 Weekly Checklist

### Week 1 End
- [ ] 理解PregelLoop执行流程
- [ ] 完成3个验证任务
- [ ] 能讲清楚tick() → executor → after_tick()

### Week 2 End
- [ ] `checkpointer.py` 实现完成
- [ ] Benchmark显示token降低 >60%
- [ ] 有图表展示效果

### Week 3 End
- [ ] `executor.py` 实现完成
- [ ] Benchmark显示latency降低 >50%
- [ ] 理解依赖检测原理

### Week 4 End
- [ ] `cost_tracker.py` 实现完成
- [ ] 3个模块都有错误处理
- [ ] Dashboard能运行
- [ ] **决策**：是否执行Week 5？

### Week 5 End（如果执行）
- [ ] 场景Agent实现
- [ ] 真实场景benchmark完成
- [ ] 报告写完

---

## 🎯 最终简历效果（B方案）

```
OptGraph - Production-Grade Agent Orchestration Framework
基于LangGraph，针对生产环境的3个痛点进行深度优化：
context爆炸、串行执行、成本失控

核心贡献：
• Adaptive Context Compression with graceful degradation
  - Sliding window + importance retention (tool_calls/errors preserved)
  - Token usage ↓66% (12k → 4.2k), API cost ↓67%
  - Benchmark: 50-turn conversation, quality preserved

• Dependency-Aware Parallel Execution
  - Channel read/write dependency analysis + topological sort
  - AsyncIO-based concurrent execution
  - Latency ↓62% (9.5s → 3.6s) for 3 independent tools

• Real-time Cost Tracking & Budget Control
  - SQLite logging + Streamlit dashboard
  - Per-thread/node cost attribution
  - Budget alerts & automatic stop on breach

• Production Features
  - Error handling with fallback strategies
  - Observability: latency/cost monitoring & alerting
  - Configuration-driven optimization (YAML-based)

[如果完成Week 5，加这行]
• Validated in research assistant scenario (10-question benchmark)

Tech Stack: Python, LangGraph, AsyncIO, SQLite, Streamlit, OpenAI API
GitHub: github.com/你的用户名/OptGraph (⭐25+ stars)
```

---

## 🚀 开始执行

**现在：完成Week 1剩余任务**

下一步：我帮你完成验证任务1（在node里拿到step数）

准备好了吗？
