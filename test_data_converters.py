#!/usr/bin/env python3
"""
数据转换器测试脚本

测试内容：
1. MarketDataNormalizer - 金融数据标准化转换器
2. WsMessageConverter - WebSocket 消息类型转换器
3. ChartDataConverter - 图表数据快速转换器
"""

import json
import sys
from datetime import datetime
from typing import Dict, List, Any

# 添加项目路径
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

import pandas as pd

from backend.utils.data_converters import (
    MarketDataNormalizer,
    WsMessageConverter,
    ChartDataConverter,
)

# 测试数据
TEST_DATA_CN = [
    {
        '日期': '2024-01-01',
        '开盘': 100.0,
        '最高': 105.0,
        '最低': 99.0,
        '收盘': 103.0,
        '成交量': 1000000,
        '成交额': 103000000
    },
    {
        '日期': '2024-01-02',
        '开盘': 103.0,
        '最高': 108.0,
        '最低': 102.0,
        '收盘': 106.0,
        '成交量': 1500000,
        '成交额': 159000000
    },
    {
        '日期': '2024-01-03',
        '开盘': 106.0,
        '最高': 110.0,
        '最低': 104.0,
        '收盘': 108.0,
        '成交量': 2000000,
        '成交额': 216000000
    }
]

TEST_DATA_US = [
    {
        'Date': '2024-01-01',
        'Open': 150.0,
        'High': 155.0,
        'Low': 149.0,
        'Close': 153.0,
        'Volume': 50000000
    },
    {
        'Date': '2024-01-02',
        'Open': 153.0,
        'High': 158.0,
        'Low': 152.0,
        'Close': 156.0,
        'Volume': 55000000
    }
]

FINANCIAL_DATA_CN = {
    '市值': 100000000000,
    '市盈率': 25.5,
    '市净率': 3.2,
    '净利润': 5000000000,
    '营业收入': 20000000000
}

FINANCIAL_DATA_US = {
    'marketCap': 2000000000000,
    'trailingPE': 28.5,
    'priceToBook': 15.8,
    'netIncome': 80000000000,
    'totalRevenue': 300000000000
}


