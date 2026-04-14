# AutoAIBlog 技术手册

> 版本：0.1.0 | 更新：2026-04-13

---

## 一、系统总览

AutoAIBlog 是一套基于 **CrewAI 多 Agent 协作框架**的 AI 资讯自动聚合系统。系统由五个专业 Agent 协作完成三项核心工作：

1. **信息搜集**：通过 Tavily Web 搜索和 arXiv 学术搜索获取原始内容（含图片 URL）
2. **聚合排版**：由 Writer Agent 调用 LLM 将原始数据整理为结构化 Markdown 日报
3. **发布存档**：将日报保存为本地 `.md` 文件，并可选上传至 Notion

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py (入口)                          │
│                                                                 │
│  check_env() → build_crew() → crew.kickoff() → save_report()   │
│                                          └──→ upload_to_notion()│
└─────────────────────────────────────────────────────────────────┘
                            │
                      crew.kickoff()
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
   [Task 1] 企业资讯  [Task 2] 学术前沿   [Task 3] HCI 前沿
   news_agent         academic_agent       hci_agent
   TavilySearchTool   ArxivSearchTool      ArxivSearchTool
                                           TavilySearchTool
          │                 │                 │
          └─────────┬───────┘                 │
                    │         ┌───────────────┘
                    │         ▼
                    │  [Task 4] AI 工具推荐
                    │  tools_agent
                    │  TavilySearchTool
                    │         │
                    └────┬────┘
                         ▼
                  [Task 5] 日报撰写
                  writer_agent (无工具)
                  context = [Task1, Task2, Task3, Task4]
                         │
                         ▼
                   Markdown 日报文本
```

---

## 二、目录结构

```
AutoAIBlog/
├── main.py               # 程序入口，环境检查 + 流水线启动
├── crew.py               # CrewAI Crew 组装（Agent + Task + Process）
├── validate.py           # 分阶段验证脚本（不消耗 LLM 调用）
├── pyproject.toml        # uv 项目配置（确保 uv run 使用 .venv）
├── requirements.txt      # Python 依赖列表
├── .env                  # API 密钥配置（不提交到 git）
│
├── agents/               # Agent 定义
│   ├── news_agent.py     # AI 企业资讯专员
│   ├── academic_agent.py # AIGC 学术前沿研究员
│   ├── hci_agent.py      # 人机交互前沿研究员
│   ├── tools_agent.py    # AI 工具推荐专员
│   └── writer_agent.py   # 日报撰写编辑
│
├── tasks/
│   └── daily_tasks.py    # 5 个 Task 的描述与期望输出定义
│
├── tools/
│   ├── search_tool.py    # TavilySearchTool（Web 搜索 + 图片）
│   ├── arxiv_tool.py     # ArxivSearchTool（学术论文搜索）
│   └── notion_uploader.py# Markdown → Notion blocks + API 上传
│
└── output/               # 生成的日报存放目录
    └── YYYY-MM-DD.md
```

---

## 三、阶段一：信息搜集

### 3.1 调用路径

```
crew.kickoff()
  ├── Task 1: create_news_task(news_agent)
  │     news_agent.tools = [TavilySearchTool()]
  │     Agent 调用 TavilySearchTool._run(query="OpenAI news today ...")
  │       └── TavilyClient.search(query, include_images=True)
  │             ├── response["results"]  → 标题、摘要、URL、发布日期
  │             │   item["image"]        → 单条结果的图片 URL（优先）
  │             └── response["images"]   → 全局图片池（按索引补充）
  │           返回格式化字符串，含「图片URL: xxx」字段
  │
  ├── Task 2: create_academic_task(academic_agent)
  │     academic_agent.tools = [ArxivSearchTool()]
  │     Agent 调用 ArxivSearchTool._run(query="image generation ...", category="cs.CV")
  │       └── arxiv.Client().results(arxiv.Search(..., sort_by=SubmittedDate))
  │             ├── 日期过滤：只保留最近 days_back 天的论文
  │             ├── paper.title / paper.authors / paper.summary
  │             └── 从 entry_id 提取 arXiv ID → 生成 HuggingFace Papers 预览链接
  │           返回格式化字符串，含「论文预览（含主图）: https://huggingface.co/papers/xxx」
  │
  ├── Task 3: create_hci_task(hci_agent)
  │     hci_agent.tools = [ArxivSearchTool(), TavilySearchTool()]
  │     同时使用两种工具：arXiv 找学术论文，Tavily 找会议/博客报道
  │
  └── Task 4: create_tools_task(tools_agent)
        tools_agent.tools = [TavilySearchTool()]
        搜索新发布 AI 工具，含官网图片 URL
