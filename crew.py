"""
AutoAIBlog 执行器 v3

架构说明：
  直接调用搜索工具（无 LLM 多轮循环），将数据分四节分别调用 LLM 撰写，
  最后拼装为完整日报。按节拆分彻底解决了单次 LLM 输出截断问题。

主要改进（v3）：
  - 【截断修复】4 节独立 LLM 调用，每节各自最多 4096 token 输出
  - 【论文数量】AIGC 精选 2-3 篇，HCI 精选 2-3 篇（优先顶级会议）
  - 【图示嵌入】精读补充搜索专门针对 HuggingFace Papers / 项目页获取架构图
  - 【深度分析】动机写成完整段落，技术细节分点展开
  - 【论文列表】每次运行追加到 output/papers_list.md，维护结构化元数据
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
# 搜索查询配置（含类别标签，供论文列表使用）
# (query, days_back, category_label, tags_cn)
# ─────────────────────────────────────────────

ACADEMIC_QUERIES: list[tuple[str, int, str, str]] = [
    ("cat:cs.CV AND image generation diffusion transformer", 3,
     "AIGC-图像生成", "图像生成, 扩散模型, Transformer"),
    ("cat:cs.CV AND video generation editing temporal consistency", 3,
     "AIGC-视频生成", "视频生成, 视频编辑, 时序一致性"),
    ("cat:cs.CL AND large language model reasoning alignment", 3,
     "AIGC-LLM", "大语言模型, 推理, 对齐"),
    ("cat:cs.CV AND 3D generation NeRF gaussian splatting", 3,
     "AIGC-3D生成", "3D生成, NeRF, Gaussian Splatting"),
    ("cat:cs.CV AND image editing inpainting style transfer", 3,
     "AIGC-图像编辑", "图像编辑, 图像修复, 风格迁换"),
]

HCI_QUERIES: list[tuple[str, int, str, str]] = [
    ("cat:cs.HC AND human computer interaction AI system interface", 7,
     "HCI-交互系统", "人机交互, AI系统, 智能界面"),
    ("cat:cs.HC AND conversational agent AI assistant user study", 7,
     "HCI-对话系统", "对话代理, 用户研究, AI助手"),
]


# ─────────────────────────────────────────────
# 主执行器
# ─────────────────────────────────────────────

class AutoAIBlogRunner:

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
        # academic_results: list of (raw_text, category_label, tags_cn)
        academic_results: list[tuple[str, str, str]] = []
        for q, d, cat, tags in ACADEMIC_QUERIES:
            result = arxiv_tool._run(q, days_back=d)
            academic_results.append((result, cat, tags))
        academic_raw = "\n\n---\n\n".join(r for r, _, _ in academic_results)

        # ── 2.5 论文精读（针对 top 3 论文补充架构图与详细介绍）──
        print("  → 精读重要学术论文...")
        paper_details_raw = self._read_top_papers(tavily, academic_raw)

        # ── 3. HCI 前沿 ─────────────────────────────────────
        print("  → 搜集 HCI 前沿工作...")
        hci_results: list[tuple[str, str, str]] = []
        for q, d, cat, tags in HCI_QUERIES:
            result = arxiv_tool._run(q, days_back=d)
            hci_results.append((result, cat, tags))
        # 额外搜索 HCI 顶会最新动态
        hci_conf_raw = tavily._run(
            "CHI 2025 UIST 2025 IEEE VR ISMAR Ubicomp DIS accepted paper AI interaction system"
        )
        hci_raw = "\n\n---\n\n".join(
            [r for r, _, _ in hci_results] + [hci_conf_raw]
        )

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

        # ── 5. 按节分次撰写（彻底解决截断问题）────────────
        print("  → [1/4] 撰写 AI 企业资讯节...")
        news_md = self._write_section_news(today, news_raw)

        print("  → [2/4] 撰写 AIGC 学术前沿节...")
        academic_md = self._write_section_academic(today, academic_raw, paper_details_raw)

        print("  → [3/4] 撰写 HCI 前沿节...")
        hci_md = self._write_section_hci(today, hci_raw)

        print("  → [4/4] 撰写 AI 工具推荐节...")
        tools_md = self._write_section_tools(today, tools_raw)

        # ── 6. 拼装完整报告 ─────────────────────────────────
        report = self._assemble_report(today, news_md, academic_md, hci_md, tools_md)

        # ── 7. 更新论文元数据列表 ───────────────────────────
        print("  → 更新论文列表...")
        self._update_paper_list(today, academic_results, hci_results)

        return _Result(report)

    # ─────────────────────────────────────────────────────────
    # 论文精读：top 3 论文，专门搜索架构图和项目主页
    # ─────────────────────────────────────────────────────────

    def _read_top_papers(self, tavily, academic_raw: str) -> str:
        """
        提取学术搜索结果中 top 3 篇论文，通过 Tavily 定向搜索：
          - HuggingFace Papers 页（含论文主图/架构图）
          - 论文项目主页（含架构图/演示图）
          - 实验结果/对比图（含结果可视化）
        每篇论文搜索两次，返回更丰富的补充原始文本（含多个图片URL）。
        """
        title_matches = re.findall(r"^\*\*(.+?)\*\*", academic_raw, re.MULTILINE)
        seen: set[str] = set()
        top_titles: list[str] = []
        for t in title_matches:
            if len(t) > 20 and "：" not in t and ":" not in t:
                if t not in seen:
                    seen.add(t)
                    top_titles.append(t)
            if len(top_titles) >= 3:
                break

        if not top_titles:
            return "（未提取到可精读的论文）"

        detail_parts = []
        for title in top_titles:
            # 搜索 1：HuggingFace + 架构图 / 概述图
            q1 = f'"{title[:65]}" huggingface paper architecture diagram overview figure'
            r1 = tavily._run(q1)
            # 搜索 2：实验结果图 / 对比图 / 项目主页
            q2 = f'"{title[:65]}" arxiv result comparison figure experiment visualization'
            r2 = tavily._run(q2)
            detail_parts.append(
                f"=== 论文精读：{title} ===\n"
                f"--- 架构与概述搜索（图片1/2来源）---\n{r1}\n\n"
                f"--- 实验与结果搜索（图片3/4来源）---\n{r2}"
            )

        return "\n\n".join(detail_parts)

    # ─────────────────────────────────────────────────────────
    # LLM 调用封装
    # ─────────────────────────────────────────────────────────

    def _llm_call(self, prompt: str, max_tokens: int = 4096) -> str:
        from openai import OpenAI
        base_url = os.getenv("ANTHROPIC_API_BASE_URL", "https://api.openai.com/v1")
        client = OpenAI(api_key=os.getenv("ANTHROPIC_API_KEY"), base_url=base_url)
        resp = client.chat.completions.create(
            model=os.getenv("MODEL", "claude-sonnet-4-6"),
            max_tokens=max_tokens,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

    # ─────────────────────────────────────────────────────────
    # 节撰写：① AI 企业资讯
    # ─────────────────────────────────────────────────────────

    def _write_section_news(self, today: str, news_raw: str) -> str:
        prompt = f"""你是 AI 日报编辑。从以下 AI 企业资讯数据中选取 5-8 条最重要的新闻，\
