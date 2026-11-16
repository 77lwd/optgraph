# Memory v2.0 优化总结

## 问题
Scenario 1 (10轮对话) 出现 +31.4% overhead

## 根本原因
- 10轮对话 = 20条消息（user + AI）
- 压缩阈值 `max_messages=20` → 第10轮触发压缩
- 压缩固定成本 ~2,500 tokens
- 10轮的节省收益 < 2,500 tokens
- 结果：净成本 +2,661 tokens (+31.4%)

## 优化方案：动态压缩阈值

### 代码修改
```python
def should_compress_v2(
    state: MemoryStateV2,
    max_messages: int = 20,
    min_total_messages: int = 25  # 新增参数
) -> bool:
    """
    Check if compression is needed
    
    Args:
        max_messages: Trigger compression when messages exceed this
        min_total_messages: Minimum total messages before allowing compression
                           (avoid compression overhead in short conversations)
    """
    messages = state.get("messages", [])
    current_count = len(messages)
    
    # 短对话不压缩
    if current_count < min_total_messages:
        return False
    
    # 长对话才压缩
    return current_count >= max_messages
```

### 参数说明
- `max_messages=20`: 超过20条消息触发压缩
- `min_total_messages=25`: 至少25条消息才允许压缩
  - 25条消息 ≈ 12-13轮对话
  - 10轮对话(20条消息) < 25 → 不压缩 ✅

### 预期效果

| 场景 | 消息数 | 是否压缩 | 预期结果 |
|-----|--------|---------|----------|
| Scenario 1 (10轮) | 20 | ❌ 否（<25） | ~0% overhead |
| Scenario 2 (30轮) | 60 | ✅ 是（≥25） | -63.8% (保持) |
| Scenario 3 (50轮) | 100 | ✅ 是（≥25） | -31.0% (保持) |
| Scenario 4 (20轮) | 40 | ✅ 是（≥25） | -28.1% (保持) |
| Scenario 5 (25轮) | 50 | ✅ 是（≥25） | -46.1% (保持) |

### 权衡分析

**为什么选择 25？**
- 10轮（20条消息）：压缩成本 > 收益 → 不压缩
- 15轮（30条消息）：压缩收益开始显现 → 可以压缩
- 设置 25 = 在12-13轮开始压缩，平衡点合理

**Trade-off**:
- ✅ 短对话（<12轮）：零overhead
- ✅ 中长对话（12-50轮）：大幅节省
- ⚠️ 10-12轮：可能漏掉一些节省机会（但避免了overhead风险）

### 原则
> **宁可少节省一点，也不要出现 overhead**
> 
> 短对话用户体验更重要，不能为了压缩而增加成本

---

## 成本收益模型

### 压缩成本（固定）
```
LLM调用（提取结构化数据）: ~500-1000 tokens
额外request开销: ~200 tokens
总固定成本: ~1,000-1,500 tokens/次
```

### 压缩收益（变量）
```
删除消息数: 10条
平均每条: ~100 tokens
删除节省: 1,000 tokens

后续轮次不传这些消息:
- 剩余5轮: 1,000 × 5 = 5,000 tokens
- 剩余10轮: 1,000 × 10 = 10,000 tokens
- 剩余30轮: 1,000 × 30 = 30,000 tokens
```

### 盈亏平衡点
```
压缩成本: 1,500 tokens
需要节省: 1,500 tokens
最少剩余轮次: 1,500 / 1,000 = 1.5轮

但实际还要考虑：
- 删除消息可能不够多（<10条）
- 每条消息可能不够长（<100 tokens）
- 安全边际：需要至少2-3倍的预期收益

所以：至少需要3-5轮对话才压缩
即：至少6-10条消息 × 2 = 12-20条消息

选择 25 = 保守但安全
```

---

## 验证计划

### 测试场景
1. **Scenario 1 (10轮)** - 验证不压缩
   - 优化前: +31.4%
   - 优化后: ~0-5% (预期)

2. **Scenario 1.5 (15轮)** - 验证压缩边界
   - 15轮 = 30条消息 > 25 → 应该压缩
   - 预期: 小幅节省（~5-10%）

3. **其他场景** - 确认不受影响
   - Scenario 2-5: 保持原有节省效果

### 成功标准
- ✅ Scenario 1: overhead < 5%
- ✅ Scenario 2-5: 节省效果不变（±5%容差）
- ✅ 所有场景: Quality = 100%

---

## 最终配置

```python
# 推荐配置
max_messages = 20          # 超过20条消息触发压缩
keep_recent = 10          # 保留最近10条
min_total_messages = 25   # 至少25条才允许压缩

# 适用场景
短对话（<12轮）: 不压缩，零overhead
中长对话（12-50轮）: 压缩，大幅节省
```

---

## 状态
- ✅ 代码已修改（`min_total_messages=25`）
- 🔄 验证测试运行中
- 📊 等待Scenario 1优化后数据

---

最后更新: 2025-01-16
作者: Claude Opus 5.5 + lwd77
