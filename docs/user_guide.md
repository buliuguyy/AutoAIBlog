# AutoAIBlog 用户手册

> 每日 AI 资讯自动聚合系统 | 版本 0.1.0

---

## 一、系统功能

AutoAIBlog 每次运行，自动完成以下工作：

1. 从互联网搜集今日 AI 企业动态、学术前沿论文、HCI 研究、AI 工具推荐
2. 由 AI 编辑汇总排版为结构化 Markdown 日报（含图片）
3. 将日报保存到本地 `output/` 文件夹
4. （可选）自动上传到你的 Notion 页面

预计每次运行耗时 **5～15 分钟**。

---

## 二、前置要求

### 2.1 必须配置的 API Keys

打开项目根目录的 `.env` 文件，确认以下两项已填写：

```
ANTHROPIC_API_KEY=sk-...   # Claude 模型调用
TAVILY_API_KEY=tvly-...    # 网页搜索
```

### 2.2 可选：Notion 自动发布

如需将日报自动上传到 Notion，还需配置：

```
NOTION_INTEGRATION_SECRET=ntn_...       # Integration Token
NOTION_PAGE_ID=22c0ef51b13749f5...      # 目标父页面 ID
```

> **注意**：必须在 Notion 页面设置中手动添加该 Integration，否则上传会报 404 错误。
> 操作：打开目标 Notion 页面 → 右上角「...」→「连接」→ 选择你的 Integration

如不需要 Notion，不填写这两项即可，程序只生成本地 Markdown 文件。

---

## 三、启动每日资讯收集

在项目根目录下，执行以下命令：

```bash
uv run python main.py
```

### 运行过程说明

程序运行时会显示以下步骤：

```
============================================================
  AutoAIBlog — 每日 AI 资讯聚合系统
  日期：2026-04-13 09:00
============================================================

[1/4] 正在构建 Agent 团队...
[2/4] 开始执行资讯搜集任务（预计需要 5-15 分钟）...
  - AI 企业资讯搜集中...
  - AIGC 学术前沿论文搜集中...
  - HCI 前沿工作搜集中...
  - AI 工具推荐搜集中...

[3/4] 正在保存日报...

============================================================
  日报已生成：output/2026-04-13.md
============================================================

[4/4] 正在上传到 Notion...      ← 仅配置了 Notion 时显示
  Notion 页面：https://www.notion.so/xxxxx
```

---

## 四、查看输出

### 4.1 本地 Markdown 文件

日报保存在：

```
output/
└── 2026-04-13.md    ← 以运行日期命名
```

用任意 Markdown 编辑器（Typora、VS Code、Obsidian 等）打开即可。

### 4.2 Notion 页面

若配置了 Notion，程序结束时会打印页面链接，直接点击访问。  
所有日报会作为子页面创建在你设置的父页面下。

---

## 五、日报内容结构

每日生成的日报包含四个板块：

| 板块 | 内容 | 数量 |
|------|------|------|
| ① AI 企业资讯 | OpenAI、Google、Anthropic 等企业动态 | 5-8 条 |
| ② AIGC 学术前沿 | 图像生成、视频生成、LLM 等 arXiv 最新论文 | 8-15 篇 |
| ③ 人机交互前沿 | HCI + AI 交叉领域的最新工作（CHI、UIST 等） | 4-8 条 |
| ④ AI 工具推荐 | 近期值得关注的优质 AI 工具 | 4-6 个 |

---

## 六、验证单项功能（可选）

如需单独测试某个环节是否正常，使用验证脚本（**不消耗 LLM 额度**）：

```bash
# 验证全部三个阶段
uv run python validate.py

# 仅验证 Tavily 搜索 + 图片获取
uv run python validate.py --stage 1

# 仅验证 Markdown 本地保存
uv run python validate.py --stage 2

# 仅验证 Notion 上传
uv run python validate.py --stage 3
```

> **说明**：验证脚本使用硬编码的示例内容测试 Notion 上传，生成的 Notion 页面内容为示例数据，不是真实新闻。真实日报请运行 `main.py`。

---

## 七、定时自动运行（macOS）

如需每天自动运行，可通过 macOS 的 `launchd` 设置定时任务。

### 方法 A：使用 cron（简单）

打开终端，运行 `crontab -e`，添加以下内容（每天早上 8 点运行）：

```cron
0 8 * * * cd /Volumes/Workplaces&Data/Claude\ Code\ Workplace/AutoAIBlog && /path/to/uv run python main.py >> output/cron.log 2>&1
```

查找 uv 路径：

```bash
which uv
```

### 方法 B：手动运行（推荐）

每天需要时在终端执行一次：

```bash
cd /Volumes/Workplaces\&Data/Claude\ Code\ Workplace/AutoAIBlog
uv run python main.py
```

---

## 八、常见问题

### Q: 运行提示「缺少 ANTHROPIC_API_KEY」

检查 `.env` 文件是否在项目根目录，且格式正确（无多余空格）。

### Q: Notion 上传失败，提示 404

原因：Integration 未添加到目标 Notion 页面。  
解决：在 Notion 页面右上角 → 「连接」→ 添加你的 Integration。

### Q: 搜索结果无图片

部分查询 Tavily 不返回图片，属正常现象。日报中该条目会省略图片行，不影响文本内容。

### Q: 运行超过 20 分钟无响应

可能是网络问题或 API 超时。按 `Ctrl+C` 中断后重新运行即可。

### Q: 提示「No module named 'tavily'」

说明 Python 环境未正确切换到项目虚拟环境。确保使用 `uv run python main.py` 而非 `python main.py`。
