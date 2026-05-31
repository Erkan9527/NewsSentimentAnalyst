<div align="center">

# :newspaper: News Sentiment Analyst

**A 股财经新闻 → 结构化数据 → LLM 情感分析 → 交易方向判断**

**[English Version](README_EN.md)**

<br/>

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white)
![akshare](https://img.shields.io/badge/akshare-1.10+-orange?logo=apache&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-1.5+-150458?logo=pandas&logoColor=white)
![pyarrow](https://img.shields.io/badge/pyarrow-10.0+-D4AA37?logo=apache&logoColor=white)
![status](https://img.shields.io/badge/status-production-brightgreen)
![tests](https://img.shields.io/badge/tests-30%20passed-brightgreen)
![license](https://img.shields.io/badge/license-Apache%202.0-blue)

<br/>

[安装](#-安装) &ensp;|&ensp; [快速开始](#-快速开始) &ensp;|&ensp; [架构](#-架构) &ensp;|&ensp; [输出格式](#-输出格式) &ensp;|&ensp; [测试](#-测试)

</div>

<br/>

---

## :dart: 功能概述

```
 东方财富(200)                           ┌──────────────┐
 富途牛牛(50)       ──→  提取实体  ──→   │  Parquet 输出  │  ──→  Agent + LLM  ──→  交易信号
 同花顺(20)            (股票/板块/实体)   │  (结构化数据)  │       (7步因果推理)
                                         └──────────────┘
```

> **设计原则**：Skill 负责数据采集和结构化，AI 负责分析和决策。

<br/>

## :sparkles: 核心能力

<table>
<tr>
<td width="50%">

### :mag: 多源采集
- 东方财富全球快讯：200 条/次
- 富途牛牛快讯：50 条/次
- 同花顺全球直播：20 条/次
- 按标题自动去重，约 225 条独立新闻

</td>
<td width="50%">

### :brain: 智能提取
- **股票代码**：正则 + 5500 只股票名称匹配
- **板块识别**：10 大板块关键词匹配
- **实体提取**：数字 / 日期 / 政策 / 事件
- **关联新闻**：跨板块自动关联

</td>
</tr>
<tr>
<td width="50%">

### :chart_with_upwards_trend: LLM Prompt
- 15 年 A 股量化分析师人设
- 7 步因果推理 Chain-of-Thought
- 4 个 Few-shot 示例（含反直觉案例）
- 结构化 JSON 输出 + 置信度评分

</td>
<td width="50%">

### :package: 标准输出
- Parquet 格式，10 个标准字段
- `result_json` 包含完整 prompt
- 支持增量打分写回
- 稳定主键设计

### :signal_strength: 选股信号
- 基于新闻情感自动生成买卖信号
- 股票代码 + 公司名称严格对应
- 置信度过滤（默认 >= 0.5）
- 按置信度降序排列

</td>
</tr>
</table>

<br/>

## :rocket: 安装

### 方式一：openskills（推荐）

```bash
npm install -g openskills
openskills install <your-username>/news-sentiment-analyst
```

### 方式二：手动安装（全局）

```bash
git clone <your-repo-url>
cd news-sentiment-analyst

# 复制 skill 到 Claude Code 全局目录
cp -r skills/news-sentiment-analyst ~/.claude/skills/news-sentiment-analyst

# 安装 Python 依赖
pip install -r ~/.claude/skills/news-sentiment-analyst/requirements.txt
```

### 方式三：项目级安装

```bash
git clone <your-repo-url>
cd news-sentiment-analyst

# 复制 skill 到项目 .claude 目录
mkdir -p .claude/skills
cp -r skills/news-sentiment-analyst .claude/skills/

# 安装 Python 依赖
pip install -r .claude/skills/news-sentiment-analyst/requirements.txt
```

> :information_source: 安装后重启 Claude Code，skill 将被自动发现。

### 验证安装

```bash
ls ~/.claude/skills/news-sentiment-analyst/
# 应显示：SKILL.md  scripts/  references/  ...

cd ~/.claude/skills/news-sentiment-analyst/scripts
python test.py
```

<br/>

## :zap: 快速开始

### 通过 Claude Code

安装后，直接对 Claude 说：

> "分析今日 A 股新闻及其对交易的影响"

Claude 会自动触发 skill：采集 → 提取 → 打分 → 报告。

### 通过 Python 代码

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/news-sentiment-analyst/scripts"))

from build import run_full_pipeline, score_single_news

# 1. 采集新闻 + 市场背景，生成 prompt
pipeline = run_full_pipeline(
    trade_date="2026-05-29",
    news_type="all",
    max_news_count=50,
    output_dir="output"
)

# 2. 逐条 LLM 打分
for item in pipeline["prompts"]:
    prompt = item["prompt"]
    llm_response = "<LLM JSON response>"
    score = score_single_news(pipeline["parquet_path"], item["idx"], llm_response)
    print(f"  {item['news_title'][:30]}... → {score['sentiment']} {score['trading_direction']}")
```

<details>
<summary>:eyes: 仅采集（不打分）</summary>

```python
from build import run

result = run(
    {"trade_date": "2026-05-29", "news_type": "all"},
    config={"max_news_count": 50, "save_parquet": True, "output_dir": "output"}
)
```

</details>

<br/>

## :brain: LLM 分析框架

每条新闻的 prompt 要求 LLM 按 **7 步因果推理** 分析：

| 步骤 | 内容 | 说明 |
|:----:|------|------|
| 1 | **核心事件** | 事实还是传闻？新信息还是旧信息？ |
| 2 | **传导路径** | 事件 → 板块 → 个股，如何传导？ |
| 3 | **时效性** | 即时影响还是滞后？已反映在股价中？ |
| 4 | **确定性** | 官方公告 > 媒体报道 > 市场传闻 |
| 5 | **市场背景** | 当前环境下是雪上加霜还是逆势利好？ |
| 6 | **交叉关联** | 和其他新闻形成共振还是对冲？ |
| 7 | **反直觉检查** | 表面利好实际利空？"利好出尽"？ |

### 输出格式

```json
{
    "sentiment": "positive / negative / neutral",
    "impact_level": "high / medium / low",
    "trading_direction": "bullish / bearish / hold",
    "confidence": 0.85,
    "reason": "100字以内的因果推理"
}
```

<details>
<summary>:eyes: Few-shot 示例</summary>

**利好** — 央行降准：
> 降准释放万亿流动性，市场缩量背景下有明确维稳意图，直接利好银行和券商，1-2日内见效
> → `positive / high / bullish / 0.85`

**利空** — 证监会立案调查：
> 立案调查+前期涨幅大+大股东减持三重利空叠加，开盘大概率跌停，同行业可能被波及
> → `negative / high / bearish / 0.90`

**反直觉** — 净利润增长50%：
> 净利润增长50%低于市场预期60%，前期涨幅已透支，利好出尽变利空
> → `negative / high / bearish / 0.80`

</details>

<br/>

## :building_construction: 架构

<div align="center">

```
┌─────────────────────────────────┐         ┌─────────────────────────────────┐
│       Skill 层 (build.py)       │         │       Agent 层 (外部 AI)        │
│                                 │         │                                 │
│   🌐 采集 3 个数据源             │         │   🧠 读取 LLM prompt            │
│   🔍 提取股票/板块/实体          │  Parquet │   📈 7步因果推理                 │
│   📝 生成 FinGPT 风格 prompt     │ ──────► │   ✏️ 写回评分结果                │
│   📦 输出结构化 Parquet          │         │   📊 输出交易信号                │
│                                 │         │                                 │
└─────────────────────────────────┘         └─────────────────────────────────┘
```

</div>

<br/>

## :outbox_tray: 输出格式

### Parquet 输出目录

```
output/news_trading_YYYY-MM-DD.parquet
```

默认输出到 `output/` 目录，可通过 `output_dir` 参数自定义。

### Parquet 字段

| 字段 | 必填 | 类型 | 说明 |
|:----:|:----:|------|------|
| `trade_date` | 视情况 | string | 交易日期 YYYY-MM-DD |
| `build_id` | ✓ | string | `NSA` |
| `build_name` | ✓ | string | `News Sentiment Analyst` |
| `target_id` | | string | 股票代码或 `板块_news_id` |
| `result_type` | ✓ | string | `news_analysis` / `summary` |
| `result_value` | ✓ | string | `pending_ai_analysis` → `data_ready` |
| `result_json` | | string | 完整新闻数据 + LLM prompt |
| `source_data_date` | | string | 原始数据日期 |
| `data_version` | ✓ | string | `1.0.0` |
| `update_time` | ✓ | string | 结果生成时间 |

### 选股信号列表

`generate_signal_list()` 从打分后的 Parquet 中提取交易信号：

```python
from build import generate_signal_list

signals = generate_signal_list("output/news_trading_2026-05-30.parquet", min_confidence=0.5)
```

输出格式：

```json
[
    {
        "code": "300750",
        "name": "宁德时代",
        "direction": "bullish",
        "confidence": 0.75,
        "sentiment": "positive",
        "impact_level": "high",
        "reason": "换电站扩张超预期，验证商业模式可行性",
        "news_title": "宁德时代：巧克力换电累计落站..."
    }
]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | string | 股票代码（6 位） |
| `name` | string | 公司名称 |
| `direction` | string | `bullish` / `bearish` |
| `confidence` | float | 置信度 0.0-1.0 |
| `sentiment` | string | `positive` / `negative` / `neutral` |
| `impact_level` | string | `high` / `medium` / `low` |
| `reason` | string | 分析理由（截断 80 字） |
| `news_title` | string | 来源新闻标题（截断 30 字） |

<details>
<summary>:eyes: result_json 完整结构</summary>

**打分前 news_analysis 记录：**
```json
{
    "news_id": "macro_0",
    "news_title": "新闻标题",
    "news_source": "东方财富",
    "publish_time": "2026-05-29 09:00:00",
    "news_type": "macro",
    "stock_codes": [{"code": "000001", "name": "平安银行", "source": "name_match"}],
    "sectors": ["金融"],
    "entities": {
        "numbers": [{"value": 30, "type": "percentage"}],
        "policies": ["降准"],
        "events": ["财报"]
    },
    "affected_targets": [{"target_id": "000001", "target_name": "平安银行", "target_type": "stock"}],
    "ai_analysis_prompt": "你是一位拥有15年经验的A股量化金融分析师..."
}
```

**打分后：**
```json
{
    "llm_score": {
        "sentiment": "positive",
        "impact_level": "high",
        "trading_direction": "bullish",
        "confidence": 0.85,
        "reason": "降准释放万亿流动性..."
    }
}
```

</details>

<br/>

## :card_file_box: 项目结构

```
.
├── README.md               ← 中文版
├── README_EN.md            ← 英文版
├── .gitignore
└── skills/
    └── news-sentiment-analyst/
        ├── SKILL.md               ← Claude Code skill 定义（必需）
        ├── LICENSE.txt            ← Apache 2.0 许可证
        ├── .openskills.json       ← openskills 元数据
        ├── requirements.txt       ← Python 依赖
        ├── scripts/
        │   ├── build.py           ← 主脚本：采集 + 提取 + 结构化 + Parquet
        │   ├── sentiment.py       ← LLM prompt 生成 + 响应解析
        │   └── test.py            ← 测试脚本（30 个测试用例）
        └── references/
            ├── api_guide.md       ← API 文档
            └── data_sources.md    ← AKShare 数据源说明
```

<br/>

## :test_tube: 测试

```bash
cd skills/news-sentiment-analyst/scripts
python test.py
```

```
======================================================================
测试汇总
======================================================================
  通过: 30
  失败: 0
  总计: 30

  ✓ 所有测试通过！
```

| 测试 | 覆盖内容 |
|------|----------|
| `test_validate_input` | 正常输入、缺少字段、错误格式、错误类型 |
| `test_stock_code_extraction` | 正则提取、名称匹配、无代码文本 |
| `test_sector_extraction` | 10 大板块关键词匹配、无板块回退 |
| `test_entity_extraction` | 数字 / 日期 / 政策 / 事件 |
| `test_news_structuring` | 完整结构化流水线 + prompt 生成 |
| `test_parquet_output` | Parquet 字段完整性验证 |
| `test_agent_call` | `run()` 标准入口 |
| `test_full_flow` | 端到端流水线 |
| `test_llm_prompt_generation` | CoT 引导 + few-shot + JSON 格式 |
| `test_llm_response_parsing` | 标准 JSON / markdown 代码块 / 混合文本 / 无效输入 / 字段标准化 |

<br/>

## :gear: 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|:------:|------|
| `trade_date` | string | *必填* | 交易日期 YYYY-MM-DD |
| `news_type` | string | `all` | `macro` / `industry` / `company` / `all` |
| `target_id` | string | `None` | 股票代码（获取个股新闻） |
| `max_news_count` | int | `50` | 最大新闻条数 |
| `output_dir` | string | `output` | 输出目录 |

<br/>

## :earth_asia: 数据源

| 数据源 | API | 条数 | 特点 |
|--------|-----|:----:|------|
| 东方财富 | `ak.stock_info_global_em()` | 200 | 全球快讯，覆盖广 |
| 富途牛牛 | `ak.stock_info_global_futu()` | 50 | 港美股视角 |
| 同花顺 | `ak.stock_info_global_ths()` | 20 | 实时直播，时效性强 |

> :information_source: 使用 [AKShare](https://github.com/akfamily/akshare) 开源 API，无需注册。详见 [data_sources.md](skills/news-sentiment-analyst/references/data_sources.md)。

<br/>

## :warning: 注意事项

- AKShare 接口有频率限制，建议请求间隔 1-2 秒
- 新闻为实时快照，不支持历史数据
- 按标题自动去重，跨源同一条新闻只保留一条
- 市场背景自动采集（大盘指数、板块涨跌）
- 关联新闻自动匹配（同板块或同股票的其他新闻）
- 本项目不构成任何形式的证券投资咨询或建议。项目所有输出，包括但不限于任何交易方向、标的筛选，仅为算法逻辑的示例性展示，不代表任何投资建议或承诺
- 明确反对使用者将本项目输出用于真实交易
- 任何使用者因参考本项目代码、逻辑或示例输出而进行真实交易，必须自行承担由此产生的全部盈亏和法律风险。作者的实盘操作与任何公开的代码及示例无关
- 本项目不提供任何形式的实时信号推送服务，不建立任何投资交流群组

<br/>

---

<div align="center">

**Apache License 2.0**

Copyright 2026 Theroix

</div>
