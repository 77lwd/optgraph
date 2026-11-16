# OptGraph 文档结构说明

## 📁 目录结构

```
docs/
├── README.md                        # 项目总览和导航
├── STRUCTURE.md                     # 本文件，文档结构说明
│
├── 【方案】LangGraph拆解与优化项目.md   # 项目整体方案
├── 【执行计划】B方案详细计划.md         # 5-6周执行计划
├── AGENTS.md                         # Agent系统说明
├── LangGraph_Complete_Breakdown.md   # LangGraph完整拆解
├── phase3_design.md                  # Phase 3设计方案
│
├── memory_v2/                        # Memory v2.0 生产版本 ⭐
│   ├── README.md                     # Memory v2概览
│   ├── MEMORY_V2_FINAL_REPORT_WITH_OPTIMIZATION.md  # 完整报告
│   └── MEMORY_V2_VS_BASELINE.md      # 基线对比
│
└── archive/                          # 历史文档归档
    ├── README.md                     # 归档说明
    ├── phase2_memory_v1/             # Memory v1（已废弃）
    ├── MEMORY_V2_FINAL_REPORT.md     # v2未优化版
    ├── MEMORY_V2_OPTIMIZATION.md     # 优化过程
    ├── MEMORY_REDESIGN_LESSONS.md    # 设计教训
    └── phase2_memory_redesign.md     # v2早期设计
```

---

## 📖 阅读顺序

### 1. 快速了解（5分钟）
- [README.md](./README.md) - 项目总览

### 2. 理解项目（20分钟）
- [【方案】LangGraph拆解与优化项目.md](./【方案】LangGraph拆解与优化项目.md)
- [【执行计划】B方案详细计划.md](./【执行计划】B方案详细计划.md)

### 3. 深入Memory v2.0（30分钟）
- [memory_v2/README.md](./memory_v2/README.md) - 开始这里
- [memory_v2/MEMORY_V2_FINAL_REPORT_WITH_OPTIMIZATION.md](./memory_v2/MEMORY_V2_FINAL_REPORT_WITH_OPTIMIZATION.md) - 完整技术报告
- [memory_v2/MEMORY_V2_VS_BASELINE.md](./memory_v2/MEMORY_V2_VS_BASELINE.md) - 数据对比分析

### 4. 技术细节（可选）
- [LangGraph_Complete_Breakdown.md](./LangGraph_Complete_Breakdown.md) - 深入理解LangGraph
- [phase3_design.md](./phase3_design.md) - 未来优化方向

---

## 🎯 按需求查找

### 面试准备
1. [memory_v2/README.md](./memory_v2/README.md) - 项目亮点
2. [memory_v2/MEMORY_V2_FINAL_REPORT_WITH_OPTIMIZATION.md](./memory_v2/MEMORY_V2_FINAL_REPORT_WITH_OPTIMIZATION.md) - 技术细节和数据

### 使用Memory v2
1. [memory_v2/README.md](./memory_v2/README.md) - 快速开始
2. `optgraph/memory_v2.py` - 源码参考
3. `examples/chat_with_memory_v2.py` - 示例代码

### 了解项目规划
1. [【方案】LangGraph拆解与优化项目.md](./【方案】LangGraph拆解与优化项目.md)
2. [【执行计划】B方案详细计划.md](./【执行计划】B方案详细计划.md)
3. [phase3_design.md](./phase3_design.md)

### 历史和演化
1. [archive/phase2_memory_v1/](./archive/phase2_memory_v1/) - 看v1如何失败
2. [archive/MEMORY_REDESIGN_LESSONS.md](./archive/MEMORY_REDESIGN_LESSONS.md) - 学到的教训
3. Git history - 完整演化过程

---

## 📝 文档类型

### 📘 方案文档
- 项目整体规划
- 技术选型
- 执行计划

### 📗 技术文档
- 架构设计
- 实现细节
- API说明

### 📊 测试报告
- 实验数据
- 性能对比
- 质量验证

### 📦 归档文档
- 历史版本
- 废弃方案
- 经验教训

---

## 🔄 维护原则

### 保持最新
- README.md - 始终反映当前状态
- memory_v2/ - 生产版本文档
- 版本号和日期保持更新

### 清理归档
- 过时文档移入archive/
- 中间版本文档归档
- 保留关键教训和数据

### 结构清晰
- 按Phase组织
- 避免文档冗余
- 明确文档用途

---

**最后更新**: 2025-01-16  
**维护者**: lwd77
