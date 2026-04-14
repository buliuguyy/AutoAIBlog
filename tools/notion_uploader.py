"""
Notion 上传工具 — 将 Markdown 格式日报转换为 Notion blocks 并上传
"""
import os
import re
import time
import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


# ─────────────────────────────────────────────
# 内部辅助：HTTP headers
# ─────────────────────────────────────────────

def _headers() -> dict:
    token = os.getenv("NOTION_INTEGRATION_SECRET")
    if not token:
        raise ValueError("未设置 NOTION_INTEGRATION_SECRET 环境变量")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ─────────────────────────────────────────────
# 行内 Markdown → Notion rich_text 数组
# ─────────────────────────────────────────────

def _parse_inline(text: str) -> list:
    """将行内 Markdown（**bold**、*italic*、[link](url)）转换为 Notion rich_text。"""
    if not text.strip():
        return [{"type": "text", "text": {"content": " "}}]

    rich_texts = []
    pos = 0

    while pos < len(text):
        # **bold**
        m = re.match(r"\*\*(.+?)\*\*", text[pos:])
        if m:
            rich_texts.append({
                "type": "text",
                "text": {"content": m.group(1)},
                "annotations": {"bold": True},
            })
            pos += m.end()
            continue

        # *italic*（确保不是 **bold**）
        m = re.match(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", text[pos:])
        if m:
            rich_texts.append({
                "type": "text",
                "text": {"content": m.group(1)},
                "annotations": {"italic": True},
            })
            pos += m.end()
            continue

        # [text](url)
        m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", text[pos:])
        if m:
            rich_texts.append({
                "type": "text",
                "text": {"content": m.group(1), "link": {"url": m.group(2)}},
            })
            pos += m.end()
            continue

        # 普通文字（直到下一个特殊字符）
        m = re.match(r"[^*\[]+", text[pos:])
        if m:
            rich_texts.append({"type": "text", "text": {"content": m.group(0)}})
            pos += m.end()
            continue

        # 兜底：跳过单个字符
        rich_texts.append({"type": "text", "text": {"content": text[pos]}})
        pos += 1

    return rich_texts or [{"type": "text", "text": {"content": text}}]


# ─────────────────────────────────────────────
# Block 构造辅助
# ─────────────────────────────────────────────

def _heading(level: int, text: str) -> dict:
    kind = f"heading_{min(level, 3)}"  # Notion 最高支持 heading_3
    return {"type": kind, kind: {"rich_text": _parse_inline(text)}}


def _paragraph(text: str) -> dict:
    return {"type": "paragraph", "paragraph": {"rich_text": _parse_inline(text)}}


def _quote(text: str) -> dict:
    return {"type": "quote", "quote": {"rich_text": _parse_inline(text)}}


def _divider() -> dict:
    return {"type": "divider", "divider": {}}


def _image(url: str) -> dict | None:
    """仅接受 http(s) URL，否则返回 None 跳过。"""
    if not url or not url.startswith("http"):
        return None
    return {"type": "image", "image": {"type": "external", "external": {"url": url}}}


def _bullet(text: str) -> dict:
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _parse_inline(text)},
    }


# ─────────────────────────────────────────────
# Markdown → Notion blocks
# ─────────────────────────────────────────────

def markdown_to_notion_blocks(markdown: str) -> list:
    """将完整 Markdown 文本逐行转换为 Notion block 列表。"""
    blocks = []

    for line in markdown.split("\n"):
        s = line.strip()
        if not s:
            continue

        if s == "---":
            blocks.append(_divider())
        elif s.startswith("#### "):
            blocks.append(_heading(3, s[5:]))
        elif s.startswith("### "):
            blocks.append(_heading(3, s[4:]))
        elif s.startswith("## "):
            blocks.append(_heading(2, s[3:]))
        elif s.startswith("# "):
            blocks.append(_heading(1, s[2:]))
        elif s.startswith("> "):
            blocks.append(_quote(s[2:]))
        elif s.startswith("- "):
            blocks.append(_bullet(s[2:]))
        else:
            # 检查是否是独立的图片行 ![alt](url)
            img_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", s)
            if img_match:
                b = _image(img_match.group(2))
                if b:
                    blocks.append(b)
            else:
                blocks.append(_paragraph(s))

    return blocks


# ─────────────────────────────────────────────
# Notion API 调用
# ─────────────────────────────────────────────

def _create_page(title: str, parent_page_id: str) -> str:
    """在指定父页面下创建新页面，返回新页面 ID。"""
    # 统一去除连字符，Notion API 两种格式都接受
    clean_id = parent_page_id.replace("-", "")
    body = {
        "parent": {"page_id": clean_id},
        "properties": {
            "title": {"title": [{"text": {"content": title}}]}
        },
    }
    resp = requests.post(f"{NOTION_API_BASE}/pages", headers=_headers(), json=body)

    if resp.status_code == 404:
        raise ValueError(
            "Notion 页面未找到（404）。请确认：\n"
            "  1. NOTION_PAGE_ID 是正确的页面 ID\n"
            "  2. 已将 Integration 添加到该页面（页面右上角 → 连接 → 选择你的 Integration）"
        )
    resp.raise_for_status()
    return resp.json()["id"]


def _append_blocks(page_id: str, blocks: list):
    """将 blocks 分批（≤100 个/批）追加到页面。"""
    for i in range(0, len(blocks), 100):
        batch = blocks[i : i + 100]
        resp = requests.patch(
            f"{NOTION_API_BASE}/blocks/{page_id}/children",
            headers=_headers(),
            json={"children": batch},
        )
        resp.raise_for_status()
        if i + 100 < len(blocks):
            time.sleep(0.3)  # 避免触发 Notion API 速率限制


# ─────────────────────────────────────────────
# 公开接口
# ─────────────────────────────────────────────

def upload_to_notion(markdown: str, title: str) -> str:
    """
    将 Markdown 日报上传至 Notion。

    Args:
        markdown: Markdown 格式的日报内容
        title:    Notion 页面标题，如 "AI 日报 — 2026-04-13"

    Returns:
        新创建的 Notion 页面 URL
    """
    parent_page_id = os.getenv("NOTION_PAGE_ID", "")
    if not parent_page_id:
        raise ValueError("未设置 NOTION_PAGE_ID 环境变量")

    page_id = _create_page(title, parent_page_id)
    blocks = markdown_to_notion_blocks(markdown)

    if blocks:
        _append_blocks(page_id, blocks)

    # Notion 页面 URL 格式
    page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
    return page_url
