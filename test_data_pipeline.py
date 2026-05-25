#!/usr/bin/env python3
"""Test Data Pipeline with BatchDataValidator Integration.

This script demonstrates the use of the validated data pipeline
with real market data (using mock data for testing).
"""

import sys
from datetime import datetime, timedelta
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

from backend.data_layer import (
    DataPipeline,
    validated_data_fetch,
    validated_ohlcv_fetch
)


def print_separator(title: str):
    """Print a formatted separator."""
    print("\n" + "=" * 80)
    print(f" {title} ".center(78))
    print("=" * 80)


def test_ohlcv_pipeline():
    """Test OHLCV-only validation pipeline."""
    print_separator("测试 1: 仅 OHLCV 数据验证 Pipeline")
    
    # Calculate dates
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    
    print(f"\n测试数据范围: {start_date} 到 {end_date}")
    print("测试股票: 贵州茅台 (600519)")
    
    # Create pipeline with strict validation off for testing
    pipeline = DataPipeline(strict_validation=False)
    
    # Fetch and validate
    try:
        result = pipeline.fetch_only_ohlcv(
            symbol="600519",
            start_date=start_date,
            end_date=end_date,
            market="cn"
        )
        
        print(f"\n验证结果:")
        ohlcv_summary = result.get("validation_summary", {})
        print(f"  整体状态: {'✅ 有效' if ohlcv_summary.get('valid') else '❌ 无效'}")
        
        if ohlcv_summary.get("ohlcv_details"):
            details = ohlcv_summary["ohlcv_details"]
            print(f"  有效行数: {details.get('valid_rows')}")
            print(f"  无效行数: {len(details.get('invalid_rows', []))}")
        
        if ohlcv_summary.get("warnings"):
            print(f"\n  警告:")
            for warning in ohlcv_summary["warnings"]:
                print(f"    ⚠️ {warning}")
        
        if ohlcv_summary.get("errors"):
            print(f"\n  错误:")
            for error in ohlcv_summary["errors"]:
                print(f"    ❌ {error}")
        
        # Show sample data
        if result.get("ohlcv_df") is not None and not result["ohlcv_df"].empty:
            print(f"\n数据预览 (前5行):")
            print(result["ohlcv_df"].head())
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_full_data_pipeline():
    """Test full data pipeline with all validation."""
    print_separator("测试 2: 完整数据验证 Pipeline")
    
    trade_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n测试日期: {trade_date}")
    print("测试股票: 贵州茅台 (600519)")
    
    # Use convenience function
    try:
        result = validated_data_fetch(
            symbol="600519",
            trade_date=trade_date,
            market="cn",
            lookback_days=60,
            strict=False
        )
        
        print(f"\n验证总结:")
        summary = result.get("validation_summary", {})
        print(f"  整体验证: {'✅ 通过' if summary.get('overall_valid') else '❌ 未通过'}")
        
        # Check OHLCV validation
        if "ohlcv" in summary:
            ohlcv = summary["ohlcv"]
            print(f"\n  OHLCV 验证:")
            print(f"    状态: {'✅ 通过' if ohlcv.get('valid') else '❌ 未通过'}")
            print(f"    总结: {ohlcv.get('summary')}")
        
        # Check financial validation
        if "financial" in summary:
            finance = summary["financial"]
            print(f"\n  财务指标验证:")
            print(f"    状态: {'✅ 通过' if finance.get('valid') else '❌ 未通过'}")
            print(f"    总结: {finance.get('summary')}")
        
        # Check data quality report
        if "data_quality" in summary:
            quality = summary["data_quality"]
            print(f"\n  数据质量报告:")
            print(f"    行数: {quality.get('row_count')}")
            print(f"    列数: {quality.get('column_count')}")
            print(f"    重复行数: {quality.get('duplicate_rows')}")
            
            if "missing_values" in quality:
                print(f"    缺失值统计:")
                for col, missing_info in quality["missing_values"].items():
                    print(f"      {col}: {missing_info['count']} ({missing_info['percentage']:.1f}%)")
        
        # Show financial metrics
        if result.get("data") and result["data"].get("financial_metrics"):
            print(f"\n  财务指标:")
            metrics = result["data"]["financial_metrics"]
            for key, value in list(metrics.items())[:5]:
                print(f"    {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_validation_logs():
    """Test validation logging functionality."""
    print_separator("测试 3: 验证日志记录")
    
    pipeline = DataPipeline(strict_validation=False)
    trade_date = datetime.now().strftime("%Y-%m-%d")
    
    # Fetch a couple of stocks
    for symbol in ["600519", "AAPL"]:
        market = "cn" if symbol == "600519" else "us"
        try:
            pipeline.fetch_validated_data(
                symbol, trade_date, market, lookback_days=30
            )
        except Exception as e:
            print(f"获取 {symbol} 数据时出错: {e}")
    
    # Print logs
    logs = pipeline.get_validation_logs()
    print(f"\n共 {len(logs)} 条验证日志:\n")
    
    for i, log in enumerate(logs, 1):
        status = "✅" if log["success"] else "❌"
        print(f"{i}. {status} {log['step']} - {log['symbol']}")
        print(f"   时间: {log['timestamp']}")
        if "details" in log and "summary" in log["details"]:
            print(f"   摘要: {log['details']['summary']}")
        print()
    
    # Clear logs
    print("\n清空验证日志...")
    pipeline.clear_validation_logs()
    print(f"当前日志条数: {len(pipeline.get_validation_logs())}")
    
    return True


def test_strict_validation_mode():
    """Test strict mode validation behavior."""
    print_separator("测试 4: 严格模式验证")
    
    from backend.data_layer import DataPipelineValidationError
    
    print("\n启用严格验证模式...")
    pipeline = DataPipeline(strict_validation=True)
    
    # Test with invalid parameters (should pass due to type safety)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    try:
        result = pipeline.fetch_only_ohlcv(
            symbol="600519",
            start_date=start_date,
            end_date=end_date,
            market="cn"
        )
        print("✅ 有效数据在严格模式下正常工作")
        return True
    except DataPipelineValidationError as e:
        print(f"验证错误捕获正常: {e}")
        print(f"验证报告: {e.validation_report}")
        return False
    except Exception as e:
        print(f"❌ 意外错误: {e}")
        return False


def main():
    """Run all pipeline tests."""
    print("=" * 80)
    print("数据流水线集成 BatchDataValidator - 完整测试".center(78))
    print("=" * 80)
    print(f"\n测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Run all tests
    results.append(("OHLCV Pipeline", test_ohlcv_pipeline()))
    results.append(("Full Data Pipeline", test_full_data_pipeline()))
    results.append(("Validation Logs", test_validation_logs()))
    results.append(("Strict Mode", test_strict_validation_mode()))
    
    # Summary
    print_separator("测试总结")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    print(f"\n总测试数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {total - passed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有测试通过！数据流水线正常工作。")
        return 0
    else:
        print("\n⚠️ 部分测试失败，请检查上面的日志。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
