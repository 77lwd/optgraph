# Archive - 未使用的实现

本目录包含OptGraph项目中未被使用的代码实现，保留作为参考。

---

## 文件说明

### 1. `executor.py` (691 bytes)
**原因**：Stub实现，只有TODO注释

**内容**：
- `DependencyAwareExecutor` 类，但所有方法都是 `pass`
- 注释说 "TODO: Week 3 implementation"

**替代方案**：
- 实际实现在 `../parallel_executor.py` 中的 `ParallelExecutor` 类
- `__init__.py` 中 `DependencyAwareExecutor` 现在是 `ParallelExecutor` 的别名

**保留原因**：历史参考，展示最初的设计意图

---

### 2. `memory_v2.py` (14,795 bytes)
**原因**：完整实现但未被使用

**内容**：
- `MemoryStateV2` - 增强的状态类，带结构化memory字段
- `StructuredMemory` - 结构化存储和检索系统
- 设计理念："Memory stored in state, NOT passed to LLM by default"

**当前方案**：
- 实际使用的是 `../memory_state.py` 中的 `MemoryState`
- 采用滑动窗口+重要性保留策略，达到43.8% token节省

**两种方案对比**：
| 特性 | memory_state.py (当前) | memory_v2.py (archived) |
|------|------------------------|-------------------------|
| 策略 | 滑动窗口+重要性保留 | 结构化存储+按需检索 |
| 存储 | 直接在messages中 | 独立的structured_memory字段 |
| 检索 | 自动保留重要消息 | 关键词索引检索 |
| 复杂度 | 简单 | 较复杂 |
| 效果 | 43.8% token节省 | 未测试 |

**保留原因**：
- 是一个有价值的替代设计
- 可能在未来场景中有用（需要更精细的memory控制）
- 代码质量高，完整实现

---

### 3. `token_tracker.py` (5,500 bytes)
**原因**：功能被 `CostTracker` 覆盖

**内容**：
- `TokenTracker` 类：追踪LLM API调用的token使用
- 功能：record_usage(), get_stats(), reset()
- 线程安全实现

**当前方案**：
- 使用 `../cost_tracker.py` 中的 `CostTracker`
- 不仅追踪tokens，还计算成本、预算控制、多维度统计

**功能对比**：
| 功能 | TokenTracker | CostTracker |
|------|-------------|-------------|
| Token追踪 | ✅ | ✅ |
| 成本计算 | ❌ | ✅ |
| 预算控制 | ❌ | ✅ |
| 多厂商定价 | ❌ | ✅ |
| 用户/线程统计 | ❌ | ✅ |
| SQLite持久化 | ❌ | ✅ |

**保留原因**：
- 作为轻量级替代方案（如果只需要token统计）
- 展示了早期的设计思路

---

## 移动历史

**日期**：2025-01-XX  
**原因**：漏洞审查发现这些文件未被使用，造成代码库混乱  
**详情**：见 `../VULNERABILITY_REPORT.md`

---

## 使用建议

这些文件**不应该在生产代码中使用**。

如果需要参考：
- 并发执行 → 使用 `../parallel_executor.py`
- Memory管理 → 使用 `../memory_state.py`
- Token/成本追踪 → 使用 `../cost_tracker.py`

---

最后更新：2025-01-XX  
状态：Archived - 仅作参考
