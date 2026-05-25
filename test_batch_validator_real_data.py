#!/usr/bin/env python3
"""
用真实的 OHLCV 数据测试 BatchDataValidator
"""

import sys
from datetime import datetime
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

import pandas as pd

# 导入mock数据生成器和验证器
from backend.data_layer.mock_data import _generate_ohlcv_df
from backend.utils.data_converters import BatchDataValidator


def print_separator(title):
    """打印分隔线"""
    print("\n" + "="*80)
    print(f" {title} ".center(78, "="))
    print("="*80)


def test_valid_data():
    """测试有效数据的验证"""
    print_separator("1. 测试有效数据 - 贵州茅台 (600519)")
    
    # 生成真实的 OHLCV 数据
    df = _generate_ohlcv_df("600519", "2026-05-25", "cn", days=60)
    
    print(f"\n生成的数据预览（前5行）:")
    print(df.head())
    
    print(f"\n数据统计:")
    print(f"  总行数: {len(df)}")
    print(f"  日期范围: {df['date'].min()} 至 {df['date'].max()}")
    print(f"  价格范围: {df['low'].min():.2f} - {df['high'].max():.2f}")
    
    # 运行验证器
    report = BatchDataValidator.validate_ohlcv_data(df, strict=False)
    
    print(f"\n验证结果:")
    print(f"  有效行数: {report['valid_rows']}")
    print(f"  无效行数: {len(report['invalid_rows'])}")
    print(f"  错误列表: {report['errors']}")
    print(f"  警告列表: {report['warnings']}")
    
    return report


def test_with_some_errors():
    """测试含有一些错误的数据"""
    print_separator("2. 测试含有错误的数据 - 模拟数据质量问题")
    
    # 生成基础数据
    df = _generate_ohlcv_df("AAPL", "2026-05-25", "us", days=60)
    
    # 引入一些错误
    df_with_errors = df.copy()
    
    # 错误1: 某些行 high < low
    df_with_errors.loc[10, 'high'] = df_with_errors.loc[10, 'low'] - 5
    df_with_errors.loc[25, 'high'] = df_with_errors.loc[25, 'low'] - 3
    
    # 错误2: 无效日期
    df_with_errors.loc[15, 'date'] = 'invalid-date'
    
    # 错误3: 负数成交量
    df_with_errors.loc[5, 'volume'] = -100000
    
    # 错误4: NaN 值
    df_with_errors.loc[30, 'close'] = None
    
    print(f"\n引入的错误:")
    print(f"  - 第10行: high < low")
    print(f"  - 第15行: 无效日期")
    print(f"  - 第5行: 负数成交量")
    print(f"  - 第30行: NaN close")
    
    # 运行验证器
    report = BatchDataValidator.validate_ohlcv_data(df_with_errors, strict=False)
    
    print(f"\n验证结果:")
    print(f"  有效行数: {report['valid_rows']}")
    print(f"  无效行数: {len(report['invalid_rows'])}")
    
    if report['invalid_rows']:
        print(f"\n详细的无效行信息:")
        for row in report['invalid_rows']:
            print(f"  行 {row['index']} (日期: {row['date']}): {row['errors']}")
    
    print(f"\n警告信息: {report['warnings']}")
    
    return report


def test_financial_data_validation():
    """测试财务数据验证"""
    print_separator("3. 测试财务数据验证")
    
    # 模拟财务数据
    financial_data = {
        'pe_ratio': 28.5,
        'pb_ratio': 3.2,
        'market_cap': 1520000000000,
        'net_profit': 52000000000,
        'revenue': 180000000000
    }
    
    print(f"\n测试的财务数据:")
    for key, value in financial_data.items():
        print(f"  {key}: {value}")
    
    # 运行验证器
    report = BatchDataValidator.validate_financial_data(financial_data, strict=False)
    
    print(f"\n财务数据验证结果:")
    print(f"  验证通过: {report['valid']}")
    print(f"  错误: {report['errors']}")
    print(f"  警告: {report['warnings']}")
    
    return report


def test_dataframe_schema_validation():
    """测试 DataFrame 模式验证"""
    print_separator("4. 测试 DataFrame 模式验证")
    
    # 生成数据
    df = _generate_ohlcv_df("600036", "2026-05-25", "cn", days=30)
    
    # 定义预期模式
    expected_schema = {
        'date': str,
        'open': float,
        'high': float,
        'low': float,
        'close': float,
        'volume': int
    }
    
    print(f"\n预期的列和类型:")
    for col, dtype in expected_schema.items():
        print(f"  {col}: {dtype.__name__}")
    
    # 运行验证器
    report = BatchDataValidator.validate_dataframe_schema(df, expected_schema, strict=False)
    
    print(f"\n模式验证结果:")
    print(f"  验证通过: {report['valid']}")
    print(f"  缺失列: {report['missing_columns']}")
    print(f"  类型不匹配: {report['type_mismatches']}")
    print(f"  额外列: {report['extra_columns']}")
    
    return report


def test_quality_report():
    """测试数据质量报告"""
    print_separator("5. 测试数据质量报告生成")
    
    # 生成数据（含一些问题）
    df = _generate_ohlcv_df("NVDA", "2026-05-25", "us", days=90)
    
    # 引入一些小问题
    df_with_issues = df.copy()
    df_with_issues.loc[45, 'volume'] = None  # 缺失值
    df_with_issues.loc[60:62, 'close'] = None  # 连续缺失
    
    # 生成质量报告
    report = BatchDataValidator.generate_quality_report(df_with_issues)
    
    print(f"\n数据质量报告:")
    print(f"  行数: {report['row_count']}")
    print(f"  列数: {report['column_count']}")
    print(f"  重复行数: {report['duplicate_rows']}")
    
    print(f"\n各列缺失值统计:")
    for col, info in report['missing_values'].items():
        print(f"  {col}: {info['count']} 个缺失值 ({info['percentage']:.1f}%)")
    
    print(f"\n数值列统计:")
    for col, stats in report['numeric_stats'].items():
        print(f"  {col}: mean={stats['mean']:.2f}, range={stats['min']:.2f}-{stats['max']:.2f}")
    
    return report


def main():
    """主函数"""
    print("="*80)
    print("BatchDataValidator - 真实数据测试".center(78))
    print("="*80)
    print(f"\n测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # 运行所有测试
    results.append(("有效数据测试", test_valid_data()))
    results.append(("错误数据测试", test_with_some_errors()))
    results.append(("财务数据验证", test_financial_data_validation()))
    results.append(("模式验证测试", test_dataframe_schema_validation()))
    results.append(("质量报告测试", test_quality_report()))
    
    # 总结
    print_separator("测试总结")
    print(f"\n所有测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n测试结果汇总:")
    for name, result in results:
        print(f"  ✓ {name} - 完成")
    
    print("\n" + "="*80)
    print("所有测试运行成功！".center(78))
    print("="*80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
