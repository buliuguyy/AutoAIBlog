"""
Notion 上传工具 — 将 Markdown 格式日报转换为 Notion blocks 并上传

支持的扩展语法（Notion-Markdown 方言，详见 docs/notion_formatting_guide.md）：
  > [!KEY/TIP/GOAL/RESULT/METHOD/NOTE/INFO/WARNING/PAPER] 文字
                          → callout block（带颜色背景和图标）
  <toggle>标题\n内容\n</toggle>
                          → toggle block（可折叠，内容嵌套）
  ```lang\n代码\n```      → code block
  $$\n公式\n$$            → equation block（LaTeX）
  1. 条目                 → numbered_list_item
  `code`                  → 行内代码（code annotation）
  ==文字==                → 黄色高亮（yellow_background annotation）
"""

import os
import re
import time
import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Callout 类型配置：图标 + 背景色
CALLOUT_CONFIGS = {
    "KEY":     {"icon": "🔑", "color": "purple_background"},
    "TIP":     {"icon": "💡", "color": "green_background"},
    "GOAL":    {"icon": "🎯", "color": "orange_background"},
    "RESULT":  {"icon": "📊", "color": "yellow_background"},
    "METHOD":  {"icon": "🔧", "color": "gray_background"},
    "NOTE":    {"icon": "📝", "color": "blue_background"},
    "INFO":    {"icon": "ℹ️",  "color": "blue_background"},
    "WARNING": {"icon": "⚠️", "color": "red_background"},
    "PAPER":   {"icon": "📄", "color": "default"},
}

