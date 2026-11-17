# Cost Tracking 设计文档

**创建日期**: 2025-01-16  
**状态**: 设计中  
**目标**: 实时成本监控和预算控制

---

## 1. 问题定义

### 1.1 痛点

**问题**：LLM API调用成本不透明

```python
# 用户不知道花了多少钱
result = llm.invoke("long prompt...")

# 多轮对话累积成本
for i in range(100):
    result = agent.invoke(...)  # 每次都在花钱，但不知道花了多少

# 超出预算才发现
# 💸 账单：$500
# 😱 "我以为只用了$50！"
```

**问题分析**：
1. **事后才知道** - 账单来了才发现超支
2. **无法控制** - 没有预算上限，可能无限制花费
3. **不知道哪里贵** - 不知道哪个功能/用户花费最多
4. **无法优化** - 没数据，不知道从哪优化

### 1.2 目标

**实时监控**：
- 每次API调用立即记录成本
- 实时查看当前花费
- 按thread/用户/功能分组统计

**预算控制**：
- 设置预算上限
- 超出预算自动停止
- 接近预算时告警

**可视化**：
- 成本趋势图
- Top消费功能/用户
- 成本分解（input vs output tokens）

---

## 2. 技术方案

### 2.1 核心架构

```
┌─────────────────────────────────────┐
│ LLM API调用                          │
│ (每次调用时)                         │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ CostTracker.log_call()               │
│ - 提取token数量                       │
│ - 计算成本                            │
│ - 存储到SQLite                        │
│ - 检查预算                            │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ SQLite数据库                         │
│ - llm_calls表：每次调用记录           │
│ - budgets表：预算配置                 │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ 查询和分析                            │
│ - get_stats(): 统计数据               │
│ - get_top_expensive(): Top消费        │
│ - visualize(): 可视化                 │
└─────────────────────────────────────┘
```

### 2.2 数据库设计

**表1: llm_calls（LLM调用记录）**

```sql
CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 模型信息
    model TEXT NOT NULL,                -- 例如：gpt-4, claude-3-opus
    provider TEXT,                      -- 例如：openai, anthropic
    
    -- Token使用
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    
    -- 成本
    input_cost_usd REAL NOT NULL,       -- Input token成本
    output_cost_usd REAL NOT NULL,      -- Output token成本
    total_cost_usd REAL NOT NULL,       -- 总成本
    
    -- 上下文
    thread_id TEXT,                     -- 对话ID
    user_id TEXT,                       -- 用户ID
    node_name TEXT,                     -- LangGraph节点名
    purpose TEXT,                       -- 用途标签（可选）
    
    -- 元数据
    metadata JSON                       -- 额外信息
);

-- 索引
CREATE INDEX idx_timestamp ON llm_calls(timestamp);
CREATE INDEX idx_thread_id ON llm_calls(thread_id);
CREATE INDEX idx_user_id ON llm_calls(user_id);
CREATE INDEX idx_model ON llm_calls(model);
```

**表2: budgets（预算配置）**

```sql
CREATE TABLE budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 预算范围
    scope TEXT NOT NULL,                -- 例如：global, thread, user
    scope_id TEXT,                      -- 范围ID（thread_id或user_id）
    
    -- 预算设置
    budget_usd REAL NOT NULL,           -- 预算金额
    period TEXT DEFAULT 'total',        -- 周期：total, daily, monthly
    
    -- 告警
    warning_threshold REAL DEFAULT 0.8, -- 告警阈值（80%）
    
    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.3 成本计算

**价格表**（2024年价格）：

```python
PRICING = {
    # OpenAI
    "gpt-4": {
        "input": 0.03 / 1000,    # $0.03 per 1K input tokens
        "output": 0.06 / 1000,   # $0.06 per 1K output tokens
    },
    "gpt-4-turbo": {
        "input": 0.01 / 1000,
        "output": 0.03 / 1000,
    },
    "gpt-3.5-turbo": {
        "input": 0.0005 / 1000,
        "output": 0.0015 / 1000,
    },
    
    # Anthropic
    "claude-3-opus": {
        "input": 0.015 / 1000,
        "output": 0.075 / 1000,
    },
    "claude-3-sonnet": {
        "input": 0.003 / 1000,
        "output": 0.015 / 1000,
    },
    "claude-3-haiku": {
        "input": 0.00025 / 1000,
        "output": 0.00125 / 1000,
    },
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> dict:
    """计算成本"""
    pricing = PRICING.get(model, {"input": 0, "output": 0})
    
    input_cost = input_tokens * pricing["input"]
    output_cost = output_tokens * pricing["output"]
    total_cost = input_cost + output_cost
    
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
    }
