"""
测试新实现的功能
- 方案4：类型安全装饰器
- 方案5：性能优化缓存装饰器
- 方案7：批量数据验证器
"""

import sys
import time
from datetime import datetime
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

import pandas as pd
import numpy as np

from backend.utils.data_converters import (
    TypeSafeDecorators,
    CacheDecorators,
    BatchDataValidator
)


def test_type_safe_decorators():
    """测试类型安全装饰器（方案4）"""
    print("\n" + "=" * 60)
    print("测试方案4：类型安全装饰器")
    print("=" * 60)
    
    test_count = 0
    passed_count = 0
    
    # 1. 测试 validate_types 装饰器
    test_count += 2  # 两个测试用例
    try:
        @TypeSafeDecorators.validate_types(data=pd.DataFrame, market=str)
        def test_func(data, market):
            return f"Processed {len(data)} rows for {market}"
        
        df = pd.DataFrame({'date': ['2024-01-01'], 'open': [100]})
        result = test_func(df, 'cn')
        print(f"  ✓ validate_types: {result}")
        passed_count += 1
        
        # 测试类型错误
        try:
            test_func("not a dataframe", 123)
            print(f"  ✗ validate_types should have raised an error")
        except TypeError as e:
            print(f"  ✓ validate_types correctly raised: {e}")
            passed_count += 1
            
    except Exception as e:
        print(f"  ✗ validate_types failed: {e}")
    
    # 2. 测试 validate_in_set 装饰器
    test_count += 2  # 两个测试用例
    try:
        @TypeSafeDecorators.validate_in_set('market', {'cn', 'us'})
        def test_market(market):
            return market
        
        result = test_market('cn')
        print(f"  ✓ validate_in_set: {result}")
        passed_count += 1
        
        try:
            test_market('invalid')
            print(f"  ✗ validate_in_set should have raised an error")
        except ValueError as e:
            print(f"  ✓ validate_in_set correctly raised: {e}")
            passed_count += 1
            
    except Exception as e:
        print(f"  ✗ validate_in_set failed: {e}")
    
    # 3. 测试 auto_convert 装饰器
    test_count += 1
    try:
        @TypeSafeDecorators.auto_convert(value=float, count=int)
        def test_convert(value, count):
            return value * count
        
        result = test_convert("10.5", "3")
        print(f"  ✓ auto_convert: '10.5' * '3' = {result}")
        passed_count += 1
    except Exception as e:
        print(f"  ✗ auto_convert failed: {e}")
    
    return passed_count, test_count


def test_cache_decorators():
    """测试性能优化缓存装饰器（方案5）"""
    print("\n" + "=" * 60)
    print("测试方案5：性能优化缓存装饰器")
    print("=" * 60)
    
    test_count = 0
    passed_count = 0
    
    # 1. 测试基本缓存功能
    test_count += 1
    try:
        call_count = 0
        
        @CacheDecorators.cache_result(ttl_seconds=60)
        def slow_function(x):
            nonlocal call_count
            call_count += 1
            time.sleep(0.01)  # 模拟慢速操作
            return x * 2
        
        # 第一次调用
        start = time.time()
        result1 = slow_function(5)
        first_time = time.time() - start
        
        # 第二次调用（应该从缓存读取）
        start = time.time()
        result2 = slow_function(5)
        second_time = time.time() - start
        
        print(f"  ✓ cache_result: First call: {first_time:.4f}s, Second call: {second_time:.4f}s")
        print(f"  ✓ Results: {result1}, {result2}, Call count: {call_count}")
        
        if result1 == result2 == 10 and call_count == 1:
            passed_count += 1
    except Exception as e:
        print(f"  ✗ cache_result failed: {e}")
    
    # 2. 测试 DataFrame 缓存
    test_count += 1
    try:
        df_call_count = 0
        
        @CacheDecorators.cache_result(ttl_seconds=60)
        def process_df(df):
            nonlocal df_call_count
            df_call_count += 1
            return df.mean(numeric_only=True).to_dict()
        
        df = pd.DataFrame({
            'open': [100, 101, 102],
            'close': [105, 106, 107]
        })
        
        result1 = process_df(df)
        result2 = process_df(df)
        
        print(f"  ✓ DataFrame cache: Call count {df_call_count}, results equal: {result1 == result2}")
        
        if df_call_count == 1 and result1 == result2:
            passed_count += 1
    except Exception as e:
        print(f"  ✗ DataFrame cache failed: {e}")
    
    # 3. 测试缓存信息和清空
    test_count += 1
    try:
        info = CacheDecorators.cache_info()
        print(f"  ✓ Cache info: {info['size']} cached items")
        
        CacheDecorators.clear_cache()
        info = CacheDecorators.cache_info()
        print(f"  ✓ Cache cleared: {info['size']} items remaining")
        
        passed_count += 1
    except Exception as e:
        print(f"  ✗ Cache info/clear failed: {e}")
    
    return passed_count, test_count