```

### 3.2 图片获取机制

| 来源类型 | 图片获取方式 | 字段名 |
|----------|-------------|--------|
| 企业资讯 / HCI / 工具 | Tavily `item["image"]` 或 `response["images"][i]` | `图片URL` |
| 学术论文 | HuggingFace Papers 预览页（含论文主图） | `论文预览（含主图）` |

Tavily 不保证每条结果都有图片（取决于原网页），图片数量因查询而异。

### 3.3 关键参数

| 参数 | 文件 | 默认值 | 说明 |
|------|------|--------|------|
| `max_results` | `TavilySearchInput` | 8 | 每次搜索返回结果数 |
| `search_depth` | `TavilySearchInput` | `"advanced"` | 搜索精度，advanced 更慢但准确 |
| `days_back` | `ArxivSearchInput` | 3 | 过滤多少天内的论文 |
| `max_iter` | 各 Agent | 4-6 | Agent 最多调用工具的轮次 |

---

## 四、阶段二：聚合为 Markdown

### 4.1 调用路径

```
Task 5: create_writing_task(writer_agent, context=[Task1,Task2,Task3,Task4])
  writer_agent.tools = []     ← 不调用外部工具，纯 LLM 写作
  writer_agent.llm = claude-sonnet-4-6（通过 ANTHROPIC_API_KEY 调用）
  
  CrewAI 将 Task1~Task4 的输出文本作为上下文注入 writer_agent 的 Prompt
  
  writer_agent 执行：
    1. 读取四段原始数据（含图片URL、预览链接等字段）
    2. 按 daily_tasks.py 中的 Markdown 模板格式化
    3. 图片规则：若原始数据有「图片URL」字段 → 插入 ![](url)
    4. 论文预览规则：若有「论文预览」字段 → 插入 **论文预览**：[HF Papers](url)
    5. 输出纯 Markdown 文本（无代码块包裹）
  
  crew.kickoff() 返回 result 对象
  report_content = result.raw  ← 最终 Markdown 字符串
```

### 4.2 Markdown 输出结构

```markdown
# AI 日报 — YYYY-MM-DD

> 每日精选 AI 企业动态、学术前沿、HCI 研究与工具推荐

---

## ① AI 企业资讯

### [新闻标题](URL)
![](图片URL)          ← 仅当 Tavily 返回图片时存在
核心内容摘要（2-3句中文）

---

## ② AIGC 学术前沿

### 图像生成
#### [论文标题](arXiv URL)
**作者**：xxx et al.
**核心贡献**：中文解读
**论文预览**：[HuggingFace Papers](HF URL)

---

## ③ 人机交互前沿
...

## ④ AI 工具推荐
...

