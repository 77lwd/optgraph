# 归档文档

此目录包含项目的历史文档和中间版本，供参考使用。

---

## 📂 目录结构

### phase2_memory_v1/
**Phase 2 Memory v1 系统（已废弃）**

- 原始memory系统实现
- 在Scenario 3遭遇-322%灾难
- 成功率: 3/5 (60%)
- 被Memory v2完全替代

关键问题：
- Summary每轮传递导致成本累积
- 长对话场景崩溃
- 无法处理50轮+对话

---

### 中间版本文档

#### MEMORY_V2_FINAL_REPORT.md
- v2未优化版本的报告
- 显示Scenario 1有+31.4% overhead
- 已被优化版本替代

#### MEMORY_V2_OPTIMIZATION.md
- 优化过程说明文档
- 记录如何将Scenario 1从+31.4%优化到-50.0%
- 技术细节已整合进最终报告

#### MEMORY_REDESIGN_LESSONS.md
- 从v1失败中总结的教训
- 设计经验和反思
- 指导v2架构设计

#### phase2_memory_redesign.md
- v2架构设计文档（早期版本）
- 技术选型和架构决策
- 实现细节已被代码覆盖

---

## 📌 当前版本

**最新文档请查看**: [`docs/memory_v2/`](../memory_v2/)

- Memory v2.0 (Optimized)
- 5/5场景全部成功
- 平均-43.8% token节省
- 生产就绪

---

**归档日期**: 2025-01-16  
**归档原因**: 已被v2.0替代
