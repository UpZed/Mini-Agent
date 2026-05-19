# Mini Agent Runtime

一个轻量级 AI Agent 框架，展示 Plan → Execute → Reflect 的完整 Agent 循环架构。

## 架构

```
用户输入 → [Planner] → [Executor] → [Reflector] → 结果输出
                ↑                        │
                └── 未完成则补充步骤 ──────┘
```

- **Planner** — LLM 将用户需求拆解为 2-6 个可执行步骤，自动分配工具
- **Executor** — 按步骤执行，支持工具调用（搜索/读写文件）和 LLM 推理
- **Reflector** — 执行完成后检查任务是否真正完成，未完成则自动补充缺失步骤

## 快速开始

```bash
# 安装依赖
pip install requests ddgs

# 方式一：直接传参
python main.py "搜索2025年最热门的3个AI编程工具"

# 方式二：修改 TASK 变量
# 打开 main.py，修改顶部 TASK 变量的值，然后运行
python main.py
```

### 切换模型

编辑 `core/llm.py` 中的 `PROVIDER` 常量：

```python
PROVIDER = "deepseek"      # 当前：DeepSeek
# PROVIDER = "openai"      # 切换为 OpenAI
# PROVIDER = "siliconflow" # 切换为 SiliconFlow
```

通过环境变量设置 API Key：
```bash
# DeepSeek
set LLM_API_KEY=sk-your-key
# OpenAI
set OPENAI_API_KEY=sk-your-key
```

## 项目结构

```
core/
├── agent.py        # 主 Agent 循环（编排器）
├── planner.py      # 任务规划器
├── executor.py     # 步骤执行器
├── reflector.py    # 完成度检查器
├── llm.py          # LLM 接口抽象（多 provider）
└── tool_system.py  # Tool 注册中心
tools/
├── web_tools.py    # DuckDuckGo 搜索
├── file_tools.py   # 读写文件
└── dev_logger.py   # 开发日志记录
```

## 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 架构模式 | Plan-then-Execute | 比 ReAct 更可控，每步可追踪 |
| LLM 框架 | 原生 requests | 避免 LangChain 黑盒，面试可解释每一行 |
| 工具接口 | BaseTool 抽象类 | 类型安全，扩展方便 |
| 完成检查 | Reflector 自检 | 执行后验证，最多 2 轮避免死循环 |
| 搜索源 | DuckDuckGo | 免费、零注册，英文技术内容够用 |

## 已知局限

- DuckDuckGo 中文搜索结果质量一般（国际技术话题不受影响）
- 搜索无结果时已做反编造处理，Agent 会诚实报告"未找到"

## 面试问答准备

详见桌面端开发日志：`Mini-Agent-Runtime_开发日志.md`，包含 8 个高频面试问答：

> 为什么不用 LangChain？怎么防止无限循环？Tool 调用失败怎么处理？跟 LangChain 的 AgentExecutor 有什么区别？...

---

## 附：开发日志自动记录机制

本项目开发过程中的关键事件（设计决策、Bug修复、测试结果、架构变更）由 Claude Code 自动记录到桌面的 `Mini-Agent-Runtime_开发日志.md`。

### 触发条件

以下情况自动记录：

1. **设计决策** — 多方案对比后选中一个（含原因和替代方案）
2. **Bug 发现与修复** — 问题定位、根因分析、修复方案
3. **测试结果** — 不论成功失败，总结关键发现
4. **功能变更** — 新模块、架构调整
5. **用户明确要求** — "记下来"

### 实现方式

| 层次 | 机制 | 作用 |
|------|------|------|
| 记忆规则 | Claude 项目记忆中的触发条件列表 | 每轮回复前自动检查 |
| 辅助脚本 | `tools/dev_logger.py` | 一行命令写入日志 |
| 定时兜底 | 30 分钟 cron 检查 | 防止遗漏 |

### 记录原则

- 只记对面试和决策有帮助的内容
- 不记流水账（装包、改代码细节等不记录）
- 风格可读，翻看时能回忆起思考过程