按照指定格式整理输出。

【输出格式（Notion 扩展 Markdown）】

每条新闻用 toggle 标题二 包裹，格式如下：

<toggle>## [新闻标题](来源链接)
![图片描述](图片URL)
> [!INFO] 核心要点：一句话概括最重要的信息（≤40字）

新闻摘要（2-3句中文，说明事件详情与行业意义）
</toggle>

【严格规则】
- 图片行：仅当原始数据含「图片URL」字段时嵌入，用简短中文描述作为 alt 文本；无图片则不加任何占位符
- 只使用原始数据中真实出现的链接，不虚构 URL
- 所有摘要用中文；技术术语可保留英文
- 从第一个 <toggle> 直接开始，不要输出「## ① AI 企业资讯」等节标题
- 不要在最前面输出任何解释说明
- 每条新闻独立一个 <toggle>，</toggle> 单独成行

【日期】{today}

【原始搜索数据】
{news_raw}
"""
        return self._llm_call(prompt, max_tokens=3000)

    # ─────────────────────────────────────────────────────────
    # 节撰写：② AIGC 学术前沿
    # ─────────────────────────────────────────────────────────

    def _write_section_academic(
        self, today: str, academic_raw: str, paper_details_raw: str
    ) -> str:
        prompt = f"""你是 AI 学术论文深度分析专家。从以下 arXiv 数据中**严格选取且仅选取 3 篇**\
AIGC 领域最重要的论文，进行深度解读。不得多于 3 篇，不得少于 3 篇。

【论文选取标准】
- 创新性强，与现有方法有明显差异
- 优先选取有精读补充数据的论文（更多素材可供深度分析）
- 覆盖不同子方向（如图像/视频/LLM/3D等）

【输出格式（Notion 扩展 Markdown）】

每篇论文用 toggle 标题二 包裹，内部嵌套两个 toggle（方法 + 结果）：

