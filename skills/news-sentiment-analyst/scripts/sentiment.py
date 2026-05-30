import json
import re
from typing import Dict, List, Optional

FEW_SHOT_EXAMPLES = """
【示例 1】利好 — 需要分析传导路径和时间窗口
新闻：央行宣布降准0.5个百分点，释放长期资金约1万亿元
市场背景：当日A股三大指数微跌，成交额缩量至8000亿
分析：
1. 核心事件：央行降准，货币政策宽松信号
2. 传导路径：降准 → 银行可贷资金增加 → 利差扩大 → 银行股利好；同时流动性释放 → 市场风险偏好提升 → 成长股受益
3. 时效性：政策公布后1-2个交易日市场会反应，但利好已被部分预期（市场此前有降准预期），实际涨幅可能有限
4. 确定性：央行官方公告，确定性极高
5. 市场情绪：在市场缩量下跌背景下公布，有维稳意图，信号明确
结论：{"sentiment":"positive","impact_level":"high","trading_direction":"bullish","confidence":0.85,"reason":"降准释放万亿流动性，在市场缩量背景下有明确维稳意图，直接利好银行和券商，1-2日内见效"}

【示例 2】利空 — 需要区分是情绪面还是基本面
新闻：某上市公司被证监会立案调查，涉嫌信息披露违规
市场背景：该股前期涨幅较大，近期有大股东减持公告
分析：
1. 核心事件：监管处罚，公司治理问题
2. 传导路径：立案调查 → 投资者信心崩塌 → 恐慌抛售 → 股价暴跌；叠加前期涨幅大+大股东减持，抛压更重
3. 时效性：即时影响，开盘大概率跌停
4. 溢出效应：可能波及同行业公司，尤其是前期涨幅大、有类似问题的标的
5. 确定性：证监会公告，确定性极高
结论：{"sentiment":"negative","impact_level":"high","trading_direction":"bearish","confidence":0.90,"reason":"立案调查+前期涨幅大+大股东减持三重利空叠加，开盘大概率跌停，同行业可能被波及"}

【示例 3】中性 — 需要判断是否有隐藏信号
新闻：今日全国天气晴朗，适合出行
市场背景：无特殊市场事件
分析：
1. 内容相关性：与金融市场无直接关联
2. 间接影响：可能微弱利好旅游、航空，但天气是短期变量，不改变基本面
3. 市场反应：不会引起显著交易行为
4. 隐藏信号：无
结论：{"sentiment":"neutral","impact_level":"low","trading_direction":"hold","confidence":0.10,"reason":"天气事件与金融市场无传导路径，不影响交易决策"}

【示例 4】反直觉 — 需要逆向思考
新闻：某龙头公司发布财报，净利润同比增长50%
市场背景：该股前期已大涨30%，市场预期增长60%
分析：
1. 核心事件：财报超市场预期吗？不，50%增长低于市场预期的60%
2. 传导路径：低于预期 → 分析师下调目标价 → 机构抛售 → 股价下跌
3. 时效性：财报公布后即时反应，通常在盘后或次日开盘
4. 关键点：表面看是利好（增长50%），但实际上是利空（低于预期）
5. 市场情绪：前期涨幅已透支增长预期，财报是"利好出尽"
结论：{"sentiment":"negative","impact_level":"high","trading_direction":"bearish","confidence":0.80,"reason":"净利润增长50%低于市场预期60%，前期涨幅已透支，利好出尽变利空"}
"""

SYSTEM_PROMPT = """你是一位拥有15年经验的A股量化金融分析师。你的任务不是简单地对新闻进行情感分类，而是像真正的分析师一样思考：找因果、串逻辑、给结论。

分析框架（必须逐步思考）：

1. **核心事件识别**：这条新闻到底说了什么？是事实还是传闻？是新的还是旧的信息？
2. **传导路径分析**：这个事件如何传导到股价？路径是什么？（事件→板块→个股，还是事件→情绪→资金流→股价？）
3. **时效性判断**：影响是即时的还是滞后的？已经反映在股价里了吗？新闻是盘前还是盘后发布的？
4. **确定性评估**：信息有多确定？官方公告 > 媒体报道 > 市场传闻 > 分析师观点
5. **市场背景关联**：结合当日市场背景，这条新闻在当前环境下意味着什么？是雪上加霜还是逆势利好？
6. **交叉关联**：这条新闻和其他新闻有没有关联？是否形成共振或对冲？
7. **反直觉检查**：表面看是利好/利空，但实际呢？有没有"利好出尽"或"利空出尽"的可能？

confidence 评分标准：
- 0.8-1.0：官方公告+明确数字+直接影响+市场背景支撑
- 0.5-0.8：间接影响+行业趋势+需要推理
- 0.2-0.5：模糊描述+传闻+间接关联+不确定因素多
- 0.0-0.2：与市场无关+信息不足+无法推理

输出规则：
- reason 控制在 100 字以内，必须包含因果推理，不要只写"利好/利空"
- 必须基于新闻事实和市场背景分析，不要臆测
- 如果新闻与市场无关，直接给 neutral/low/hold/0.0-0.2"""


