# OptGraph 内存管理系统

基于 LangGraph (44.9K⭐)、Mem0 (23K⭐) 和学术研究的生产级内存管理方案。

## 核心特性

✅ **双重内存存储**
- 结构化用户画像（永不丢失）
- 语义摘要（LLM 压缩）

✅ **遵循官方 LangGraph 模式**
- State 层内存管理
- RemoveMessage API 删除消息
- 标准 Checkpointer 持久化

✅ **经过实战测试**
- 完整测试套件
- 边界情况处理
- 多轮对话质量保持

## 快速开始

### 安装

```bash
# 安装依赖
pip install langgraph langchain-openai
```

### 基础使用

```python
from examples.chat_with_memory import create_chat_agent_with_memory

# 配置 LLM
llm_config = {
    "model": "deepseek-v4.1-flash",
    "api_key": "your-api-key",
    "base_url": "https://beeapi.dev/v1",
    "temperature": 0.7
}

# 创建带内存的 Agent
agent = create_chat_agent_with_memory(
    llm_config=llm_config,
    max_messages=20,   # 20 条消息后压缩
    keep_recent=10     # 保留最近 10 条
)

# 使用 Agent
config = {"configurable": {"thread_id": "user-123"}}

# 第 1 轮：用户自我介绍
agent.invoke(
    {"messages": [("user", "Hi! I'm Alice from Beijing. I love Python.")]},
    config
)

# 第 2-20 轮：正常对话...
for i in range(2, 21):
    agent.invoke(
        {"messages": [("user", f"Tell me about topic {i}")]},
        config
    )

# 第 21 轮：Agent 仍然记得！
result = agent.invoke(
    {"messages": [("user", "What's my name and where am I from?")]},
    config
)
# 回复："Your name is Alice and you're from Beijing."
```

## 工作原理

```
┌─────────────────────────────────┐
│  用户: "I'm Alice from Beijing" │
└───────────────┬─────────────────┘
                │
                ▼
    ┌───────────────────────┐
    │  提取用户画像:        │
    │  • name: Alice        │
    │  • location: Beijing  │
    └───────────┬───────────┘
                │
                ▼
    ┌───────────────────────┐
    │  存储到 State         │
    └───────────┬───────────┘
                │
                ▼
    [... 再来 20 条消息 ...]
                │
                ▼
    ┌───────────────────────┐
    │  触发压缩             │
    └───────────┬───────────┘
                │
                ▼
    ┌───────────────────────┐
    │  1. 生成摘要          │
    │  2. 删除旧消息        │
    │  3. 保留最近 10 条    │
    └───────────┬───────────┘
                │
                ▼
    ┌───────────────────────┐
    │  上下文 = 画像 +      │
    │  摘要 + 最近消息      │
    └───────────────────────┘
```

## 架构设计

详见 [MEMORY_ARCHITECTURE.md](MEMORY_ARCHITECTURE.md)。

**核心概念：**
- **MemoryState**：增强的 State，包含 `summary` 和 `user_profile` 字段
- **压缩机制**：消息数超过阈值时触发
- **上下文组装**：画像 + 摘要以假对话形式注入

## 测试

运行完整测试套件：

```bash
# 全部测试（15-20 分钟）
python tests/run_all_tests.py

# 单独测试
python tests/test_stability.py           # 10 次一致性检查
python tests/test_long_conversation.py   # 50 轮质量测试
python tests/test_efficiency.py          # Token 节省对比
python tests/test_edge_cases.py          # 鲁棒性测试
python tests/test_model_comparison.py    # SystemMessage 支持
python tests/test_memory_overhead.py     # 上下文大小分析
```

### 测试结果（2026-11-14）

✅ **6/6 全部通过**（17.3 分钟）

| 测试 | 结果 | 关键指标 |
|------|------|----------|
| Stability | ✅ 100% | 10/10 次都是 100% 质量 |
| Long Conversation | ✅ 100% | 50 轮后仍记住全部信息 |
| Efficiency | ✅ **34.4% 节省** | 28,769 → 18,886 tokens |
| Edge Cases | ✅ 5/5 | 全部边界情况通过 |
| Model Comparison | ✅ 确认 | DeepSeek 不支持 SystemMessage |
| Memory Overhead | ✅ **1.4%** | 假对话仅增加 1.4% 开销 |

