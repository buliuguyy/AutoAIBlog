"""
Task 定义：四个板块的搜集任务 + 最终写作任务
"""
from datetime import datetime
from crewai import Task
from crewai import Agent


def create_news_task(agent: Agent) -> Task:
    today = datetime.now().strftime("%Y年%m月%d日")
    return Task(
        description=(
            f"搜集 {today} 的 AI 企业重要动态。\n\n"
            "请依次搜索以下内容：\n"
            "1. 'OpenAI news today site release announcement'\n"
            "2. 'Google DeepMind AI news latest'\n"
            "3. 'Meta AI Anthropic xAI news announcement'\n"
            "4. 'AI startup funding product launch this week'\n\n"
            "筛选标准：\n"
            "- 优先选择产品发布、重大技术突破、重要合作/融资消息\n"
            "- 排除纯商业软文、重复报道\n"
            "- 每条新闻保留：标题、核心内容（1-2句）、来源链接\n\n"
            "目标：找到 5-8 条今日最值得关注的 AI 企业动态。"
        ),
        expected_output=(
            "一份包含 5-8 条 AI 企业资讯的列表，每条包含：\n"
            "- 新闻标题\n"
            "- 核心内容摘要（中文，1-3句话）\n"
            "- 来源 URL\n"
            "- 相关企业名称"
        ),
        agent=agent,
    )


def create_academic_task(agent: Agent) -> Task:
    return Task(
        description=(
            "搜集最近3天内 AIGC 领域的前沿 arXiv 论文。\n\n"
            "请按以下子方向分别调用 arxiv_search 工具（每个方向搜索1次）：\n"
            "1. query='cat:cs.CV AND image generation diffusion transformer', days_back=3\n"
            "2. query='cat:cs.CV AND video generation editing temporal', days_back=3\n"
            "3. query='cat:cs.CV AND 3D generation NeRF gaussian splatting', days_back=3\n"
            "4. query='cat:cs.CL AND large language model reasoning alignment', days_back=3\n"
            "5. query='cat:cs.CV AND image editing inpainting style transfer', days_back=3\n\n"
            "筛选标准：\n"
            "- 优先选择方法有明显创新的论文，非单纯调参改进\n"
            "- 每个方向最多保留 2-3 篇最重要的论文\n"
            "- 需用中文简述每篇论文的核心贡献（2-3句话）"
        ),
        expected_output=(
            "按子方向分组的论文列表，每篇包含：\n"
            "- 论文标题（英文）\n"
            "- 作者（前3位）\n"
            "- arXiv 链接\n"
            "- 核心贡献（中文，2-3句话）\n"
            "总计 8-15 篇论文，按方向分组呈现。"
        ),
        agent=agent,
    )


def create_hci_task(agent: Agent) -> Task:
    return Task(
        description=(
            "搜集人机交互（HCI）领域结合 AI 的最新前沿工作。\n\n"
            "请进行以下搜索：\n"
            "1. arxiv_search: query='cat:cs.HC AND human computer interaction AI system interface', days_back=7\n"
            "2. arxiv_search: query='cat:cs.HC AND conversational agent AI assistant user study', days_back=7\n"
            "3. tavily_search: query='CHI 2025 UIST AI interaction system paper'\n"
            "4. tavily_search: query='AI human computer interaction new system 2026'\n\n"
            "筛选标准：\n"
            "- 关注真实的用户研究或系统演示，而非纯理论\n"
            "- 优先选择 AI 辅助用户完成特定任务的工作\n"
            "- 关注多模态交互、智能界面、具身 AI 等新颖方向"
        ),
        expected_output=(
            "4-8 条 HCI + AI 前沿工作，每条包含：\n"
            "- 工作标题\n"
            "- 来源（期刊/会议/arXiv）\n"
            "- 核心内容（中文，2-3句话）：系统/方法介绍 + 应用场景\n"
            "- 链接"
        ),
        agent=agent,
    )


