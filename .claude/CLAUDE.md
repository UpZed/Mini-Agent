# CLAUDE.md — Mini-Agent-Runtime

本项目相关的指令和约定。

## 项目概述

Mini-Agent-Runtime 是一个轻量级 Plan → Execute → Reflect Agent 框架。**不含 LangChain 或任何 Agent 框架**，所有代码手写、面试可解释。总代码量约 1160 行 Python。

## 架构

```
用户输入 → [Planner] → [Executor] → [Reflector] → 结果输出
                ↑                          │
                └── 未完成 → 重新分派 ──────┘
```

- **Planner** (`core/planner.py`) — LLM 将任务拆解为 2-6 个步骤，为每步分配工具
- **Executor** (`core/executor.py`) — 顺序执行步骤：工具调用（搜索/文件）或 LLM 推理。反编造：搜索无结果时必须说"未找到"，不能编造
- **Reflector** (`core/reflector.py`) — 执行后检查任务完成度，返回 JSON。未完成时缺失步骤回 Planner 重新分配工具
- **Agent** (`core/agent.py`) — 主循环编排器。安全阀：`max_total_steps=15`，`max_reflection_rounds=2`
- **Memory** (`core/memory.py`) — 情节记忆，三级结构：最近（最近 3 条原始内容）+ 摘要（超过 8 条时 LLM 压缩）+ 关键词搜索。自动摘要压缩
- **LLM** (`core/llm.py`) — 多 Provider（deepseek/openai/siliconflow）。重试 + 超时 + JSON 容错解析

### 工具系统

`BaseTool` 抽象类在 `core/tool_system.py`。工具注册到 `ToolRegistry` 中，当前有：
- `web_search` (`tools/web_tools.py`) — DuckDuckGo 搜索（免费，无需 API key）
- `read_file` / `write_file` (`tools/file_tools.py`)
- 开发日志 (`tools/dev_logger.py`) — CLI 工具，用于记录设计决策到桌面开发日志

## 常用命令

```bash
# 安装依赖
pip install requests ddgs

# 直接传参运行
python main.py "搜索2025年AI突破并保存到report.md"

# 运行面试 Demo（交互式菜单）
python demo.py

# 开发日志记录
python -m tools.dev_logger "标题" "内容"
python -m tools.dev_logger --list
```

切换模型：修改 `core/llm.py` 中的 `PROVIDER` 常量。

## 重要约束

- **反编造**：Executor 提示词明确禁止编造搜索结果。搜不到就诚实说"未找到"
- **尚无 git 仓库** — 项目目前没有版本控制
- **API key**：`core/llm.py` 中硬编码了一个 DeepSeek key，公开前需移除。改用环境变量 `LLM_API_KEY`
- **依赖**：`requirements.txt` 需要同时列出 `requests` 和 `ddgs`

## 可用工具

### OpenCLI（浏览器自动化）
> 项目已安装 OpenCLI（`@jackwener/opencli`），通过已登录的 Edge 浏览器桥接访问任意网站。

所有浏览器操作直接用 Bash 调用 `opencli`：
```bash
opencli doctor                           # 检查浏览器桥接状态
opencli xiaohongshu feed -f json         # 小红书热门
opencli xiaohongshu search <query>       # 小红书搜索
opencli <site> <command> -f json         # 其他站点（微博/知乎/B站等）
opencli list                             # 查看所有支持的站点
```
- 用户 Edge 浏览器已登录各网站，无需额外认证
- 输出格式支持：json / yaml / md / table / csv
- 适用于：小红书、微博、知乎、B站、抖音、Twitter、Reddit 等 136+ 站点

## 自定义 Agent

### architect-reviewer（架构顾问 + 设计评审）

定义文件：`.claude/agents/architect-reviewer.md`

**两种工作模式：**

| 模式 | 时机 | 用途 |
|------|------|------|
| **设计提案评估** | 架构决策、功能新增、方案选型之前 | Claude 先提交方案给 reviewer 评估，通过后再实现 |
| **代码审查** | 实现完成后、Demo 前 | 从 5 个维度（架构/工程/稳定性/安全/技术栈）把关质量 |

**协作流程**：遇到架构设计或新功能问题时，Claude 会主动调起此 Agent 进行评估，输出结构化评估报告。用户也可以直接说"跑一下架构审查"或"帮我评估这个方案"来手动触发。
