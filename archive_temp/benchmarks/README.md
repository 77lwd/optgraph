# Context Compression Benchmark

Week 2 Phase 2 - 验证压缩质量和性能

## 🎯 测试目标

验证 `AdaptiveCheckpointSaver` 的压缩策略：
1. **对话连贯性**：压缩后 Agent 能否记住重要信息
2. **Token 节省**：实际能节省多少 Token
3. **性能影响**：压缩对响应时间的影响

---

## 📋 测试场景

### Test 1: Memory Retention（记忆保留测试）
- 用户提供个人信息（姓名、城市）
- 15轮填充对话（触发压缩）
- 询问 Agent 是否记得之前的信息
- **验证**：压缩后信息是否保留

### Test 2: Long Conversation（长对话测试）
- 30轮连续对话
- 对比 Baseline（不压缩）vs Compressed（压缩版）
- **验证**：Token 节省效果和性能影响

---

## 🚀 运行方法

### 1. 设置 OpenAI API Key

```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY="your-api-key-here"

# Windows (CMD)
set OPENAI_API_KEY=your-api-key-here

# Linux/Mac
export OPENAI_API_KEY="your-api-key-here"
```

### 2. 运行 Benchmark

```bash
python benchmarks/context_compression_benchmark.py
```

### 3. 查看结果

结果保存在：`benchmarks/benchmark_results.json`

---

## 📊 预期结果

```
COMPARISON SUMMARY:
=====================================================
Baseline:
  Time: 45.23s

Compressed:
  Time: 43.87s
  Compressions: 8
  Token reduction: 65.3%

Impact:
  Time change: +1.36s (+3.0%)
=====================================================
```

**解读**：
- ✅ Token 降低 ~65%
- ✅ 记忆保留正常
- ⚠️ 时间略微增加（压缩计算开销）

---

## 💰 成本估算

使用 `gpt-3.5-turbo`：
- 每次完整测试：约 50 轮对话
- 预估成本：$0.05 - $0.10

---

## 🔍 输出文件

- `benchmark_results.json` - 完整测试数据（JSON格式）

---

## ⚠️ 注意事项

1. **需要联网**：测试会调用 OpenAI API
2. **需要 API Key**：确保设置了 `OPENAI_API_KEY` 环境变量
3. **会产生费用**：使用的是真实 LLM 调用
4. **运行时间**：完整测试约 2-3 分钟

---

## 🐛 问题排查

### 问题1：`OpenAI API key not set`
```bash
# 检查环境变量
echo $OPENAI_API_KEY  # Linux/Mac
echo %OPENAI_API_KEY%  # Windows CMD
$env:OPENAI_API_KEY    # Windows PowerShell
```

### 问题2：`ModuleNotFoundError: No module named 'langchain_openai'`
```bash
pip install langchain-openai
```

### 问题3：API 调用失败
- 检查 API Key 是否有效
- 检查网络连接
- 检查 OpenAI 账户余额