```

### 2.4 预算检查

```python
def check_budget(thread_id: str = None, user_id: str = None) -> dict:
    """
    检查预算状态
    
    Returns:
        {
            "within_budget": True/False,
            "current_spend": 12.34,
            "budget_limit": 100.0,
            "usage_percent": 12.34,
            "warning": True/False,
        }
    """
    
    # 1. 获取预算配置
    budget = get_budget(thread_id=thread_id, user_id=user_id)
    
    # 2. 计算当前花费
    current_spend = get_total_cost(thread_id=thread_id, user_id=user_id)
    
    # 3. 计算使用百分比
    usage_percent = (current_spend / budget["limit"]) * 100
    
    # 4. 判断状态
    return {
        "within_budget": current_spend < budget["limit"],
        "current_spend": current_spend,
        "budget_limit": budget["limit"],
        "usage_percent": usage_percent,
        "warning": usage_percent >= budget["warning_threshold"],
    }
```

---

## 3. 集成到LangGraph

### 3.1 自动记录

**方案1：Hook到LLM调用**

```python
from langchain_core.callbacks import BaseCallbackHandler

class CostTrackingCallback(BaseCallbackHandler):
    """回调记录每次LLM调用"""
    
    def __init__(self, cost_tracker: CostTracker):
        self.cost_tracker = cost_tracker
    
    def on_llm_end(self, response, **kwargs):
        """LLM调用结束时记录"""
        # 提取token使用
        usage = response.llm_output.get("token_usage", {})
        
        # 记录成本
        self.cost_tracker.log_call(
            model=response.llm_output.get("model_name"),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            thread_id=kwargs.get("thread_id"),
        )

# 使用
cost_tracker = CostTracker(db_path="costs.db")
callback = CostTrackingCallback(cost_tracker)

llm = ChatOpenAI(callbacks=[callback])
```

**方案2：Wrapper模式**

```python
class CostTrackedLLM:
    """包装LLM，自动记录成本"""
    
    def __init__(self, llm, cost_tracker: CostTracker):
        self.llm = llm
        self.cost_tracker = cost_tracker
    
    def invoke(self, *args, **kwargs):
        # 调用LLM
        response = self.llm.invoke(*args, **kwargs)
        
        # 记录成本
        self.cost_tracker.log_call(
            model=self.llm.model_name,
            input_tokens=response.usage_metadata.input_tokens,
            output_tokens=response.usage_metadata.output_tokens,
            thread_id=kwargs.get("config", {}).get("thread_id"),
        )
        
        return response

# 使用
llm = ChatOpenAI(model="gpt-4")
tracked_llm = CostTrackedLLM(llm, cost_tracker)
```

**方案3：集成到OptGraph**

```python
from optgraph import OptGraph, CostTracker

# 编译时启用cost tracking
app = OptGraph.compile(
    graph,
    enable_parallel=True,
    enable_cost_tracking=True,
    cost_tracker_config={
        "db_path": "costs.db",
        "budget_limit": 100.0,  # $100预算
    }
)

# 自动记录所有LLM调用
result = app.invoke(...)

# 查看统计
stats = app.cost_tracker.get_stats()
print(f"Total cost: ${stats['total_cost']:.2f}")
```

---

## 4. 查询和分析

### 4.1 基础统计

```python
def get_stats(
    thread_id: str = None,
    user_id: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
) -> dict:
    """
    获取统计数据
    
    Returns:
        {
            "total_calls": 1234,
            "total_tokens": 500000,
            "total_cost": 12.34,
            "average_cost_per_call": 0.01,
            "by_model": {
                "gpt-4": {"calls": 100, "cost": 5.0},
                "claude-3-opus": {"calls": 50, "cost": 3.0},
            }
        }
    """
