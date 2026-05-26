#!/usr/bin/env python3
"""Test integration of validation into data pipeline."""

import sys
from datetime import datetime, timedelta
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

from backend.data_layer.unified_data import fetch_all_data
from backend.data_layer.data_pipeline import DataPipeline


def print_separator(title: str):
    print("\n" + "=" * 80)
    print(f" {title} ".center(78))
    print("=" * 80)


def test_fetch_all_data_validation():
    """Test that fetch_all_data now returns validation_report."""
    print_separator("Test 1: fetch_all_data (CN stock)")
    
    trade_date = datetime.now().strftime("%Y-%m-%d")
    result = fetch_all_data("600519", trade_date, "cn", lookback_days=60)
    
    print(f"\nGot data bundle:")
    print(f"  Market: {result.get('market')}")
    print(f"  Has OHLCV: {result.get('ohlcv_df') is not None}")
    if result.get('ohlcv_df') is not None:
        print(f"  OHLCV rows: {len(result['ohlcv_df'])}")
    
    # Check validation report
    if 'validation_report' in result:
        print(f"\n✅ Found validation_report")
        vr = result['validation_report']
        print(f"  OHLCV valid: {vr.get('ohlcv_valid')}")
        print(f"  Financial valid: {vr.get('financial_valid')}")
        print(f"  Warnings: {len(vr.get('warnings', []))}")
        print(f"  Errors: {len(vr.get('errors', []))}")
        if vr.get('warnings'):
            print(f"  Warning details: {vr.get('warnings')}")
        return True
    else:
        print(f"\n❌ validation_report not found")
        return False


def test_data_pipeline_standalone():
    """Test DataPipeline standalone use."""
    print_separator("Test 2: DataPipeline standalone")
    
    pipeline = DataPipeline(preset="PRODUCTION")
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
    
    try:
        result = pipeline.fetch_only_ohlcv("600036", start_date, end_date, "cn")
        
        print(f"\nDataPipeline result:")
        summary = result.get('validation_summary', {})
        print(f"  Valid: {summary.get('valid')}")
        print(f"  Summary: {summary.get('summary')}")
        
        if result.get('ohlcv_df') is not None:
            print(f"  Rows: {len(result['ohlcv_df'])}")
        
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_compare_approaches():
    """Compare both approaches work."""
    print_separator("Test 3: Both approaches comparison")
    
    print("\nApproach 1: Using fetch_all_data (automatically has validation)")
    trade_date = datetime.now().strftime("%Y-%m-%d")
    result1 = fetch_all_data("AAPL", trade_date, "us", lookback_days=60)
    print(f"  Result1 has validation_report: {'validation_report' in result1}")
    
    print("\nApproach 2: Using DataPipeline directly")
    pipeline = DataPipeline(preset="DEVELOPMENT")
    result2 = pipeline.fetch_validated_data("AAPL", trade_date, "us", lookback_days=60)
    print(f"  Result2 has data: {'data' in result2}")
    
    # Both should work
    return 'validation_report' in result1 and 'data' in result2


def main():
    print("=" * 80)
    print("Data Pipeline Integration Test".center(78))
    print("=" * 80)
    
    tests = [
        ("fetch_all_data validation", test_fetch_all_data_validation),
        ("DataPipeline standalone", test_data_pipeline_standalone),
        ("Both approaches", test_compare_approaches),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Test {name} failed: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print_separator("Summary")
    
    passed = sum(1 for _, s in results if s)
    print(f"\nTests: {passed}/{len(results)} passed")
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")
    
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
