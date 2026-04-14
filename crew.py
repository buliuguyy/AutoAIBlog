"""
AutoAIBlog 执行器

架构说明：
  直接调用搜索工具（无 LLM 多轮循环），将所有原始数据汇总后，
  通过 OpenAI SDK（兼容 nuwaflux 代理）单次调用 Claude 生成完整日报。
  此方案绕过了 CrewAI ReAct 框架的 assistant-prefill 问题。
"""
import os
from datetime import datetime


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
      2. 汇总原始数据，单次调用 Claude 生成 Markdown 日报
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
        report = self._write_report(today, news_raw, academic_raw, hci_raw, tools_raw)
        return _Result(report)

    def _write_report(
        self,
        today: str,
        news_raw: str,
        academic_raw: str,
        hci_raw: str,
        tools_raw: str,
    ) -> str:
        from openai import OpenAI

        prompt = f"""你是 AI 日报撰写编辑，请将以下原始搜索数据整理为一份结构清晰的 Markdown 日报。

**日期**：{today}

================
【① AI 企业资讯 原始数据】
{news_raw}

================
【② AIGC 学术前沿 原始数据】
{academic_raw}

================
【③ 人机交互前沿 原始数据】
{hci_raw}

================
【④ AI 工具推荐 原始数据】
{tools_raw}

================
请严格按照以下 Markdown 格式输出（不要用 ``` 包裹输出内容）：

# AI 日报 — {today}

> 每日精选 AI 企业动态、学术前沿、HCI 研究与工具推荐

---

## ① AI 企业资讯

### [新闻标题](来源链接)
![](图片URL)
核心内容摘要（2-3 句中文）

（重复以上格式，5-8 条，仅在原始数据有「图片URL」字段时才加 ![]() 行）

---

## ② AIGC 学术前沿

（按子方向分组：图像生成 / 视频生成与编辑 / 3D 生成 / LLM 等）

### 图像生成

#### [论文标题](arXiv链接)
**作者**：xxx et al.
**核心贡献**：中文解读（2-3 句）
**论文预览**：[HuggingFace Papers](预览URL)

（仅在原始数据有「论文预览（含主图）」字段时才加「论文预览」行）

---

## ③ 人机交互前沿

### [工作标题](链接)
**来源**：CHI 2025 / UIST / arXiv 等
**内容**：中文介绍（2-3 句）

---

## ④ AI 工具推荐

### [工具名称](链接)
![](图片URL)
**功能**：简介
**适用**：场景
**费用**：免费 / 付费 / 开源

（仅在有「图片URL」时才加 ![]() 行，4-6 个工具）

---

*由 AutoAIBlog 自动生成 | {today}*

附加规则：
- 所有解读/摘要必须是中文
- 只使用原始数据中出现的真实链接，不要虚构 URL
- 图片：原始数据含「图片URL」字段才嵌入，无则不加占位符
- 论文预览：原始数据含「论文预览（含主图）」才加，无则省略
- 整体风格专业简洁，适合 AI 从业者快速浏览
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
