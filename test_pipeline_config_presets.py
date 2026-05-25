#!/usr/bin/env python3
"""测试数据流水线的预设配置"""

import sys
from datetime import datetime, timedelta
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

from backend.data_layer import DataPipeline


def print_separator(title):
    print("\n" + "=" * 80)
    print(f" {title} ".center(78))
    print("=" * 80)


def test_presets():
    """测试预设配置"""
    
    print_separator("预设配置测试")
    
    presets = ["PRODUCTION", "BACKTEST", "DEVELOPMENT"]
    
    for preset_name in presets:
        print(f"\n{'─' * 80}")
        print(f"测试预设: {preset_name}")
        print('─' * 80)
        
        # 创建使用预设的 pipeline
        pipeline = DataPipeline(preset=preset_name)
        
        # 输出配置
        print(f"  严格模式: {pipeline.strict_validation}")
        print(f"  最小行数: {pipeline.min_ohlcv_rows}")
        print(f"  最大无效比例: {pipeline.max_invalid_ratio * 100}%")
        
        # 使用真实数据测试
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        
        try:
            result = pipeline.fetch_only_ohlcv(
                symbol="600519",
                start_date=start_date,
                end_date=end_date,
                market="cn"
            )
            
            summary = result["validation_summary"]
            print(f"\n  验证结果:")
            print(f"    有效: {summary.get('valid')}")
            print(f"    总结: {summary.get('summary')}")
            
            if summary.get("warnings"):
                print(f"    警告: {len(summary.get('warnings'))} 条")
            if summary.get("errors"):
                print(f"    错误: {len(summary.get('errors'))} 条")
                
        except Exception as e:
            print(f"  ❌ 测试失败: {e}")
    
    return True


def test_custom_config():
    """测试自定义配置"""
    
    print_separator("自定义配置测试")
    
    # 使用自定义配置
    pipeline = DataPipeline(
        strict_validation=True,
        min_ohlcv_rows=10,
        max_invalid_ratio=0.15
    )
    
    print(f"自定义配置:")
    print(f"  严格模式: {pipeline.strict_validation}")
    print(f"  最小行数: {pipeline.min_ohlcv_rows}")
    print(f"  最大无效比例: {pipeline.max_invalid_ratio * 100}%")
    
    # 验证
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    result = pipeline.fetch_only_ohlcv("600036", start_date, end_date, "cn")
    print(f"\n验证结果: {'✅ 通过' if result['validation_summary']['valid'] else '❌ 失败'}")
    
    return True


def test_comparison():
    """对比不同预设的表现"""
    
    print_separator("不同预设对比")
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    results = []
    
    for preset_name in ["DEVELOPMENT", "PRODUCTION", "BACKTEST"]:
        pipeline = DataPipeline(preset=preset_name)
        
        try:
            result = pipeline.fetch_only_ohlcv("600519", start_date, end_date, "cn")
            valid = result["validation_summary"]["valid"]
            
            results.append({
                "preset": preset_name,
                "valid": valid,
                "summary": result["validation_summary"]["summary"]
            })
            
        except Exception as e:
            results.append({
                "preset": preset_name,
                "valid": False,
                "summary": f"Exception: {str(e)}"
            })
    
    # 打印对比表
    print(f"\n{'Preset':<15} | {'Valid':<6} | {'Summary'}")
    print("-" * 80)
    for r in results:
        status = "✅" if r["valid"] else "❌"
        print(f"{r['preset']:<15} | {status:<6} | {r['summary']}")
    
    return True


def test_convenience_functions():
    """测试便捷函数"""
    
    print_separator("便捷函数测试")
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # 测试使用预设的便捷函数
    from backend.data_layer import validated_ohlcv_fetch
    
    print("\n测试 validated_ohlcv_fetch with PRODUCTION preset:")
    try:
        result = validated_ohlcv_fetch(
            "600519", start_date, end_date, "cn",
            preset="PRODUCTION"
        )
        print(f"  结果: {'✅ 有效' if result['validation_summary']['valid'] else '❌ 无效'}")
    except Exception as e:
        print(f"  ❌ 错误: {e}")
    
    print("\n测试 validated_ohlcv_fetch with BACKTEST preset:")
    try:
        result = validated_ohlcv_fetch(
            "600519", start_date, end_date, "cn",
            preset="BACKTEST"
        )
        print(f"  结果: {'✅ 有效' if result['validation_summary']['valid'] else '❌ 无效'}")
    except Exception as e:
        print(f"  ❌ 错误: {e}")
    
    return True


def main():
    print("=" * 80)
    print("数据流水线配置预设测试".center(78))
    print("=" * 80)
    print(f"\n开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("预设配置", test_presets),
        ("自定义配置", test_custom_config),
        ("预设对比", test_comparison),
        ("便捷函数", test_convenience_functions)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ 测试 {name} 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    print_separator("测试总结")
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n{'测试项':<15} | 结果")
    print("-" * 40)
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:<15} | {status}")
    
    success_count = sum(1 for _, r in results if r)
    print(f"\n总计: {success_count}/{len(results)} 个测试通过")
    
    return 0 if success_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
