# Phase 2 Memory System 重新设计方案

## 文档信息
- **版本**: v2.0 设计方案
- **日期**: 2025-01-15
- **状态**: 设计阶段，待实现
- **目标**: 从 -322% 失败中重建，实现真正的 token 节省

---

## 执行摘要

### 问题
当前 Memory 系统完全失败：50轮对话从预期节省35%变成**损失322%**（增加56万tokens）。

### 根本原因
Summary 在每轮都被完整传递给 LLM，导致：
1. 直接成本：300 tokens/轮 × 50轮 = 15,000 tokens
2. 隐藏成本：长 context 导致 LLM 回复暴增 5-10倍
3. 恶性循环：更长回复 → 更长 summary → 更长 context

### 解决方案
**核心原则：Memory 存在 state 中，不传递给 LLM，只在需要时检索注入。**

预期效果：
- 不需要 memory 的轮次：**0% overhead**（45/50轮）
- 需要 memory 的轮次：**<10% overhead**（5/50轮）
- 整体：**+2-5% overhead**，而不是 -322%

---

## 设计原理

### 当前架构的致命缺陷

```python
# ❌ 当前实现：每轮都传 summary
def get_context_with_memory(state):
    messages = []
    
    # 每轮都添加 summary（300+ tokens）
    if summary:
        messages.append(HumanMessage("[Earlier conversation summary]"))
        messages.append(AIMessage(content=summary))  # ← 灾难源头
    
    # 最近10条消息
    messages.extend(state["messages"][-10:])
    
    return messages
```

**问题分析：**
| 轮次 | Summary 大小 | 累积传递成本 | LLM 回复增长 | 总成本 |
|-----|------------|------------|-------------|--------|
| 20  | 300 tokens | 300        | +200        | 500    |
| 30  | 300 tokens | 3,000      | +2,000      | 5,000  |
| 50  | 300 tokens | 15,000     | +10,000     | 25,000 |

### 新架构的核心思想

```
核心对比：

当前架构：
  State → [summary + messages] → LLM
           ↑
           每轮都传，累积膨胀

新架构：
  State → [messages only] → LLM  （大部分时候）
           ↓
       structured_memory
           ↓
       只在需要时检索 → [memory snippet + messages] → LLM
```

**关键差异：**
1. Memory 默认不在 LLM 的输入中
2. Memory 以结构化格式存储（不是自然语言）
3. 只在明确需要时才检索并注入

---

## 技术设计

### 1. 数据结构

```python
class MemoryState(TypedDict):
    """Graph state with structured memory"""
    
    # 常规字段（baseline）
    messages: List[BaseMessage]  # 所有历史消息
    
    # 新增：结构化 memory（不传递给 LLM）
    structured_memory: Dict[str, Any]
    """
    {
        "user_profile": {
            "name": "Alice",
            "location": "Beijing",
            "preferences": ["Python", "AI"],
            "expertise": "intermediate"
        },
        "key_facts": [
            {
                "id": 1,
                "fact": "User is building OptGraph project",
                "round": 5,
                "importance": 0.9,
                "keywords": ["optgraph", "langgraph", "optimization"]
            },
            {
                "id": 2,
                "fact": "Discussed token compression strategies",
                "round": 15,
                "importance": 0.7,
                "keywords": ["token", "compression", "memory"]
            }
        ],
        "topic_threads": {
            "coding_help": [5, 12, 23, 34],
            "design_discussion": [8, 19, 27]
        }
    }
    """
    
    # 用于检索的索引
    memory_index: Optional[Dict[str, List[int]]]  # keyword -> fact_ids
```

### 2. 核心组件

#### 2.1 Memory 压缩器

```python
class MemoryCompressor:
    """
    将旧消息压缩为结构化存储
    不是生成自然语言 summary，而是提取结构化数据
    """
    
    def compress_messages(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        """
        输入：10条要删除的旧消息（~1000 tokens）
        输出：结构化数据（~100 tokens JSON）
        
        压缩比：10:1
        """
        
        # 使用 LLM 提取结构化信息
        prompt = f"""
从以下对话中提取关键信息，返回JSON格式：

对话：
{format_messages(messages)}

返回格式：
{{
    "user_profile_updates": {{"key": "value", ...}},
    "key_facts": [
        {{"fact": "...", "importance": 0.0-1.0, "keywords": [...]}}
    ],
    "topics": ["topic1", "topic2"]
}}

只提取重要信息，忽略闲聊和临时内容。
"""
        
        result = llm.invoke(prompt)
        extracted = json.loads(result)
        
        return extracted
    
    def should_compress(self, state: MemoryState) -> bool:
        """
        决定是否需要压缩
        """
        message_count = len(state["messages"])
        
        # 每20条消息压缩一次，保留最近10条
        return message_count >= 20
```

