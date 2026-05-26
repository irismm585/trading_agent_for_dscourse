#!/usr/bin/env python3
"""测试所有十个优化模块"""

import sys
from datetime import datetime, timedelta
sys.path.insert(0, '/Users/bytedance/Documents/trae_projects/trading_agent_finance')

import pandas as pd
import numpy as np


def print_separator(title: str):
    print("\n" + "=" * 80)
    print(f" {title} ".center(78))
    print("=" * 80)


def test_async_data_fetcher():
    """测试优化1: 异步数据获取"""
    print_separator("优化1: 异步数据获取 (AsyncDataFetcher)")
    
    try:
        from backend.data_layer import AsyncDataFetcher
        
        fetcher = AsyncDataFetcher(max_concurrent=5)
        
        # 检查属性
        assert fetcher.max_concurrent == 5
        assert fetcher.timeout == 30
        
        print("✅ AsyncDataFetcher 初始化成功")
        print(f"   最大并发: {fetcher.max_concurrent}")
        print(f"   超时时间: {fetcher.timeout}秒")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_smart_fallback():
    """测试优化2: 智能数据回退策略"""
    print_separator("优化2: 智能数据回退策略 (SmartFallbackManager)")
    
    try:
        from backend.data_layer import SmartFallbackManager, DataSource
        
        manager = SmartFallbackManager()
        
        # 注册数据源
        manager.register_source("test_source1", priority=3, weight=1.0)
        manager.register_source("test_source2", priority=2, weight=0.8)
        
        # 选择数据源（使用 get_sorted_sources 获取排序后的列表）
        sorted_sources = manager.get_sorted_sources()
        assert len(sorted_sources) >= 2
        
        # 第一个应该是优先级最高的
        assert sorted_sources[0].name == "test_source1"  # 优先级更高
        assert sorted_sources[0].priority == 3
        assert sorted_sources[1].name == "test_source2"
        assert sorted_sources[1].priority == 2
        
        # 记录调用
        sorted_sources[0].record_success(100.0)
        assert sorted_sources[0].success_count == 1
        assert sorted_sources[0].health_score > 0
        
        # 获取统计
        stats = manager.get_global_stats()
        assert stats["source_count"] >= 2
        
        print("✅ SmartFallbackManager 测试通过")
        print(f"   注册数据源: {stats['source_count']}")
        print(f"   排序后第一个: {sorted_sources[0].name} (优先级: {sorted_sources[0].priority})")
        print(f"   健康度评分: {sorted_sources[0].health_score:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_incremental_updater():
    """测试优化3: 增量数据更新机制"""
    print_separator("优化3: 增量数据更新机制 (IncrementalUpdater)")
    
    try:
        from backend.data_layer import IncrementalUpdater
        
        updater = IncrementalUpdater()
        
        # 检查是否需要更新（没有版本记录时应该需要）
        needs_update = updater.needs_update("600519", "cn", "ohlcv")
        assert needs_update == True
        
        # 获取增量范围
        start_date, end_date, is_incremental = updater.get_incremental_range(
            "600519", "cn", "ohlcv", full_refresh_days=90
        )
        assert start_date
        assert end_date
        assert is_incremental == False  # 没有版本记录，应该是全量
        
        # 创建测试数据
        df = pd.DataFrame({
            "date": ["2026-01-01", "2026-01-02"],
            "open": [100, 101],
            "close": [100.5, 101.5]
        })
        
        # 更新版本
        version = updater.update_version(
            "600519", "cn", "ohlcv", df,
            date_range=("2026-01-01", "2026-01-02")
        )
        assert version.version == 1
        assert version.row_count == 2
        
        print("✅ IncrementalUpdater 测试通过")
        print(f"   版本号: {version.version}")
        print(f"   数据行数: {version.row_count}")
        print(f"   数据哈希: {version.data_hash[:12]}...")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_quality_monitor():
    """测试优化4: 数据质量监控仪表盘"""
    print_separator("优化4: 数据质量监控仪表盘 (QualityMonitor)")
    
    try:
        from backend.data_layer import QualityMonitor
        
        monitor = QualityMonitor()
        
        # 记录指标
        metric = monitor.record_metric(
            name="data_completeness",
            value=0.98,
            threshold=0.95,
            unit="%"
        )
        assert metric.status == "normal"
        
        # 更新数据源健康状态
        health = monitor.update_source_health(
            name="yfinance",
            availability=0.99,
            latency_ms=150,
            error_rate=0.01
        )
        assert health.status == "healthy"
        
        # 获取仪表盘数据
        dashboard = monitor.get_dashboard()
        assert "overall_health" in dashboard
        assert "sources" in dashboard
        assert "metrics" in dashboard
        
        print("✅ QualityMonitor 测试通过")
        print(f"   指标状态: {metric.status}")
        print(f"   数据源状态: {health.status}")
        print(f"   整体健康度: {dashboard['overall_health']:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_center():
    """测试优化5: 配置中心化管理"""
    print_separator("优化5: 配置中心化管理 (ConfigCenter)")
    
    try:
        from backend.data_layer import ConfigCenter
        
        config = ConfigCenter(environment="development")
        
        # 获取配置
        env = config.get_environment()
        assert env == "development"
        
        # 获取嵌套配置
        preset = config.get("data_pipeline.preset")
        assert preset is not None
        
        # 设置配置
        config.set("test.key", "test_value", author="test")
        value = config.get("test.key")
        assert value == "test_value"
        
        # 获取所有配置
        all_config = config.get_all()
        assert "environment" in all_config
        
        # 获取版本历史
        versions = config.get_versions()
        assert len(versions) >= 1
        
        print("✅ ConfigCenter 测试通过")
        print(f"   环境: {env}")
        print(f"   数据流水线预设: {preset}")
        print(f"   配置版本数: {len(versions)}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_multi_level_cache():
    """测试优化6: 多级缓存策略"""
    print_separator("优化6: 多级缓存策略 (MultiLevelCache)")
    
    try:
        from backend.data_layer import MultiLevelCache, LRUCache, FileCache
        
        # 测试 LRU 缓存
        lru = LRUCache(max_size=100, default_ttl=3600)
        lru.set("test_key", {"value": 123})
        value = lru.get("test_key")
        assert value == {"value": 123}
        
        # 测试多级缓存
        cache = MultiLevelCache(
            memory_max_size=100,
            memory_ttl=3600,
            file_cache_dir="./test_cache"
        )
        
        # 设置缓存
        cache.set("test_data", {"name": "test", "value": 456})
        
        # 获取缓存
        cached = cache.get("test_data")
        assert cached == {"name": "test", "value": 456}
        
        # 获取统计
        stats = cache.get_stats()
        assert "memory" in stats
        assert "file" in stats
        
        print("✅ MultiLevelCache 测试通过")
        print(f"   内存缓存命中: {stats['memory']['hits']}")
        print(f"   文件缓存命中: {stats['file']['hits']}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_lineage():
    """测试优化7: 数据血缘追踪"""
    print_separator("优化7: 数据血缘追踪 (DataLineageTracker)")
    
    try:
        from backend.data_layer import DataLineageTracker
        
        tracker = DataLineageTracker()
        
        # 开始追踪
        tracking_id = tracker.start_tracking(
            symbol="600519",
            market="cn",
            data_type="ohlcv",
            source_id="yfinance"
        )
        assert tracking_id
        
        # 添加转换步骤
        step_id = tracker.add_transform(
            tracking_id=tracking_id,
            name="normalize_columns",
            description="标准化列名",
            parameters={"method": "lowercase"}
        )
        assert step_id
        
        # 完成追踪
        record = tracker.complete_tracking(
            tracking_id=tracking_id,
            status="success",
            metadata={"row_count": 100}
        )
        assert record
        assert record.status == "success"
        assert len(record.transforms) == 1
        
        # 获取血缘报告
        report = tracker.get_lineage_report()
        assert "total_records" in report
        
        print("✅ DataLineageTracker 测试通过")
        print(f"   追踪ID: {tracking_id[:12]}...")
        print(f"   转换步骤: {len(record.transforms)}")
        print(f"   记录状态: {record.status}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_preprocessor():
    """测试优化8: 数据预处理流水线"""
    print_separator("优化8: 数据预处理流水线 (DataPreprocessor)")
    
    try:
        from backend.data_layer import DataPreprocessor, create_ohlcv_pipeline
        
        # 创建测试数据
        df = pd.DataFrame({
            "date": ["2026-01-01", "2026-01-02", "2026-01-02"],  # 重复日期
            "open": [100, 101, 101],
            "high": [102, 103, 103],
            "low": [99, 100, 100],
            "close": [101, 102, 102],
            "volume": [1000, 2000, 2000]
        })
        
        # 创建 OHLCV 流水线
        pipeline = create_ohlcv_pipeline()
        
        # 执行处理
        result = pipeline.process(df)
        
        assert result.success == True
        assert len(result.steps_executed) > 0
        assert result.quality_score >= 0
        
        print("✅ DataPreprocessor 测试通过")
        print(f"   处理成功: {result.success}")
        print(f"   执行步骤: {len(result.steps_executed)}")
        print(f"   质量分数: {result.quality_score:.1f}")
        print(f"   耗时: {result.duration_ms:.2f}ms")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_indicator_engine():
    """测试优化9: 指标计算引擎"""
    print_separator("优化9: 指标计算引擎 (IndicatorEngine)")
    
    try:
        from backend.data_layer import IndicatorEngine
        
        engine = IndicatorEngine()
        
        # 获取可用指标
        available = engine.get_available_indicators()
        assert len(available) > 0
        
        # 创建测试数据
        dates = pd.date_range("2026-01-01", periods=50)
        df = pd.DataFrame({
            "date": dates,
            "open": np.random.uniform(90, 110, 50),
            "high": np.random.uniform(100, 120, 50),
            "low": np.random.uniform(80, 100, 50),
            "close": np.random.uniform(90, 110, 50),
            "volume": np.random.randint(1000, 10000, 50)
        })
        
        # 计算指标
        results = engine.calculate(df, ["sma", "rsi", "price_change_pct"])
        
        assert "sma" in results
        assert "rsi" in results
        assert "price_change_pct" in results
        
        # 检查结果
        for name, result in results.items():
            assert result.success == True
            assert result.values is not None
        
        print("✅ IndicatorEngine 测试通过")
        print(f"   可用指标数: {len(available)}")
        print(f"   计算指标数: {len(results)}")
        print(f"   示例指标: {list(results.keys())[:3]}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_gateway():
    """测试优化10: API网关和限流保护"""
    print_separator("优化10: API网关和限流保护 (APIGateway)")
    
    try:
        from backend.data_layer import APIGateway, RateLimitConfig, CircuitBreakerConfig
        
        # 创建网关
        gateway = APIGateway(
            rate_limit_config=RateLimitConfig(
                requests_per_second=100,
                burst=200
            ),
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=0.5,
                recovery_timeout=30
            )
        )
        
        # 检查限流
        for i in range(10):
            allowed = gateway.check_rate_limit()
            assert allowed == True
        
        # 检查熔断器
        allowed = gateway.check_circuit_breaker()
        assert allowed == True
        
        # 测试装饰器
        @gateway.wrap(endpoint="test_api", cost=0.01)
        def test_function(x, y):
            return x + y
        
        # 调用被装饰的函数
        result = test_function(1, 2)
        assert result == 3
        
        # 获取统计
        stats = gateway.get_stats()
        assert "global" in stats
        assert "endpoints" in stats
        
        print("✅ APIGateway 测试通过")
        print(f"   限流检查: 通过")
        print(f"   熔断器状态: 关闭")
        print(f"   总调用数: {stats['global']['total_calls']}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("十个优化模块测试".center(78))
    print("=" * 80)
    print(f"\n测试开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("异步数据获取", test_async_data_fetcher),
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
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ 测试 {name} 异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
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
    
    if passed == total:
        print("\n🎉 所有十个优化模块测试通过！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 个测试失败，请检查上面的日志。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
