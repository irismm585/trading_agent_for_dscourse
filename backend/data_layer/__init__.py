"""Stock data fetching layer — all data via yfinance.

Works for both US stocks and Chinese A-shares.
"""

from .stock_data import get_stock_ohlcv, compute_indicators
from .fundamental_data import get_financial_data
from .news_data import get_stock_news, get_market_news
from .sentiment_data import get_social_sentiment
from .unified_data import fetch_all_data
from .anysearch import search_stock_info, format_search_summary
from .data_pipeline import (
    DataPipeline,
    DataPipelineValidationError,
    validated_data_fetch,
    validated_ohlcv_fetch,
    get_pipeline
)

# 新优化模块
from .async_data_fetcher import (
    AsyncDataFetcher,
    async_fetch_all,
    get_async_fetcher
)
from .smart_fallback import (
    SmartFallbackManager,
    DataSource,
    get_fallback_manager
)
from .incremental_updater import (
    IncrementalUpdater,
    DataVersion,
    get_incremental_updater
)
from .quality_monitor import (
    QualityMonitor,
    QualityMetric,
    DataSourceHealth,
    Alert,
    get_quality_monitor
)
from .config_center import (
    ConfigCenter,
    ConfigVersion,
    ConfigAuditLog,
    get_config_center,
    get_config,
    set_config
)
from .multi_level_cache import (
    MultiLevelCache,
    LRUCache,
    FileCache,
    RedisCache,
    get_cache
)
from .data_lineage import (
    DataLineageTracker,
    DataSource as LineageDataSource,
    TransformStep,
    LineageRecord,
    get_lineage_tracker
)
from .data_preprocessor import (
    DataPreprocessor,
    PipelineStep,
    PipelineResult,
    create_ohlcv_pipeline,
    create_financial_pipeline
)
from .indicator_engine import (
    IndicatorEngine,
    IndicatorDefinition,
    IndicatorResult,
    get_indicator_engine
)
from .api_gateway import (
    APIGateway,
    RateLimitConfig,
    CircuitBreakerConfig,
    APIStats,
    RateLimitError,
    CircuitBreakerError,
    CostLimitError,
    get_api_gateway
)

__all__ = [
    # 核心数据获取
    "get_stock_ohlcv",
    "compute_indicators",
    "get_financial_data",
    "get_stock_news",
    "get_market_news",
    "get_social_sentiment",
    "fetch_all_data",
    "search_stock_info",
    "format_search_summary",
    
    # 数据流水线
    "DataPipeline",
    "DataPipelineValidationError",
    "validated_data_fetch",
    "validated_ohlcv_fetch",
    "get_pipeline",
    
    # 优化1: 异步数据获取
    "AsyncDataFetcher",
    "async_fetch_all",
    "get_async_fetcher",
    
    # 优化2: 智能数据回退
    "SmartFallbackManager",
    "DataSource",
    "get_fallback_manager",
    
    # 优化3: 增量数据更新
    "IncrementalUpdater",
    "DataVersion",
    "get_incremental_updater",
    
    # 优化4: 数据质量监控
    "QualityMonitor",
    "QualityMetric",
    "DataSourceHealth",
    "Alert",
    "get_quality_monitor",
    
    # 优化5: 配置中心化
    "ConfigCenter",
    "ConfigVersion",
    "ConfigAuditLog",
    "get_config_center",
    "get_config",
    "set_config",
    
    # 优化6: 多级缓存
    "MultiLevelCache",
    "LRUCache",
    "FileCache",
    "RedisCache",
    "get_cache",
    
    # 优化7: 数据血缘追踪
    "DataLineageTracker",
    "LineageDataSource",
    "TransformStep",
    "LineageRecord",
    "get_lineage_tracker",
    
    # 优化8: 数据预处理流水线
    "DataPreprocessor",
    "PipelineStep",
    "PipelineResult",
    "create_ohlcv_pipeline",
    "create_financial_pipeline",
    
    # 优化9: 指标计算引擎
    "IndicatorEngine",
    "IndicatorDefinition",
    "IndicatorResult",
    "get_indicator_engine",
    
    # 优化10: API网关和限流
    "APIGateway",
    "RateLimitConfig",
    "CircuitBreakerConfig",
    "APIStats",
    "RateLimitError",
    "CircuitBreakerError",
    "CostLimitError",
    "get_api_gateway",
]
