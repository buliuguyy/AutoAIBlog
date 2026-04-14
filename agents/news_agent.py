"""
Agent 定义：AI 企业资讯搜集专员
负责搜集 OpenAI、Google DeepMind、Meta AI、Anthropic、Mistral 等知名 AI 企业的最新动态
"""
from crewai import Agent
from tools.search_tool import TavilySearchTool


def create_news_agent(llm) -> Agent:
    return Agent(
        role="AI 企业资讯专员",
        goal=(
            "搜集今天（最近24-48小时内）知名 AI 企业的重要动态和新闻，"
            "包括产品发布、技术突破、商业合作、融资消息等。"
            "重点关注：OpenAI、Google DeepMind、Meta AI、Anthropic、"
            "Mistral AI、xAI、Stability AI、Cohere、Runway 等企业。"
        ),
        backstory=(
            "你是一位资深的 AI 行业分析师，长期追踪全球顶尖 AI 企业动态。"
            "你善于从海量信息中筛选出真正重要的企业新闻，"
            "并能准确判断哪些消息对 AI 从业者和研究者最具价值。"
            "你的分析客观专业，注重事实而非炒作。"
        ),
        tools=[TavilySearchTool()],
        llm=llm,
        verbose=True,
        max_iter=4,
    )
