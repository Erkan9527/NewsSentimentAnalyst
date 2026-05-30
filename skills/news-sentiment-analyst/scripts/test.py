import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build import (
    run, validate_input, collect_news, extract_stock_codes_from_text,
    extract_sectors_from_text, extract_key_entities, structure_news_for_ai,
    save_to_parquet
)
from sentiment import generate_llm_prompt, parse_llm_response


def test_validate_input():
    print("=" * 70)
    print("1. 测试输入校验")
    print("=" * 70)

    test_cases = [
        ({"trade_date": "2026-05-28"}, False, "正常输入"),
        ({}, True, "缺少 trade_date"),
        ({"trade_date": "20260528"}, True, "错误日期格式"),
        ({"trade_date": "2026-05-28", "news_type": "invalid"}, True, "错误 news_type"),
    ]

    passed = 0
    failed = 0

    for input_data, should_error, desc in test_cases:
        try:
            validate_input(input_data)
            if should_error:
                print(f"  ✗ {desc}: 应该报错但没有")
                failed += 1
            else:
                print(f"  ✓ {desc}: 校验通过")
                passed += 1
        except (ValueError, KeyError) as e:
            if should_error:
                print(f"  ✓ {desc}: 正确报错 - {e}")
                passed += 1
            else:
                print(f"  ✗ {desc}: 不应报错但报错了 - {e}")
                failed += 1

    return passed, failed


def test_stock_code_extraction():
    print("\n" + "=" * 70)
    print("2. 测试股票代码提取")
    print("=" * 70)

    test_cases = [
        ("平安银行000001.SZ发布财报", ["000001"], "正则提取代码"),
        ("贵州茅台600519今日涨停", ["600519"], "正则提取代码"),
        ("新能源汽车销量大增", [], "无代码文本"),
    ]

    passed = 0
    failed = 0

    for text, expected_codes, desc in test_cases:
        codes = extract_stock_codes_from_text(text)
        found_codes = [c["code"] for c in codes]

        if all(code in found_codes for code in expected_codes):
            print(f"  ✓ {desc}: 找到 {found_codes}")
            passed += 1
        else:
            print(f"  ✗ {desc}: 预期 {expected_codes}, 实际 {found_codes}")
            failed += 1

    return passed, failed


def test_sector_extraction():
    print("\n" + "=" * 70)
    print("3. 测试板块提取")
    print("=" * 70)

    test_cases = [
        ("新能源汽车销量大增，锂电池需求旺盛", ["新能源", "汽车"], "新能源+汽车"),
        ("芯片半导体技术突破", ["半导体"], "半导体板块"),
        ("央行降准利好银行券商", ["金融"], "金融板块"),
        ("今日天气晴朗", ["market"], "无板块"),
    ]

    passed = 0
    failed = 0

    for text, expected, desc in test_cases:
        sectors = extract_sectors_from_text(text)
        if all(s in sectors for s in expected):
            print(f"  ✓ {desc}: {sectors}")
            passed += 1
        else:
            print(f"  ✗ {desc}: 预期 {expected}, 实际 {sectors}")
            failed += 1

    return passed, failed


def test_entity_extraction():
    print("\n" + "=" * 70)
    print("4. 测试关键实体提取")
    print("=" * 70)

    test_text = "2026年5月28日，央行宣布降准0.5个百分点，释放资金约1万亿元。"
    entities = extract_key_entities(test_text)

    print(f"  ✓ 提取的实体:")
    print(f"    数字: {entities['numbers']}")
    print(f"    日期: {entities['dates']}")
    print(f"    政策: {entities['policies']}")
    print(f"    事件: {entities['events']}")

    return 1, 0


