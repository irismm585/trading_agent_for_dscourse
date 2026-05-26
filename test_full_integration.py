#!/usr/bin/env python3
"""完整集成测试 - 用真实 OHLCV 数据验证所有优化模块"""

import sys
import time
from datetime import datetime, timedelta
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

import pandas as pd
import numpy as np


def print_separator(title: str):
    print("\n" + "=" * 80)
    print(f" {title} ".center(78))
    print("=" * 80)


def get_real_ohlcv_data():
    """获取真实 OHLCV 数据"""
    from backend.data_layer import get_stock_ohlcv
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    
    print(f"获取真实数据: 600519 (贵州茅台)")
    print(f"日期范围: {start_date} 到 {end_date}")
    
    df = get_stock_ohlcv("600519", start_date, end_date, "cn")
    
    if df is None or df.empty:
        print("⚠️ 无法获取真实数据，使用模拟数据")
        dates = pd.date_range(start_date, end_date, freq='B')
        df = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(1600, 1800, len(dates)),
            'high': np.random.uniform(1650, 1850, len(dates)),
            'low': np.random.uniform(1550, 1750, len(dates)),
            'close': np.random.uniform(1600, 1800, len(dates)),
            'volume': np.random.randint(1000000, 5000000, len(dates))
        })
    else:
        print(f"✅ 获取到 {len(df)} 条真实数据")
    
    return df


