# PaperPilot (顶级会议论文收集与热点分类系统)

**中文版 (Chinese)** | [**English Version**](./README.md)

自动采集 CVPR、ICCV、NeurIPS、ICLR、ICML、CoRL、RSS 等顶会论文，支持研究热点分类、CSV/BibTeX 导出。

纯 JSON 存储，无需配置数据库。

---

## 快速上手

```bash
# 安装依赖
pip install requests beautifulsoup4

# 采集 CVPR 2024
python main.py collect CVPR -y 2024

# 采集 NeurIPS 2024
python main.py collect NeurIPS -y 2024

# 导出 BibTeX 用于导入 Zotero
python main.py export -i papers_NeurIPS_2024.json --output-bib neurips.bib --include-abstract
```

---

## 使用实例

### 1. 采集单个会议

```bash
python main.py collect CVPR -y 2024
# → papers_CVPR_2024.json  （含摘要、作者、PDF 链接）
```

### 2. 采集多个年份，分别保存

```bash
python main.py collect NeurIPS -y 2023,2024
# → papers_NeurIPS_2023.json
# → papers_NeurIPS_2024.json
```

### 3. 采集多个会议，合并为一个文件

```bash
python main.py collect CVPR,ICCV -y 2023,2024 -o cv_papers.json
# → cv_papers.json  （CVPR 2023 + CVPR 2024 + ICCV 2023 + ICCV 2024 合并）
```

### 4. 一次性采集所有会议

```bash
python main.py collect ALL -y 2024
# → papers_CVPR_2024.json, papers_ICCV_2024.json, ...
```

### 5. 快速测试（每个会议只取 10 篇）

```bash
python main.py collect ALL -y 2024 -n 10
# 快速验证所有采集器是否正常工作
```

### 6. 完整工作流：采集 → 分类 → 导出 BibTeX

```bash
# 第一步：采集 CVPR 2024
python main.py collect CVPR -y 2024

# 第二步：按研究热点分类
python main.py categorize -i papers_CVPR_2024.json
# → Papers_By_Hot_Topic/01_多模态大模型与基础模型.json
# → Papers_By_Hot_Topic/02_具身智能与机器人.json
# → Papers_By_Hot_Topic/HotTopic_Report.md

# 第三步：批量导出为 BibTeX（可直接导入 Zotero）
python main.py export --input-dir Papers_By_Hot_Topic --output-dir Bibtex --include-abstract
# → Bibtex/01_多模态大模型与基础模型.bib
# → Bibtex/02_具身智能与机器人.bib
```

### 7. 调试某个采集器

```bash
python main.py collect RSS -y 2023 -n 3 -v
# 详细模式会显示 HTTP 请求和解析过程
```

---

## 命令说明

### `list` — 查看支持的会议

```bash
python main.py list
```

### `collect` — 采集论文

```bash
python main.py collect [会议名...] [选项]

# 会议名:  CVPR ICCV NeurIPS ICLR ICML CoRL RSS
#          或 ALL（所有会议）

# 选项:
  -y, --year YEAR      年份，逗号分隔（默认今年）
  -o, --output FILE    合并为一个 JSON 文件
  -n, --max-papers N   每个会议限取 N 篇（测试模式）
  -v, --verbose        显示调试日志
```

### `categorize` — 按热点分类

```bash
python main.py categorize -i papers.json

# 选项:
  -o, --output-dir DIR      输出目录（默认 Papers_By_Hot_Topic）
  --topic-config FILE        热点关键词配置文件（默认 config/topics.json）
```

### `export` — 导出 CSV / BibTeX

```bash
python main.py export -i papers.json --output-bib papers.bib

# 选项:
  --output-csv FILE         导出为 CSV
  --output-bib FILE         导出为 BibTeX
  --dedupe                  去除重复条目
  --include-abstract        在 BibTeX 中包含摘要
  --include-keywords        在 BibTeX 中包含关键词
  --include-topics          在 BibTeX 中包含主题分类
  --include-arxiv-id        在 BibTeX 中包含 arXiv ID

# 批量模式：转换整个目录的 JSON
python main.py export --input-dir Papers_By_Hot_Topic --output-dir Bibtex
```

---

## 自定义热点分类

编辑 `config/topics.json`，按正则表达式定义关注方向，系统会匹配论文标题和摘要：

```json
{
  "01_多模态大模型与基础模型": [
    "\\bllm\\b",
    "vision-language model",
    "visual language model",
    "multimodal"
  ],
  "02_具身智能与机器人": [
    "embodied",
    "manipulation",
    "locomotion",
    "reinforcement learning"
  ],
  "03_扩散模型与生成": [
    "diffusion model",
    "image generation",
    "text-to-image",
    "video generation"
  ]
}
```

修改后重新运行 `categorize` 即可按新规则重新归类已有的 JSON 文件。

---

## 项目结构

```
PaperPilot/
  main.py              # 命令行入口
  collectors.py        # 所有会议采集器
  classifier.py        # 热点分类器 + 关键词提取
  utils/
    csv_to_bib.py      # CSV 转 BibTeX
  config/
    topics.json        # 热点关键词正则配置
```

---

## 数据源

| 会议 | 来源 | 类型 |
|-----------|--------|------|
| CVPR, ICCV | openaccess.thecvf.com | CVF HTML |
| NeurIPS | papers.nips.cc | 一览页 |
| ICLR | api2.openreview.net | OpenReview v2 API |
| ICML, CoRL | proceedings.mlr.press | PMLR HTML |
| RSS | roboticsproceedings.org | 逐篇解析 |

---

## 依赖

```bash
pip install requests beautifulsoup4
```

Python 3.8+。

## License

MIT License。详见 [LICENSE](./LICENSE)。