def test_batch_data_validator():
    """测试批量数据验证器（方案7）"""
    print("\n" + "=" * 60)
    print("测试方案7：批量数据验证器")
    print("=" * 60)
    
    test_count = 0
    passed_count = 0
    
    # 1. 测试 validate_ohlcv_data
    test_count += 1
    try:
        valid_df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'open': [100, 101],
            'high': [105, 106],
            'low': [98, 99],
            'close': [103, 104],
            'volume': [100000, 150000]
        })
        
        report = BatchDataValidator.validate_ohlcv_data(valid_df, strict=True)
        print(f"  ✓ validate_ohlcv_data: Valid rows {report['valid_rows']}, Invalid {len(report['invalid_rows'])}")
        
        if report['valid_rows'] == 2 and len(report['invalid_rows']) == 0:
            passed_count += 1
    except Exception as e:
        print(f"  ✗ validate_ohlcv_data failed: {e}")
    
    # 2. 测试无效数据检测
    test_count += 1
    try:
        invalid_df = pd.DataFrame({
            'date': ['2024-01-01', 'invalid-date'],
            'open': [100, 'not-a-number'],
            'high': [90, 106],  # High < Low
            'low': [98, 99],
            'close': [103, 104]
        })
        
        report = BatchDataValidator.validate_ohlcv_data(invalid_df, strict=False)
        print(f"  ✓ Invalid data detected: {len(report['invalid_rows'])} invalid rows")
        
        if len(report['invalid_rows']) > 0:
            passed_count += 1
    except Exception as e:
        print(f"  ✗ Invalid data test failed: {e}")
    
    # 3. 测试 validate_financial_data
    test_count += 1
    try:
        financial_data = {
            'pe_ratio': 25.5,
            'pb_ratio': 3.2,
            'market_cap': 1000000000,
            'net_profit': 500000000,
            'revenue': 2000000000
        }
        
        report = BatchDataValidator.validate_financial_data(financial_data, strict=True)
        print(f"  ✓ validate_financial_data: Valid={report['valid']}, Errors={len(report['errors'])}")
        
        if report['valid']:
            passed_count += 1
    except Exception as e:
        print(f"  ✗ validate_financial_data failed: {e}")
    
    # 4. 测试 validate_dataframe_schema
    test_count += 1
    try:
        df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'open': [100.0, 101.0],
            'close': [105.0, 106.0]
        })
        
        schema = {
            'date': str,
            'open': float,
            'close': float
        }
        
        report = BatchDataValidator.validate_dataframe_schema(df, schema, strict=True)
        print(f"  ✓ validate_dataframe_schema: Valid={report['valid']}")
        
        if report['valid']:
            passed_count += 1
    except Exception as e:
        print(f"  ✗ validate_dataframe_schema failed: {e}")
    
    # 5. 测试 generate_quality_report
    test_count += 1
    try:
        df = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'open': [100, 101, 102],
            'close': [105, 106, None],
            'volume': [100000, 150000, 200000]
        })
        
        report = BatchDataValidator.generate_quality_report(df)
        print(f"  ✓ generate_quality_report: Rows={report['row_count']}, Columns={report['column_count']}")
        print(f"  ✓ Missing values in 'close': {report['missing_values']['close']['percentage']:.1f}%")
        
        passed_count += 1
    except Exception as e:
        print(f"  ✗ generate_quality_report failed: {e}")
    
    return passed_count, test_count


def main():
    """主测试函数"""
    print("=" * 60)
    print("新功能测试套件")
    print("=" * 60)
    
    total_tests = 0
    total_passed = 0
    
    # 测试类型安全装饰器
    passed, count = test_type_safe_decorators()
    total_passed += passed
    total_tests += count
    
    # 测试缓存装饰器
    passed, count = test_cache_decorators()
    total_passed += passed
    total_tests += count
    
    # 测试批量数据验证器
    passed, count = test_batch_data_validator()
    total_passed += passed
    total_tests += count
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"总测试数: {total_tests}")
    print(f"通过: {total_passed}")
    print(f"失败: {total_tests - total_passed}")
    print(f"通过率: {(total_passed/total_tests*100):.1f}%")
    
    if total_passed == total_tests:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n✗ {total_tests - total_passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