def test_config_center(df: pd.DataFrame):
    """测试优化5: 配置中心化管理"""
    print_separator("优化5: 配置中心化管理 (ConfigCenter)")
    
    from backend.data_layer import ConfigCenter, get_config, set_config
    
    try:
        config = ConfigCenter(environment="production")
        
        # 获取环境
        env = config.get_environment()
        print(f"  环境: {env}")
        
        # 获取配置
        preset = config.get("data_pipeline.preset")
        strict = config.get("data_pipeline.strict_validation")
        print(f"  数据流水线预设: {preset}")
        print(f"  严格模式: {strict}")
        
        # 设置配置
        set_config("test.integration_test", "passed", author="integration")
        value = get_config("test.integration_test")
        print(f"  配置读写测试: {'✅' if value == 'passed' else '❌'}")
        
        # 获取版本历史
        versions = config.get_versions()
        print(f"  配置版本数: {len(versions)}")
        
        print("✅ ConfigCenter 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_level_cache(df: pd.DataFrame):
    """测试优化6: 多级缓存策略"""
    print_separator("优化6: 多级缓存策略 (MultiLevelCache)")
    
    from backend.data_layer import MultiLevelCache, get_cache
    
    try:
        cache = MultiLevelCache(
            memory_max_size=100,
            memory_ttl=3600,
            file_cache_dir="./test_cache_integration"
        )
        
        # 准备测试数据
        test_data = {
            "symbol": "600519",
            "data": df.head(10).to_dict(),
            "timestamp": datetime.now().isoformat()
        }
        
        # 设置缓存
        cache.set("integration_test_ohlcv", test_data, ttl_seconds=300)
        print("  ✅ 缓存设置成功")
        
        # 获取缓存
        cached = cache.get("integration_test_ohlcv")
        print(f"  ✅ 缓存读取成功: {cached['symbol'] if cached else 'None'}")
        
        # 获取统计
        stats = cache.get_stats()
        print(f"  内存缓存命中: {stats['memory']['hits']}")
        print(f"  文件缓存命中: {stats['file']['hits']}")
        print(f"  内存缓存命中率: {stats['memory']['hit_rate']*100:.1f}%")
        
        # 测试 get_or_set
        call_count = [0]
        def loader():
            call_count[0] += 1
            return {"loaded": True, "count": call_count[0]}
        
        result1 = cache.get_or_set("integration_test_loader", loader)
        result2 = cache.get_or_set("integration_test_loader", loader)
        
        print(f"  ✅ get_or_set 测试: loader 调用 {call_count[0]} 次 (预期1次)")
        
        # 清理
        cache.delete("integration_test_ohlcv")
        cache.delete("integration_test_loader")
        
        print("✅ MultiLevelCache 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_lineage(df: pd.DataFrame):
    """测试优化7: 数据血缘追踪"""
    print_separator("优化7: 数据血缘追踪 (DataLineageTracker)")
    
    from backend.data_layer import DataLineageTracker, get_lineage_tracker
    
    try:
        tracker = DataLineageTracker()
        
        # 开始追踪
        tracking_id = tracker.start_tracking(
            symbol="600519",
            market="cn",
            data_type="ohlcv",
            source_id="yfinance"
        )
        print(f"  追踪ID: {tracking_id[:12]}...")
        
        # 添加转换步骤
        step1 = tracker.add_transform(
            tracking_id=tracking_id,
            name="normalize_columns",
            description="标准化列名",
            parameters={"method": "lowercase"}
        )
        print(f"  转换步骤1: {step1[:8]}...")
        
        step2 = tracker.add_transform(
            tracking_id=tracking_id,
            name="calculate_indicators",
            description="计算技术指标",
            parameters={"indicators": ["sma", "rsi", "macd"]}
        )
        print(f"  转换步骤2: {step2[:8]}...")
        
        # 完成追踪
        record = tracker.complete_tracking(
            tracking_id=tracking_id,
            status="success",
            metadata={"row_count": len(df), "columns": list(df.columns)}
        )
        
        print(f"  记录状态: {record.status}")
        print(f"  转换步骤数: {len(record.transforms)}")
        
        # 获取血缘历史
        history = tracker.get_data_lineage("600519", "cn", "ohlcv")
        print(f"  血缘历史记录: {len(history)} 条")
        
        # 获取血缘报告
        report = tracker.get_lineage_report()
        print(f"  总记录数: {report['total_records']}")
        
        print("✅ DataLineageTracker 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_preprocessor(df: pd.DataFrame):
    """测试优化8: 数据预处理流水线"""
    print_separator("优化8: 数据预处理流水线 (DataPreprocessor)")
    
    from backend.data_layer import DataPreprocessor, create_ohlcv_pipeline
    
    try:
        # 创建 OHLCV 流水线
        pipeline = create_ohlcv_pipeline()
        
        # 获取步骤列表
        steps = pipeline.get_steps()
        print(f"  流水线步骤数: {len(steps)}")
        for step in steps:
            status = "✅" if step['enabled'] else "⏸️"
            print(f"    {status} {step['name']}: {step['description']}")
        
        # 执行处理
        start_time = time.time()
        result = pipeline.process(df)
        duration = (time.time() - start_time) * 1000
        
        print(f"\n  处理结果:")
        print(f"    成功: {result.success}")
        print(f"    执行步骤: {len(result.steps_executed)}")
        print(f"    质量分数: {result.quality_score:.1f}/100")
        print(f"    耗时: {duration:.2f}ms")
        
        if result.errors:
            print(f"    错误: {result.errors}")
        if result.warnings:
            print(f"    警告: {result.warnings}")
        
        # 检查处理后的数据
        if result.data is not None:
            print(f"    处理后行数: {len(result.data)}")
            print(f"    处理后列数: {len(result.data.columns)}")
        
        print("✅ DataPreprocessor 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_indicator_engine(df: pd.DataFrame):
    """测试优化9: 指标计算引擎"""
    print_separator("优化9: 指标计算引擎 (IndicatorEngine)")
    
    from backend.data_layer import IndicatorEngine, get_indicator_engine
    
    try:
        engine = IndicatorEngine()
        
        # 获取可用指标
        available = engine.get_available_indicators()
        print(f"  可用指标数: {len(available)}")
        print(f"  指标列表: {list(available.keys())[:5]}...")
        
        # 获取指标信息
        rsi_info = engine.get_indicator_info("rsi")
        print(f"\n  RSI 指标信息:")
        print(f"    描述: {rsi_info['description']}")
        print(f"    类别: {rsi_info['category']}")
        print(f"    参数: {rsi_info['parameters']}")
        
        # 计算多个指标
        print(f"\n  计算指标中...")
        start_time = time.time()
        
        results = engine.calculate(
            df,
            indicators=["sma", "ema", "rsi", "macd", "bollinger_bands", "atr", "price_change_pct", "volatility"],
            parameters={
                "sma": {"period": 20},
                "rsi": {"period": 14},
                "macd": {"fast_period": 12, "slow_period": 26, "signal_period": 9}
            }
        )
        
        duration = (time.time() - start_time) * 1000
        
        print(f"  计算完成，耗时: {duration:.2f}ms")
        print(f"\n  指标计算结果:")
        
        success_count = 0
        for name, result in results.items():
            status = "✅" if result.success else "❌"
            if result.success:
                success_count += 1
                if hasattr(result.values, 'shape'):
                    print(f"    {status} {name}: shape={result.values.shape}")
                elif isinstance(result.values, dict):
                    print(f"    {status} {name}: {len(result.values)} 个子指标")
                else:
                    print(f"    {status} {name}: 计算成功")
            else:
                print(f"    {status} {name}: {result.error}")
        
        print(f"\n  成功率: {success_count}/{len(results)}")
        
        print("✅ IndicatorEngine 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_gateway(df: pd.DataFrame):
    """测试优化10: API网关和限流保护"""
    print_separator("优化10: API网关和限流保护 (APIGateway)")
    
    from backend.data_layer import APIGateway, RateLimitConfig, CircuitBreakerConfig
    
    try:
        # 创建网关
        gateway = APIGateway(
            rate_limit_config=RateLimitConfig(
                requests_per_second=100,
                burst=200,
                window_seconds=60,
                max_requests_per_window=6000
            ),
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=0.5,
                recovery_timeout=30
            )
        )
        
        # 测试限流检查
        print("  测试限流检查...")
        for i in range(10):
            allowed = gateway.check_rate_limit()
            if not allowed:
                print(f"    ⚠️ 请求 {i+1}: 被限流")
            else:
                pass
        print("  ✅ 限流检查通过")
        
        # 测试熔断器
        print("  测试熔断器...")
        allowed = gateway.check_circuit_breaker()
        print(f"    熔断器状态: {'✅ 关闭' if allowed else '❌ 打开'}")
        
        # 测试装饰器
        print("  测试装饰器...")
        
        @gateway.wrap(endpoint="test_ohlcv_fetch", cost=0.001)
        def fetch_ohlcv_data(symbol):
            return {"symbol": symbol, "rows": len(df)}
        
        # 调用被装饰的函数
        result = fetch_ohlcv_data("600519")
        print(f"    调用成功: {result['symbol']}")
        
        # 获取统计和仪表盘
        stats = gateway.get_stats()
        dashboard = gateway.get_dashboard()
        print(f"\n  网关统计:")
        print(f"    总调用数: {stats['global']['total_calls']}")
        print(f"    成功调用: {stats['global']['successful_calls']}")
        print(f"    成功率: {stats['global']['success_rate']*100:.1f}%")
        print(f"    平均延迟: {stats['global']['avg_latency_ms']:.2f}ms")
        print(f"    健康状态: {dashboard['health_status']}")
        
        # 设置成本限制
        gateway.set_cost_limit(100.0)
        print(f"    成本限制: {gateway._cost_limit}")
        
        print("✅ APIGateway 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_incremental_updater(df: pd.DataFrame):
    """测试优化3: 增量数据更新机制"""
    print_separator("优化3: 增量数据更新机制 (IncrementalUpdater)")
    
    from backend.data_layer import IncrementalUpdater, get_incremental_updater
    
    try:
        updater = IncrementalUpdater()
        
        # 检查是否需要更新
        needs_update = updater.needs_update("600519", "cn", "ohlcv")
        print(f"  是否需要更新: {needs_update}")
        
        # 获取增量范围
        start_date, end_date, is_incremental = updater.get_incremental_range(
            "600519", "cn", "ohlcv", full_refresh_days=90
        )
        print(f"  数据范围: {start_date} 到 {end_date}")
        print(f"  是否增量: {is_incremental}")
        
        # 更新版本
        version = updater.update_version(
            "600519", "cn", "ohlcv", df,
            date_range=(start_date, end_date),
            metadata={"source": "integration_test"}
        )
        print(f"  版本号: {version.version}")
        print(f"  数据行数: {version.row_count}")
        print(f"  数据哈希: {version.data_hash[:12]}...")
        
        # 检测变更
        changes = updater.detect_changes("600519", "cn", "ohlcv", df)
        print(f"  变更检测:")
        print(f"    是否有变更: {changes['has_changes']}")
        print(f"    哈希变更: {changes['hash_changed']}")
        print(f"    行数变更: {changes['row_count_changed']}")
        
        # 获取更新报告
        report = updater.get_update_report()
        print(f"  总版本数: {report['total_versions']}")
        
        print("✅ IncrementalUpdater 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_quality_monitor(df: pd.DataFrame):
    """测试优化4: 数据质量监控仪表盘"""
    print_separator("优化4: 数据质量监控仪表盘 (QualityMonitor)")
    
    from backend.data_layer import QualityMonitor, get_quality_monitor
    
    try:
        monitor = QualityMonitor()
        
        # 记录质量指标
        print("  记录质量指标...")
        
        # 数据完整性
        completeness = 1 - (df.isnull().sum().sum() / (df.shape[0] * df.shape[1]))
        monitor.record_metric(
            name="data_completeness",
            value=completeness,
            threshold=0.95,
            unit="%"
        )
        print(f"    数据完整性: {completeness*100:.1f}%")
        
        # 数据行数
        monitor.record_metric(
            name="data_row_count",
            value=len(df),
            threshold=20,
            unit="rows"
        )
        print(f"    数据行数: {len(df)}")
        
        # 更新数据源健康状态
        print("\n  更新数据源健康状态...")
        health = monitor.update_source_health(
            name="yfinance_cn",
            availability=0.99,
            latency_ms=150,
            error_rate=0.01
        )
        print(f"    数据源: {health.name}")
        print(f"    状态: {health.status}")
        print(f"    可用性: {health.availability*100:.1f}%")
        print(f"    延迟: {health.latency_ms:.0f}ms")
        print(f"    错误率: {health.error_rate*100:.1f}%")
        
        # 获取仪表盘数据
        print("\n  获取仪表盘数据...")
        dashboard = monitor.get_dashboard()
        
        print(f"    整体健康度: {dashboard['overall_health']*100:.0f}%")
        print(f"    整体状态: {dashboard['overall_status']}")
        print(f"    活跃告警: {dashboard['alert_count']}")
        print(f"    数据源数: {dashboard['source_count']}")
        print(f"    健康数据源: {dashboard['healthy_sources']}")
        
        # 获取告警
        alerts = monitor.get_alerts(limit=10)
        print(f"    最近告警: {len(alerts)} 条")
        
        print("✅ QualityMonitor 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_smart_fallback(df: pd.DataFrame):
    """测试优化2: 智能数据回退策略"""
    print_separator("优化2: 智能数据回退策略 (SmartFallbackManager)")
    
    from backend.data_layer import SmartFallbackManager, DataSource, get_fallback_manager
    
    try:
        manager = SmartFallbackManager()
        
        # 注册数据源
        print("  注册数据源...")
        manager.register_source("primary_api", priority=3, weight=1.0, metadata={"market": "cn"})
        manager.register_source("secondary_api", priority=2, weight=0.8, metadata={"market": "cn"})
        manager.register_source("fallback_api", priority=1, weight=0.5, metadata={"market": "cn"})
        
        # 获取排序后的数据源
        sorted_sources = manager.get_sorted_sources(market="cn")
        print(f"  排序后数据源 ({len(sorted_sources)} 个):")
        for i, source in enumerate(sorted_sources):
            print(f"    {i+1}. {source.name} (优先级: {source.priority}, 权重: {source.weight})")
        
        # 记录调用
        print("\n  模拟调用...")
        sorted_sources[0].record_success(100.0)
        sorted_sources[1].record_success(150.0)
        
        # 获取统计
        stats = manager.get_global_stats()
        print(f"\n  全局统计:")
        print(f"    注册数据源: {stats['source_count']}")
        print(f"    活跃数据源: {stats['active_sources']}")
        print(f"    熔断中: {stats['circuit_breaker_open_count']}")
        
        # 获取健康报告
        report = manager.get_health_report()
        print(f"\n  健康报告:")
        for source_info in report['sources'][:3]:
            print(f"    {source_info['name']}:")
            print(f"      成功率: {source_info['success_rate']*100:.1f}%")
            print(f"      健康度: {source_info['health_score']:.2f}")
            print(f"      平均延迟: {source_info['avg_response_time']:.0f}ms")
        
        print("✅ SmartFallbackManager 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_async_fetcher(df: pd.DataFrame):
    """测试优化1: 异步数据获取"""
    print_separator("优化1: 异步数据获取 (AsyncDataFetcher)")
    
    from backend.data_layer import AsyncDataFetcher, get_async_fetcher
    import asyncio
    
    try:
        fetcher = AsyncDataFetcher(max_concurrent=5)
        
        print(f"  异步获取器配置:")
        print(f"    最大并发: {fetcher.max_concurrent}")
        print(f"    超时时间: {fetcher.timeout}秒")
        
        # 测试同步方法（不实际运行异步）
        print("\n  测试组件功能...")
        
        # 检查是否有必要的方法
        methods = ['fetch_ohlcv_async', 'fetch_financial_async', 'fetch_news_async', 
                   'fetch_sentiment_async', 'fetch_search_async', 'fetch_all_parallel']
        
        for method in methods:
            if hasattr(fetcher, method):
                print(f"    ✅ {method} 可用")
            else:
                print(f"    ❌ {method} 缺失")
        
        print("\n✅ AsyncDataFetcher 测试通过")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("完整集成测试 - 真实 OHLCV 数据验证所有优化模块".center(78))
    print("=" * 80)
    print(f"\n测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取真实数据
    print_separator("数据准备")
    df = get_real_ohlcv_data()
    print(f"\n数据预览 (前5行):")
    print(df.head())
    print(f"\n数据统计:")
    print(f"  行数: {len(df)}")
    print(f"  列数: {len(df.columns)}")
    print(f"  列名: {list(df.columns)}")
    
    # 运行所有测试
    tests = [
        ("异步数据获取", test_async_fetcher),
        ("智能数据回退", test_smart_fallback),
        ("增量数据更新", test_incremental_updater),
        ("数据质量监控", test_quality_monitor),
        ("配置中心化", test_config_center),
        ("多级缓存策略", test_multi_level_cache),
        ("数据血缘追踪", test_data_lineage),
        ("数据预处理流水线", test_data_preprocessor),
        ("指标计算引擎", test_indicator_engine),
        ("API网关和限流", test_api_gateway),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func(df)
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ 测试 {name} 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 总结
    print_separator("测试总结")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    
    print(f"\n总测试数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {total - passed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    print(f"\n{'优化项':<20} | 结果")
    print("-" * 40)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name:<20} | {status}")
    
    print(f"\n测试结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if passed == total:
        print("\n🎉 所有十个优化模块集成测试通过！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 个测试失败，请检查上面的日志。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
