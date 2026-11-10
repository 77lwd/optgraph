# LangGraph 入门：从零开始理解

> 给完全没接触过LangGraph的人看的

---

## 一、什么是LangGraph？（用人话说）

### 最简单的类比

**LangGraph = 给AI写程序的"流程图工具"**

想象你要让AI完成一个复杂任务，比如"帮我调研竞品并写报告"：

```
传统做法（一次性prompt）：
User: "帮我调研竞品并写报告"
AI: 直接生成一堆文字（可能不完整，没法中途控制）

LangGraph做法（流程图）：
User: "帮我调研竞品并写报告"
  ↓
[搜索竞品] → [分析数据] → [写报告] → [人工审核] → [修改] → 完成
   ↑______________________________________________|
        （如果审核不通过，回到修改步骤）
```

**LangGraph让你把AI任务拆成多个步骤，每步可以：**
- 调用工具（搜索、计算器、数据库）
- 做决策（if/else分支）
- 循环执行（直到满足条件）
- 人工介入（暂停等你确认）

---

## 二、核心概念（4个关键词）

### 1. **Graph（图）**= 流程图

```python
# 定义一个流程
workflow = StateGraph()
workflow.add_node("步骤A", function_a)  # 添加节点
workflow.add_node("步骤B", function_b)
workflow.add_edge("步骤A", "步骤B")    # A完成后执行B
```

就像画流程图：
```
[开始] → [步骤A] → [步骤B] → [结束]
```

### 2. **Node（节点）**= 一个具体任务

每个节点可以是：
- **调用LLM**："分析这段文字"
- **调用工具**："搜索网页"
- **人工审核**："等用户确认"

```python
def analyze_node(state):
    # 这个节点的工作：分析数据
    result = llm.invoke(f"分析: {state['data']}")
    return {"analysis": result}
```

### 3. **State（状态）**= 数据在节点间传递

```python
# 初始state
state = {
    "query": "竞品分析",
    "search_results": [],
    "analysis": "",
    "report": ""
}

# 每个节点可以读取和更新state
def search_node(state):
    results = google_search(state["query"])
    return {"search_results": results}  # 更新state

def analyze_node(state):
    analysis = llm.invoke(state["search_results"])
    return {"analysis": analysis}  # 再次更新state
```

State就像一个**共享的记事本**，每个节点都能读写。

### 4. **Edge（边）**= 节点之间的连接

```python
# 固定连接
workflow.add_edge("搜索", "分析")  # 搜索完了一定执行分析

# 条件连接
workflow.add_conditional_edges(
    "分析",
    lambda state: "写报告" if state["quality"] > 0.8 else "重新搜索"
)
# 如果分析质量好，就写报告；否则重新搜索
```

---

## 三、一个完整例子（最简单的Agent）

**任务**：做一个能查天气的AI助手

### 传统方式（单次对话）
```python
# 用户问
user_input = "北京今天天气怎么样？"

# AI回答
response = llm.invoke(user_input)
print(response)  # 可能瞎编："我觉得是晴天"（没真查）
```

### LangGraph方式（有工具的Agent）

```python
from langgraph.graph import StateGraph, MessagesState

# 1. 定义工具
def get_weather(city: str) -> str:
    # 真实调用天气API
    return f"{city}今天晴天，25度"

# 2. 定义节点
def agent_node(state):
    """LLM决策：需要调用工具吗？"""
    messages = state["messages"]
    response = llm.invoke(messages)
    
    if "查天气" in response:
        return {"action": "call_tool", "city": "北京"}
    else:
        return {"messages": [response]}

def tool_node(state):
    """执行工具"""
    city = state["city"]
    result = get_weather(city)
    return {"messages": [f"工具返回: {result}"]}

# 3. 构建流程
workflow = StateGraph(MessagesState)
workflow.add_node("agent", agent_node)
workflow.add_node("tool", tool_node)

# 4. 连接节点
workflow.add_conditional_edges(
    "agent",
    lambda s: "tool" if s.get("action") == "call_tool" else END
)
workflow.add_edge("tool", "agent")  # 工具执行完回到agent

# 5. 编译并运行
app = workflow.compile()
result = app.invoke({"messages": [("user", "北京今天天气怎么样？")]})
print(result)
```

**执行流程**：
```
用户: "北京天气怎么样？"
  ↓
[agent节点] LLM说："我需要调用get_weather工具"
  ↓
[tool节点] 调用get_weather("北京") → "晴天，25度"
  ↓
[agent节点] LLM说："根据查询结果，北京今天晴天25度"
  ↓
返回给用户
```

---

## 四、为什么需要LangGraph？（vs 直接调用LLM）