<toggle>## [论文完整英文标题](arXiv完整链接)
![图1: 模型架构图](图片URL1)
![图2: 实验结果对比](图片URL2)
> [!KEY] 核心贡献：一句话概括最大创新点，突出与现有工作的本质差异（≤50字）

**作者**：xxx, xxx et al. | **发布**：YYYY-MM-DD | **领域**：子方向

**研究动机**

[写成 2-3 段连贯的叙述性文字，逻辑结构为：
① 当前该方向的主流方法是什么，存在什么根本局限或痛点；
② 这些局限在实际应用中会导致什么具体问题；
③ 因此本文选择从什么角度切入，目标是什么。
不要用列表，要写成有逻辑衔接的自然段落。]

<toggle>🔧 方法详解
**核心框架/模型名称**：[给出明确的技术命名]

- **[模块/阶段1名称]**：[描述具体功能、内部结构、与整体的关系]
- **[模块/阶段2名称]**：[描述具体功能、内部结构、与整体的关系]
- **[训练策略/损失函数]**：[描述关键训练设计，如有特殊之处]
- **关键技术亮点**：[与已有工作相比，最本质的技术差异是什么]
</toggle>

<toggle>📊 实验与结果
- **评估基准**：[数据集名称 / benchmark 名称]
- **定量结果**：在 [指标名] 上达到 [数值]，超越 [对比方法] [幅度]（若数据可用）
- **消融 / 用户研究**：[最关键的消融发现，或用户研究主要结论]
- **局限性**：[若作者或评论提到明显局限，可简述]
</toggle>

**论文预览**：[HuggingFace Papers](HF链接)
</toggle>

【图示嵌入规则（重要）】
- 从「精读补充数据」中提取图片URL，优先选用来自 huggingface.co、arxiv.org、论文项目主页的图片
- 每篇论文尽量嵌入 **2-3 张图**（架构图、流程图、实验结果对比图各一张）
- alt 文字用简短中文描述图片内容，例如「图1: 模型整体架构」「图2: 与SOTA方法的性能对比」
- 若无合适图片（如图片是网站 logo、广告、人物照片等），则省略图片行
- 仅在「论文预览（含主图）」字段存在时才输出「**论文预览**」行

【其他规则】
- 研究动机必须写成段落，禁止用列表
- 方法 Toggle 中要具体，充分利用精读补充数据补充技术细节
- 从第一个 <toggle> 直接开始，不输出「## ② AIGC 学术前沿」等节标题，也不输出子方向分组标题
- 所有解读用中文，技术术语保留英文，只使用真实链接
- 每篇论文独立一个外层 <toggle>，各 </toggle> 单独成行

【日期】{today}

【arXiv 论文数据（包含摘要、arXiv链接、HF预览链接）】
{academic_raw}

【论文精读补充数据（含图片URL、技术博客、项目主页介绍等）】
{paper_details_raw}
"""
        return self._llm_call(prompt, max_tokens=4096)

    # ─────────────────────────────────────────────────────────
    # 节撰写：③ HCI 前沿
    # ─────────────────────────────────────────────────────────

    def _write_section_hci(self, today: str, hci_raw: str) -> str:
        prompt = f"""你是人机交互领域专家兼日报编辑。从以下数据中**严格选取且仅选取 3 篇**\
最重要的 HCI 工作进行深度介绍。不得多于 3 篇，不得少于 3 篇。

【选取优先级（从高到低）】
1. 已发表/录用于 CHI、UIST、IEEE VR、ISMAR、Ubicomp、IMWUT、DIS、TOCHI、
   IUI、MobileHCI、Displays 等顶级 HCI 会议/期刊的工作
2. 聚焦真实用户交互问题、有用户研究的 arXiv 预印本
3. 纯技术性、缺乏交互研究的工作（低优先级）

【输出格式（Notion 扩展 Markdown）】

每篇工作用 toggle 标题二 包裹，内部嵌套三个 toggle（方法 + 用户研究 + 讨论）：

<toggle>## [工作完整标题](链接)
![图示描述](图片URL)
> [!GOAL] 研究问题：本工作聚焦解决的核心 HCI 问题（≤45字）

**来源**：[尽量准确标注，如 CHI 2025 / UIST 2025 / arXiv 2026-04 等]
**作者**：xxx et al.

**研究背景与动机**

[写成 2-3 段连贯的叙述性文字：
① 当前该交互场景/问题的现状，用户面临什么痛点或挑战；
② 现有方案的局限性，为什么不够好；
③ 因此本文切入的角度和核心目标。
不要用列表，写成有逻辑衔接的自然段落。]

