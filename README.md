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