#### 2.2 Memory 检索器

```python
class MemoryRetriever:
    """
    按需检索相关记忆
    只在需要时调用，大部分时候不用
    """
    
    def retrieve(
        self, 
        query: str, 
        structured_memory: Dict[str, Any],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        输入：用户查询
        输出：最相关的 k 个记忆片段
        
        检索方法：简单关键词匹配（Phase 1）
        """
        
        query_keywords = extract_keywords(query)
        facts = structured_memory.get("key_facts", [])
        
        # 计算相关性分数
        scored_facts = []
        for fact in facts:
            score = self._compute_relevance(
                query_keywords, 
                fact["keywords"]
            )
            if score > 0:
                scored_facts.append((score, fact))
        
        # 返回 top-k
        scored_facts.sort(reverse=True, key=lambda x: x[0])
        return [fact for score, fact in scored_facts[:top_k]]
    
    def _compute_relevance(self, query_kw, fact_kw):
        """简单的关键词重叠计数"""
        overlap = set(query_kw) & set(fact_kw)
        return len(overlap)
    
    def format_for_llm(self, facts: List[Dict]) -> str:
        """
        将检索到的记忆格式化为简洁的文本
        
        输出示例：
        "Relevant context from earlier:
        - Round 5: User is building OptGraph project
        - Round 15: Discussed token compression strategies"
        """
        if not facts:
            return ""
        
        lines = ["Relevant context from earlier:"]
        for fact in facts:
            lines.append(
                f"- Round {fact['round']}: {fact['fact']}"
            )
        
        return "\n".join(lines)
```

#### 2.3 Graph 节点

```python
def chat_node(state: MemoryState) -> MemoryState:
    """
    主对话节点：只使用最近消息，不传 memory
    这是默认路径，零 overhead
    """
    
    # 只取最近10条消息（baseline）
    recent_messages = state["messages"][-10:]
    
    # 调用 LLM
    response = llm.invoke(recent_messages)
    
    # 更新 state
    return {
        "messages": state["messages"] + [response]
    }


def recall_node(state: MemoryState) -> MemoryState:
    """
    记忆检索节点：需要历史上下文时才调用
    """
    
    user_query = state["messages"][-1].content
    
    # 检索相关记忆
    retriever = MemoryRetriever()
    relevant_facts = retriever.retrieve(
        user_query, 
        state["structured_memory"],
        top_k=3
    )
    
    # 格式化为简洁文本
    memory_context = retriever.format_for_llm(relevant_facts)
    
    # 注入到消息中（作为 system message）
    recent_messages = state["messages"][-10:]
    
    if memory_context:
        messages_with_memory = [
            SystemMessage(content=memory_context)
        ] + recent_messages
    else:
        messages_with_memory = recent_messages
    
    # 调用 LLM
    response = llm.invoke(messages_with_memory)
    
    # 更新 state
    return {
        "messages": state["messages"] + [response]
    }


def compress_node(state: MemoryState) -> MemoryState:
    """
    压缩节点：定期将旧消息压缩为结构化存储
    """
    
    messages = state["messages"]
    
    # 保留最近10条，压缩更早的10条
    to_compress = messages[-20:-10]
    to_keep = messages[-10:]
    
    # 压缩
    compressor = MemoryCompressor()
    extracted = compressor.compress_messages(to_compress)
    
    # 合并到现有 memory
    current_memory = state.get("structured_memory", {
        "user_profile": {},
        "key_facts": [],
        "topic_threads": {}
    })
    
    # 更新 user_profile
    current_memory["user_profile"].update(
        extracted.get("user_profile_updates", {})
    )
    
    # 添加新的 key_facts
    new_facts = extracted.get("key_facts", [])
    for fact in new_facts:
        fact["id"] = len(current_memory["key_facts"]) + 1
    current_memory["key_facts"].extend(new_facts)
    
    # 更新 state
    return {
        "messages": to_keep,  # 只保留最近10条
        "structured_memory": current_memory
    }
```

### 3. Graph 结构

