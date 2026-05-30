# News Sentiment Analyst - API 指南

## 数据源说明

本项目使用 **AKShare** 作为数据源（开源免费，无需注册，`pip install akshare` 即可使用）。所有新闻和市场数据均由 `build.py` 内部通过 AKShare 接口自主采集。

AKShare 是国内最主流的开源 A 股数据接口库，数据源覆盖东方财富、同花顺、富途等主流财经平台（详见 [data_sources.md](data_sources.md)）。

### 新闻接口

| 接口 | 来源 | 条数 | 返回字段 |
|------|------|:----:|----------|
| `ak.stock_info_global_em()` | 东方财富全球快讯 | 200 | 标题/摘要/发布时间/链接 |
| `ak.stock_info_global_futu()` | 富途牛牛快讯 | 50 | 标题/内容/发布时间/链接 |
| `ak.stock_info_global_ths()` | 同花顺全球直播 | 20 | 标题/内容/发布时间/链接 |
| `ak.stock_news_em(symbol)` | 东方财富个股新闻 | 20 | 新闻标题/新闻内容/发布时间/文章来源 |

> :warning: `stock_news_em(symbol)` 用于获取**特定股票**的新闻，`symbol` 参数为股票代码（如 `"000001"`），不是关键词。

### 辅助接口

| 接口 | 功能 |
|------|------|
| `ak.stock_info_a_code_name()` | A 股股票名称→代码映射（5500+只） |

### 新闻来源识别

从链接域名自动识别来源：

```python
domain_map = {
    "finance.eastmoney.com": "东方财富",
    "news.futunn.com": "富途牛牛",
    "news.10jqka.com.cn": "同花顺",
    "finance.sina.com.cn": "新浪财经",
}
```

## 输出字段说明

### Parquet 标准字段

| 字段 | 必须 | 类型 | 说明 |
|------|:----:|------|------|
| trade_date | 视情况 | string | 结果所属日期 |
| build_id | 是 | string | NSA |
| build_name | 是 | string | News Sentiment Analyst |
| target_id | 否 | string | 股票代码或 `板块_news_id` |
| result_type | 是 | string | news_analysis / summary |
| result_value | 是 | string | pending_ai_analysis / data_ready |
| result_json | 否 | string | 完整结果 JSON |
| source_data_date | 否 | string | 原始数据日期 |
| data_version | 是 | string | 1.0.0 |
| update_time | 是 | string | 结果生成时间 |

### result_json 内容

每条新闻的 `result_json` 包含：
- `news_id` / `news_title` / `news_source` / `publish_time`
- `news_type`（macro/industry/company）
- `stock_codes`：提取的股票代码列表
- `sectors`：匹配的板块列表
- `entities`：关键实体（数字/日期/政策/事件）
- `ai_analysis_prompt`：FinGPT 风格 LLM prompt

## LLM Prompt 设计

### 结构

```
System: 15年经验的A股量化金融分析师
Analysis Framework: 7步因果推理（核心事件/传导路径/时效性/确定性/市场背景/交叉关联/反直觉检查）
Confidence标准: 0.8-1.0 / 0.5-0.8 / 0.2-0.5 / 0.0-0.2
Few-shot: 4个示例（利好/利空/中性/反直觉，含CoT推理）
News: 待分析新闻（标题+内容+股票+板块+实体）
Output: JSON（sentiment/impact/direction/confidence/reason）
```

### 输出格式

```json
{
    "sentiment": "positive/negative/neutral",
    "impact_level": "high/medium/low",
    "trading_direction": "bullish/bearish/hold",
    "confidence": 0.0-1.0,
    "reason": "100字以内的因果推理"
}
```

## 调用示例

### 基础调用

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.claude/skills/news-sentiment-analyst/scripts"))

from build import run

result = run(
    {"trade_date": "2026-05-29", "news_type": "all"},
    config={"max_news_count": 50, "save_parquet": True, "output_dir": "output"}
)
```

### 查询特定股票

```python
result = run(
    {"trade_date": "2026-05-29", "news_type": "company", "target_id": "000001"}
)
```

### Agent 打分

```python
from sentiment import parse_llm_response

for news in result["structured_news"]:
    prompt = news["ai_analysis_prompt"]
    llm_response = call_llm(prompt)  # 外部 LLM
    score = parse_llm_response(llm_response)
```

## 选股信号

### generate_signal_list()

从打分后的 Parquet 中提取交易信号列表。

```python
from build import generate_signal_list

signals = generate_signal_list(parquet_path, min_confidence=0.5)
```

**参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `parquet_path` | string | *必填* | Parquet 文件路径 |
| `min_confidence` | float | `0.5` | 最低置信度过滤 |

**返回值：** `List[Dict]`，每个元素包含：

```json
{
    "code": "300750",           // 股票代码
    "name": "宁德时代",         // 公司名称（自动补全）
    "direction": "bullish",     // bullish / bearish
    "confidence": 0.75,         // 置信度
    "sentiment": "positive",    // 情感
    "impact_level": "high",     // 影响级别
    "reason": "...",            // 分析理由（80字）
    "news_title": "..."         // 来源新闻（30字）
}
```

**特性：**
- 自动过滤 `hold` 方向（只保留 bullish/bearish）
- 自动补全公司名称（从股票映射表查找）
- 按置信度降序排列
- 同一股票出现在多条新闻中时，各自独立输出

## 注意事项

1. **频率限制**：AKShare 免费接口有频率限制，建议每次请求间隔 1-2 秒
2. **数据时效**：新闻数据为实时快照，不支持历史查询
3. **去重**：按标题自动去重，跨源同一条新闻只保留一条
4. **个股新闻**：`stock_news_em` 有 pyarrow 兼容性问题，可能失败