# Notion 支持的语言名称映射
CODE_LANG_MAP = {
    "python": "python", "py": "python",
    "javascript": "javascript", "js": "javascript",
    "typescript": "typescript", "ts": "typescript",
    "bash": "shell", "sh": "shell", "shell": "shell",
    "json": "json", "yaml": "yaml", "yml": "yaml",
    "markdown": "markdown", "md": "markdown",
    "sql": "sql", "html": "html", "css": "css",
    "go": "go", "rust": "rust", "java": "java",
    "cpp": "c++", "c": "c", "c++": "c++",
    "": "plain text", "text": "plain text",
}


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
    """将行内 Markdown 转换为 Notion rich_text 数组。

    支持：**bold**、*italic*、`code`、==highlight==、[link](url)
    """
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

        # `code`（行内代码）
        m = re.match(r"`([^`]+)`", text[pos:])
        if m:
            rich_texts.append({
                "type": "text",
                "text": {"content": m.group(1)},
                "annotations": {"code": True},
            })
            pos += m.end()
            continue

        # ==highlight==（黄色高亮）
        m = re.match(r"==(.+?)==", text[pos:])
        if m:
            rich_texts.append({
                "type": "text",
                "text": {"content": m.group(1)},
                "annotations": {"color": "yellow_background"},
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
        m = re.match(r"[^*`=\[]+", text[pos:])
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
    kind = f"heading_{min(level, 3)}"
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


def _numbered_list_item(text: str) -> dict:
    return {
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": _parse_inline(text)},
    }


def _callout(text: str, callout_type: str = "NOTE") -> dict:
    """创建 callout block，带颜色背景和 emoji 图标。"""
    config = CALLOUT_CONFIGS.get(callout_type.upper(), CALLOUT_CONFIGS["NOTE"])
    return {
        "type": "callout",
        "callout": {
            "rich_text": _parse_inline(text),
            "icon": {"type": "emoji", "emoji": config["icon"]},
            "color": config["color"],
        },
    }


def _toggle(title: str, children: list) -> dict:
    """创建 toggle block，标题可见，内容默认折叠。"""
    return {
        "type": "toggle",
        "toggle": {
            "rich_text": _parse_inline(title),
            "children": children if children else [_paragraph(" ")],
        },
    }


def _code_block(code: str, language: str = "") -> dict:
    """创建代码块，自动映射 Notion 支持的语言名称。"""
    notion_lang = CODE_LANG_MAP.get(language.lower(), "plain text")
    # Notion code block 的 rich_text 内容限制在 2000 字符
    code_content = code[:1990] if len(code) > 2000 else code
    return {
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content": code_content}}],
            "language": notion_lang,
        },
    }


def _equation(expression: str) -> dict:
    """创建数学公式块（LaTeX 格式）。"""
    return {
        "type": "equation",
        "equation": {"expression": expression.strip()},
    }


# ─────────────────────────────────────────────
# Markdown → Notion blocks（状态机解析）
# ─────────────────────────────────────────────

# Callout 类型识别正则
_CALLOUT_PATTERN = re.compile(
    r'^>\s*\[!(KEY|TIP|GOAL|RESULT|METHOD|NOTE|INFO|WARNING|PAPER)\]\s*(.*)',
    re.IGNORECASE,
)


def markdown_to_notion_blocks(markdown: str) -> list:
    """将完整 Markdown 文本（含扩展语法）逐行解析为 Notion block 列表。

    多行块（代码、公式、toggle）通过状态机处理，其余逐行转换。
    """
    blocks = []
    lines = markdown.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        # ── 空行跳过 ───────────────────────────────────────────
        if not s:
            i += 1
            continue

        # ── 代码块 `````lang ─────────────────────────────────────
        if s.startswith("```"):
            lang = s[3:].strip()
            i += 1
            code_lines = []
            while i < len(lines):
                if lines[i].strip().startswith("```"):
                    i += 1
                    break
                code_lines.append(lines[i])
                i += 1
            blocks.append(_code_block("\n".join(code_lines), lang))
            continue

        # ── 数学公式块 $$ ─────────────────────────────────────────
        if s == "$$":
            i += 1
            eq_lines = []
            while i < len(lines) and lines[i].strip() != "$$":
                eq_lines.append(lines[i])
                i += 1
            blocks.append(_equation("\n".join(eq_lines)))
            if i < len(lines):
                i += 1
            continue

        # ── Toggle 折叠块 <toggle>标题 ────────────────────────────
        if s.startswith("<toggle>"):
            title = s[8:].strip()
            i += 1
            child_lines = []
            while i < len(lines) and lines[i].strip() != "</toggle>":
                child_lines.append(lines[i])
                i += 1
            # 递归转换子块
            child_blocks = markdown_to_notion_blocks("\n".join(child_lines))
            blocks.append(_toggle(title, child_blocks))
            if i < len(lines):
                i += 1
            continue

        # ── Callout 块 > [!TYPE] 文字 ─────────────────────────────
        callout_m = _CALLOUT_PATTERN.match(s)
        if callout_m:
            blocks.append(_callout(callout_m.group(2), callout_m.group(1)))
            i += 1
            continue

        # ── 分割线 ─────────────────────────────────────────────────
        if s == "---":
            blocks.append(_divider())
            i += 1
            continue

        # ── 标题 ───────────────────────────────────────────────────
        if s.startswith("#### "):
            blocks.append(_heading(3, s[5:]))
        elif s.startswith("### "):
            blocks.append(_heading(3, s[4:]))
        elif s.startswith("## "):
            blocks.append(_heading(2, s[3:]))
        elif s.startswith("# "):
            blocks.append(_heading(1, s[2:]))

        # ── 普通引用 > ─────────────────────────────────────────────
        elif s.startswith("> "):
            blocks.append(_quote(s[2:]))

        # ── 有序列表 1. ────────────────────────────────────────────
        elif re.match(r"^\d+\.\s", s):
            text = re.sub(r"^\d+\.\s+", "", s)
            blocks.append(_numbered_list_item(text))

        # ── 无序列表 - / * ─────────────────────────────────────────
        elif s.startswith("- ") or s.startswith("* "):
            blocks.append(_bullet(s[2:]))

        # ── 图片行 ![alt](url) ─────────────────────────────────────
        else:
            img_match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", s)
            if img_match:
                b = _image(img_match.group(2))
                if b:
                    blocks.append(b)
            else:
                blocks.append(_paragraph(s))

        i += 1

    return blocks


# ─────────────────────────────────────────────
# Notion API 调用
# ─────────────────────────────────────────────

def _create_page(title: str, parent_page_id: str) -> str:
    """在指定父页面下创建新页面，返回新页面 ID。"""
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
    """将 blocks 分批（≤100 个/批）追加到页面。

    注意：包含 children 的 toggle 块会整体发送，其子块不计入批次限制。
    """
    for i in range(0, len(blocks), 100):
        batch = blocks[i: i + 100]
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
        markdown: Markdown 格式的日报内容（支持扩展 Notion 方言）
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

    page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
    return page_url