def test_news_structuring():
    print("\n" + "=" * 70)
    print("5. 测试新闻结构化（供 AI 分析）")
    print("=" * 70)

    mock_news = {
        "news_id": "test_001",
        "news_title": "平安银行000001.SZ发布2026年一季报，净利润增长30%",
        "news_content": "平安银行今日发布公告，2026年一季度净利润同比增长30%，超市场预期。",
        "news_source": "公司公告",
        "publish_time": "2026-05-28 10:00:00",
        "news_type": "company",
        "target_id": "000001",
        "data_platform": "东方财富"
    }

    try:
        result = structure_news_for_ai(mock_news)
        print(f"  ✓ 新闻结构化成功")
        print(f"    标题: {result['news_title'][:40]}...")
        print(f"    股票: {[s['code'] for s in result['extracted_data']['stock_codes']]}")
        print(f"    板块: {result['extracted_data']['sectors']}")
        print(f"    实体: {result['extracted_data']['entities']}")
        print(f"\n    AI 分析提示词:")
        print(f"    {result['ai_analysis_prompt'][:200]}...")
        return 1, 0
    except Exception as e:
        print(f"  ✗ 新闻结构化失败: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1


def test_parquet_output():
    print("\n" + "=" * 70)
    print("6. 测试 Parquet 输出（符合 BUILD 规则）")
    print("=" * 70)

    test_result = {
        "trade_date": "2026-05-28",
        "news_count": 1,
        "structured_news": [
            {
                "news_id": "test_001",
                "news_title": "测试新闻",
                "news_content": "测试内容",
                "news_source": "测试来源",
                "publish_time": "2026-05-28 10:00:00",
                "news_type": "company",
                "data_platform": "东方财富",
                "extracted_data": {
                    "stock_codes": [{"code": "000001", "name": "平安银行", "source": "regex"}],
                    "sectors": ["金融"],
                    "entities": {"numbers": [], "dates": [], "policies": [], "events": ["财报"]}
                },
                "ai_analysis_prompt": "请分析以下新闻..."
            }
        ],
        "summary": {
            "stock_codes_found": ["000001"],
            "sectors_found": ["金融"],
            "news_by_type": {"macro": 0, "industry": 0, "company": 1}
        },
        "data_version": "1.0.0",
        "update_time": "2026-05-28 10:00:00"
    }

    try:
        test_output_dir = "test_output"
        parquet_path = save_to_parquet(test_result, test_output_dir)

        if os.path.exists(parquet_path):
            print(f"  ✓ Parquet 文件创建成功: {parquet_path}")

            import pandas as pd
            df = pd.read_parquet(parquet_path)

            required_columns = [
                "trade_date", "build_id", "build_name", "target_id",
                "result_type", "result_value", "result_json",
                "source_data_date", "data_version", "update_time"
            ]

            missing_columns = [col for col in required_columns if col not in df.columns]

            if not missing_columns:
                print(f"  ✓ Parquet 字段完整（符合 BUILD 规则）")
                print(f"  ✓ 记录数量: {len(df)}")

                news_records = df[df["result_type"] == "news_analysis"]
                if len(news_records) > 0:
                    import json
                    data = json.loads(news_records.iloc[0]["result_json"])
                    print(f"  ✓ 包含股票代码: {data.get('stock_codes', [])}")
                    print(f"  ✓ 包含板块: {data.get('sectors', [])}")
                    print(f"  ✓ 包含 AI 提示词: {bool(data.get('ai_analysis_prompt'))}")

                os.remove(parquet_path)
                os.rmdir(test_output_dir)
                return 1, 0
            else:
                print(f"  ✗ Parquet 缺少字段: {missing_columns}")
                return 0, 1
        else:
            print(f"  ✗ Parquet 文件未创建")
            return 0, 1
    except Exception as e:
        print(f"  ✗ Parquet 输出失败: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1


def test_agent_call():
    print("\n" + "=" * 70)
    print("7. 测试 Agent 调用接口")
    print("=" * 70)

    try:
        input_data = {
            "trade_date": "2026-05-28",
            "news_type": "all"
        }

        config = {
            "max_news_count": 10,
            "save_parquet": False,
            "output_dir": "test_output"
        }

        result = run(input_data, config=config)

        required_keys = [
            "trade_date", "news_count", "structured_news",
            "summary", "data_version", "update_time", "ai_instructions"
        ]

        missing_keys = [key for key in required_keys if key not in result]

        if not missing_keys:
            print(f"  ✓ Agent 调用成功")
            print(f"  ✓ 返回结构完整")
            print(f"  ✓ 新闻数量: {result['news_count']}")
            print(f"  ✓ 发现股票: {result['summary']['stock_codes_found']}")
            print(f"  ✓ 发现板块: {result['summary']['sectors_found']}")
            print(f"  ✓ AI 指令: {result['ai_instructions']['task']}")

            if result['structured_news']:
                news = result['structured_news'][0]
                print(f"  ✓ 包含 AI 提示词: {bool(news.get('ai_analysis_prompt'))}")

            return 1, 0
        else:
            print(f"  ✗ 返回结构缺少字段: {missing_keys}")
            return 0, 1
    except Exception as e:
        print(f"  ✗ Agent 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1


def test_full_flow():
    print("\n" + "=" * 70)
    print("8. 测试完整流程（含 Parquet 输出）")
    print("=" * 70)

    try:
        input_data = {
            "trade_date": "2026-05-28",
            "news_type": "all"
        }

        config = {
            "max_news_count": 10,
            "save_parquet": True,
            "output_dir": "test_output"
        }

        result = run(input_data, config=config)

        print(f"  ✓ 完整流程执行成功")
        print(f"  ✓ 新闻数量: {result['news_count']}")
        print(f"  ✓ 发现股票: {result['summary']['stock_codes_found']}")
        print(f"  ✓ 发现板块: {result['summary']['sectors_found']}")

        if result.get('parquet_path'):
            print(f"  ✓ Parquet 文件: {result['parquet_path']}")

        if result.get('structured_news'):
            news = result['structured_news'][0]
            print(f"\n  示例 AI 分析提示词:")
            print(f"  {news['ai_analysis_prompt'][:300]}...")

        return 1, 0
    except Exception as e:
        print(f"  ✗ 完整流程失败: {e}")
        import traceback
        traceback.print_exc()
        return 0, 1


def test_llm_prompt_generation():
    print("\n" + "=" * 70)
    print("9. 测试 LLM prompt 生成")
    print("=" * 70)

    passed = 0
    failed = 0

    prompt = generate_llm_prompt(
        title="央行宣布降准0.5个百分点",
        content="中国人民银行决定下调存款准备金率0.5个百分点，释放长期资金约1万亿元。",
        stock_codes=[{"code": "000001", "name": "平安银行"}],
        sectors=["金融"],
        entities={"numbers": [{"value": 0.5, "type": "percentage"}, {"value": 10000, "type": "amount_wan"}], "policies": ["降准"]},
    )
    checks = [
        ("包含标题", "央行宣布降准" in prompt),
        ("包含股票", "平安银行" in prompt and "000001" in prompt),
        ("包含板块", "金融" in prompt),
        ("包含实体", "降准" in prompt),
        ("包含 CoT 引导", "分析框架" in prompt or "步骤" in prompt),
        ("包含 few-shot 示例", "示例" in prompt),
        ("包含 JSON 输出格式", '"sentiment"' in prompt),
    ]
    for name, ok in checks:
        if ok:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}")
            failed += 1

    prompt_min = generate_llm_prompt(
        title="测试",
        content="内容",
    )
    if "测试" in prompt_min and "无明确个股" in prompt_min:
        print(f"  ✓ 最小输入正常生成")
        passed += 1
    else:
        print(f"  ✗ 最小输入生成失败")
        failed += 1

    return passed, failed


def test_llm_response_parsing():
    print("\n" + "=" * 70)
    print("10. 测试 LLM 响应解析")
    print("=" * 70)

    passed = 0
    failed = 0

    r = parse_llm_response('{"sentiment":"positive","impact_level":"high","trading_direction":"bullish","confidence":0.85,"reason":"利好消息"}')
    if r["sentiment"] == "positive" and r["confidence"] == 0.85 and r["method"] == "llm":
        print(f"  ✓ 标准 JSON 解析")
        passed += 1
    else:
        print(f"  ✗ 标准 JSON 解析失败: {r}")
        failed += 1

    r2 = parse_llm_response('```json\n{"sentiment":"negative","impact_level":"medium","trading_direction":"bearish","confidence":0.70,"reason":"利空"}\n```')
    if r2["sentiment"] == "negative" and r2["confidence"] == 0.70:
        print(f"  ✓ markdown 代码块解析")
        passed += 1
    else:
        print(f"  ✗ markdown 代码块解析失败: {r2}")
        failed += 1

    r3 = parse_llm_response('分析如下：\n{"sentiment":"neutral","impact_level":"low","trading_direction":"hold","confidence":0.30,"reason":"无明确信号"}\n以上是分析结果。')
    if r3["sentiment"] == "neutral" and r3["trading_direction"] == "hold":
        print(f"  ✓ 混合文本 JSON 提取")
        passed += 1
    else:
        print(f"  ✗ 混合文本 JSON 提取失败: {r3}")
        failed += 1

    r4 = parse_llm_response("这不是JSON")
    if r4["method"] == "llm_parse_error" and r4["trading_direction"] == "hold":
        print(f"  ✓ 无效输入降级为默认值")
        passed += 1
    else:
        print(f"  ✗ 无效输入未正确降级: {r4}")
        failed += 1

    r5 = parse_llm_response("")
    if r5["method"] == "llm_parse_error":
        print(f"  ✓ 空输入降级")
        passed += 1
    else:
        print(f"  ✗ 空输入未降级")
        failed += 1

    r6 = parse_llm_response('{"sentiment":"invalid","impact_level":"extreme","trading_direction":"maybe","confidence":999,"reason":"test"}')
    if r6["sentiment"] == "neutral" and r6["impact_level"] == "low" and r6["trading_direction"] == "hold" and r6["confidence"] == 1.0:
        print(f"  ✓ 非法字段值正确标准化")
        passed += 1
    else:
        print(f"  ✗ 字段值标准化失败: {r6}")
        failed += 1

    return passed, failed


if __name__ == "__main__":
    print("新闻助手交易方向 - 完整测试")
    print("架构：Skill 采集数据 → LLM 分析情感 → Agent 写回结果")
    print("=" * 70)

    total_passed = 0
    total_failed = 0

    tests = [
        test_validate_input,
        test_stock_code_extraction,
        test_sector_extraction,
        test_entity_extraction,
        test_news_structuring,
        test_parquet_output,
        test_agent_call,
        test_full_flow,
        test_llm_prompt_generation,
        test_llm_response_parsing,
    ]

    for test_func in tests:
        passed, failed = test_func()
        total_passed += passed
        total_failed += failed

    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    print(f"  通过: {total_passed}")
    print(f"  失败: {total_failed}")
    print(f"  总计: {total_passed + total_failed}")

    if total_failed == 0:
        print("\n  ✓ 所有测试通过！")
        print("  ✓ 数据采集：新闻 → 股票代码/板块/实体提取 → 结构化输出")
        print("  ✓ Parquet 输出：符合 BUILD 规则文档标准")
        print("  ✓ Agent 接口：run() 入口完整")
        print("  ✓ LLM prompt：FinGPT 风格（CoT + few-shot + 结构化输出）")
        print("  ✓ LLM 响应解析：支持多种 JSON 格式 + 字段标准化")
    else:
        print(f"\n  ✗ 有 {total_failed} 个测试失败")

    sys.exit(0 if total_failed == 0 else 1)
