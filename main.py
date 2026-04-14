#!/usr/bin/env python3
"""
AutoAIBlog — 每日 AI 资讯自动聚合系统
手动触发：python main.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv


def check_env():
    """检查必要的环境变量"""
    load_dotenv()
    missing = []
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not os.getenv("TAVILY_API_KEY"):
        missing.append("TAVILY_API_KEY")
    if missing:
        print(f"[错误] 缺少以下环境变量，请检查 .env 文件：")
        for var in missing:
            print(f"  - {var}")
        print("\n请参考 .env.example 配置你的 API Keys。")
        sys.exit(1)


def save_report(content: str) -> Path:
    """将日报保存为 Markdown 文件"""
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    output_path = output_dir / f"{today}.md"

    output_path.write_text(content, encoding="utf-8")
    return output_path


def main():
    print("=" * 60)
    print("  AutoAIBlog — 每日 AI 资讯聚合系统")
    print(f"  日期：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 检查环境变量
    check_env()

    # 导入并构建 Crew（在 load_dotenv 之后）
    from crew import build_crew

    print("\n[1/4] 正在构建 Agent 团队...")
    crew = build_crew()

    print("\n[2/4] 开始执行资讯搜集任务（预计需要 5-15 分钟）...")
    print("  - AI 企业资讯搜集中...")
    print("  - AIGC 学术前沿论文搜集中...")
    print("  - HCI 前沿工作搜集中...")
    print("  - AI 工具推荐搜集中...")
    print()

    try:
        result = crew.kickoff()
    except Exception as e:
        print(f"\n[错误] 任务执行失败：{e}")
        sys.exit(1)

    # 获取最终输出文本
    if hasattr(result, "raw"):
        report_content = result.raw
    else:
        report_content = str(result)

    print("\n[3/4] 正在保存日报...")
    output_path = save_report(report_content)

    print("\n" + "=" * 60)
    print(f"  日报已生成：{output_path}")
    print("=" * 60)
    print()
    print(report_content[:500] + "..." if len(report_content) > 500 else report_content)

    # ── 上传到 Notion（可选）──
    if os.getenv("NOTION_INTEGRATION_SECRET") and os.getenv("NOTION_PAGE_ID"):
        print("\n[4/4] 正在上传到 Notion...")
        try:
            from tools.notion_uploader import upload_to_notion
            today = datetime.now().strftime("%Y-%m-%d")
            page_url = upload_to_notion(report_content, f"AI 日报 — {today}")
            print(f"  Notion 页面：{page_url}")
        except Exception as e:
            print(f"  [警告] Notion 上传失败（本地 Markdown 已保存，不影响使用）：{e}")


if __name__ == "__main__":
    main()
