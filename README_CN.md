# PaperPilot (顶级会议论文收集与前沿热点分类系统)

**中文版 (Chinese)** | [**English Version**](./README.md)

一个自动化的顶会论文收集、匹配和摘要分类提取系统。用于批量收集 CVPR, ICCV, NeurIPS, ECCV, ICML, ICLR, ICRA, IROS, RSS, CoRL 等顶级会议的中稿论文，并根据论文的**摘要 (Abstract)** 对其进行灵活、自定义的前沿热点(如具身智能、多模态大模型、视觉分割)自动划分保存。

## 功能特性
- **双引擎架构设计**: "抓取(Collect)" 与 "二次分类(Categorize)" 分离，互不干扰，支持从历史数据(JSON)再次随时重新分类。
- **智能摘要补全**: 如果官方数据未给出论文摘要，分类引擎能够在匹配时智能反向去源站点爬取并补全缺失的 Abstract 数据。
- **多会议支持**: 灵活支持 10+ 个顶级计算机科学和机器人学会议。
- **动态前沿热点划分**: 基于灵活的 `config/topics.json` 正则匹配词典。可由用户随时针对最新研究热点（如"生成式AI"、"大语言模型"等）增减匹配规则自动生成分类子集与总览报告。
- **灵活存储**: 支持导出详尽 JSON 数据格式与 SQLite 数据库存储（支持全文搜索和复杂查询）。
- **断点防丢及去重**: 优化至单批次实时保存策略（每抓取50篇自动保存）。

## 项目结构

```
PaperPilot/
 collectors/          # 会议网页收集解析器
    base.py          
    cvf_collector.py 
    openreview_collector.py 
    pmlr_collector.py       
    ieee_collector.py       
    rss_collector.py        
    factory.py       # 收集器工厂
 classifier/          # 原 arXiv 分类模块
    arxiv_category_classifier.py
 matchers/            # 论文匹配器
    arxiv_matcher.py # arXiv匹配引擎
 storage/             # 数据存储模块
    paper_storage.py # SQLite及JSON落盘存储
 utils/               # 工具模块
    config_loader.py 
 core/                # 核心处理系统
    coordinator.py   # 主协调器(负责抓取流程调度)
    categorizer.py   # 摘要匹配分类器(负责主题分析调度)
 config/              # 配置文件
    conferences.json # 官方顶会采集配置
    topics.json      # 领域热点(正则表达式)自定义分类词典
 csv_to_bib.py        # CSV 转 BibTeX 工具 (支持 Zotero 导入)
 main.py              # 主入口点 (集成了 collect, categorize 和 export 子命令)
 pyproject.toml       # 项目配置
 README.md            # 英文文档
 README_CN.md         # 中文文档
```

## 安装部署

### 前提条件

- Python 3.8+
- [uv](https://github.com/astral-sh/uv) (强烈推荐) 或 pip

### 快速安装 (使用 uv)

1. 克隆项目：
```bash
git clone https://github.com/你的用户名/PaperPilot.git
cd PaperPilot
```

2. 安装依赖并自动建立虚拟环境：
```bash
uv sync
```

## 核心使用方法

本系统主要通过 `main.py` 的子命令 `collect` 和 `categorize` 进行驱动。

### 阶段一：收集顶会论文 (`collect`)

`collect` 命令能够从各大会议首页或 ArXiv 获取完整的论文信息：

1. 列出所有支持收集的会议及其可用年份：
```bash
uv run python main.py collect --list-conferences
```

2. 收集某个会议单一年度的论文，并实时导出 JSON 进度文件：
```bash
# 收集 CVPR 2025 年录用的论文
uv run python main.py collect --conference CVPR --year 2025 --export-json papers.json --verbose
```

3. 批量收集并缓存至不同数据库：
```bash
uv run python main.py collect --conference CVPR,ICCV --year 2023,2024 --db-path archive.db
```

### 阶段二：前沿热点领域分类 (`categorize`)

基于刚抓取下来的 `.json` 会议长列表，你可以基于 **Abstract（最精细的数据维度）** 将它们划分成几个不同的文件来快速审阅研究趋势。

```bash
uv run python main.py categorize --input papers.json --fill-abstracts --verbose
```

**关键参数说明：**
- `--input`: 阶段一生成的总览 JSON 文件。
- `--fill-abstracts`: (强烈推荐) 如果某些论文仅抓到了 PDF/URL 而没有 Abstract 解析，它会自动通过多线程对这篇论文的源网页进行访问填补摘要。
- `--topic-config`: 指定分类的规则词典，默认为 `config/topics.json`。

**执行结果：**
它会在项目下创建一个名为 `Papers_By_Hot_Topic/` 的文件夹，其中不仅有根据学术热点切割后的具体 JSON，还会包含一份汇总分类的分析报告（如 `HotTopic_Report.md`）。

### 阶段三：导出为 CSV / BibTeX (`export`)

将数据库中的论文导出为 CSV 格式，并可选择将其转换为支持导入 Zotero 的 BibTeX 文件。

```bash
# 导出所有论文为 CSV 并转换为 BibTeX
uv run python main.py export --output-csv all_papers.csv --output-bib all_papers.bib --include-abstract --dedupe

# 仅导出指定会议的论文
uv run python main.py export --conference CVPR,ICCV --output-bib cv_papers.bib
```

**关键参数说明：**
- `--output-csv`: 输出的 CSV 文件路径。
- `--output-bib`: 输出的 BibTeX 文件路径。
- `--conference`: 逗号分隔的会议名称，用于过滤导出结果。
- `--dedupe`: 对 BibTeX 条目去重（根据 arXiv ID 或标题+年份）。
- `--include-abstract`: 在 BibTeX 的 note 字段中包含摘要。
- `--include-keywords`: 在 BibTeX 的 note 字段中包含关键词。
- `--include-topics`: 在 BibTeX 的 note 字段中包含分类主题。
- `--include-arxiv-id`: 在 BibTeX 的 note 字段中包含 arXiv ID。

---

## 进阶与客制化

### 调整研究热点标签 (`config/topics.json`)
当前系统默认预制了 **"具身智能"**、**"多模态大模型"**、**"扩散模型"** 等十大分类。你可以随时按照正则规范添加你当下的学术关注点：

```json
{
  "01_多模态大模型与基础模型_(Multimodal_LLM_VLM)": ["\\bllm\\b", "vision-language model"],
  "02_具身智能与机器人_(Embodied_AI_Robotics)": ["embodied", "manipulation", "locomotion"],
  "11_你需要的新方向_(New_Topic)": ["federated learning", "few-shot learning"]
}
```
保存配置后再次执行 `uv run python main.py categorize ...` 即可重新根据新的词典快速梳理成百上千篇论文。
