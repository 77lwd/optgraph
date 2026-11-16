# OptGraph Documentation

**OptGraph** - Production-Ready Agent Orchestration Framework with Cost & Performance Optimization

基于 LangGraph 核心架构，针对生产环境的三大痛点进行深度优化。

---

## 📁 文档目录

### 核心文档

- **[【方案】LangGraph拆解与优化项目.md](./【方案】LangGraph拆解与优化项目.md)**  
  项目整体方案，技术定位，核心优化方向

- **[【执行计划】B方案详细计划.md](./【执行计划】B方案详细计划.md)**  
  5-6 周详细执行计划，每周目标和交付物

- **[AGENTS.md](./AGENTS.md)**  
  LangGraph Agent 系统说明

### Phase 2: Memory v2.0 系统 ✅

📂 **[memory_v2/](./memory_v2/)**

生产就绪的内存管理系统，核心成果：
- ✅ **平均Token节省**: 43.8%
- ✅ **成功率**: 5/5 (100%)
- ✅ **Quality保持**: 100%
- ✅ **解决v1灾难**: -322% → -31.0%

详见：[Memory v2 README](./memory_v2/README.md)

### Phase 3: 参数优化（设计中）

- **[phase3_design.md](./phase3_design.md)**  
  参数优化设计方案，目标 60%+ token 节省

### 归档文档

📂 **[archive/](./archive/)**
- phase2_memory_v1/ - 旧版memory系统（v1）
- 中间版本文档和设计迭代记录

---

## 🎯 项目目标

解决 LangGraph 在生产环境的三大痛点：

1. **Context 爆炸** - 长对话导致 token 成本线性增长
2. **串行执行** - 多工具调用浪费时间  
3. **成本失控** - 缺乏预算控制和实时监控

---

## 🏗️ 技术栈

- **基础框架**: LangGraph (44.9K⭐)
- **参考项目**: Mem0 (23K⭐), AgeMem 论文
- **测试模型**: DeepSeek-V4.1-Flash
- **开发语言**: Python 3.11+

---

## 📊 当前进度

- ✅ Phase 1: 理解 LangGraph 核心机制
- ✅ Phase 2: Memory v2.0 系统（生产就绪，平均-43.8% token）
- 🚧 Phase 3: 参数优化（设计中）
- 📋 Phase 4: 并发执行优化（待启动）
- 📋 Phase 5: 成本追踪系统（待启动）

---

## 📝 更新日志

**2025-01-16**: Phase 2 Memory v2.0 完成，5场景验证通过  
**2024-11-15**: Phase 2 v1 完成，发现-322%灾难  
**2024-11-12**: Phase 3 设计方案  
**2024-11-10**: B 方案执行计划  
**2024-11-09**: 项目方案定稿  
**2024-11-07**: 项目启动

---

**项目状态**: 🟢 进行中  
**当前版本**: v2.0  
**维护者**: lwd77
