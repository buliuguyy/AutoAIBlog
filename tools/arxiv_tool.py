"""
arXiv 搜索工具 — 用于搜集学术前沿论文
支持按关键词、分类、日期范围搜索
"""
import re
import arxiv
from datetime import datetime, timedelta
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ArxivSearchInput(BaseModel):
    query: str = Field(description="搜索关键词，例如 'image generation diffusion model'。可以在关键词前加 cat:cs.CV AND 来过滤分类")
    days_back: int = Field(default=3, description="搜索最近几天的论文，默认3天")


class ArxivSearchTool(BaseTool):
    name: str = "arxiv_search"
    description: str = (
        "从 arXiv 搜索最新学术论文。"
        "适用于搜索图像生成、视频生成、LLM、3D生成、人机交互等AI学术前沿论文。"
        "返回论文标题、作者、摘要、链接等信息。"
        "输入参数：query（搜索关键词，可含 cat:cs.CV 等分类前缀）；days_back（搜索最近几天，默认3）"
    )
    args_schema: type[BaseModel] = ArxivSearchInput

    def _run(self, query: str, days_back: int = 3) -> str:
        max_results = 10
        try:
            # 构建时间过滤（最近 N 天）
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            client = arxiv.Client(
                delay_seconds=3.0,
                num_retries=3,
            )
            search = arxiv.Search(
                query=query,
                max_results=max_results * 2,  # 多取一些以便日期过滤
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )

            results = []
            for paper in client.results(search):
                # 过滤日期
                published = paper.published.replace(tzinfo=None)
                if published < cutoff_date:
                    break
                if len(results) >= max_results:
                    break

                authors = ", ".join(a.name for a in paper.authors[:3])
                if len(paper.authors) > 3:
                    authors += " et al."

                # 从 entry_id 提取纯 arXiv ID（如 2401.12345）
                arxiv_id_match = re.search(r"arxiv\.org/abs/([^v]+)", paper.entry_id)
                arxiv_id = arxiv_id_match.group(1) if arxiv_id_match else ""
                hf_url = (
                    f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else ""
                )
                hf_str = f"\n- 论文预览（含主图）：{hf_url}" if hf_url else ""

                results.append(
                    f"**{paper.title}**\n"
                    f"- 作者：{authors}\n"
                    f"- 发布时间：{published.strftime('%Y-%m-%d')}\n"
                    f"- arXiv：{paper.entry_id}\n"
                    f"- 摘要：{paper.summary[:300].strip()}...{hf_str}\n"
                )

            if not results:
                return f"未找到最近 {days_back} 天内关于 '{query}' 的论文。"

            header = f"找到 {len(results)} 篇相关论文（最近 {days_back} 天）：\n\n"
            return header + "\n---\n".join(results)

        except Exception as e:
            return f"arXiv 搜索出错：{str(e)}"