```

### 4.2 Top消费

```python
def get_top_expensive(
    by: str = "thread",  # thread, user, node
    limit: int = 10,
) -> list:
    """
    获取Top消费
    
    Returns:
        [
            {"id": "thread_123", "cost": 50.0, "calls": 100},
            {"id": "thread_456", "cost": 30.0, "calls": 80},
            ...
        ]
    """
```

### 4.3 时间序列

```python
def get_cost_timeline(
    granularity: str = "day",  # hour, day, week, month
    thread_id: str = None,
) -> list:
    """
    获取成本时间序列
    
    Returns:
        [
            {"date": "2024-01-01", "cost": 10.5},
            {"date": "2024-01-02", "cost": 15.2},
            ...
        ]
    """
```

---

## 5. 可视化

### 5.1 命令行输出

```python
def print_summary():
    """打印成本摘要"""
    
    stats = cost_tracker.get_stats()
    
    print("=" * 60)
    print("COST SUMMARY")
    print("=" * 60)
    print(f"Total Calls:  {stats['total_calls']}")
    print(f"Total Tokens: {stats['total_tokens']:,}")
    print(f"Total Cost:   ${stats['total_cost']:.2f}")
    print()
    print("By Model:")
    for model, data in stats['by_model'].items():
        print(f"  {model:<20} {data['calls']:>5} calls  ${data['cost']:>6.2f}")
    print("=" * 60)
```

### 5.2 HTML报告

```python
def generate_html_report(output_path: str = "cost_report.html"):
    """生成HTML成本报告"""
    
    # 使用plotly生成图表
    import plotly.graph_objects as go
    
    # 成本趋势图
    timeline = cost_tracker.get_cost_timeline()
    fig_timeline = go.Figure(
        data=go.Scatter(x=[t["date"] for t in timeline],
                       y=[t["cost"] for t in timeline])
    )
    
    # 模型分布饼图
    stats = cost_tracker.get_stats()
    fig_pie = go.Figure(
        data=go.Pie(labels=list(stats["by_model"].keys()),
                    values=[v["cost"] for v in stats["by_model"].values()])
    )
    
    # 生成HTML
    html = f"""
    <html>
    <head><title>Cost Report</title></head>
    <body>
        <h1>LLM Cost Report</h1>
        <div>{fig_timeline.to_html()}</div>
        <div>{fig_pie.to_html()}</div>
    </body>
    </html>
    """
    
    with open(output_path, "w") as f:
        f.write(html)
```

---

## 6. 预算控制

### 6.1 设置预算

```python
# 全局预算
cost_tracker.set_budget(limit=100.0, scope="global")

# 单个对话预算
cost_tracker.set_budget(limit=5.0, scope="thread", scope_id="thread_123")

# 单个用户预算
cost_tracker.set_budget(limit=50.0, scope="user", scope_id="user_456")
```

### 6.2 自动停止

```python
class BudgetExceededError(Exception):
    """预算超出异常"""
    pass

def log_call(self, ...):
    """记录调用并检查预算"""
    
    # 1. 记录成本
    self._insert_record(...)
    
    # 2. 检查预算
    budget_status = self.check_budget(thread_id=thread_id)
    
    # 3. 如果超出，抛出异常
    if not budget_status["within_budget"]:
        raise BudgetExceededError(
            f"Budget exceeded: ${budget_status['current_spend']:.2f} / "
            f"${budget_status['budget_limit']:.2f}"
        )
    
    # 4. 如果接近告警阈值，发出警告
    if budget_status["warning"]:
        print(f"⚠️  Warning: {budget_status['usage_percent']:.1f}% of budget used")
```

---

## 7. 使用示例

### 7.1 基础使用

```python
from optgraph.cost_tracker import CostTracker

# 初始化
tracker = CostTracker(db_path="costs.db")

# 设置预算
tracker.set_budget(limit=100.0)

# 记录调用
tracker.log_call(
    model="gpt-4",
    input_tokens=1000,
    output_tokens=500,
    thread_id="conversation_123",
)

# 查看统计
stats = tracker.get_stats()
print(f"Total cost: ${stats['total_cost']:.2f}")