def create_tools_task(agent: Agent) -> Task:
    return Task(
        description=(
            "发现并推荐近期值得关注的优质 AI 工具。\n\n"
            "请搜索以下内容：\n"
            f"1. 'new AI tools launched this week {datetime.now().strftime('%B %Y')}'\n"
            f"2. 'best AI productivity tools {datetime.now().strftime('%B %Y')}'\n"
            "3. 'open source AI model tool release GitHub'\n"
            "4. 'AI image video code generation tool new'\n\n"
            "筛选标准：\n"
            "- 工具需具备明显实用价值，非噱头产品\n"
            "- 优先选择：开源项目、免费工具、有真实用户反馈的产品\n"
            "- 覆盖不同类型：创意工具、效率工具、开发者工具"
        ),
        expected_output=(
            "4-6 个 AI 工具推荐，每个包含：\n"
            "- 工具名称\n"
            "- 核心功能介绍（中文，1-2句）\n"
            "- 适用人群/场景\n"
            "- 获取链接（官网/GitHub）\n"
            "- 是否免费/开源"
        ),
        agent=agent,
    )


def create_writing_task(
    agent: Agent,
    news_task: Task,
    academic_task: Task,
    hci_task: Task,
    tools_task: Task,
) -> Task:
    today = datetime.now().strftime("%Y-%m-%d")
    return Task(
        description=(
            f"将四个板块的搜集结果整理为一份完整的 AI 日报（{today}）。\n\n"
            "请严格按照以下 Markdown 格式输出：\n\n"
            "```\n"
            f"# AI 日报 — {today}\n\n"
            "> 每日精选 AI 企业动态、学术前沿、HCI 研究与工具推荐\n\n"
            "---\n\n"
            "## ① AI 企业资讯\n\n"
            "### [新闻标题](来源链接)\n"
            "![](图片URL，若搜索结果中有「图片URL」字段则填入，否则删除此行)\n"
            "核心内容摘要（2-3句中文）\n\n"
            "（重复以上格式，共 5-8 条）\n\n"
            "---\n\n"
            "## ② AIGC 学术前沿\n\n"
            "### 图像生成\n"
            "#### [论文标题](arXiv链接)\n"
            "**作者**：xxx et al.\n"
            "**核心贡献**：中文解读（2-3句）\n"
            "**论文预览**：[HuggingFace Papers](论文预览链接，若搜索结果有「论文预览」字段则填入)\n\n"
            "### 视频生成与编辑\n"
            "...（按子方向分组，每篇格式同上）\n\n"
            "---\n\n"
            "## ③ 人机交互前沿\n\n"
            "### [工作标题](链接)\n"
            "![](图片URL，若有则填入，否则删除此行)\n"
            "**来源**：会议/期刊名\n"
            "**内容**：中文介绍（2-3句）\n\n"
            "---\n\n"
            "## ④ AI 工具推荐\n\n"
            "### [工具名称](链接)\n"
            "![](图片URL，若搜索结果中有「图片URL」字段则填入，否则删除此行)\n"
            "**功能**：简介\n"
            "**适用**：场景\n"
            "**费用**：免费/付费/开源\n\n"
            "---\n"
            "*由 AutoAIBlog 自动生成*\n"
            "```\n\n"
            "重要规则：\n"
            "- 输出纯 Markdown，不要包含代码块标记\n"
            "- 所有解读必须是中文\n"
            "- 确保每个链接真实有效\n"
            "- 学术板块按子方向分组（图像生成、视频生成、3D生成、LLM 等）\n"
            "- 图片规则：搜索结果中若有「图片URL」字段，用 ![](URL) 嵌入；若无则不添加占位符，直接省略该行\n"
            "- 学术板块：若有「论文预览」字段则添加预览链接，无则省略"
        ),
        expected_output=(
            f"一份完整的 Markdown 格式 AI 日报，包含四个板块，"
            f"日期为 {today}，格式规范，可直接保存为 .md 文件。"
        ),
        agent=agent,
        context=[news_task, academic_task, hci_task, tools_task],
    )
