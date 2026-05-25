#!/usr/bin/env python3
"""Test Data Pipeline in Strict Mode with Realistic Edge Cases.

This script demonstrates the pipeline in strict mode,
including valid data and scenarios with data issues.
"""

import sys
import random
from datetime import datetime, timedelta
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

import pandas as pd
import numpy as np

from backend.data_layer import (
    DataPipeline,
    DataPipelineValidationError,
    validated_data_fetch,
    validated_ohlcv_fetch,
    get_pipeline
)
from backend.utils.data_converters import BatchDataValidator


def print_separator(title: str):
    """Print a formatted separator."""
    print("\n" + "=" * 80)
    print(f" {title} ".center(78, "="))
    print("=" * 80)


def test_clean_data_strict_mode():
    """Test clean data in strict mode - should pass successfully."""
    print_separator("场景 1: 干净数据 - 严格模式")
    
    print("\n🎯 目标: 验证干净的真实数据在严格模式下正常工作")
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    
    pipeline = DataPipeline(strict_validation=True)
    
    try:
        result = pipeline.fetch_only_ohlcv(
            symbol="600519",
            start_date=start_date,
            end_date=end_date,
            market="cn"
        )
        
        summary = result.get("validation_summary", {})
        
        print(f"\n✅ 结果:")
        print(f"   整体状态: {'✅ 通过' if summary.get('valid') else '❌ 未通过'}")
        
        if summary.get("ohlcv_details"):
            details = summary["ohlcv_details"]
            print(f"   数据行数: {details.get('total_rows') or len(result.get('ohlcv_df', []))}")
            print(f"   有效行数: {details.get('valid_rows')}")
            print(f"   无效行数: {len(details.get('invalid_rows', []))}")
        
        if summary.get("warnings"):
            print(f"\n⚠️ 警告:")
            for warning in summary["warnings"]:
                print(f"   - {warning}")
        
        if result.get("ohlcv_df") is not None and not result["ohlcv_df"].empty:
            print(f"\n📊 数据预览 (最后3行):")
            print(result["ohlcv_df"].tail(3))
        
        return True
        
    except DataPipelineValidationError as e:
        print(f"\n❌ 验证失败: {e}")
        print(f"详细报告: {e.validation_report}")
        return False
    except Exception as e:
        print(f"\n❌ 意外错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_injected_issues():
    """Test data with intentionally injected issues in non-strict mode."""
    print_separator("场景 2: 注入问题的数据 - 非严格模式")
    
    print("\n🎯 目标: 验证管道能检测到数据问题（非严格模式，用于演示）")
    
    # First fetch clean data
    pipeline = DataPipeline(strict_validation=False)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    try:
        result = pipeline.fetch_only_ohlcv("600036", start_date, end_date, "cn")
        df = result.get("ohlcv_df")
        
        if df is None or df.empty:
            print("❌ 无法获取测试数据")
            return False
        
        print("\n📥 已获取基础数据")
        print(f"   原始行数: {len(df)}")
        
        # Make a copy and inject issues
        df_injected = df.copy()
        
        # Inject issue 1: some high < low
        num_to_inject = min(3, len(df_injected) - 2)
        for idx in random.sample(range(1, len(df_injected) - 1), num_to_inject):
            df_injected.loc[idx, "high"] = df_injected.loc[idx, "low"] - 1.0
        
        # Inject issue 2: some missing values
        for idx in random.sample(range(len(df_injected)), 2):
            df_injected.loc[idx, "close"] = None
        
        print(f"\n🔧 注入问题:")
        print(f"   - {num_to_inject} 个 high < low")
        print(f"   - 2 个缺失值")
        
        # Now validate using BatchDataValidator directly
        print(f"\n🔍 验证注入问题的数据:")
        report = BatchDataValidator.validate_ohlcv_data(df_injected, strict=False)
        
        print(f"\n📋 验证结果:")
        print(f"   有效行数: {report.get('valid_rows')}")
        print(f"   无效行数: {len(report.get('invalid_rows', []))}")
        
        if report.get("invalid_rows"):
            print(f"\n❌ 发现的问题:")
            for row_info in report["invalid_rows"][:3]:
                print(f"   - 行 {row_info.get('index')}: {row_info.get('errors')}")
        
        if report.get("warnings"):
            print(f"\n⚠️ 警告:")
            for warning in report["warnings"]:
                print(f"   - {warning}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multiple_symbols_pipeline():
    """Test pipeline with multiple symbols for comparison."""
    print_separator("场景 3: 多股票并行处理演示")
    
    print("\n🎯 目标: 验证管道能处理多股票并记录日志")
    
    symbols = [
        ("600519", "cn", "贵州茅台"),
        ("600036", "cn", "招商银行"),
        ("AAPL", "us", "Apple"),
    ]
    
    pipeline = DataPipeline(strict_validation=False)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    results = []
    
    for symbol, market, name in symbols:
        print(f"\n{'─'*40}")
        print(f"处理 {name} ({symbol})")
        print(f"{'─'*40}")
        
        try:
            result = pipeline.fetch_only_ohlcv(symbol, start_date, end_date, market)
            summary = result.get("validation_summary", {})
            
            success = summary.get("valid", False)
            row_count = len(result.get("ohlcv_df", [])) if result.get("ohlcv_df") is not None else 0
            
            results.append({
                "symbol": symbol,
                "name": name,
                "success": success,
                "row_count": row_count
            })
            
            status = "✅" if success else "❌"
            print(f"   状态: {status} {'通过' if success else '未通过'}")
            print(f"   行数: {row_count}")
            
        except Exception as e:
            print(f"   ❌ 错误: {e}")
            results.append({
                "symbol": symbol,
                "name": name,
                "success": False,
                "error": str(e)
            })
    
    # Summary
    print_separator("多股票处理总结")
    
    success_count = sum(1 for r in results if r["success"])
    print(f"\n处理完成: {success_count}/{len(results)} 成功")
    
    print(f"\n详情:")
    for r in results:
        status = "✅" if r["success"] else "❌"
        print(f"  {status} {r['name']} ({r['symbol']})")
    
    # Show logs
    print_separator("验证日志")
    logs = pipeline.get_validation_logs()
    print(f"\n共 {len(logs)} 条验证日志")
    
    return True


def test_full_pipeline_with_report():
    """Test full pipeline and show quality report."""
    print_separator("场景 4: 完整流水线 - 质量报告")
    
    print("\n🎯 目标: 演示完整流水线与详细的质量报告")
    
    trade_date = datetime.now().strftime("%Y-%m-%d")
    
    result = validated_data_fetch(
        "600036",
        trade_date,
        "cn",
        lookback_days=60,
        strict=False
    )
    
    summary = result.get("validation_summary", {})
    
    print(f"\n📋 整体验证: {'✅ 通过' if summary.get('overall_valid') else '❌ 未通过'}")
    
    if "data_quality" in summary:
        quality = summary["data_quality"]
        print(f"\n📊 数据质量报告:")
        print(f"   行数: {quality.get('row_count')}")
        print(f"   列数: {quality.get('column_count')}")
        print(f"   重复行: {quality.get('duplicate_rows')}")
        
        print(f"\n   列与数据类型:")
        if "data_types" in quality:
            for col, dtype in quality["data_types"].items():
                print(f"     {col}: {dtype}")
        
        print(f"\n   缺失值统计:")
        if "missing_values" in quality:
            for col, info in quality["missing_values"].items():
                missing_pct = info.get("percentage", 0)
                status = "✅" if missing_pct == 0 else "⚠️"
                print(f"     {status} {col}: {info.get('count')} 个 ({missing_pct:.1f}%)")
        
        print(f"\n   数值列统计:")
        if "numeric_stats" in quality:
            for col, stats in quality["numeric_stats"].items():
                print(f"     {col}:")
                print(f"       均值: {stats.get('mean', 'N/A'):.2f}")
                print(f"       范围: {stats.get('min', 'N/A'):.2f} ~ {stats.get('max', 'N/A'):.2f}")
    
    # Show some data
    if result.get("data") and result["data"].get("ohlcv_df") is not None:
        df = result["data"]["ohlcv_df"]
        print(f"\n📈 数据预览 (最后5行):")
        print(df.tail())
    
    return True


def main():
    """Run all strict mode tests."""
    print("=" * 80)
    print("数据流水线 - 严格模式与真实数据测试".center(78))
    print("=" * 80)
    print(f"\n测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Test 1: Clean data
    results.append(("干净数据", test_clean_data_strict_mode()))
    
    # Test 2: Injected issues
    results.append(("问题数据检测", test_with_injected_issues()))
    
    # Test 3: Multiple symbols
    results.append(("多股票处理", test_multiple_symbols_pipeline()))
    
    # Test 4: Full pipeline with quality report
    results.append(("质量报告", test_full_pipeline_with_report()))
    
    # Final summary
    print_separator("最终总结")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    print(f"\n总测试数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {total - passed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    print(f"\n各场景:")
    for name, ok in results:
        status = "✅ 通过" if ok else "❌ 失败"
        print(f"   - {name}: {status}")
    
    if passed == total:
        print("\n🎉 所有测试通过！数据流水线在严格模式下正常工作！")
        return 0
    else:
        print(f"\n⚠️ 部分测试失败，请检查。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
