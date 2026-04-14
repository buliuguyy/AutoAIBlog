"""
AutoAIBlog 执行器

架构说明：
  直接调用搜索工具（无 LLM 多轮循环），将所有原始数据汇总后，
  通过 OpenAI SDK（兼容 nuwaflux 代理）单次调用 Claude 生成完整日报。
  此方案绕过了 CrewAI ReAct 框架的 assistant-prefill 问题。

改进（v2）：
  - 对学术论文增加精读步骤：提取 top 5 论文，通过 Tavily 补充搜索获取
    更丰富的方法介绍、实验结果等网络资料，供 writer 撰写深度分析
  - Writer 输出采用 Notion 扩展 Markdown 方言，支持 callout / toggle /
    代码块 / 公式等富文本块，详见 docs/notion_formatting_guide.md
"""
import os
import re
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────
# 返回值包装（兼容 main.py 的 result.raw 接口）
# ─────────────────────────────────────────────

class _Result:
    def __init__(self, text: str):
        self.raw = text


# ─────────────────────────────────────────────
# 主执行器
# ─────────────────────────────────────────────

class AutoAIBlogRunner:
    """
    替代 CrewAI Crew 的轻量执行器。
    kickoff() 对外接口保持不变，内部改为：
      1. 用 Python 直接调用搜索工具（Tavily + arXiv）
      2. 对 top 论文补充精读（Tavily 补充搜索）
      3. 汇总原始数据，单次调用 Claude 生成 Notion 富文本 Markdown 日报
    """

    def kickoff(self) -> _Result:
        from tools.search_tool import TavilySearchTool
        from tools.arxiv_tool import ArxivSearchTool

        tavily = TavilySearchTool()
        arxiv_tool = ArxivSearchTool()
        month_str = datetime.now().strftime("%B %Y")
        today = datetime.now().strftime("%Y-%m-%d")

        # ── 1. AI 企业资讯 ──────────────────────────────────
        print("  → 搜集 AI 企业资讯...")
        news_parts = []
        for q in [
            f"OpenAI news release announcement {month_str}",
            f"Google DeepMind AI news latest {month_str}",
            f"Anthropic Meta AI xAI Mistral news announcement {month_str}",
            f"AI startup funding product launch {month_str}",
        ]:
            news_parts.append(tavily._run(q))
        news_raw = "\n\n---\n\n".join(news_parts)

        # ── 2. AIGC 学术前沿 ────────────────────────────────
        print("  → 搜集 AIGC 学术论文...")
        academic_parts = []
        for q, d in [
            ("cat:cs.CV AND image generation diffusion transformer", 3),
            ("cat:cs.CV AND video generation editing temporal consistency", 3),
            ("cat:cs.CL AND large language model reasoning alignment", 3),
            ("cat:cs.CV AND 3D generation NeRF gaussian splatting", 3),
            ("cat:cs.CV AND image editing inpainting style transfer", 3),
        ]:
            academic_parts.append(arxiv_tool._run(q, days_back=d))
        academic_raw = "\n\n---\n\n".join(academic_parts)

        # ── 2.5 学术论文精读（补充深度内容）────────────────
        print("  → 精读重要学术论文...")
        paper_details_raw = self._read_top_papers(tavily, academic_raw)

        # ── 3. HCI 前沿 ─────────────────────────────────────
        print("  → 搜集 HCI 前沿工作...")
        hci_parts = [
            arxiv_tool._run("cat:cs.HC AND human computer interaction AI system interface", days_back=7),
            arxiv_tool._run("cat:cs.HC AND conversational agent AI assistant user study", days_back=7),
            tavily._run("CHI 2025 UIST AI interaction system interface paper"),
        ]
        hci_raw = "\n\n---\n\n".join(hci_parts)

        # ── 4. AI 工具推荐 ──────────────────────────────────
        print("  → 搜集 AI 工具推荐...")
        tools_parts = []
        for q in [
            f"new AI tools launched this week {month_str}",
            f"best AI productivity tools {month_str}",
            "open source AI model tool GitHub trending release",
        ]:
            tools_parts.append(tavily._run(q))
        tools_raw = "\n\n---\n\n".join(tools_parts)

        # ── 5. 单次 LLM 调用生成日报 ────────────────────────
        print("  → 调用 Claude 生成日报...")
        report = self._write_report(
            today, news_raw, academic_raw, paper_details_raw, hci_raw, tools_raw
        )
        return _Result(report)

    # ─────────────────────────────────────────────────────────
    # 论文精读：提取 top 论文并通过 Tavily 补充方法/结果信息
    # ─────────────────────────────────────────────────────────

    def _read_top_papers(self, tavily, academic_raw: str) -> str:
        """
        从 arXiv 搜索结果中提取 top 5 论文标题，
        对每篇用 Tavily 补充搜索：获取方法介绍、图示说明、实验结论等网络资料。
        返回拼接后的精读原始文本，供 writer 生成深度分析。
        """
        # 从 academic_raw 提取论文标题（arXiv 工具以 **Title** 开头）
        title_matches = re.findall(r"\*\*(.+?)\*\*", academic_raw)
        seen: set[str] = set()
        top_titles: list[str] = []
        for t in title_matches:
            # 过滤掉"作者"等字段标签（通常很短或含冒号）
            if len(t) > 20 and "：" not in t and ":" not in t:
                if t not in seen:
                    seen.add(t)
                    top_titles.append(t)
            if len(top_titles) >= 5:
                break

        if not top_titles:
            return "（未提取到可精读的论文）"

        detail_parts = []
        for title in top_titles:
            # 搜索该论文的详细介绍（博文、项目页、Papers with Code 等）
            query = f'"{title[:70]}" paper method architecture experiment result'
            result = tavily._run(query)
            detail_parts.append(
                f"=== 论文精读：{title} ===\n{result}"
            )

        return "\n\n".join(detail_parts)

    # ─────────────────────────────────────────────────────────
    # Writer：单次 LLM 调用，输出 Notion 富文本 Markdown
    # ─────────────────────────────────────────────────────────

    def _write_report(
        self,
        today: str,
        news_raw: str,
        academic_raw: str,
        paper_details_raw: str,
        hci_raw: str,
        tools_raw: str,
    ) -> str:
        from openai import OpenAI

        # 读取 Notion 格式指南（供 prompt 参考）
        guide_path = Path(__file__).parent / "docs" / "notion_formatting_guide.md"
        notion_guide = guide_path.read_text(encoding="utf-8") if guide_path.exists() else ""

        prompt = f"""你是 AI 日报撰写编辑。请将以下原始搜索数据整理为一份结构清晰的 Notion 富文本 Markdown 日报。

**日期**：{today}

---

## Notion 格式规范（必须严格遵守）

{notion_guide}

---

================
【① AI 企业资讯 原始数据】
{news_raw}

================
【② AIGC 学术前沿 原始数据（arXiv 摘要）】
{academic_raw}

================
【② 学术论文精读补充（方法/结果/图示/博客等网络资料）】
{paper_details_raw}

================
【③ 人机交互前沿 原始数据】
{hci_raw}

================
【④ AI 工具推荐 原始数据】
{tools_raw}

================

请严格按照以下结构输出（不要用 ``` 包裹整体输出内容）：

# AI 日报 — {today}

> 每日精选 AI 企业动态、学术前沿、HCI 研究与工具推荐

---

## ① AI 企业资讯

（5-8 条，每条使用以下格式）

### [新闻标题](来源链接)
![](图片URL)
> [!INFO] 核心要点：一句话概括最重要的信息（≤40字）

新闻摘要（2-3句中文，说明事件详情与行业意义）

---

## ② AIGC 学术前沿

（按子方向分组：图像生成 / 视频生成与编辑 / 3D生成 / 大语言模型 / 图像编辑等）
（每方向 2-4 篇，总计 8-15 篇，优先选取有精读补充数据的论文）

### [子方向名称]

#### [论文标题](arXiv链接)

> [!KEY] 核心贡献：一句话概括本文最大创新点（突出与现有工作的差异）

**作者**：xxx et al. | **发布**：YYYY-MM-DD

**研究动机**：当前方法存在什么问题，本文为何要解决这个问题（1-2句）

<toggle>🔧 方法详解
**核心框架**：方法/模型名称

- **组件/步骤 1**：描述
- **组件/步骤 2**：描述
- **关键创新**：技术亮点说明
</toggle>

<toggle>📊 实验与结果
- **评估基准**：XXX benchmark / XXX dataset
- **关键指标**：XXX，相比 [对比方法] 提升 XX%
- **重要发现**：核心结论（1-2条）
</toggle>

**论文预览**：[HuggingFace Papers](HF URL)

（重复以上格式，仅当原始数据有「论文预览（含主图）」时才加「论文预览」行）

---

## ③ 人机交互前沿

（4-8 条，每条使用以下格式）

### [工作标题](链接)
> [!GOAL] 研究问题：本工作聚焦解决的核心问题（≤40字）

**来源**：CHI 2025 / UIST 2025 / arXiv 等
**内容**：简洁中文介绍，包括方法特色与实际应用价值（2-3句）

---

## ④ AI 工具推荐

（4-6 个工具，每条使用以下格式）

### [工具名称](官网/GitHub链接)
> [!TIP] 核心功能：一句话描述工具核心价值（≤40字）

**功能**：详细介绍工具能做什么
**适用**：目标用户与使用场景
**费用**：免费 / 付费（价格）/ 开源（协议）

---

*由 AutoAIBlog 自动生成 | {today}*

附加规则（严格遵守）：
1. 所有解读/摘要/分析必须使用中文；技术术语可保留英文
2. 只使用原始数据中出现的真实链接，不虚构任何 URL
3. 图片：原始数据含「图片URL」字段才嵌入 ![]()，无则不加占位符
4. 论文预览：原始数据含「论文预览（含主图）」才附上链接，无则省略
5. Toggle 内容必须有实质信息，充分利用精读补充数据填写方法和结果细节
6. Callout 文字控制在 50 字以内，突出最关键信息
7. 输出纯 Markdown，不含多余解释说明
"""

        base_url = os.getenv("ANTHROPIC_API_BASE_URL", "https://api.openai.com/v1")
        client = OpenAI(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            base_url=base_url,
        )

        resp = client.chat.completions.create(
            model=os.getenv("MODEL", "claude-sonnet-4-6"),
            max_tokens=8192,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )

        return resp.choices[0].message.content


# ─────────────────────────────────────────────
# 公开接口（兼容 main.py）
# ─────────────────────────────────────────────

def build_crew() -> AutoAIBlogRunner:
    """返回执行器实例，兼容 main.py 的 build_crew().kickoff() 调用方式。"""
    return AutoAIBlogRunner()