def generate_llm_prompt(
    title: str,
    content: str,
    stock_codes: Optional[List] = None,
    sectors: Optional[List] = None,
    entities: Optional[Dict] = None,
    market_context: Optional[str] = None,
    related_news: Optional[List[str]] = None,
) -> str:
    stock_str = (
        ", ".join([f"{s.get('name', '')}({s.get('code', '')})" for s in stock_codes])
        if stock_codes
        else "无明确个股"
    )
    sector_str = ", ".join(sectors) if sectors else "无明确板块"

    entity_parts = []
    entities = entities or {}
    if entities.get("numbers"):
        nums = [f"{n['value']}{n.get('type', '')}" for n in entities["numbers"][:3]]
        entity_parts.append(f"关键数字: {', '.join(nums)}")
    if entities.get("policies"):
        entity_parts.append(f"政策关键词: {', '.join(entities['policies'][:3])}")
    if entities.get("events"):
        entity_parts.append(f"事件类型: {', '.join(entities['events'][:3])}")
    entity_str = "; ".join(entity_parts) if entity_parts else "无"

    context_section = ""
    if market_context:
        context_section = f"\n【当日市场背景】\n{market_context}\n"

    related_section = ""
    if related_news:
        related_items = "\n".join(f"  - {n}" for n in related_news[:5])
        related_section = f"\n【关联新闻（可能影响判断）】\n{related_items}\n"

    return f"""{SYSTEM_PROMPT}

{FEW_SHOT_EXAMPLES}
{context_section}{related_section}
【待分析新闻】
标题：{title}
内容：{content[:500]}
涉及股票：{stock_str}
相关板块：{sector_str}
关键信息：{entity_str}

请按以下步骤逐步分析后输出 JSON：
1. 这条新闻的核心事件是什么？是事实还是传闻？
2. 传导路径：事件 → 板块 → 个股，具体怎么传导？
3. 时效性：影响是即时的还是滞后的？已经反映在股价里了吗？
4. 结合当日市场背景，这条新闻在当前环境下意味着什么？
5. 和其他新闻有没有关联？形成共振还是对冲？
6. 有没有反直觉的可能？表面利好实际利空？
7. 给出最终判断

输出格式（只输出 JSON）：
{{"sentiment":"positive/negative/neutral","impact_level":"high/medium/low","trading_direction":"bullish/bearish/hold","confidence":0.0-1.0,"reason":"100字以内的因果推理"}}"""


def parse_llm_response(response_text: str) -> Dict:
    default = {
        "sentiment": "neutral",
        "impact_level": "low",
        "trading_direction": "hold",
        "confidence": 0.0,
        "reason": "LLM 响应解析失败",
        "method": "llm_parse_error",
    }

    if not response_text or not response_text.strip():
        return default

    data = None

    try:
        data = json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    if data is None:
        code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if code_match:
            try:
                data = json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

    if data is None:
        json_matches = re.findall(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_matches:
            for match in reversed(json_matches):
                try:
                    data = json.loads(match)
                    break
                except json.JSONDecodeError:
                    continue

    if data is None:
        return default

    sentiment = str(data.get("sentiment", "neutral")).lower()
    if sentiment not in ("positive", "negative", "neutral"):
        sentiment = "neutral"

    impact = str(data.get("impact_level", "low")).lower()
    if impact not in ("high", "medium", "low"):
        impact = "low"

    direction = str(data.get("trading_direction", "hold")).lower()
    if direction not in ("bullish", "bearish", "hold"):
        direction = "hold"

    try:
        confidence = float(data.get("confidence", 0.0))
        confidence = round(max(0.0, min(1.0, confidence)), 2)
    except (ValueError, TypeError):
        confidence = 0.0

    reason = str(data.get("reason", ""))[:150]

    return {
        "sentiment": sentiment,
        "impact_level": impact,
        "trading_direction": direction,
        "confidence": confidence,
        "reason": reason,
        "method": "llm",
    }