---
*由 AutoAIBlog 自动生成 | YYYY-MM-DD*
```

---

## 五、阶段三：上传 Notion

### 5.1 调用路径

```
main.py: upload_to_notion(report_content, title)
  │
  └── tools/notion_uploader.py: upload_to_notion(markdown, title)
        │
        ├── _create_page(title, parent_page_id)
        │     POST https://api.notion.com/v1/pages
        │     body: { parent: { page_id }, properties: { title } }
        │     返回新页面 ID
        │
        ├── markdown_to_notion_blocks(markdown)
        │     逐行解析 Markdown → Notion block 列表
        │     "# heading"   → heading_1 block
        │     "## heading"  → heading_2 block
        │     "### heading" / "#### heading" → heading_3 block
        │     "> quote"     → quote block
        │     "- item"      → bulleted_list_item block
        │     "---"         → divider block
        │     "![](url)"    → image block（仅 http/https URL）
        │     其他          → paragraph block
        │     行内解析：**bold** *italic* [text](url) → rich_text 数组
        │
        └── _append_blocks(page_id, blocks)
              PATCH https://api.notion.com/v1/blocks/{page_id}/children
              分批上传，每批 ≤ 100 个 block
              批次间隔 0.3 秒（避免 Notion API 速率限制）
              
  返回：https://www.notion.so/{page_id}
```

### 5.2 Notion API 权限要求

| 配置项 | 说明 |
|--------|------|
| `NOTION_INTEGRATION_SECRET` | Integration Token（`ntn_xxx` 格式） |
| `NOTION_PAGE_ID` | 父页面 ID（32位十六进制，去除连字符） |
| Integration 权限 | 必须在 Notion 页面设置中手动添加该 Integration |

---

## 六、LLM 调用配置

系统通过以下环境变量配置 LLM：

| 变量 | 值 | 说明 |
|------|----|------|
| `ANTHROPIC_API_KEY` | `sk-xxx` | API 密钥 |
| `ANTHROPIC_API_BASE_URL` | `https://api.nuwaflux.com/v1` | 代理端点（非官方） |
| `MODEL` | `claude-sonnet-4-6` | CrewAI 读取此变量选择模型 |

`crew.py` 中 LLM 初始化：

```python
from langchain_anthropic import ChatAnthropic
llm = ChatAnthropic(model="claude-sonnet-4-6", ...)
```

五个 Agent 共享同一个 LLM 实例。

---

## 七、validate.py 的设计意图

`validate.py` 是**组件验证工具，不产生真实日报内容**。

| 阶段 | 验证内容 | 数据来源 | 是否调用 LLM |
|------|----------|----------|-------------|
| Stage 1 | Tavily API 连通性 + 图片返回 | 真实 Tavily 搜索 | 否 |
| Stage 2 | Markdown 格式结构 + 本地保存 | `SAMPLE_MARKDOWN`（硬编码） | 否 |
| Stage 3 | Notion API 连通性 + block 转换 | `SAMPLE_MARKDOWN`（硬编码） | 否 |

**因此 Notion 验证页面中的内容是示例数据（OpenAI o3、Gemini 2.5 等），并非当日真实新闻。** 真实内容须运行 `main.py` 完整流水线。

---

## 八、数据流总结

```
环境变量(.env)
    │
    ▼
main.py::check_env()
    │
    ▼
crew.py::build_crew()
    │ 创建 5 Agent + 5 Task + Crew(process=sequential)
    ▼
crew.kickoff()
    │
    ├─▶ Task1(news_agent)
    │       └─▶ TavilySearchTool × 4次搜索
    │               └─▶ Tavily API (HTTP)  →  新闻文本 + 图片URL
    │
    ├─▶ Task2(academic_agent)
    │       └─▶ ArxivSearchTool × 5次搜索
    │               └─▶ arXiv API (HTTP)  →  论文元数据 + HF预览链接
    │
    ├─▶ Task3(hci_agent)
    │       └─▶ ArxivSearchTool + TavilySearchTool
    │
    ├─▶ Task4(tools_agent)
    │       └─▶ TavilySearchTool × 4次搜索
    │
    └─▶ Task5(writer_agent)  ← 读取 Task1~4 全部输出
            └─▶ Anthropic API (HTTP)  →  Markdown 日报
                    │
                    ├─▶ output/YYYY-MM-DD.md  (本地保存)
                    └─▶ Notion API (HTTP)     (可选上传)
```