### 场景1：多步骤任务

**需求**："帮我找一个Python库，读它的文档，写个使用示例"

**直接调用LLM**：
- ❌ 一次性生成，可能瞎编
- ❌ 没法中途修正
- ❌ 无法真的"读文档"

**用LangGraph**：
```
[搜索库] → [爬取文档] → [阅读文档] → [写代码] → [测试代码] → [返回]
```
- ✅ 每步都真实执行
- ✅ 可以重试失败的步骤
- ✅ 可以加人工审核

### 场景2：循环/迭代任务

**需求**："不断优化这段代码，直到测试通过"

```python
workflow.add_node("写代码", write_code)
workflow.add_node("运行测试", run_tests)
workflow.add_node("分析错误", analyze_errors)

workflow.add_edge("写代码", "运行测试")
workflow.add_conditional_edges(
    "运行测试",
    lambda s: END if s["tests_passed"] else "分析错误"
)
workflow.add_edge("分析错误", "写代码")  # 循环
```

**LLM会一直循环改代码，直到测试通过。**

### 场景3：人工介入

**需求**："写一篇文章，但我要先审核大纲"

```python
workflow.add_node("写大纲", write_outline)
workflow.add_node("等待审核", human_review)  # 暂停，等用户确认
workflow.add_node("写正文", write_content)

workflow.add_edge("写大纲", "等待审核")
workflow.add_edge("等待审核", "写正文")
```

**流程会暂停在"等待审核"，直到你点"继续"。**

---

## 五、LangGraph vs 其他方案对比

| 方案 | 适用场景 | 复杂度 | 可控性 |
|------|---------|--------|--------|
| **直接调用LLM** | 简单问答 | 极低 | 低 |
| **LangChain** | 链式任务 | 低 | 中 |
| **LangGraph** | 复杂流程（循环、分支、人工介入） | 中 | 高 |
| **AutoGPT** | 全自动agent | 高 | 低（不可控）|

**LangGraph的sweet spot**：你需要控制AI的执行流程，但不想从零写harness。

---

## 六、LangGraph和Harness的关系

### Harness是什么？

**Harness = Agent的"操作系统"**

它负责：
1. 调用LLM
2. 解析LLM的回复（"它想调用哪个工具？"）
3. 执行工具
4. 把结果反馈给LLM
5. 循环上述过程，直到任务完成

**伪代码**：
```python
def harness(user_input):
    context = [user_input]
    
    while not done:
        # 1. 调用LLM
        response = llm.invoke(context)
        
        # 2. 解析
        if "调用工具" in response:
            tool_name = parse_tool(response)
            tool_result = execute_tool(tool_name)
            context.append(tool_result)  # 反馈给LLM
        else:
            return response  # 完成
```

### LangGraph包含了Harness功能

LangGraph的**PregelLoop**就是一个harness：
```
libs/langgraph/langgraph/pregel/_loop.py
↓
class PregelLoop:
    def tick():  # 这就是harness的主循环
        1. 读取当前state
        2. 决定下一步执行哪个node
        3. 执行node（可能调用LLM或工具）
        4. 更新state
        5. 判断是否继续
```

**所以你学LangGraph，就是在学一个production-grade的harness实现。**

---

## 七、LangGraph的核心价值（为什么它火）

1. **Graph = 可视化**
   - 你能看到AI的执行流程
   - 调试时知道卡在哪一步

2. **State = 可追溯**
   - 每一步的输入输出都记录了
   - 可以"时光倒流"到任意步骤

3. **Checkpoint = 可恢复**
   - Agent执行到一半断了？没关系，从checkpoint继续
   - 适合长时间运行的任务

4. **Production-ready**
   - 有错误处理、重试、超时
   - 大公司在用（不是玩具项目）

---

## 八、现在你应该理解的关键点

### ✅ LangGraph是什么
一个让你用"流程图"方式构建AI应用的框架

### ✅ 核心概念
- **Graph**：流程图
- **Node**：一个步骤
- **State**：数据在步骤间传递
- **Edge**：步骤之间的连接

### ✅ 它解决什么问题
让AI能执行**多步骤、有分支、可循环、可人工介入**的复杂任务

### ✅ 和Harness的关系
LangGraph内部的PregelLoop就是一个harness（执行引擎）

---

## 九、下一步

现在你理解了概念，接下来：

1. **跑通一个最简单的例子**（我给你写好了代码）
2. **trace一遍执行流程**（加print看数据怎么流动）
3. **读PregelLoop的代码**（看harness是怎么实现的）

**准备好了吗？我给你写一个超简单的Hello World例子，5分钟跑通！**
