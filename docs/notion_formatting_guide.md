# Notion 富文本格式规范

本文档为 AI 日报撰写编辑（writer agent）提供 Notion 专属 Markdown 方言的格式说明。
输出的 Markdown 将通过程序自动转换为 Notion blocks 并上传，因此需要遵循本规范。

---

## 一、支持的块类型（Block Types）

### 1. 标准 Markdown（通用）

| 语法 | Notion Block |
|------|-------------|
| `# 标题` | heading_1 |
| `## 标题` | heading_2 |
| `### 标题` | heading_3 |
| `#### 标题` | heading_3（等同 ###）|
| `> 引用` | quote |
| `- 条目` | bulleted_list_item |
| `1. 条目` | numbered_list_item |
| `---` | divider |
| `![caption](url)` | image（仅支持 http/https，alt 文字作为 caption）|
| `**文字**` | 粗体（bold annotation）|
| `*文字*` | 斜体（italic annotation）|
| `[文字](url)` | 超链接 |

### 2. 代码块

````
```python
# 代码内容
x = 1 + 2
```
````

→ 转换为 Notion code block，支持语言：`python`, `javascript`, `typescript`, `bash`, `json`, `yaml`, `markdown`，其他均以 `plain text` 处理。

### 3. 数学公式块（Equation）

```
$$
\mathcal{L} = \mathbb{E}_{x,t}\left[\|\epsilon - \epsilon_\theta(x_t, t)\|^2\right]
$$
```

→ 转换为 Notion equation block（LaTeX 格式）。

### 4. Callout 块

```
> [!TYPE] 文字内容
```

`TYPE` 可选值及对应样式：

| TYPE | 图标 | 背景色 | 适用场景 |
|------|------|--------|----------|
| `KEY` | 🔑 | 紫色 | 核心贡献、关键创新 |
| `TIP` | 💡 | 绿色 | 亮点提示、实用技巧 |
| `GOAL` | 🎯 | 橙色 | 研究目标、动机 |
| `RESULT` | 📊 | 黄色 | 关键结果、数据指标 |
| `METHOD` | 🔧 | 灰色 | 方法说明 |
| `NOTE` | 📝 | 蓝色 | 备注信息 |
| `INFO` | ℹ️ | 蓝色 | 背景信息 |
| `WARNING` | ⚠️ | 红色 | 警告、局限性 |
| `PAPER` | 📄 | 默认 | 论文相关 |

**示例：**
```
> [!KEY] 本文首次提出将扩散模型与流匹配统一在同一理论框架下，显著提升采样效率。
> [!GOAL] 解决现有文本到图像模型在细粒度语义控制方面的不足。
> [!RESULT] 在 GenEval 基准上达到 0.87，超越 DALL·E 3 等主流模型。
```

### 5. Toggle 折叠块（三种形式）

**普通 Toggle**（无标题级别样式）：
```
<toggle>标题文字
内容行 1
内容行 2
- 列表项
</toggle>
```

**可折叠标题 heading_2**（用于每个条目的外层 toggle）：
```
<toggle>## [条目标题](链接)
内容...
<toggle>🔧 子toggle
内容...
</toggle>
</toggle>
```

**可折叠标题 heading_3**（用于较小分组）：
```
<toggle>### 子方向标题
内容...
</toggle>
```

→ `<toggle>## ` 转换为 `heading_2` with `is_toggleable: true`（点击可折叠展开）
→ `<toggle>### ` 转换为 `heading_3` with `is_toggleable: true`
→ `<toggle>标题` 转换为普通 `toggle` block

**嵌套 Toggle（支持多层嵌套）**：
- 内层 `<toggle>` 正确识别，深度追踪防止被外层 `</toggle>` 提前截断
- 递归解析子块，内层 toggle 仍可使用所有 Markdown 语法

**注意：**
- `<toggle>` 与标题文字在同一行（无换行）
- `</toggle>` 必须单独成行
- 内容可包含任意支持的 Markdown 语法，包括嵌套 toggle

### 6. 行内格式

| 语法 | 效果 |
|------|------|
| `` `代码` `` | 行内代码（code annotation）|
| `==高亮文字==` | 黄色高亮背景 |
| `**粗体**` | 粗体 |
| `*斜体*` | 斜体 |
| `[文字](url)` | 超链接 |

---

## 二、整体页面结构规范（重要）

**板块标题使用 heading_1（`#`），每个具体条目使用 toggle heading_2（`<toggle>## `）**

```markdown
# AI 日报 — YYYY-MM-DD

> 每日精选 AI 企业动态、学术前沿、HCI 研究与工具推荐

---

# ① AI 企业资讯

<toggle>## [新闻标题](链接)
内容...
</toggle>

---

# ② AIGC 学术前沿

<toggle>## [论文标题](链接)
内容...
</toggle>

---

# ③ 人机交互前沿

<toggle>## [论文标题](链接)
内容...
</toggle>

---

# ④ AI 工具推荐

<toggle>## [工具名称](链接)
内容...
</toggle>

---

*由 AutoAIBlog 自动生成 | YYYY-MM-DD*
```