<toggle>🔬 系统与方法设计
**系统/框架名称**：[明确命名]

- **[核心组件/模块1]**：[功能、设计思路、与用户交互的方式]
- **[核心组件/模块2]**：[功能、设计思路]
- **[界面/交互设计]**：[如何体现 HCI 创新，具体交互范式]
- **关键技术支撑**：[使用了哪些 AI/ML/感知技术，如何集成到系统中]
</toggle>

<toggle>👥 用户研究
- **研究设计**：[被试数量、招募标准、任务类型、实验条件/对照设计]
- **量化结果**：[效率指标（时间、错误率等）、主观评分（NASA-TLX、SUS等）的具体数值]
- **定性发现**：[用户反馈、行为观察、访谈中的代表性洞察]
- **统计检验**：[显著性水平（如 p<0.05）、效果量等关键统计信息]
</toggle>

<toggle>💬 讨论与设计启示
- **核心贡献**：[在 HCI 领域的理论/实践贡献是什么]
- **设计启示**：[对未来系统/界面设计有什么指导意义]
- **局限性**：[作者承认的研究局限，如样本规模、任务限定、泛化性等]
- **未来工作**：[作者提到的后续研究方向]
</toggle>
</toggle>

【图示规则】
- 仅当原始数据含图片URL时嵌入，用简短中文描述系统界面/交互截图
- 若无合适图片，则省略图片行

【规则】
- 从第一个 <toggle> 直接开始，不输出「## ③ 人机交互前沿」等节标题
- 所有介绍用中文，只使用真实链接
- 每篇工作独立一个外层 <toggle>，各 </toggle> 单独成行

【日期】{today}

【原始数据（arXiv cs.HC + 顶会搜索结果）】
{hci_raw}
"""
        return self._llm_call(prompt, max_tokens=4096)

    # ─────────────────────────────────────────────────────────
    # 节撰写：④ AI 工具推荐
    # ─────────────────────────────────────────────────────────

    def _write_section_tools(self, today: str, tools_raw: str) -> str:
        prompt = f"""你是 AI 工具推荐专家。从以下数据中选取**严格 3 个**最值得推荐的 AI 工具，\
按照指定格式整理输出。

【选取规则】
- 必须是具体的工具、应用或开源项目，不得推荐 LLM 基础模型本身（如 GPT-5、Gemini 3、Claude 4 等）
- 优先选取有实际应用价值、可立即上手的工具
- 每个工具必须有可访问的官网或 GitHub 链接
- 严格只选 3 个，不多不少

【输出格式（Notion 扩展 Markdown）】

每个工具用 toggle 标题二 包裹：

<toggle>## [工具名称](官网/GitHub链接)
![工具界面或Logo](图片URL)
> [!TIP] 核心功能：一句话描述工具核心价值（≤40字）

**功能**：详细介绍工具能做什么（2-3句）
**适用**：目标用户群体与典型使用场景
**费用**：免费 / 付费（XX元/月）/ 开源（协议名）
</toggle>

【规则】
- 图片：仅当原始数据含「图片URL」时嵌入，用简短描述作为 alt 文本；无则不加
- 从第一个 <toggle> 直接开始，不输出节标题
- 所有介绍用中文，只使用真实链接
- 每个工具独立一个 <toggle>，</toggle> 单独成行

【日期】{today}

