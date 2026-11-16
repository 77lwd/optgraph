# OptGraph 内存系统 - 架构文档

## 概述

基于以下研究的生产级内存管理系统：
- **LangGraph 官方** (44.9K 星) - 设计原则
- **Mem0** (23K 星) - 内存架构模式
- **AgeMem 论文** (arXiv:2601.01885) - LLM 驱动的内存操作

## 设计原则

### 1. 关注点分离

- **Checkpointer 层**：仅负责存储（无逻辑）
- **State 层**：内存管理（决定保留/压缩什么）
- **Node 层**：业务逻辑

这符合 LangGraph 官方设计哲学：`MemorySaver` 仅处理持久化，不负责压缩。

### 2. 双重内存存储

```python
class MemoryState(MessagesState):
    summary: str           # 语义压缩（LLM 生成）
    user_profile: dict     # 结构化事实（确定性提取）
    messages: List         # 最近对话
```

**为什么需要两种类型？**
- **user_profile**：绝不能丢失的关键事实（姓名、位置、偏好）
  - 使用规则确定性提取
  - 压缩时永不删除
  
- **summary**：旧对话的语义上下文
  - 由 LLM 生成
  - 允许有损压缩，同时保留含义

### 3. 使用官方 API

使用 LangGraph 的 `RemoveMessage` API 删除消息：

```python
old_messages = messages[:-keep_recent]
delete_messages = [RemoveMessage(id=m.id) for m in old_messages]
return {"messages": delete_messages}
```

这是 LangGraph 文档推荐的方法。

## 架构设计

### 内存生命周期

```
┌─────────────────┐
│  新消息到达     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  需要压缩吗？               │
│  (messages > threshold)     │
└──────────┬──────────────────┘
           │
     ┌─────┴──────┐
     │            │
    否           是
     │            │
     ▼            ▼
  ┌─────┐  ┌───────────────────┐
  │ 结束│  │ 压缩内存          │
  └─────┘  └─────────┬─────────┘
                     │
                     ▼
           ┌──────────────────────────┐
           │ 1. 提取用户画像          │
           │    (如果尚未提取)        │
           └──────────┬───────────────┘
                     │
                     ▼
           ┌──────────────────────────┐
           │ 2. 生成摘要              │
           │    (LLM 调用)            │
           └──────────┬───────────────┘
                     │
                     ▼
           ┌──────────────────────────┐
           │ 3. 删除旧消息            │
           │    (RemoveMessage API)   │
           └──────────┬───────────────┘
                     │
                     ▼
                  ┌─────┐
                  │ 结束│
                  └─────┘
```

### 上下文组装

当 Agent 需要调用 LLM 时：

```python
def get_context_with_memory(state: MemoryState) -> List[BaseMessage]:
    messages = []
    
    # 1. 将用户画像注入为假对话
    if state.user_profile:
        messages.append(HumanMessage("Hi! my name is Alice, ..."))
        messages.append(AIMessage("Got it! I'll remember that."))
    
    # 2. 将摘要注入为假对话
    if state.summary:
        messages.append(HumanMessage("[Earlier conversation summary]"))
        messages.append(AIMessage(state.summary))
    
    # 3. 添加最近消息
    messages.extend(state.messages)
    
    return messages
```

**为什么用假对话而不是 SystemMessage？**

测试发现 **DeepSeek 模型忽略 SystemMessage** 作为上下文。它们只尊重 HumanMessage/AIMessage 对中的信息。

测试结果：
```
SystemMessage("用户名是 Alice") → LLM 说"我不知道" ❌
HumanMessage("我叫 Alice") → LLM 说"你叫 Alice" ✓
```

## 核心组件

### 1. 用户画像提取

```python
def extract_user_profile(messages: Sequence[BaseMessage]) -> dict:
    """从消息中提取结构化用户信息
    
    使用确定性规则提取：
    - 姓名 (模式: "my name is X", "I'm X")
    - 位置 (模式: "I live in X", "I'm from X")
    - 偏好 (关键词匹配: python, java 等)
    """
```

**确定性方法**确保关键信息永不丢失，不像基于 LLM 的提取可能不一致。

### 2. LLM 驱动的摘要生成

```python
def create_summary_with_llm(
    messages: Sequence[BaseMessage],
    existing_summary: str,
    summarizer_llm
) -> str:
    """使用 LLM 生成摘要
    
    策略：
    - 保持摘要在 80 词以内
    - 保留用户画像信息
    - 与现有摘要合并（如果有）
    - 安全性：生成失败时回退到旧摘要
    """
```

**安全特性：**
- `max_tokens=120` 硬限制
- 验证：拒绝 < 10 字符的摘要
- 失败时回退到现有摘要

### 3. 内存压缩

```python
def compress_memory(
    state: MemoryState,
    summarizer_llm,
    keep_recent: int = 10
) -> dict:
    """压缩对话内存
    
    返回 State 更新：
    - summary: 新的/更新的摘要
    - user_profile: 提取的画像（如果是新的）
    - messages: 旧消息的 RemoveMessage 列表
    """
```

