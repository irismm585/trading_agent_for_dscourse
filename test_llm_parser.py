#!/usr/bin/env python3
"""
LLMResponseParser 测试脚本

测试功能：
1. 从JSON代码块中提取数据
2. 使用正则表达式提取数据
3. 评级标准化
4. 风险列表标准化
5. 财务指标提取
6. 技术指标提取
"""

import sys
import json

# 添加项目路径
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

from backend.utils.data_converters import LLMResponseParser

class TestResult:
    """测试结果记录"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.errors = []
    
    def add_pass(self, test_name):
        self.passed += 1
        self.total += 1
        print(f"  ✅ {test_name}")
    
    def add_fail(self, test_name, error):
        self.failed += 1
        self.total += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  ❌ {test_name}")
    
    def add_warning(self, warning):
        print(f"  ⚠️ {warning}")

def test_extract_json_from_markdown(result):
    """测试从Markdown代码块提取JSON"""
    print("\n1. 测试从Markdown代码块提取JSON")
    
    # 测试1: 标准JSON代码块
    test1 = '''```json
{"rating": "Buy", "reasoning": "这是一个买入建议"}
```'''
    parsed1 = LLMResponseParser.extract_json_from_markdown(test1)
    if parsed1 and parsed1.get('rating') == 'Buy':
        result.add_pass("标准JSON代码块解析")
        print(f"     解析结果: {json.dumps(parsed1, ensure_ascii=False)}")
    else:
        result.add_fail("标准JSON代码块解析", "无法正确解析或结果不正确")
    
    # 测试2: 没有json标记的代码块
    test2 = '''```
{"rating": "Sell", "reasoning": "这是一个卖出建议"}
```'''
    parsed2 = LLMResponseParser.extract_json_from_markdown(test2)
    if parsed2 and parsed2.get('rating') == 'Sell':
        result.add_pass("无json标记的代码块解析")
    else:
        result.add_fail("无json标记的代码块解析", "无法正确解析")
    
    # 测试3: 直接JSON字符串
    test3 = '{"rating": "Hold", "reasoning": "观望"}'
    parsed3 = LLMResponseParser.extract_json_from_markdown(test3)
    if parsed3 and parsed3.get('rating') == 'Hold':
        result.add_pass("直接JSON字符串解析")
    else:
        result.add_fail("直接JSON字符串解析", "无法正确解析")
    
    # 测试4: 无效JSON
    test4 = '''```
{"rating": "Buy", invalid}
```'''
    parsed4 = LLMResponseParser.extract_json_from_markdown(test4)
    if parsed4 is None:
        result.add_pass("无效JSON正确返回None")
    else:
        result.add_fail("无效JSON处理", "应该返回None")

def test_normalize_rating(result):
    """测试评级标准化"""
    print("\n2. 测试评级标准化")
    
    # 中文评级测试
    test_cases = [
        ("买入", "Buy"),
        ("持有", "Hold"),
        ("观望", "Hold"),
        ("持有/观望", "Hold"),
        ("卖出", "Sell"),
        ("建议买入", "Buy"),
        ("强烈卖出", "Sell"),
        ("暂时持有", "Hold"),
    ]
    
    for input_rating, expected in test_cases:
        normalized = LLMResponseParser._normalize_rating(input_rating)
        if normalized == expected:
            result.add_pass(f"评级'{input_rating}'标准化为'{expected}'")
        else:
            result.add_fail(f"评级'{input_rating}'标准化", f"期望'{expected}', 实际'{normalized}'")
    
    # 英文评级测试
    test_cases_en = [
        ("Buy", "Buy"),
        ("Hold", "Hold"),
        ("Sell", "Sell"),
        ("buy", "Buy"),
        ("hold", "Hold"),
        ("sell", "Sell"),
    ]
    
    for input_rating, expected in test_cases_en:
        normalized = LLMResponseParser._normalize_rating(input_rating)
        if normalized == expected:
            result.add_pass(f"英文评级'{input_rating}'标准化为'{expected}'")
        else:
            result.add_fail(f"英文评级'{input_rating}'标准化", f"期望'{expected}', 实际'{normalized}'")

def test_extract_final_decision(result):
    """测试提取最终投资决策"""
    print("\n3. 测试提取最终投资决策")
    
    # 测试1: JSON格式响应
    test1 = '''```json
{
  "rating": "持有/观望",
  "reasoning": "多空双方在技术面和基本面均提出了有力论据",
  "key_risks": ["估值风险", "技术面背离", "政策风险"],
  "suggested_entry_price": 180.5,
  "suggested_holding_period": "中期(1-3月)"
}
```'''
    decision1 = LLMResponseParser.extract_final_decision(test1)
    if (decision1.get('rating') == 'Hold' and
        decision1.get('reasoning') and
        len(decision1.get('key_risks', [])) > 0 and
        decision1.get('suggested_entry_price') == 180.5):
        result.add_pass("JSON格式决策提取")
        print(f"     评级: {decision1.get('rating')}")
        print(f"     风险: {decision1.get('key_risks')}")
    else:
        result.add_fail("JSON格式决策提取", "提取结果不正确")
    
    # 测试2: 纯文本格式响应
    test2 = '''最终评级: 买入
评判理由: 公司基本面强劲，技术面向好
风险提示: 市场波动风险；政策风险
建议入场价: ¥200.0
建议持有周期: 长期(3-6月)'''
    decision2 = LLMResponseParser.extract_final_decision(test2)
    if (decision2.get('rating') == 'Buy' and
        decision2.get('reasoning') and
        len(decision2.get('key_risks', [])) > 0):
        result.add_pass("纯文本格式决策提取")
    else:
        result.add_fail("纯文本格式决策提取", "提取结果不正确")

def test_normalize_risks(result):
    """测试风险列表标准化"""
    print("\n4. 测试风险列表标准化")
    
    # 测试1: 字符串列表
    test1 = ["风险1", "风险2", "风险3"]
    normalized1 = LLMResponseParser._normalize_risks(test1)
    if len(normalized1) == 3:
        result.add_pass("字符串列表标准化")
    else:
        result.add_fail("字符串列表标准化", f"期望3个风险，实际{len(normalized1)}")
    
    # 测试2: 字典列表
    test2 = [
        {"risk": "估值风险", "description": "估值过高"},
        {"details": "技术面背离"},
        {"risk": "政策风险"}
    ]
    normalized2 = LLMResponseParser._normalize_risks(test2)
    if len(normalized2) >= 2:
        result.add_pass("字典列表标准化")
    else:
        result.add_fail("字典列表标准化", "提取结果不正确")
    
    # 测试3: 字符串
    test3 = "风险1；风险2；风险3"
    normalized3 = LLMResponseParser._normalize_risks(test3)
    if len(normalized3) >= 3:
        result.add_pass("分号分隔字符串标准化")
    else:
        result.add_fail("分号分隔字符串标准化", "提取结果不正确")

def test_extract_financial_metrics(result):
    """测试财务指标提取"""
    print("\n5. 测试财务指标提取")
    
    test_text = '''估值分析：
市盈率(PE): 18.5
市净率(PB): 2.3
总市值: 500000000000
净利润: 20000000000
营业收入: 100000000000'''
    
    metrics = LLMResponseParser.extract_financial_metrics(test_text)
    
    if metrics.get('pe_ratio') == 18.5:
        result.add_pass("市盈率提取")
    else:
        result.add_fail("市盈率提取", f"期望18.5，实际{metrics.get('pe_ratio')}")
    
    if metrics.get('pb_ratio') == 2.3:
        result.add_pass("市净率提取")
    else:
        result.add_fail("市净率提取", f"期望2.3，实际{metrics.get('pb_ratio')}")
    
    if metrics.get('market_cap') == 500000000000.0:
        result.add_pass("市值提取")
    else:
        result.add_fail("市值提取", f"期望500000000000，实际{metrics.get('market_cap')}")

def test_extract_technical_indicators(result):
    """测试技术指标提取"""
    print("\n6. 测试技术指标提取")
    
    test_text = '''技术面分析：
趋势: 上升趋势
MACD: 金叉信号，看涨
均线: MA5向上突破MA20'''
    
    indicators = LLMResponseParser.extract_technical_indicators(test_text)
    
    if indicators.get('trend'):
        result.add_pass("趋势提取")
    else:
        result.add_fail("趋势提取", "未提取到趋势")
    
    if indicators.get('macd_signal'):
        result.add_pass("MACD信号提取")
    else:
        result.add_fail("MACD信号提取", "未提取到MACD信号")

def test_real_world_example(result):
    """测试真实世界的例子"""
    print("\n7. 测试真实世界例子")
    
    # 使用之前保存的测试数据
    test_file = '/Users/bytedance/Documents/trae_projects/trading_agent_finance/test_results/analysis_600519_20260522_181419.json'
    
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        final_decision_text = data.get('final_decision', '')
        
        if final_decision_text:
            decision = LLMResponseParser.extract_final_decision(final_decision_text)
            print(f"     提取到的评级: {decision.get('rating')}")
            print(f"     提取到的风险数: {len(decision.get('key_risks', []))}")
            if decision.get('rating'):
                result.add_pass("真实世界例子解析")
            else:
                result.add_fail("真实世界例子解析", "未提取到有效信息")
    except FileNotFoundError:
        result.add_warning("测试文件不存在，跳过此测试")

def print_summary(result):
    """打印测试总结"""
    print("\n" + "=" * 60)
    print("📋 测试总结")
    print("=" * 60)
    
    print(f"\n总测试数: {result.total}")
    print(f"✅ 通过: {result.passed}")
    print(f"❌ 失败: {result.failed}")
    
    if result.errors:
        print(f"\n❌ 错误:")
        for error in result.errors:
            print(f"  - {error}")
    
    success_rate = (result.passed / result.total * 100) if result.total > 0 else 0
    print(f"\n🎯 通过率: {success_rate:.1f}%")
    
    return success_rate == 100

def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 LLMResponseParser 测试套件")
    print("=" * 60)
    
    result = TestResult()
    
    # 运行所有测试
    test_extract_json_from_markdown(result)
    test_normalize_rating(result)
    test_extract_final_decision(result)
    test_normalize_risks(result)
    test_extract_financial_metrics(result)
    test_extract_technical_indicators(result)
    test_real_world_example(result)
    
    # 打印总结
    all_passed = print_summary(result)
    
    print(f"\n完成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if all_passed:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print("\n💥 部分测试失败！")
        return 1

if __name__ == '__main__':
    sys.exit(main())