class TestResult:
    """测试结果记录"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_pass(self, test_name: str):
        self.passed += 1
        self.total += 1
        print(f"  ✅ {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.total += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"  ❌ {test_name}")

    def add_warning(self, warning: str):
        self.warnings.append(warning)
        print(f"  ⚠️ {warning}")


def test_market_data_normalizer(result: TestResult):
    """测试金融数据标准化转换器"""
    print("\n" + "=" * 60)
    print("📊 测试 1: MarketDataNormalizer - 金融数据标准化转换器")
    print("=" * 60)

    # 测试1: A股 OHLCV 数据标准化
    print("\n1.1 测试 A股 OHLCV 数据标准化...")
    try:
        normalized = MarketDataNormalizer.normalize_ohlcv(TEST_DATA_CN, market='cn')
        
        # 验证字段（amount 是可选的）
        required_fields = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_fields = [f for f in required_fields if f not in normalized.columns]
        
        if not missing_fields:
            result.add_pass("A股 OHLCV 字段标准化")
        else:
            result.add_fail("A股 OHLCV 字段标准化", f"缺失字段: {missing_fields}")

        # 验证日期格式
        if normalized['date'].iloc[0] == '2024-01-01':
            result.add_pass("A股日期格式标准化")
        else:
            result.add_fail("A股日期格式标准化", f"期望 '2024-01-01', 实际 '{normalized['date'].iloc[0]}'")

        # 验证数值类型
        if pd.api.types.is_numeric_dtype(normalized['close']):
            result.add_pass("A股数值类型标准化")
        else:
            result.add_fail("A股数值类型标准化", "close 字段不是数值类型")

        # 显示结果
        print(f"\n  标准化结果 (前2条):")
        print(f"  {normalized[['date', 'open', 'high', 'low', 'close']].head(2).to_string(index=False)}")
        
    except Exception as e:
        result.add_fail("A股 OHLCV 数据标准化", str(e))

    # 测试2: 美股 OHLCV 数据标准化
    print("\n1.2 测试 美股 OHLCV 数据标准化...")
    try:
        normalized = MarketDataNormalizer.normalize_ohlcv(TEST_DATA_US, market='us')
        
        if 'date' in normalized.columns and 'close' in normalized.columns:
            result.add_pass("美股 OHLCV 字段标准化")
        else:
            result.add_fail("美股 OHLCV 字段标准化", "缺失必要字段")

        print(f"\n  标准化结果 (全部):")
        print(f"  {normalized.to_string(index=False)}")
        
    except Exception as e:
        result.add_fail("美股 OHLCV 数据标准化", str(e))

    # 测试3: A股财务数据标准化
    print("\n1.3 测试 A股财务数据标准化...")
    try:
        normalized = MarketDataNormalizer.normalize_financial(FINANCIAL_DATA_CN, market='cn')
        
        if normalized.get('market_cap') is not None:
            result.add_pass("A股财务数据标准化")
            print(f"\n  财务数据:")
            for key, value in normalized.items():
                print(f"    {key}: {value}")
        else:
            result.add_fail("A股财务数据标准化", "market_cap 字段未找到")
            
    except Exception as e:
        result.add_fail("A股财务数据标准化", str(e))

    # 测试4: 统一格式转换
    print("\n1.4 测试统一格式转换...")
    try:
        unified = MarketDataNormalizer.to_unified_format(
            symbol='600519',
            ohlcv=TEST_DATA_CN,
            financial=FINANCIAL_DATA_CN,
            market='cn'
        )
        
        if all(k in unified for k in ['symbol', 'market', 'ohlcv', 'updated_at']):
            result.add_pass("统一格式转换")
            print(f"\n  统一格式:")
            print(f"    股票代码: {unified['symbol']}")
            print(f"    市场: {unified['market']}")
            print(f"    OHLCV条数: {len(unified['ohlcv'])}")
        else:
            result.add_fail("统一格式转换", "缺少必要字段")
            
    except Exception as e:
        result.add_fail("统一格式转换", str(e))


def test_ws_message_converter(result: TestResult):
    """测试 WebSocket 消息类型转换器"""
    print("\n" + "=" * 60)
    print("🔌 测试 2: WsMessageConverter - WebSocket 消息类型转换器")
    print("=" * 60)

    # 测试1: 创建状态消息
    print("\n2.1 测试创建状态消息...")
    try:
        status_msg = WsMessageConverter.create_status("正在分析中...")
        
        if status_msg.get('type') == 'status' and 'message' in status_msg:
            result.add_pass("创建状态消息")
            print(f"  消息: {status_msg}")
        else:
            result.add_fail("创建状态消息", "消息格式不正确")
            
    except Exception as e:
        result.add_fail("创建状态消息", str(e))

    # 测试2: 创建节点更新消息
    print("\n2.2 测试创建节点更新消息...")
    try:
        update_msg = WsMessageConverter.create_node_update(
            node="DataCollector",
            section="valuation",
            content="正在获取估值数据..."
        )
        
        if update_msg.get('type') == 'node_update' and 'node' in update_msg:
            result.add_pass("创建节点更新消息")
            print(f"  消息: {update_msg}")
        else:
            result.add_fail("创建节点更新消息", "消息格式不正确")
            
    except Exception as e:
        result.add_fail("创建节点更新消息", str(e))

    # 测试3: 序列化为 JSON
    print("\n2.3 测试 JSON 序列化...")
    try:
        test_msg = WsMessageConverter.create_complete("分析完成！")
        json_str = WsMessageConverter.to_json(test_msg)
        
        if isinstance(json_str, str) and 'type' in json_str:
            result.add_pass("JSON 序列化")
            print(f"  序列化结果 (前100字符): {json_str[:100]}...")
        else:
            result.add_fail("JSON 序列化", "序列化结果不是字符串")
            
    except Exception as e:
        result.add_fail("JSON 序列化", str(e))

    # 测试4: JSON 反序列化
    print("\n2.4 测试 JSON 反序列化...")
    try:
        test_json = '{"type": "status", "message": "测试消息", "timestamp": "2024-01-01T00:00:00"}'
        parsed = WsMessageConverter.from_json(test_json)
        
        if parsed.get('type') == 'status' and 'message' in parsed:
            result.add_pass("JSON 反序列化")
            print(f"  反序列化结果: {parsed}")
        else:
            result.add_fail("JSON 反序列化", "解析结果不正确")
            
    except Exception as e:
        result.add_fail("JSON 反序列化", str(e))

    # 测试5: 便捷方法
    print("\n2.5 测试所有便捷方法...")
    try:
        complete_msg = WsMessageConverter.create_complete("完成")
        error_msg = WsMessageConverter.create_error("出错了")
        
        if complete_msg.get('type') == 'complete' and error_msg.get('type') == 'error':
            result.add_pass("所有便捷方法")
            print(f"  完成消息: {complete_msg}")
            print(f"  错误消息: {error_msg}")
        else:
            result.add_fail("所有便捷方法", "消息类型不正确")
            
    except Exception as e:
        result.add_fail("所有便捷方法", str(e))


def test_chart_data_converter(result: TestResult):
    """测试图表数据快速转换器"""
    print("\n" + "=" * 60)
    print("📈 测试 3: ChartDataConverter - 图表数据快速转换器")
    print("=" * 60)

    import pandas as pd

    # 创建测试 DataFrame
    df = pd.DataFrame({
        'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'open': [100, 103, 106],
        'high': [105, 108, 110],
        'low': [99, 102, 104],
        'close': [103, 106, 108],
        'volume': [1000000, 1500000, 2000000]
    })

    # 测试1: Lightweight Charts 格式
    print("\n3.1 测试 Lightweight Charts 格式转换...")
    try:
        lw_data = ChartDataConverter.dataframe_to_ohlc(df, chart_type='lightweight')
        
        if len(lw_data) == 3 and all('time' in d for d in lw_data):
            result.add_pass("Lightweight Charts 格式")
            print(f"  转换结果 (第1条):")
            print(f"    time: {lw_data[0]['time']}")
            print(f"    open: {lw_data[0]['open']}")
            print(f"    close: {lw_data[0]['close']}")
        else:
            result.add_fail("Lightweight Charts 格式", "数据格式不正确")
            
    except Exception as e:
        result.add_fail("Lightweight Charts 格式", str(e))

    # 测试2: ECharts 格式
    print("\n3.2 测试 ECharts 格式转换...")
    try:
        echarts_data = ChartDataConverter.dataframe_to_ohlc(df, chart_type='echarts')
        
        if len(echarts_data) == 3 and all(isinstance(d, list) for d in echarts_data):
            result.add_pass("ECharts 格式")
            print(f"  转换结果 (第1条): {echarts_data[0]}")
        else:
            result.add_fail("ECharts 格式", "数据格式不正确")
            
    except Exception as e:
        result.add_fail("ECharts 格式", str(e))

    # 测试3: Plotly 格式
    print("\n3.3 测试 Plotly 格式转换...")
    try:
        plotly_data = ChartDataConverter.dataframe_to_ohlc(df, chart_type='plotly')
        
        if 'x' in plotly_data and 'close' in plotly_data:
            result.add_pass("Plotly 格式")
            print(f"  转换结果:")
            print(f"    x轴数据: {plotly_data['x'][:2]}")
            print(f"    close数据: {plotly_data['close'][:2]}")
        else:
            result.add_fail("Plotly 格式", "数据格式不正确")
            
    except Exception as e:
        result.add_fail("Plotly 格式", str(e))

    # 测试4: numpy 快速转换
    print("\n3.4 测试 numpy 数组快速转换 (零拷贝)...")
    try:
        import numpy as np
        np_data = np.array([
            ['2024-01-01', 100, 105, 99, 103, 1000000],
            ['2024-01-02', 103, 108, 102, 106, 1500000],
            ['2024-01-03', 106, 110, 104, 108, 2000000],
        ], dtype=object)
        
        fast_data = ChartDataConverter.fast_convert_ndarray(
            np_data,
            date_index=0,
            open_index=1,
            high_index=2,
            low_index=3,
            close_index=4
        )
        
        if len(fast_data) == 3:
            result.add_pass("numpy 数组快速转换")
            print(f"  转换成功: {len(fast_data)} 条数据")
        else:
            result.add_fail("numpy 数组快速转换", "数据条数不正确")
            
    except ImportError:
        result.add_warning("numpy 未安装，跳过快速转换测试")
    except Exception as e:
        result.add_fail("numpy 数组快速转换", str(e))


def print_summary(result: TestResult):
    """打印测试总结"""
    print("\n" + "=" * 60)
    print("📋 测试总结")
    print("=" * 60)
    
    print(f"\n总测试数: {result.total}")
    print(f"✅ 通过: {result.passed}")
    print(f"❌ 失败: {result.failed}")
    
    if result.warnings:
        print(f"\n⚠️ 警告 ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"  - {warning}")
    
    if result.errors:
        print(f"\n❌ 错误 ({len(result.errors)}):")
        for error in result.errors:
            print(f"  - {error}")
    
    success_rate = (result.passed / result.total * 100) if result.total > 0 else 0
    print(f"\n🎯 通过率: {success_rate:.1f}%")
    
    return success_rate == 100


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("🧪 数据转换器测试套件")
    print("=" * 60)
    print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    result = TestResult()

    try:
        # 运行所有测试
        test_market_data_normalizer(result)
        test_ws_message_converter(result)
        test_chart_data_converter(result)

        # 打印总结
        all_passed = print_summary(result)

        print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if all_passed:
            print("\n🎉 所有测试通过！")
            return 0
        else:
            print("\n💥 部分测试失败！")
            return 1

    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