**可配置参数：**
- `max_messages`：触发压缩的阈值
- `keep_recent`：保留多少条最近消息

## 对比：旧方案 vs 新方案

| 维度 | 旧方案 | 新方案 |
|------|--------|--------|
| **在哪层？** | Checkpointer 层 (`.put()`) | State/Node 层 |
| **删除方式** | 手动列表切片 | `RemoveMessage` API |
| **内存结构** | 单一 summary 字段 | Profile + summary |
| **上下文注入** | SystemMessage | 假对话 |
| **官方兼容** | ❌ 违反 LangGraph 设计 | ✅ 遵循官方模式 |

## 配置建议

### 推荐设置

基于测试结果（已通过完整测试套件验证）：

```python
agent = create_chat_agent_with_memory(
    llm_config={...},
    max_messages=20,    # 20 条消息后压缩
    keep_recent=10      # 保留最近 10 条
)
```

**权衡：**
- 降低 `max_messages` → 压缩更频繁 → 上下文更少
- 提高 `keep_recent` → 上下文更多 → Token 成本更高

## 测试

完整测试套件覆盖：

1. **Stability** (10 runs) - 一致性检查
2. **Long Conversation** (50 rounds) - 可扩展性测试
3. **Efficiency** - Token 节省 vs 基线
4. **Edge Cases** - 鲁棒性
5. **Model Comparison** - SystemMessage 支持
6. **Memory Overhead** - 上下文大小分析

### 测试结果 (2026-11-14)

✅ **6/6 全部通过**（17.3 分钟）

| 测试 | 结果 | 关键指标 |
|------|------|----------|
| Stability | ✅ 100% | 10/10 次都达到 100% 质量 |
| Long Conversation | ✅ 100% | 50 轮后仍记住全部信息 |
| **Efficiency** | ✅ **34.4% 节省** | 28,769 → 18,886 tokens |
| Edge Cases | ✅ 5/5 | 全部边界情况通过 |
| Model Comparison | ✅ 确认 | DeepSeek 不支持 SystemMessage |
| Memory Overhead | ✅ **1.4%** | 假对话仅增加 1.4% 开销 |

运行全部测试：
```bash
python tests/run_all_tests.py
```

## 使用示例

```python
from optgraph.memory_state import MemoryState
from examples.chat_with_memory import create_chat_agent_with_memory

# 创建 Agent
agent = create_chat_agent_with_memory(
    llm_config={
        "model": "deepseek-v4.1-flash",
        "api_key": "...",
        "base_url": "...",
        "temperature": 0.7
    },
    max_messages=20,
    keep_recent=10
)

# 使用 Agent
config = {"configurable": {"thread_id": "user-123"}}

result = agent.invoke(
    {"messages": [("user", "Hi! I'm Alice from Beijing.")]},
    config
)

# 稍后...
result = agent.invoke(
    {"messages": [("user", "What's my name?")]},
    config
)
# Agent 正确回答："Your name is Alice"
```

## 已知限制

1. **模型特定行为**
   - DeepSeek 忽略 SystemMessage
   - 需要假对话注入
   - 其他模型（GPT-4、Claude）可能支持 SystemMessage

2. **画像提取**
   - 使用简单正则表达式模式
   - 可能错过复杂的自我介绍
   - 可以通过 NLP 改进

3. **摘要质量**
   - 取决于 LLM 质量
   - 多次压缩后可能退化
   - 安全检查可减轻但无法完全消除

4. **信息更新**
   - 用户画像提取只运行一次
   - 更新（如"我搬到上海了"）不会自动捕获
   - 未来：添加画像更新检测

## 未来增强

1. **外部内存存储**
   - 集成 Mem0 或类似方案
   - 基于向量的检索
   - 跨会话的真正长期记忆

2. **更智能的画像提取**
   - 使用 NER（命名实体识别）
   - LLM 驱动的提取 + 验证
   - 画像更新检测

3. **自适应压缩**
   - 根据对话重要性调整 `keep_recent`
   - 主题建模提升摘要质量
   - 基于图的实体关系

4. **多模型支持**
   - 自动检测 SystemMessage 支持
   - 每个模型的回退策略
   - 每个提供商的优化 Prompt

## 参考资料

- [LangGraph 文档](https://docs.langchain.com/oss/python/langgraph)
- [Mem0 架构](https://docs.mem0.ai/architecture)
- [AgeMem 论文](https://arxiv.org/abs/2601.01885)
- [LangGraph 内存概念](https://docs.langchain.com/oss/python/langgraph/memory)

## 版本历史

- **v0.2.0** (2026-11-14)
  - 基于行业研究的完全重写
  - 从 Checkpointer 层迁移到 State 层
  - 添加双重内存（画像 + 摘要）
  - 为 DeepSeek 注入假对话
  - 完整测试套件（6/6 通过）
  - **性能：34.4% token 节省，100% 质量保持**

- **v0.1.0** (已弃用)
  - 初始实现（基于 Checkpointer）
  - 存在摘要膨胀和不稳定问题
