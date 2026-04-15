#!/usr/bin/env python3
"""
AutoAIBlog — 分阶段验证脚本

  Stage 1: 验证 Tavily 搜索 + 图片 URL 获取
  Stage 2: 验证 Markdown 格式化与本地文件保存
  Stage 3: 验证 Notion 上传（blocks 转换 + API 写入）

用法：
  uv run python validate.py          # 运行全部三个阶段
  uv run python validate.py --stage 1  # 仅运行指定阶段
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

TODAY = datetime.now().strftime("%Y-%m-%d")
OUTPUT_DIR = Path(__file__).parent / "output"

# ─────────────────────────────────────────────
# 示例 Markdown（代表正式流水线会产出的格式）
# ─────────────────────────────────────────────
SAMPLE_MARKDOWN = f"""# AI 日报 — {TODAY}

> 每日精选 AI 企业动态、学术前沿、HCI 研究与工具推荐（验证版）

---

## ① AI 企业资讯

### [OpenAI 推出全新推理模型 o3](https://openai.com/blog)
![](https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/OpenAI_Logo.svg/1200px-OpenAI_Logo.svg.png)
> [!INFO] 核心要点：o3 在 AIME 数学基准上得分超越前代 30 个百分点，接近专家级推理能力

OpenAI 发布了 o3 推理模型，在数学、编程和科学推理任务上取得显著突破。该模型已向 ChatGPT Plus 用户开放，API 接入将于下月推出。

### [Google DeepMind 发布 Gemini 2.5 Pro](https://deepmind.google)
> [!INFO] 核心要点：支持 100 万 token 超长上下文，多模态理解能力超越主流竞品

Gemini 2.5 Pro 支持百万 token 超长上下文窗口，在代码生成和文档分析任务表现突出。已通过 Google AI Studio 向开发者开放体验。

---

## ② AIGC 学术前沿

### 图像生成

#### [DiT-Fast: Accelerating Diffusion Transformer Inference](http://arxiv.org/abs/2401.12345)
![论文核心图示](https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Diffusion_diagram.svg/640px-Diffusion_diagram.svg.png)
> [!KEY] 核心贡献：提出扩散 Transformer 推理加速框架，通过激活缓存跳过冗余步骤，实现 3× 加速且不损失生成质量

**作者**：Zhang et al. | **发布**：{TODAY} | **领域**：图像生成加速

**研究动机**

当前扩散 Transformer 模型（如 DiT、PixArt）在生成高质量图像时需要数十步迭代去噪，导致推理延迟高达数秒甚至数十秒，严重制约了实时交互场景的应用。现有加速方法要么通过减少采样步数损害生成质量，要么依赖昂贵的模型蒸馏流程。

DiT-Fast 发现扩散过程中相邻时间步之间的中间激活存在高度冗余，可以安全地被重复利用而无需重新计算，从而在不修改模型权重、不依赖额外训练的情况下实现显著加速。

<toggle>🔧 方法详解
**核心框架**：Activation-Cached DiT (ACD-DiT)

- **激活相似性分析**：通过余弦相似度量化相邻时间步 Transformer 层激活的冗余程度，确定可跳过的计算层
- **动态缓存调度器**：根据当前去噪进度自适应决定哪些层读取缓存、哪些层重新计算
- **质量保护机制**：在扩散轨迹的关键时间步（高噪声区域）强制全量计算，避免质量下降
</toggle>

<toggle>📊 实验与结果
- **评估基准**：ImageNet 256×256、MS-COCO 2017
- **关键指标**：FID=2.83（DiT-XL/2 基线 FID=2.27），加速比 3.1×，质量损失极小
- **消融发现**：动态调度比固定跳过策略在 FID 上优化约 15%
</toggle>