## 配置

### 参数说明

```python
create_chat_agent_with_memory(
    llm_config=dict,      # LLM 配置
    max_messages=20,      # 超过此数量触发压缩
    keep_recent=10        # 保留最近多少条消息
)
```

**调优指南：**
- `max_messages`：越小 → 压缩越频繁 → 上下文越少
- `keep_recent`：越大 → 上下文越多 → 成本越高

**推荐起点：** `max_messages=20, keep_recent=10`

### Token 节省

对比无压缩方案的预期节省（基于 30 轮测试）：

| 配置 | 质量 | Token 节省 | 适用场景 |
|------|------|------------|----------|
| 20/10 | ~100% | ~30-40% | 均衡（推荐） |
| 15/8 | ~90%+ | ~40-50% | 激进压缩 |
| 30/15 | ~100% | ~20-30% | 保守策略 |

## 高级用法

### 自定义 State

```python
from optgraph.memory_state import MemoryState

class MyCustomState(MemoryState):
    custom_field: str = ""
    
# 在 Graph 中使用...
```

### 手动压缩

```python
from optgraph.memory_state import compress_memory

# 手动触发压缩
updates = compress_memory(
    state=current_state,
    summarizer_llm=my_llm,
    keep_recent=10
)
```

### 直接访问上下文

```python
from optgraph.memory_state import get_context_with_memory

# 获取完整上下文（含内存）
messages = get_context_with_memory(state)
# 返回: [假对话_画像, 假对话_摘要, ...最近消息]
```

## 已知问题与解决方案

### 问题：DeepSeek 忽略 SystemMessage

**问题：** DeepSeek 模型不遵守 SystemMessage 作为上下文。

**解决方案：** 我们将内存注入为假对话：
```python
HumanMessage("Hi! my name is Alice...")
AIMessage("Got it! I'll remember that.")
```

**影响：** 极小（~1.4% 额外 tokens）

### 问题：用户画像未更新

**问题：** 用户说"我搬到上海了"，但画像仍显示"北京"。

**临时方案：** 画像提取只在第一条消息时运行。未来版本会添加更新检测。

## 示例代码

参见 `examples/` 目录：
- `chat_with_memory.py` - 完整可运行示例
- 更多示例即将推出...

## 项目结构

```
optgraph/
├── memory_state.py       # 核心内存管理
├── token_tracker.py      # Token 跟踪
├── executor.py           # 并行执行（Phase 2）
└── __init__.py

examples/
└── chat_with_memory.py   # 使用示例

tests/
├── test_stability.py          # 一致性测试
├── test_long_conversation.py  # 可扩展性测试
├── test_efficiency.py         # 性能测试
├── test_edge_cases.py         # 鲁棒性测试
├── test_model_comparison.py   # 模型兼容性
├── test_memory_overhead.py    # 上下文分析
└── run_all_tests.py          # 主测试运行器

MEMORY_ARCHITECTURE.md    # 详细设计文档
README_MEMORY.md          # 本文件
```

## 研究与参考

基于以下研究构建：
- **LangGraph** (44.9K⭐) - 官方内存模式
- **Mem0** (23K⭐) - 内存架构
- **AgeMem** (arXiv:2601.01885) - LLM 驱动的内存

**关键经验：**
1. ❌ 不要在 Checkpointer 层压缩
2. ✅ 在 State 层管理内存逻辑
3. ✅ 分离关键事实（画像）和上下文（摘要）
4. ✅ 使用 RemoveMessage API 删除消息

## 贡献

发现 Bug？有建议？欢迎提 Issue 或 PR！

## 许可证

MIT

## 版本

当前版本：**v0.2.0** (2026-11-14)

基于行业最佳实践的重大重写。详见 [MEMORY_ARCHITECTURE.md](MEMORY_ARCHITECTURE.md)。
