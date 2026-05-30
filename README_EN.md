<div align="center">

# :newspaper: News Sentiment Analyst

**A-share Financial News → Structured Data → LLM Sentiment Analysis → Trading Direction**

**[中文版](README.md)**

<br/>

![Python](https://img.shields.io/badge/python-3.10+-blue?logo=python&logoColor=white)
![akshare](https://img.shields.io/badge/akshare-1.10+-orange?logo=apache&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-1.5+-150458?logo=pandas&logoColor=white)
![pyarrow](https://img.shields.io/badge/pyarrow-10.0+-D4AA37?logo=apache&logoColor=white)
![status](https://img.shields.io/badge/status-production-brightgreen)
![tests](https://img.shields.io/badge/tests-30%20passed-brightgreen)
![license](https://img.shields.io/badge/license-Apache%202.0-blue)

<br/>

[Install](#-install) &ensp;|&ensp; [Quick Start](#-quick-start) &ensp;|&ensp; [Architecture](#-architecture) &ensp;|&ensp; [Output](#-output-format) &ensp;|&ensp; [Tests](#-tests)

</div>

<br/>

---

## :dart: What It Does

```
 Eastmoney(200)                          ┌──────────────┐
 Futu(50)         ──→  Extract  ──→     │  Parquet Output │  ──→  Agent + LLM  ──→  Trading Signal
 Tonghuashun(20)      (stocks/sectors)   │  (Structured)   │       (7-step CoT)
                                         └──────────────┘
```

> **Design principle**: Skill handles data collection and structuring. AI handles analysis and decisions.

<br/>

## :sparkles: Core Capabilities

<table>
<tr>
<td width="50%">

### :mag: Multi-Source Collection
- Eastmoney global news: 200 items/req
- Futu NiuNiu news: 50 items/req
- Tonghuashun live: 20 items/req
- Auto dedup by title, ~225 unique news

</td>
<td width="50%">

### :brain: Smart Extraction
- **Stock codes**: regex + 5500 name matching
- **Sectors**: 10 category keyword matching
- **Entities**: numbers / dates / policies / events
- **Related news**: cross-sector auto linking

</td>
</tr>
<tr>
<td width="50%">

### :chart_with_upwards_trend: LLM Prompt
- 15-year A-share quant analyst persona
- 7-step causal reasoning Chain-of-Thought
- 4 Few-shot examples (incl. counter-intuitive)
- Structured JSON output + confidence score

</td>
<td width="50%">

### :package: Standard Output
- Parquet format, 10 standard fields
- `result_json` contains full prompt
- Incremental scoring writeback
- Stable primary key design

</td>
</tr>
</table>

<br/>

## :rocket: Install

### Option A: openskills (Recommended)

```bash
npm install -g openskills
openskills install <your-username>/news-sentiment-analyst
```

### Option B: Manual Install (Global)

```bash
git clone <your-repo-url>
cd news-sentiment-analyst

# Copy skill to Claude Code global directory
cp -r skills/news-sentiment-analyst ~/.claude/skills/news-sentiment-analyst

# Install Python dependencies
pip install -r ~/.claude/skills/news-sentiment-analyst/requirements.txt
```

### Option C: Project-Level Install

```bash
git clone <your-repo-url>
cd news-sentiment-analyst

# Copy skill to project .claude directory
mkdir -p .claude/skills
cp -r skills/news-sentiment-analyst .claude/skills/

# Install Python dependencies
pip install -r .claude/skills/news-sentiment-analyst/requirements.txt
```

> :information_source: After installation, restart Claude Code. The skill will be auto-discovered.

### Verify Installation

```bash
ls ~/.claude/skills/news-sentiment-analyst/
# Should show: SKILL.md  scripts/  references/  ...

cd ~/.claude/skills/news-sentiment-analyst/scripts
python test.py
```

<br/>

## :zap: Quick Start

### Via Claude Code

After installation, just say to Claude:

> "Analyze today's A-share news and its impact on trading"

Claude will automatically trigger the skill: collect → extract → score → report.

### Via Python Code

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/news-sentiment-analyst/scripts"))

from build import run_full_pipeline, score_single_news

# 1. Collect news + market context, generate prompts
pipeline = run_full_pipeline(
    trade_date="2026-05-29",
    news_type="all",
    max_news_count=50,
    output_dir="output"
)

# 2. Score each news with LLM
for item in pipeline["prompts"]:
    prompt = item["prompt"]
    llm_response = "<LLM JSON response>"
    score = score_single_news(pipeline["parquet_path"], item["idx"], llm_response)
    print(f"  {item['news_title'][:30]}... → {score['sentiment']} {score['trading_direction']}")
```

<details>
<summary>:eyes: Collect only (no scoring)</summary>

```python
from build import run

result = run(
    {"trade_date": "2026-05-29", "news_type": "all"},
    config={"max_news_count": 50, "save_parquet": True, "output_dir": "output"}
)
```

</details>

<br/>

## :brain: LLM Analysis Framework

Each news prompt requires the LLM to analyze via **7-step causal reasoning**:

| Step | Content | Description |
|:----:|---------|-------------|
| 1 | **Core Event** | Fact or rumor? New or old information? |
| 2 | **Transmission Path** | Event → Sector → Stock, how does it propagate? |
| 3 | **Timeliness** | Immediate or delayed? Already priced in? |
| 4 | **Certainty** | Official announcement > Media report > Market rumor |
| 5 | **Market Context** | In current environment, is this a headwind or tailwind? |
| 6 | **Cross-Correlation** | Does it resonate or offset with other news? |
| 7 | **Counter-Intuitive Check** | Looks bullish but actually bearish? "Buy the rumor, sell the news"? |

### Output Format

```json
{
    "sentiment": "positive / negative / neutral",
    "impact_level": "high / medium / low",
    "trading_direction": "bullish / bearish / hold",
    "confidence": 0.85,
    "reason": "Causal reasoning within 100 chars"
}
```

<details>
<summary>:eyes: Few-shot Examples</summary>

**Bullish** — Central bank RRR cut:
> RRR cut releases trillion-yuan liquidity, clear stabilization intent in a shrinking-volume market, directly bullish for banks and brokerages, effective within 1-2 days
> → `positive / high / bullish / 0.85`

**Bearish** — CSRC investigation:
> Investigation + high prior gains + major shareholder selling triple bearish overlay, likely limit-down at open, spillover to same-sector peers
> → `negative / high / bearish / 0.90`

**Counter-Intuitive** — Net profit up 50%:
> 50% profit growth below market expectation of 60%, prior rally already priced in expectations, good news becomes bad news
> → `negative / high / bearish / 0.80`

</details>

<br/>

## :building_construction: Architecture

<div align="center">

```
┌─────────────────────────────────┐         ┌─────────────────────────────────┐
│       Skill Layer (build.py)    │         │       Agent Layer (External AI) │
│                                 │         │                                 │
│   🌐 Collect 3 data sources     │         │   🧠 Read LLM prompts           │
│   🔍 Extract stocks/sectors     │  Parquet │   📈 7-step causal reasoning    │
│   📝 Generate FinGPT prompts    │ ──────► │   ✏️ Writeback scores            │
│   📦 Output structured Parquet  │         │   📊 Output trading signals     │
│                                 │         │                                 │
└─────────────────────────────────┘         └─────────────────────────────────┘
```

</div>

<br/>

## :outbox_tray: Output Format

### Parquet Output Location

```
output/news_trading_YYYY-MM-DD.parquet
```

Default output directory: `output/` (customizable via `output_dir` parameter)

### Parquet Fields

| Field | Required | Type | Description |
|:-----:|:--------:|------|-------------|
| `trade_date` | conditional | string | Date YYYY-MM-DD |
| `build_id` | ✓ | string | `NSA` |
| `build_name` | ✓ | string | `News Sentiment Analyst` |
| `target_id` | | string | Stock code or `sector_news_id` |
| `result_type` | ✓ | string | `news_analysis` / `summary` |
| `result_value` | ✓ | string | `pending_ai_analysis` → `data_ready` |
| `result_json` | | string | Full news data + LLM prompt |
| `source_data_date` | | string | Original data date |
| `data_version` | ✓ | string | `1.0.0` |
| `update_time` | ✓ | string | Result generation time |

<details>
<summary>:eyes: result_json Full Structure</summary>

**Before scoring (news_analysis record):**
```json
{
    "news_id": "macro_0",
    "news_title": "News title",
    "news_source": "Eastmoney",
    "publish_time": "2026-05-29 09:00:00",
    "news_type": "macro",
    "stock_codes": [{"code": "000001", "name": "Ping An Bank", "source": "name_match"}],
    "sectors": ["Finance"],
    "entities": {
        "numbers": [{"value": 30, "type": "percentage"}],
        "policies": ["RRR cut"],
        "events": ["Earnings"]
    },
    "affected_targets": [{"target_id": "000001", "target_name": "Ping An Bank", "target_type": "stock"}],
    "ai_analysis_prompt": "You are a senior A-share quant analyst with 15 years..."
}
```

**After scoring:**
```json
{
    "llm_score": {
        "sentiment": "positive",
        "impact_level": "high",
        "trading_direction": "bullish",
        "confidence": 0.85,
        "reason": "RRR cut releases trillion-yuan liquidity..."
    }
}
```

</details>

<br/>

## :card_file_box: Project Structure

```
.
├── README.md               ← Chinese version
├── README_EN.md            ← English version (this file)
├── .gitignore
└── skills/
    └── news-sentiment-analyst/
        ├── SKILL.md               ← Claude Code skill definition (required)
        ├── LICENSE.txt            ← Apache 2.0 License
        ├── .openskills.json       ← openskills metadata
        ├── requirements.txt       ← Python dependencies
        ├── scripts/
        │   ├── build.py           ← Main: collect + extract + structure + Parquet
        │   ├── sentiment.py       ← LLM prompt generation + response parsing
        │   └── test.py            ← 30 tests (unit + integration)
        └── references/
            ├── api_guide.md       ← API documentation
            └── data_sources.md    ← AKShare data source details
```

<br/>

## :test_tube: Tests

```bash
cd skills/news-sentiment-analyst/scripts
python test.py
```

```
======================================================================
Test Summary
======================================================================
  Passed: 30
  Failed: 0
  Total: 30

  ✓ All tests passed!
```

| Test | Coverage |
|------|----------|
| `test_validate_input` | Valid input, missing fields, wrong format, invalid type |
| `test_stock_code_extraction` | Regex extraction, name matching, no-code text |
| `test_sector_extraction` | 10 sector keyword matching, no-sector fallback |
| `test_entity_extraction` | Numbers / dates / policies / events |
| `test_news_structuring` | Full structuring pipeline + prompt generation |
| `test_parquet_output` | Parquet field completeness validation |
| `test_agent_call` | `run()` standard entry point |
| `test_full_flow` | End-to-end pipeline |
| `test_llm_prompt_generation` | CoT guidance + few-shot + JSON format |
| `test_llm_response_parsing` | Standard JSON / markdown code blocks / mixed text / invalid input / field normalization |

<br/>

## :gear: Parameters

| Parameter | Type | Default | Description |
|-----------|------|:-------:|-------------|
| `trade_date` | string | *required* | Trading date YYYY-MM-DD |
| `news_type` | string | `all` | `macro` / `industry` / `company` / `all` |
| `target_id` | string | `None` | Stock code (for individual stock news) |
| `max_news_count` | int | `50` | Maximum news items |
| `output_dir` | string | `output` | Output directory |

<br/>

## :earth_asia: Data Sources

| Source | API | Count | Features |
|--------|-----|:-----:|----------|
| Eastmoney | `ak.stock_info_global_em()` | 200 | Global news, broad coverage |
| Futu NiuNiu | `ak.stock_info_global_futu()` | 50 | HK/US stock perspective |
| Tonghuashun | `ak.stock_info_global_ths()` | 20 | Live feed, high timeliness |

> :information_source: Uses [AKShare](https://github.com/akfamily/akshare) open-source API, no registration required. See [data_sources.md](skills/news-sentiment-analyst/references/data_sources.md) for details.

<br/>

## :warning: Notes

- AKShare has rate limits, 1-2 second interval between requests
- News is a real-time snapshot, no historical data support
- Auto dedup by title, only one copy per cross-source duplicate
- Market context auto-collected (indices, sector performance)
- Related news auto-matched (same sector or same stock)

<br/>

---

<div align="center">

**Apache License 2.0**

Copyright 2026 Theroix

</div>