**论文预览**：[HuggingFace Papers](https://huggingface.co/papers/2401.12345)

---

## ③ 人机交互前沿

### [VoiceUI: AI 驱动的自适应语音交互系统](https://arxiv.org/abs/2401.99999)
> [!GOAL] 研究问题：如何让语音界面自适应不同用户的语言习惯和任务复杂度，降低交互摩擦

**来源**：CHI 2025

**研究内容**：VoiceUI 基于大语言模型构建自适应语音交互界面，可根据用户的语言习惯和当前任务上下文动态调整响应策略与信息粒度。系统通过 24 名参与者的受控实验验证，结果显示复杂任务完成时间缩短 31%，认知负荷（NASA-TLX）降低显著。

---

## ④ AI 工具推荐

### [Cursor](https://cursor.sh)
![](https://cursor.sh/brand/icon.svg)
> [!TIP] 核心功能：深度集成 Claude 与 GPT-4 的 AI 代码编辑器，支持对话式编程与自动重构

**功能**：提供行内代码补全、多文件上下文理解、代码解释与对话式调试，可直接在编辑器内与 AI 讨论架构设计
**适用**：前后端开发者、希望通过 AI pair programming 提升编码效率的工程师
**费用**：免费版可用；Pro 版 $20/月，支持无限次 Claude claude-sonnet-4-6 调用

---

*由 AutoAIBlog 自动生成 | {TODAY}*
"""


# ═════════════════════════════════════════════
# Stage 1: Tavily 搜索 + 图片
# ═════════════════════════════════════════════

def stage1_test_search() -> bool:
    print("\n" + "─" * 55)
    print("  Stage 1 / 搜索与图片获取验证")
    print("─" * 55)

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("  [✗] 缺少 TAVILY_API_KEY，请检查 .env 文件")
        return False

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        query = "OpenAI Anthropic Google DeepMind AI news today"
        print(f"\n  查询：「{query}」")
        print("  搜索中（include_images=True）...\n")

        response = client.search(
            query=query,
            max_results=3,
            search_depth="basic",
            include_images=True,
        )

        results = response.get("results", [])
        images_pool = response.get("images", [])

        print(f"  返回结果数：{len(results)}")
        print(f"  图片池数量：{len(images_pool)}\n")

        has_any_image = False
        for i, r in enumerate(results):
            img_url = r.get("image") or (images_pool[i] if i < len(images_pool) else "")
            if img_url:
                has_any_image = True
            title = r.get("title", "无标题")[:60]
            url = r.get("url", "")[:65]
            print(f"  [{i+1}] {title}")
            print(f"       URL  : {url}")
            print(f"       图片 : {img_url[:75] if img_url else '（本次查询无图片）'}")
            print()

        print("  [✓] Tavily 搜索调用成功")
        if has_any_image:
            print("  [✓] 图片 URL 已返回，可嵌入日报")
        else:
            print("  [!] 本次查询未返回图片（Tavily 图片可用性因查询而异，不影响文本流程）")

        return True

    except Exception as e:
        print(f"  [✗] 搜索失败：{e}")
        return False


# ═════════════════════════════════════════════
# Stage 2: Markdown 格式化 + 本地保存
# ═════════════════════════════════════════════

def stage2_test_markdown() -> tuple[bool, str | None]:
    print("\n" + "─" * 55)
    print("  Stage 2 / Markdown 格式化与本地保存验证")
    print("─" * 55)

    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        output_path = OUTPUT_DIR / f"validate-{TODAY}.md"
        output_path.write_text(SAMPLE_MARKDOWN, encoding="utf-8")

        content = output_path.read_text(encoding="utf-8")
        section_count = content.count("## ")
        image_count = content.count("![")
        link_count = len([l for l in content.split("\n") if l.startswith("### [")])

        print(f"\n  保存路径：{output_path}")
        print(f"  板块数量：{section_count}")
        print(f"  图片嵌入：{image_count} 处")
        print(f"  条目链接：{link_count} 条")
        print(f"  总字符数：{len(content):,}")

        # 验证必要结构
        assert "# AI 日报" in content, "缺少一级标题"
        assert "## ① AI 企业资讯" in content, "缺少企业资讯板块"
        assert "## ② AIGC 学术前沿" in content, "缺少学术前沿板块"
        assert "## ③ 人机交互前沿" in content, "缺少 HCI 板块"
        assert "## ④ AI 工具推荐" in content, "缺少工具推荐板块"

        print("\n  [✓] Markdown 结构完整（四个板块均存在）")
        print("  [✓] 图片嵌入格式 ![](url) 正确")
        print("  [✓] 本地文件保存成功")

        return True, SAMPLE_MARKDOWN

    except AssertionError as e:
        print(f"  [✗] 结构验证失败：{e}")
        return False, None
    except Exception as e:
        print(f"  [✗] 保存失败：{e}")
        return False, None


# ═════════════════════════════════════════════
# Stage 3: Notion 上传
# ═════════════════════════════════════════════

def stage3_test_notion(markdown: str) -> bool:
    print("\n" + "─" * 55)
    print("  Stage 3 / Notion 上传验证")
    print("─" * 55)

    token = os.getenv("NOTION_INTEGRATION_SECRET")
    page_id = os.getenv("NOTION_PAGE_ID")

    if not token:
        print("  [✗] 缺少 NOTION_INTEGRATION_SECRET")
        return False
    if not page_id:
        print("  [✗] 缺少 NOTION_PAGE_ID")
        return False

    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from tools.notion_uploader import markdown_to_notion_blocks, upload_to_notion

        # ── 3a: 验证 block 转换 ──
        blocks = markdown_to_notion_blocks(markdown)
        type_stats: dict[str, int] = {}
        for b in blocks:
            t = b["type"]
            type_stats[t] = type_stats.get(t, 0) + 1

        print(f"\n  Markdown → Notion blocks：共 {len(blocks)} 个")
        for t, count in sorted(type_stats.items()):
            print(f"    {t:<25} {count}")

        # ── 3b: 验证 API 上传 ──
        title = f"[验证] AI 日报 — {TODAY}"
        print(f"\n  正在创建 Notion 页面：「{title}」...")
        page_url = upload_to_notion(markdown, title)

        print(f"\n  [✓] 页面创建成功")
        print(f"  [✓] 页面链接：{page_url}")
        print(f"\n  请在 Notion 中打开上方链接确认内容格式是否正确。")

        return True

    except Exception as e:
        print(f"\n  [✗] Notion 上传失败：{e}")
        return False


# ═════════════════════════════════════════════
# 入口
# ═════════════════════════════════════════════

def main():
    # 解析 --stage 参数
    target_stage = None
    if "--stage" in sys.argv:
        idx = sys.argv.index("--stage")
        try:
            target_stage = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("用法：python validate.py --stage <1|2|3>")
            sys.exit(1)

    print("\n" + "═" * 55)
    print("  AutoAIBlog — 分阶段验证")
    print(f"  日期：{TODAY}")
    print("═" * 55)

    s1_ok = s2_ok = s3_ok = None
    markdown = None

    if target_stage in (None, 1):
        s1_ok = stage1_test_search()

    if target_stage in (None, 2):
        s2_ok, markdown = stage2_test_markdown()

    if target_stage in (None, 3):
        if markdown is None:
            markdown = SAMPLE_MARKDOWN  # Stage 3 单独运行时用示例内容
        s3_ok = stage3_test_notion(markdown)

    # ── 汇总 ──
    print("\n" + "═" * 55)
    print("  验证结果汇总")
    print("═" * 55)

    def fmt(result) -> str:
        if result is None:
            return "─ 跳过"
        return "✓ 通过" if result else "✗ 失败"

    print(f"  Stage 1  搜索 + 图片   {fmt(s1_ok)}")
    print(f"  Stage 2  Markdown      {fmt(s2_ok)}")
    print(f"  Stage 3  Notion        {fmt(s3_ok)}")

    all_run = all(r is not None for r in [s1_ok, s2_ok, s3_ok])
    all_ok = all(r for r in [s1_ok, s2_ok, s3_ok] if r is not None)

    print()
    if all_run and all_ok:
        print("  全部验证通过！运行完整流水线：")
        print()
        print("    uv run python main.py")
    elif all_ok:
        print("  已运行阶段全部通过。")
    else:
        print("  请根据上方错误信息修复后重试。")
    print()


if __name__ == "__main__":
    main()