# 检查预算
budget = tracker.check_budget()
if budget["warning"]:
    print(f"⚠️  {budget['usage_percent']:.1f}% of budget used")
```

### 7.2 集成到LangGraph

```python
from optgraph import OptGraph, CostTracker
from langgraph.graph import StateGraph

# 方式1：手动集成
cost_tracker = CostTracker()

def agent_node(state):
    response = llm.invoke(state["messages"])
    
    # 手动记录
    cost_tracker.log_call(
        model="gpt-4",
        input_tokens=response.usage_metadata.input_tokens,
        output_tokens=response.usage_metadata.output_tokens,
    )
    
    return {"messages": [response]}

# 方式2：自动集成（OptGraph）
app = OptGraph.compile(
    graph,
    enable_cost_tracking=True,
    cost_tracker_config={"budget_limit": 100.0}
)

# 所有LLM调用自动记录
result = app.invoke(...)
```

---

## 8. 实现计划

### Phase 1: 核心功能（1天）
- [ ] CostTracker类基础实现
- [ ] 数据库schema
- [ ] 成本计算（PRICING字典）
- [ ] 基础记录功能
- [ ] 基础查询功能

### Phase 2: 预算控制（0.5天）
- [ ] 预算设置
- [ ] 预算检查
- [ ] 告警机制
- [ ] BudgetExceededError

### Phase 3: 查询和分析（0.5天）
- [ ] get_stats()
- [ ] get_top_expensive()
- [ ] get_cost_timeline()
- [ ] 命令行输出美化

### Phase 4: 可视化（可选，1天）
- [ ] HTML报告生成
- [ ] Plotly图表
- [ ] Dashboard（Streamlit）

### Phase 5: 集成和测试（1天）
- [ ] LangGraph集成
- [ ] OptGraph集成
- [ ] 测试场景（5个）
- [ ] 文档

**总耗时：3-4天**

---

## 9. 测试方案

### 9.1 单元测试

```python
def test_cost_calculation():
    """测试成本计算准确性"""
    cost = calculate_cost("gpt-4", 1000, 500)
    assert cost["input_cost"] == 0.03
    assert cost["output_cost"] == 0.03
    assert cost["total_cost"] == 0.06

def test_budget_check():
    """测试预算检查"""
    tracker = CostTracker()
    tracker.set_budget(limit=10.0)
    
    # 花费$5
    tracker.log_call("gpt-4", 1000, 500)
    status = tracker.check_budget()
    assert status["within_budget"] == True
    
    # 再花费$10，超预算
    for _ in range(10):
        tracker.log_call("gpt-4", 1000, 500)
    
    status = tracker.check_budget()
    assert status["within_budget"] == False
```

### 9.2 集成测试

```python
def test_langgraph_integration():
    """测试与LangGraph集成"""
    
    # 启用cost tracking
    app = OptGraph.compile(graph, enable_cost_tracking=True)
    
    # 执行对话
    result = app.invoke({"messages": [HumanMessage("Hello")]})
    
    # 验证成本被记录
    stats = app.cost_tracker.get_stats()
    assert stats["total_calls"] > 0
    assert stats["total_cost"] > 0
```

---

## 10. 面试价值

**这个功能能体现什么**：

1. **产品思维**
   - 发现真实痛点（成本超支）
   - 设计完整解决方案（监控+预算+可视化）

2. **系统设计**
   - 数据库设计
   - 查询优化（索引）
   - 可扩展架构

3. **工程能力**
   - 集成到现有系统
   - 错误处理（预算超出）
   - 可视化实现

**面试时可以讲的故事**：
> "我实现了一个LLM成本追踪系统。它在每次API调用时自动记录token使用和成本，存入SQLite。我设计了两张表：llm_calls记录每次调用，budgets管理预算配置。系统支持实时预算检查，超出预算时自动停止并告警。我还实现了统计查询（按模型、用户、时间分组）和可视化报告（HTML+Plotly图表）。集成到LangGraph后，所有Agent的LLM调用自动跟踪，用户可以实时看到成本，避免超支。关键技术是SQLite索引优化、回调机制集成、和异常处理。"

---

**文档状态**：设计完成，待实现  
**下一步**：开始Phase 1核心功能实现
