"""
Web 搜索工具封装 — 基于 Tavily API
用于搜索 AI 企业资讯、HCI 动态、AI 工具推荐
"""
import os
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class TavilySearchInput(BaseModel):
    query: str = Field(description="搜索查询关键词，例如 'OpenAI news today release announcement'")


class TavilySearchTool(BaseTool):
    name: str = "tavily_search"
    description: str = (
        "使用 Tavily API 搜索互联网最新资讯。"
        "适合搜索 AI 企业新闻、产品发布、工具推荐、行业动态。"
        "返回包含标题、内容摘要、来源链接和图片 URL 的搜索结果。"
        "输入参数：query（搜索关键词字符串）"
    )
    args_schema: type[BaseModel] = TavilySearchInput

    def _run(self, query: str) -> str:
        max_results = 8
        search_depth = "advanced"
        include_images = True
        try:
            from tavily import TavilyClient

            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                raise ValueError("未设置 TAVILY_API_KEY 环境变量")

            client = TavilyClient(api_key=api_key)

            kwargs = {
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_images": include_images,
            }

            response = client.search(**kwargs)
            results_data = response.get("results", [])
            # 查询级别的图片列表（Tavily 返回与整体查询相关的图片）
            images_pool = response.get("images", [])

            if not results_data:
                return f"未找到关于 '{query}' 的相关结果。"

            results = []
            for i, item in enumerate(results_data):
                title = item.get("title", "无标题")
                url = item.get("url", "")
                content = item.get("content", "")[:400].strip()
                published_date = item.get("published_date", "")
                date_str = f"\n- 日期：{published_date}" if published_date else ""

                # 优先用结果自带的 image 字段，否则从图片池中按索引取
                image_url = item.get("image", "") or (
                    images_pool[i] if i < len(images_pool) else ""
                )
                image_str = f"\n- 图片URL：{image_url}" if image_url else ""

                results.append(
                    f"**{title}**{date_str}\n"
                    f"- 来源：{url}\n"
                    f"- 摘要：{content}...{image_str}\n"
                )

            header = f"搜索 '{query}' 找到 {len(results)} 条结果：\n\n"
            return header + "\n---\n".join(results)

        except ImportError:
            return "请安装 tavily-python：pip install tavily-python"
        except Exception as e:
            return f"Tavily 搜索出错：{str(e)}"