---

## 三、AIGC 论文条目格式规范

**每篇论文用外层 `<toggle>## ` 包裹，内部嵌套两个子 toggle：**

```markdown
<toggle>## [论文完整英文标题](arXiv链接)
![图1: 模型整体架构图](图片URL1)
![图2: 与SOTA方法的性能对比](图片URL2)
> [!KEY] 核心贡献：一句话概括本文最大创新点（突出与现有工作的本质差异，≤50字）

**作者**：xxx, xxx et al. | **发布**：YYYY-MM-DD | **领域**：图像生成 / LLM / HCI 等

**研究动机**

当前该方向的主流方法存在什么局限（2-3段连贯叙述性文字，不要用列表）...

本文为解决这些问题从什么角度切入...

<toggle>🔧 方法详解
**核心框架/模型名称**：XXX

- **[组件1名称]**：功能与设计细节
- **[组件2名称]**：功能与设计细节
- **[训练策略]**：关键训练设计（如有）
- **关键技术亮点**：与已有工作最本质的差异
</toggle>

<toggle>📊 实验与结果
- **评估基准**：数据集 / benchmark 名称
- **定量结果**：在 [指标] 上达到 [数值]，超越 [对比] [幅度]
- **消融发现**：最关键的消融实验结论
- **局限性**：作者承认的主要局限
</toggle>

**论文预览**：[HuggingFace Papers](HF URL)
</toggle>
```

**图片规范：**
- 每篇论文尽量嵌入 2-3 张图（架构图、流程图、实验对比图）
- alt 文字用简短中文描述，如「图1: 模型整体架构」「图2: 消融实验结果」
- 仅使用来自 huggingface.co、arxiv.org、论文项目主页的图片 URL
- 禁止使用网站 logo、广告图、人物照片

---

## 四、HCI 论文条目格式规范

**比 AIGC 多一个用户研究 toggle 和讨论 toggle：**

```markdown
<toggle>## [工作完整标题](链接)
![系统界面截图](图片URL)
> [!GOAL] 研究问题：本工作聚焦解决的核心 HCI 问题（≤45字）

**来源**：CHI 2025 / UIST 2025 / arXiv YYYY-MM
**作者**：xxx et al.

**研究背景与动机**

当前该交互场景用户面临的痛点（2-3段连贯叙述，不用列表）...

<toggle>🔬 系统与方法设计
**系统名称**：XXX

- **[组件/功能1]**：交互方式与设计思路
- **[界面/交互设计]**：HCI 创新点
- **关键技术支撑**：AI/ML 如何集成
</toggle>

<toggle>👥 用户研究
- **研究设计**：被试数量、任务类型、实验范式
- **量化结果**：效率/错误率/主观评分的具体数值（如 NASA-TLX、SUS）
- **定性发现**：用户反馈与行为观察的代表性洞察
- **统计检验**：显著性水平（p<0.05）、效果量
</toggle>

<toggle>💬 讨论与设计启示
- **核心贡献**：在 HCI 领域的理论/实践贡献
- **设计启示**：对未来系统/界面设计的指导意义
- **局限性**：样本规模、任务限定、泛化性等
- **未来工作**：作者提到的后续方向
</toggle>
</toggle>
```

---

## 五、新闻条目格式规范

```markdown
<toggle>## [新闻标题](来源链接)
![图片简短描述](图片URL)
> [!INFO] 核心要点：一句话概括最重要的信息（≤40字）

新闻摘要（2-3句中文，说明事件详情、意义、行业影响）
</toggle>
```

---

## 六、工具条目格式规范

```markdown
<toggle>## [工具名称](官网/GitHub链接)
![工具界面或Logo](图片URL)
> [!TIP] 核心功能：一句话描述工具的核心价值（≤40字）

**功能**：详细介绍工具能做什么（2-3句）
**适用**：目标用户群体与使用场景
**费用**：免费 / 付费（价格）/ 开源（协议）
</toggle>
```

---

## 七、重要约束

1. **链接真实性**：只使用原始数据中出现的真实链接，严禁虚构 URL
2. **图片条件**：仅当原始数据中含图片URL时才嵌入，无则不加占位符
3. **图片质量**：只用架构图、系统图、结果图；不用 logo、广告、人物照片
4. **图片 alt 文字**：必须提供简短中文描述，作为 Notion 图片 caption
5. **论文数量**：AIGC 严格 3 篇，HCI 严格 3 篇
6. **工具限制**：严格 3 个，不含基础模型（GPT、Gemini、Claude 等）
7. **Callout 简洁性**：每个 callout 的文字控制在 50 字以内
8. **Toggle 层级**：条目外层用 `<toggle>## `（heading_2 toggleable），内层子节用普通 `<toggle>`
9. **</toggle> 换行**：`</toggle>` 必须单独占一行
10. **语言**：所有解读、摘要、分析必须使用中文；技术术语可保留英文
11. **不输出多余内容**：最终输出为纯 Markdown，不含解释性说明、代码围栏包裹等