```python
def build_memory_graph():
    """
    构建带 memory 的 graph
    
    关键设计：
    1. 默认走 chat_node（零 overhead）
    2. 需要时走 recall_node（有 overhead，但可控）
    3. 定期走 compress_node（压缩旧消息）
    """
    
    graph = StateGraph(MemoryState)
    
    # 添加节点
    graph.add_node("chat", chat_node)
    graph.add_node("recall", recall_node)
    graph.add_node("compress", compress_node)
    
    # 入口：决定是否需要 recall
    graph.add_conditional_edges(
        START,
        route_by_need,
        {
            "chat": "chat",
            "recall": "recall"
        }
    )
    
    # 出口：决定是否需要 compress
    graph.add_conditional_edges(
        "chat",
        check_compression,
        {
            "compress": "compress",
            "end": END
        }
    )
    
    graph.add_conditional_edges(
        "recall",
        check_compression,
        {
            "compress": "compress",
            "end": END
        }
    )
    
    graph.add_edge("compress", END)
    
    return graph.compile()


def route_by_need(state: MemoryState) -> str:
    """
    决定是否需要检索 memory
    
    Phase 1: 简单的关键词检测
    Phase 2: 可以用小模型做意图分类
    """
    
    user_message = state["messages"][-1].content.lower()
    
    # 检测 recall 关键词
    recall_keywords = [
        "earlier", "before", "previous", "记得", "之前",
        "recall", "remember", "上次", "刚才"
    ]
    
    if any(kw in user_message for kw in recall_keywords):
        return "recall"
    
    # 默认不需要 memory
    return "chat"


def check_compression(state: MemoryState) -> str:
    """
    决定是否需要压缩
    """
    
    message_count = len(state["messages"])
    
    # 每20条消息压缩一次
    if message_count >= 20:
        return "compress"
    
    return "end"
```

---

## 成本分析

### 场景1：50轮对话，不需要 recall（最常见）

| 轮次 | 传递内容 | Input tokens | Output tokens | 总计 |
|-----|---------|-------------|--------------|------|
| 1-10 | 最近消息 | 100-500 | 50-100 | 150-600 |
| 11-19 | 最近10条 | 500 | 100 | 600 |
| 20 | 压缩 | +250 (LLM调用) | - | +250 |
| 21-39 | 最近10条 | 500 | 100 | 600 |
| 40 | 压缩 | +250 | - | +250 |
| 41-50 | 最近10条 | 500 | 100 | 600 |

**总计**：
- 正常轮次：50 × 600 = 30,000 tokens
- 压缩成本：2 × 250 = 500 tokens
- **总计：30,500 tokens**

**对比 baseline**（没有 memory，直接传所有消息）：
- Baseline 在第50轮会传递所有50条消息（~30,000 tokens input）
- 新系统只传递最近10条（~500 tokens input）
- **节省：~29,500 tokens input**

**实际节省率：** (29,500 / 30,000) = **~98%**（相对于传递所有历史）

### 场景2：50轮对话，5次 recall

| 类型 | 轮次数 | 额外成本/轮 | 总额外成本 |
|-----|-------|-----------|----------|
| 普通轮次 | 45 | 0 | 0 |
| Recall 轮次 | 5 | +150 tokens | 750 |
| 压缩 | 2 | +250 tokens | 500 |

**总额外成本：** 750 + 500 = **1,250 tokens**

**相对于 baseline 的 overhead：** 1,250 / 30,000 = **+4.2%**

### 对比当前失败的系统

| 系统 | 50轮总 tokens | vs Baseline | vs 当前失败系统 |
|-----|-------------|-------------|----------------|
| Baseline（无memory） | 173,922 | 0% | - |
| 当前失败系统 | 734,863 | **-322%** ❌ | - |
| 新系统（无recall） | ~30,500 | **+98%** ✅ | +2,307% ✅ |
| 新系统（5次recall） | ~31,750 | **+96%** ✅ | +2,215% ✅ |

---

## 实现计划

### Phase 1: 最小可行版本（MVP）

**目标**: 证明核心原理可行

**实现内容**：
1. `StructuredMemory` 类（dict 存储，关键词检索）
2. `MemoryCompressor`（LLM 提取结构化数据）
3. `MemoryRetriever`（关键词匹配）
4. Graph 节点：`chat_node`, `recall_node`, `compress_node`
5. 路由逻辑：`route_by_need`, `check_compression`

**不包括**：
- ❌ 向量 embedding
- ❌ 语义搜索
- ❌ 自动相关性检测
- ❌ Memory 重要性评分

**测试**：
- 5轮对话，不需要 recall → 验证零 overhead
- 5轮对话，1次手动 recall → 验证检索工作

**预计时间**：3-4小时

### Phase 2: 验证和测试

**目标**: 在真实场景下验证性能

**测试场景**：

1. **Scenario A: 零 recall**
   - 50轮独立问答
   - 预期：0% overhead vs baseline
   - 验证：不会出现累积膨胀

2. **Scenario B: 偶尔 recall**
   - 50轮对话，5次手动 recall（用户说"记得之前..."）
   - 预期：<5% overhead vs baseline
   - 验证：recall 成本可控