【原始数据】
{tools_raw}
"""
        return self._llm_call(prompt, max_tokens=2000)

    # ─────────────────────────────────────────────────────────
    # 拼装完整报告（纯字符串拼接，无 LLM 调用）
    # ─────────────────────────────────────────────────────────

    def _assemble_report(
        self,
        today: str,
        news_md: str,
        academic_md: str,
        hci_md: str,
        tools_md: str,
    ) -> str:
        return (
            f"# AI 日报 — {today}\n\n"
            f"> 每日精选 AI 企业动态、学术前沿、HCI 研究与工具推荐\n\n"
            f"---\n\n"
            f"# ① AI 企业资讯\n\n"
            f"{news_md.strip()}\n\n"
            f"---\n\n"
            f"# ② AIGC 学术前沿\n\n"
            f"{academic_md.strip()}\n\n"
            f"---\n\n"
            f"# ③ 人机交互前沿\n\n"
            f"{hci_md.strip()}\n\n"
            f"---\n\n"
            f"# ④ AI 工具推荐\n\n"
            f"{tools_md.strip()}\n\n"
            f"---\n\n"
            f"*由 AutoAIBlog 自动生成 | {today}*"
        )

    # ─────────────────────────────────────────────────────────
    # 论文列表：解析 arXiv 数据，追加写入 output/papers_list.md
    # ─────────────────────────────────────────────────────────

    def _update_paper_list(
        self,
        today: str,
        academic_results: list[tuple[str, str, str]],
        hci_results: list[tuple[str, str, str]],
    ):
        """
        解析当次搜索到的所有 arXiv 论文，去重后追加到 output/papers_list.md。
        字段：收录日期 | 标题 | 类别 | 发表场所 | 年份 | 关键词标签 | arXiv链接 | HF预览 | 备注
        """
        papers: list[dict] = []

        for raw, category, tags in academic_results + hci_results:
            # 每篇论文之间以 "\n---\n" 分隔（arXiv 工具的输出格式）
            blocks = raw.split("\n---\n")
            for block in blocks:
                if not block.strip():
                    continue

                # 标题在首行，格式为 **Title**
                title_m = re.search(r"^\*\*(.+?)\*\*", block.strip(), re.MULTILINE)
                if not title_m:
                    continue
                title = title_m.group(1).strip()
                # 过滤掉非标题内容（太短、含冒号、开头是「找到」等）
                if len(title) < 15 or "：" in title or title.startswith("找到"):
                    continue

                date_m    = re.search(r"- 发布时间：(\d{4}-\d{2}-\d{2})", block)
                link_m    = re.search(r"- arXiv：(https://arxiv\.org/abs/\S+)", block)
                hf_m      = re.search(r"论文预览（含主图）：(https://huggingface\.co/papers/\S+)", block)

                papers.append({
                    "collect_date": today,
                    "title":        title,
                    "category":     category,
                    "venue":        "arXiv",
                    "year":         date_m.group(1)[:4] if date_m else today[:4],
                    "published":    date_m.group(1)     if date_m else "",
                    "tags":         tags,
                    "link":         link_m.group(1)     if link_m else "",
                    "hf_link":      hf_m.group(1)       if hf_m   else "",
                    "notes":        "",
                })

        if not papers:
            print("  → 未解析到论文元数据，跳过列表更新")
            return

        list_path = Path("output") / "papers_list.md"

        # 首次运行时初始化文件头
        if not list_path.exists() or list_path.stat().st_size < 50:
            header = (
                "# AI 论文收录列表\n\n"
                "> 由 AutoAIBlog 自动维护，每次运行追加新论文。\n"
                "> **字段说明**：收录日期 | 标题 | 类别 | 发表场所（初始为 arXiv）"
                " | 年份 | 关键词标签 | arXiv链接 | HF预览 | 备注（可手动补充会议/期刊信息）\n\n"
                "| 收录日期 | 标题 | 类别 | 发表场所 | 年份 | 关键词标签 | arXiv | HF预览 | 备注 |\n"
                "|----------|------|------|----------|------|------------|-------|--------|------|\n"
            )
            list_path.write_text(header, encoding="utf-8")

        # 读取已有内容，用于去重
        existing_content = list_path.read_text(encoding="utf-8")
        # 以标题前 40 字作去重 key（避免截断差异导致误判重复）
        existing_keys = set(
            t[:40] for t in re.findall(r"\| \d{4}-\d{2}-\d{2} \| (.+?) \|", existing_content)
        )

        new_rows: list[str] = []
        for p in papers:
            title_display = (p["title"][:58] + "…") if len(p["title"]) > 60 else p["title"]
            dedup_key = title_display[:40]
            if dedup_key in existing_keys:
                continue
            existing_keys.add(dedup_key)

            arxiv_cell = f"[arXiv]({p['link']})"   if p["link"]    else ""
            hf_cell    = f"[HF]({p['hf_link']})"   if p["hf_link"] else ""
            new_rows.append(
                f"| {p['collect_date']} | {title_display} | {p['category']} "
                f"| {p['venue']} | {p['year']} | {p['tags']} "
                f"| {arxiv_cell} | {hf_cell} | {p['notes']} |\n"
            )

        if new_rows:
            with list_path.open("a", encoding="utf-8") as f:
                f.writelines(new_rows)
            print(f"  → 论文列表已追加 {len(new_rows)} 条（共搜集 {len(papers)} 篇，去重后新增）")
        else:
            print(f"  → 今日 {len(papers)} 篇论文均已在列表中，无新增")


# ─────────────────────────────────────────────
# 公开接口（兼容 main.py）
# ─────────────────────────────────────────────

def build_crew() -> AutoAIBlogRunner:
    """返回执行器实例，兼容 main.py 的 build_crew().kickoff() 调用方式。"""
    return AutoAIBlogRunner()
