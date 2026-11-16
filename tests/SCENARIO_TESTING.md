# 多场景测试指南

## 📋 测试列表

所有测试已拆分成独立的小测试，每个 5-10 分钟完成，可以单独运行。

| 测试 | 文件 | 轮次 | 预期效果 | 耗时 |
|------|------|------|---------|------|
| 场景 1 | `test_scenario_1_short.py` | 10 | 0-10% | 3-5 分钟 |
| 场景 2 | `test_scenario_2_medium.py` | 30 | 30-40% | 5-8 分钟 |
| 场景 3 | `test_scenario_3_long.py` | 50 | 40-50% | 8-12 分钟 |
| 场景 4 | `test_scenario_4_long_messages.py` | 20 | 35-45% | 6-10 分钟 |
| 场景 5 | `test_scenario_5_realistic.py` | 25 | 30-40% | 5-8 分钟 |

---

## 🚀 如何运行

### 选项 A：运行单个场景（推荐）

每次运行一个，5-10 分钟完成，不怕中断：

```bash
cd C:\Users\lwd77\Desktop\拆解harness

# 场景 1: 短对话
py -3 tests/test_scenario_1_short.py

# 场景 2: 中等对话（已知 34.4%）
py -3 tests/test_scenario_2_medium.py

# 场景 3: 长对话
py -3 tests/test_scenario_3_long.py

# 场景 4: 长消息
py -3 tests/test_scenario_4_long_messages.py

# 场景 5: 混合真实
py -3 tests/test_scenario_5_realistic.py
```

### 选项 B：查看已完成的结果

```bash
py -3 tests/view_summary.py
```

---

## 📊 特性

✅ **实时输出** - 立即看到进度
✅ **结果保存** - 每个场景结果保存到 `test_results/scenario_N.json`
✅ **增量运行** - 跑完的不用重跑
✅ **快速完成** - 5-10 分钟/场景
✅ **不怕中断** - 每个独立运行

---

## 📁 输出文件

测试结果保存在：
```
test_results/
├── scenario_1_short.json
├── scenario_2_medium.json
├── scenario_3_long.json
├── scenario_4_long_messages.json
└── scenario_5_realistic.json
```

每个文件包含：
- Token 使用量（baseline vs memory）
- Token 节省百分比
- 质量评分
- 运行时间

---

## 💡 建议运行顺序

**最快验证**（选 2-3 个）：
1. 场景 2（中等对话）- 已知结果，验证系统工作
2. 场景 1（短对话）- 测试边界情况
3. 场景 4（长消息）- 测试不同消息类型

**完整测试**（全部 5 个）：
- 按顺序全跑一遍
- 总耗时：~30-45 分钟
- 但可以分批跑，不用一次性完成

---

## 🎯 预期结果

根据理论分析，预期：

```
场景 1 (短对话):     0-10%  (不触发压缩)
场景 2 (中等对话):   30-40% (已知 34.4%)
场景 3 (长对话):     40-50% (压缩累积效果)
场景 4 (长消息):     35-45% (大消息删除有效)
场景 5 (混合真实):   30-40% (接近中等对话)

平均预期: 25-45%
```

---

## 🔧 故障排除

**问题：ImportError**
```bash
# 确保在项目根目录
cd C:\Users\lwd77\Desktop\拆解harness
```

**问题：API 错误**
- 检查 API key 是否有效
- 检查网络连接

**问题：测试卡住**
- 按 Ctrl+C 停止
- 重新运行即可（不会丢失已完成的场景）

---

## 📝 查看详细结果

查看 JSON 文件：
```bash
cat test_results/scenario_2_medium.json
```

或使用汇总脚本：
```bash
py -3 tests/view_summary.py
```
