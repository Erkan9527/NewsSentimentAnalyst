from datetime import datetime
from typing import Dict, List, Optional
import logging
import json
import os
import sys
import re
import akshare as ak
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sentiment import generate_llm_prompt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STOCK_CODE_PATTERN = re.compile(r'(?<!\d)(688\d{3}|[036]\d{5})(?!\d)')

_stock_name_to_code = {}


def _load_stock_mapping() -> Dict[str, str]:
    global _stock_name_to_code
    if _stock_name_to_code:
        return _stock_name_to_code

    try:
        stock_info = ak.stock_info_a_code_name()
        for _, row in stock_info.iterrows():
            name = row.get('name', '')
            code = row.get('code', '')
            if name and code:
                _stock_name_to_code[name] = code
        logger.info(f"加载了 {len(_stock_name_to_code)} 只股票的名称映射")
    except Exception as e:
        logger.warning(f"加载股票映射失败: {e}")

    return _stock_name_to_code


def validate_input(input_data: Dict) -> None:
    if not isinstance(input_data, dict):
        raise ValueError("input_data 必须是字典类型")

    if "trade_date" not in input_data:
        raise ValueError("缺少必要字段: trade_date")

    trade_date = input_data["trade_date"]
    try:
        datetime.strptime(trade_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("trade_date 格式必须为 YYYY-MM-DD")

    valid_news_types = ["macro", "industry", "company", "all"]
    news_type = input_data.get("news_type", "all")
    if news_type not in valid_news_types:
        raise ValueError(f"news_type 必须是 {valid_news_types} 之一")


def _extract_source_from_url(url: str) -> str:
    from urllib.parse import urlparse
    domain_map = {
        "finance.eastmoney.com": "东方财富",
        "news.futunn.com": "富途牛牛",
        "news.10jqka.com.cn": "同花顺",
        "finance.sina.com.cn": "新浪财经",
        "kuaixun.eastmoney.com": "东方财富",
    }
    try:
        domain = urlparse(url).netloc
        return domain_map.get(domain, domain)
    except Exception:
        return "未知"


def collect_news(news_type: str = "all", target_id: Optional[str] = None) -> List[Dict]:
    news_list = []
    seen_titles = set()

    def _add_news(title, content, source, publish_time, url, news_type, target_id=None):
        if not title or title in seen_titles:
            return
        seen_titles.add(title)
        news_list.append({
            "news_id": f"{news_type}_{len(news_list)}",
            "news_title": title,
            "news_content": content or "",
            "news_source": source,
            "publish_time": publish_time or "",
            "news_type": news_type,
            "target_id": target_id or "",
            "data_platform": source,
            "url": url or "",
        })

    if news_type in ["macro", "all"]:
        try:
            df = ak.stock_info_global_em()
            for _, row in df.iterrows():
                url = row.get("链接", "")
                source = _extract_source_from_url(url)
                _add_news(
                    title=row.get("标题", ""),
                    content=row.get("摘要", ""),
                    source=source,
                    publish_time=row.get("发布时间", ""),
                    url=url,
                    news_type="macro",
                )
            logger.info(f"东方财富: {len(df)} 条新闻")
        except Exception as e:
            logger.warning(f"东方财富新闻获取失败: {e}")

        try:
            df = ak.stock_info_global_futu()
            for _, row in df.iterrows():
                url = row.get("链接", "")
                source = _extract_source_from_url(url)
                _add_news(
                    title=row.get("标题", ""),
                    content=row.get("内容", ""),
                    source=source,
                    publish_time=row.get("发布时间", ""),
                    url=url,
                    news_type="macro",
                )
            logger.info(f"富途牛牛: {len(df)} 条新闻")
        except Exception as e:
            logger.warning(f"富途新闻获取失败: {e}")

        try:
            df = ak.stock_info_global_ths()
            for _, row in df.iterrows():
                url = row.get("链接", "")
                source = _extract_source_from_url(url)
                _add_news(
                    title=row.get("标题", ""),
                    content=row.get("内容", ""),
                    source=source,
                    publish_time=row.get("发布时间", ""),
                    url=url,
                    news_type="macro",
                )
            logger.info(f"同花顺: {len(df)} 条新闻")
        except Exception as e:
            logger.warning(f"同花顺新闻获取失败: {e}")

    if news_type in ["company", "all"] and target_id:
        try:
            company_news = ak.stock_news_em(symbol=target_id)
            for _, row in company_news.head(20).iterrows():
                _add_news(
                    title=row.get("新闻标题", ""),
                    content=row.get("新闻内容", ""),
                    source="东方财富",
                    publish_time=row.get("发布时间", ""),
                    url="",
                    news_type="company",
                    target_id=target_id,
                )
        except Exception as e:
            logger.warning(f"个股新闻获取失败: {e}")

    logger.info(f"共采集 {len(news_list)} 条新闻（去重后）")
    return news_list


def extract_stock_codes_from_text(text: str) -> List[Dict]:
    if not text:
        return []

    results = []
    seen_codes = set()

    code_matches = STOCK_CODE_PATTERN.findall(text)
    for code in code_matches:
        if code not in seen_codes:
            seen_codes.add(code)
            results.append({
                "code": code,
                "name": "",
                "source": "regex"
            })

    stock_mapping = _load_stock_mapping()
    for name, code in stock_mapping.items():
        if len(name) >= 2 and name in text and code not in seen_codes:
            seen_codes.add(code)
            results.append({
                "code": code,
                "name": name,
                "source": "name_match"
            })

    return results


def extract_sectors_from_text(text: str) -> List[str]:
    sector_keywords = {
        "新能源": ["新能源", "光伏", "风电", "锂电池", "储能", "充电桩", "电动车"],
        "半导体": ["芯片", "半导体", "集成电路", "光刻机", "晶圆", "封装"],
        "医药": ["医药", "生物", "疫苗", "创新药", "医疗器械", "CRO"],
        "消费": ["消费", "白酒", "食品", "零售", "电商", "直播"],
        "金融": ["银行", "券商", "保险", "降准", "降息", "信贷"],
        "科技": ["科技", "人工智能", "AI", "云计算", "大数据", "5G"],
        "地产": ["地产", "房价", "楼市", "土地", "开发商", "物业"],
        "能源": ["石油", "天然气", "煤炭", "能源", "原油", "化工"],
        "军工": ["军工", "国防", "航天", "导弹", "战斗机", "航母"],
        "汽车": ["汽车", "新车", "销量", "自动驾驶", "智能网联"]
    }

    sectors = []
    for sector, keywords in sector_keywords.items():
        if any(kw in text for kw in keywords):
            sectors.append(sector)

    return sectors if sectors else ["market"]


def extract_key_entities(text: str) -> Dict:
    entities = {
        "numbers": [],
        "dates": [],
        "policies": [],
        "companies": [],
        "events": []
    }

    number_patterns = [
        (r'(\d+(?:\.\d+)?)\s*%', 'percentage'),
        (r'(\d+(?:\.\d+)?)\s*亿', 'amount_yi'),
        (r'(\d+(?:\.\d+)?)\s*万', 'amount_wan'),
        (r'(\d+(?:\.\d+)?)\s*元', 'price'),
    ]

    for pattern, num_type in number_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            entities["numbers"].append({
                "value": float(match),
                "type": num_type
            })

    date_patterns = [
        r'(\d{4})年(\d{1,2})月(\d{1,2})日',
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
        r'(\d{4})/(\d{1,2})/(\d{1,2})',
    ]

    for pattern in date_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            entities["dates"].append(f"{match[0]}-{match[1].zfill(2)}-{match[2].zfill(2)}")

    policy_keywords = ["降准", "降息", "加息", "限购", "限贷", "补贴", "税收", "监管", "审批"]
    for keyword in policy_keywords:
        if keyword in text:
            entities["policies"].append(keyword)

    event_keywords = {
        "财报": ["财报", "年报", "季报", "业绩", "营收", "净利润"],
        "政策": ["政策", "监管", "央行", "证监会", "发改委"],
        "技术": ["技术", "研发", "专利", "创新", "突破"],
        "市场": ["销量", "市占率", "需求", "供给", "库存"],
        "资本": ["融资", "IPO", "增发", "减持", "回购"],
    }

    for event_type, keywords in event_keywords.items():
        if any(kw in text for kw in keywords):
            entities["events"].append(event_type)

    return entities


def collect_market_context(trade_date: str) -> str:
    context_parts = []

    try:
        df_index = ak.stock_zh_index_daily_em(symbol="sh000001")
        if not df_index.empty:
            latest = df_index.iloc[-1]
            close = latest.get("close", 0)
            change_pct = latest.get("涨跌幅", 0)
            context_parts.append(f"上证指数: {close}点, 涨跌幅{change_pct}%")
    except Exception as e:
        logger.warning(f"获取上证指数失败: {e}")

    try:
        df_cy = ak.stock_zh_index_daily_em(symbol="sz399006")
        if not df_cy.empty:
            latest = df_cy.iloc[-1]
            close = latest.get("close", 0)
            change_pct = latest.get("涨跌幅", 0)
            context_parts.append(f"创业板指: {close}点, 涨跌幅{change_pct}%")
    except Exception as e:
        logger.warning(f"获取创业板指失败: {e}")

    try:
        df_sector = ak.stock_board_industry_name_em()
        if not df_sector.empty:
            top5 = df_sector.head(5)
            sectors = []
            for _, row in top5.iterrows():
                name = row.get("板块名称", "")
                pct = row.get("涨跌幅", 0)
                if name:
                    sectors.append(f"{name}({pct}%)")
            if sectors:
                context_parts.append(f"板块涨幅前5: {', '.join(sectors)}")
    except Exception as e:
        logger.warning(f"获取板块数据失败: {e}")

    return "; ".join(context_parts) if context_parts else "市场背景数据暂不可用"


def structure_news_for_ai(news: Dict, all_news_titles: Optional[List[str]] = None,
                          market_context: Optional[str] = None) -> Dict:
    title = news.get("news_title", "")
    content = news.get("news_content", "")
    full_text = f"{title} {content}"

    stock_codes = extract_stock_codes_from_text(full_text)
    sectors = extract_sectors_from_text(full_text)
    entities = extract_key_entities(full_text)

    related_news = []
    if all_news_titles:
        for other_title in all_news_titles:
            if other_title == title:
                continue
            other_sectors = extract_sectors_from_text(other_title)
            matching = [s for s in other_sectors if s in sectors and s != "market"]
            if matching:
                related_news.append(other_title)
            if len(related_news) >= 3:
                break

    return {
        "news_id": news.get("news_id", ""),
        "news_title": title,
        "news_content": content,
        "news_source": news.get("news_source", ""),
        "publish_time": news.get("publish_time", ""),
        "news_type": news.get("news_type", "industry"),
        "data_platform": news.get("data_platform", ""),
        "extracted_data": {
            "stock_codes": stock_codes,
            "sectors": sectors,
            "entities": entities
        },
        "ai_analysis_prompt": generate_llm_prompt(
            title, content, stock_codes, sectors, entities,
            market_context=market_context,
            related_news=related_news
        )
    }


def save_to_parquet(result: Dict, output_dir: str = "output") -> str:
    os.makedirs(output_dir, exist_ok=True)

    trade_date = result.get("trade_date", "")
    build_id = "NSA"
    build_name = "News Sentiment Analyst"

    records = []

    for news in result.get("structured_news", []):
        affected_targets = []
        for stock in news.get("extracted_data", {}).get("stock_codes", []):
            affected_targets.append({
                "target_id": stock["code"],
                "target_name": stock.get("name", ""),
                "target_type": "stock"
            })
        for sector in news.get("extracted_data", {}).get("sectors", []):
            affected_targets.append({
                "target_id": sector,
                "target_name": sector,
                "target_type": "sector"
            })

        news_id = news.get("news_id", "")
        if affected_targets:
            first_target = affected_targets[0]["target_id"]
            if first_target in ("market",) or first_target in [
                s["target_id"] for s in affected_targets if s["target_type"] == "sector"
            ]:
                target_id = f"{first_target}_{news_id}" if news_id else first_target
            else:
                target_id = first_target
        else:
            target_id = f"market_{news_id}" if news_id else "market"

        records.append({
            "trade_date": trade_date,
            "build_id": build_id,
            "build_name": build_name,
            "target_id": target_id,
            "result_type": "news_analysis",
            "result_value": "pending_ai_analysis",
            "result_json": json.dumps({
                "news_id": news.get("news_id"),
                "news_title": news.get("news_title"),
                "news_source": news.get("news_source"),
                "publish_time": news.get("publish_time"),
                "news_type": news.get("news_type"),
                "stock_codes": news.get("extracted_data", {}).get("stock_codes", []),
                "sectors": news.get("extracted_data", {}).get("sectors", []),
                "entities": news.get("extracted_data", {}).get("entities", {}),
                "affected_targets": affected_targets,
                "ai_analysis_prompt": news.get("ai_analysis_prompt", "")
            }, ensure_ascii=False),
            "source_data_date": trade_date,
            "data_version": result.get("data_version", "1.0.0"),
            "update_time": result.get("update_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        })

    summary = result.get("summary", {})
    records.append({
        "trade_date": trade_date,
        "build_id": build_id,
        "build_name": build_name,
        "target_id": "market",
        "result_type": "summary",
        "result_value": "data_ready",
        "result_json": json.dumps(summary, ensure_ascii=False),
        "source_data_date": trade_date,
        "data_version": result.get("data_version", "1.0.0"),
        "update_time": result.get("update_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    })

    df = pd.DataFrame(records)
    parquet_path = os.path.join(output_dir, f"news_trading_{trade_date}.parquet")
    df.to_parquet(parquet_path, index=False, engine='pyarrow')

    logger.info(f"结果已保存到: {parquet_path}")
    return parquet_path


def run(input_data: Dict, config: Optional[Dict] = None) -> Dict:
    validate_input(input_data)

    config = config or {}
    max_news_count = config.get("max_news_count", 50)
    save_parquet = config.get("save_parquet", True)
    output_dir = config.get("output_dir", "output")

    trade_date = input_data["trade_date"]
    news_type = input_data.get("news_type", "all")
    target_id = input_data.get("target_id")

    logger.info(f"开始处理 {trade_date} 的新闻数据，类型: {news_type}")

    _load_stock_mapping()

    news_list = collect_news(news_type, target_id)
    news_list = news_list[:max_news_count]

    if not news_list:
        logger.warning("未采集到新闻数据")
        return {
            "trade_date": trade_date,
            "news_count": 0,
            "structured_news": [],
            "summary": {
                "stock_codes_found": [],
                "sectors_found": [],
                "news_by_type": {"macro": 0, "industry": 0, "company": 0}
            },
            "data_version": "1.0.0",
            "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    market_context = collect_market_context(trade_date)
    logger.info(f"市场背景: {market_context[:100]}...")

    all_titles = [n.get("news_title", "") for n in news_list]
    structured_news = []
    for news in news_list:
        structured = structure_news_for_ai(news, all_titles, market_context)
        structured_news.append(structured)

    all_stock_codes = set()
    all_sectors = set()
    news_by_type = {"macro": 0, "industry": 0, "company": 0}

    for news in structured_news:
        for stock in news.get("extracted_data", {}).get("stock_codes", []):
            all_stock_codes.add(stock["code"])
        for sector in news.get("extracted_data", {}).get("sectors", []):
            all_sectors.add(sector)
        news_type_key = news.get("news_type", "industry")
        if news_type_key in news_by_type:
            news_by_type[news_type_key] += 1

    result = {
        "trade_date": trade_date,
        "news_count": len(structured_news),
        "structured_news": structured_news,
        "summary": {
            "stock_codes_found": list(all_stock_codes),
            "sectors_found": list(all_sectors),
            "news_by_type": news_by_type,
            "total_stock_codes": len(all_stock_codes),
            "total_sectors": len(all_sectors)
        },
        "data_version": "1.0.0",
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ai_instructions": {
            "task": "请分析每条新闻的情感和交易方向",
            "output_format": {
                "news_id": "新闻ID",
                "sentiment": "positive/negative/neutral",
                "impact_level": "high/medium/low",
                "trading_direction": "bullish/bearish/hold",
                "reason": "分析理由"
            }
        }
    }

    if save_parquet:
        parquet_path = save_to_parquet(result, output_dir)
        result["parquet_path"] = parquet_path

    logger.info(f"数据准备完成: {len(structured_news)} 条新闻")
    logger.info(f"发现 {len(all_stock_codes)} 只股票代码, {len(all_sectors)} 个板块")

    return result


def get_pending_prompts(parquet_path: str) -> List[Dict]:
    df = pd.read_parquet(parquet_path)
    pending = []
    for idx, row in df[df["result_type"] == "news_analysis"].iterrows():
        if row["result_value"] == "pending_ai_analysis":
            data = json.loads(row["result_json"])
            pending.append({
                "idx": idx,
                "news_id": data.get("news_id", ""),
                "news_title": data.get("news_title", ""),
                "prompt": data.get("ai_analysis_prompt", ""),
            })
    return pending


def score_single_news(parquet_path: str, idx: int, llm_response: str) -> Dict:
    from sentiment import parse_llm_response

    score = parse_llm_response(llm_response)
    df = pd.read_parquet(parquet_path)

    df.at[idx, "result_value"] = "data_ready"

    existing_json = json.loads(df.at[idx, "result_json"])
    existing_json["llm_score"] = {
        "sentiment": score["sentiment"],
        "impact_level": score["impact_level"],
        "trading_direction": score["trading_direction"],
        "confidence": score["confidence"],
        "reason": score["reason"],
    }
    df.at[idx, "result_json"] = json.dumps(existing_json, ensure_ascii=False)

    df.to_parquet(parquet_path, index=False)
    return score


def generate_signal_list(parquet_path: str, min_confidence: float = 0.5) -> List[Dict]:
    df = pd.read_parquet(parquet_path)
    signals = []

    for _, row in df[df["result_type"] == "news_analysis"].iterrows():
        if row["result_value"] != "data_ready":
            continue
        rj = json.loads(row["result_json"])
        score = rj.get("llm_score", {})
        if not score or score.get("confidence", 0) < min_confidence:
            continue
        direction = score.get("trading_direction", "hold")
        if direction == "hold":
            continue

        stock_codes = rj.get("stock_codes", [])
        if not stock_codes:
            continue

        for stock in stock_codes:
            code = stock.get("code", "")
            name = stock.get("name", "")
            if not code:
                continue
            if not name:
                stock_mapping = _load_stock_mapping()
                for sname, scode in stock_mapping.items():
                    if scode == code:
                        name = sname
                        break
            signals.append({
                "code": code,
                "name": name or code,
                "direction": direction,
                "confidence": score.get("confidence", 0),
                "sentiment": score.get("sentiment", "neutral"),
                "impact_level": score.get("impact_level", "low"),
                "reason": score.get("reason", "")[:80],
                "news_title": rj.get("news_title", "")[:30],
            })

    signals.sort(key=lambda x: x["confidence"], reverse=True)
    return signals


def run_full_pipeline(trade_date: str, news_type: str = "all",
                      target_id: Optional[str] = None,
                      max_news_count: int = 50,
                      output_dir: str = "output") -> Dict:
    result = run(
        {"trade_date": trade_date, "news_type": news_type, "target_id": target_id},
        config={"max_news_count": max_news_count, "save_parquet": True, "output_dir": output_dir}
    )

    parquet_path = result["parquet_path"]

    prompts = get_pending_prompts(parquet_path)

    return {
        "parquet_path": parquet_path,
        "news_count": result["news_count"],
        "prompts": prompts,
        "summary": result["summary"],
    }


if __name__ == "__main__":
    test_input = {
        "trade_date": "2026-05-28",
        "news_type": "all"
    }

    result = run(test_input, config={"save_parquet": True, "output_dir": "test_output"})

    print(f"\n数据准备完成:")
    print(f"  新闻数量: {result['news_count']}")
    print(f"  发现股票: {result['summary']['stock_codes_found']}")
    print(f"  发现板块: {result['summary']['sectors_found']}")

    if result.get('structured_news'):
        print(f"\n示例新闻（供 AI 分析）:")
        news = result['structured_news'][0]
        print(f"  标题: {news['news_title'][:50]}...")
        print(f"  股票: {[s['code'] for s in news['extracted_data']['stock_codes']]}")
        print(f"  板块: {news['extracted_data']['sectors']}")
        print(f"\n  AI 分析提示词:")
        print(f"  {news['ai_analysis_prompt'][:200]}...")