3. **Scenario C: 压力测试**
   - 100轮对话
   - 预期：无累积膨胀，overhead 保持稳定
   - 验证：长期稳定性

**成功标准**：
- ✅ Scenario A: overhead < 5%
- ✅ Scenario B: overhead < 10%
- ✅ Scenario C: 第100轮 overhead ≈ 第50轮 overhead（无累积）
- ✅ **绝对不能出现负收益**

**预计时间**：2-3小时

### Phase 3: 优化（可选）

**前提**: Phase 2 测试全部通过

**优化内容**：
1. 向量 embedding + 语义搜索
2. 自动相关性检测（不依赖关键词）
3. Memory 重要性评分和自动清理
4. 压缩策略优化（自适应压缩频率）

**预计时间**：4-6小时

---

## 设计权衡

### 为什么不用自然语言 summary？

| 方案 | 优点 | 缺点 | 选择 |
|-----|------|------|------|
| 自然语言 summary | 容易理解 | 冗长（300+ tokens），传递成本高 | ❌ |
| 结构化存储 | 紧凑（~100 tokens），精确检索 | 需要设计数据结构 | ✅ |

**决策**: 结构化存储，只在注入 LLM 时才转换为自然语言。

### 为什么不自动检索，而是手动触发？

| 方案 | 优点 | 缺点 | Phase |
|-----|------|------|-------|
| 手动触发（关键词） | 零误触发，成本可控 | 可能漏掉需要 memory 的情况 | Phase 1 |
| 自动相关性检测 | 更智能，UX 更好 | 可能误触发，增加 overhead | Phase 3 |

**决策**: Phase 1 先用手动触发验证核心原理，Phase 3 再加自动检测。

### 为什么压缩频率是20轮？

| 频率 | 优点 | 缺点 | 选择 |
|-----|------|------|------|
| 每10轮 | 更及时，不会累积太多消息 | 压缩次数多，成本高 | ❌ |
| 每20轮 | 平衡：10条压缩，10条保留 | - | ✅ |
| 每50轮 | 压缩次数少 | 需要保留大量消息，context 变大 | ❌ |

**决策**: 20轮，保持最近10条完整，压缩10-20条。可在 Phase 3 改为自适应。

---

## 面试准备

### 核心问题和回答

**Q: 为什么之前的设计失败了？**

A: 之前的设计在每轮都传递 summary 到 LLM，导致三个问题：
1. 直接成本：300 tokens × 50轮 = 15,000 tokens
2. 隐藏成本：长 context 导致 LLM 回复暴增 5-10倍（+10,000+ tokens）
3. 恶性循环：更长回复 → 更长 summary → 更长 context

最终导致 -322% 的灾难性结果。

**Q: 新设计的核心思想是什么？**

A: **Memory 存在 state 中，不传递给 LLM，只在需要时检索注入。**

大部分轮次（90%）零 overhead，少数需要 memory 的轮次（10%）才有可控的检索成本。

**Q: 如何避免累积膨胀？**

A: 三个机制：
1. Memory 用结构化格式存储（不是自然语言），大小固定
2. 只传递检索到的相关片段（3个 facts），不是全部 memory
3. 定期压缩旧消息，保持最近10条完整

**Q: Trade-offs 是什么？**

A: 
- 优点：零 baseline overhead，可扩展到任意轮次
- 缺点：可能漏掉需要 memory 的情况（Phase 1 关键词触发不够智能）
- 后续优化：Phase 3 加入自动相关性检测

**Q: 如何验证设计有效？**

A: 三个测试场景：
1. 50轮零 recall：验证零 overhead（<5%）
2. 50轮5次 recall：验证可控 overhead（<10%）
3. 100轮：验证无累积膨胀（第100轮 overhead ≈ 第50轮）

全部通过才算成功。

---

## 参考文献

### 内部文档
- `docs/MEMORY_REDESIGN_LESSONS.md` - 失败教训和根本原因分析
- `PROGRESS_ADAPTIVE_STRATEGY.md` - 自适应策略失败分析
- `optgraph/memory_state.py` - 失败的实现（反面教材）

### 外部参考
- LangGraph Memory 机制：https://langchain-ai.github.io/langgraph/concepts/memory/
- RAG 检索策略：按需检索 vs 全量传递
- Context window optimization: 分层存储策略

---

## 下一步

1. **Review 这份设计文档** - 确认方向正确
2. **开始 Phase 1 实现** - 最小可行版本
3. **快速迭代测试** - 5轮 → 50轮 → 100轮

**关键原则：先验证核心原理，再添加复杂功能。不要重复之前"先写代码再测试"的错误。**

---

最后更新：2025-01-15
作者：Claude Opus 5.5 + lwd77
状态：✅ 设计完成，待实现
