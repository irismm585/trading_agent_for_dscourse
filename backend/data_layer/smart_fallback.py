"""Smart Fallback Strategy - 智能数据回退策略

提供多数据源优先级管理、健康度评分、自动切换和负载均衡功能。
"""

from __future__ import annotations

import time
import random
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class DataSource:
    """数据源配置"""
    name: str
    priority: int = 0
    enabled: bool = True
    weight: float = 1.0
    health_score: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_response_time: float = 0.0
    circuit_breaker_open: bool = False
    circuit_breaker_open_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_calls(self) -> int:
        return self.success_count + self.failure_count
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.success_count / self.total_calls
    
    def record_success(self, response_time: float):
        """记录成功调用"""
        self.success_count += 1
        self.last_success = datetime.now()
        self.avg_response_time = (
            (self.avg_response_time * (self.total_calls - 1) + response_time) 
            / self.total_calls
        )
        self._update_health_score()
    
    def record_failure(self):
        """记录失败调用"""
        self.failure_count += 1
        self.last_failure = datetime.now()
        self._update_health_score()
    
    def _update_health_score(self):
        """更新健康度评分"""
        if self.total_calls == 0:
            self.health_score = 1.0
            return
        
        # 成功率权重 60%
        success_factor = self.success_rate * 0.6
        
        # 响应时间权重 20% (越快越好)
        if self.avg_response_time > 0:
            time_factor = min(1.0, 1.0 / (self.avg_response_time / 1000)) * 0.2
        else:
            time_factor = 0.2
        
        # 最近活跃度权重 20%
        recency_factor = 0.2
        if self.last_failure:
            time_since_failure = (datetime.now() - self.last_failure).total_seconds()
            recency_factor = min(1.0, time_since_failure / 3600) * 0.2
        
        self.health_score = success_factor + time_factor + recency_factor


class SmartFallbackManager:
    """智能回退管理器"""
    
    def __init__(self):
        self._sources: Dict[str, DataSource] = {}
        self._global_stats = {
            "total_calls": 0,
            "fallback_count": 0,
            "circuit_breaker_triggers": 0
        }
        self._circuit_breaker_threshold = 0.3  # 30% 失败率触发熔断
        self._circuit_breaker_timeout = 300  # 5 分钟后尝试恢复
    
    def register_source(
        self,
        name: str,
        priority: int = 0,
        weight: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> DataSource:
        """注册数据源"""
        source = DataSource(
            name=name,
            priority=priority,
            weight=weight,
            metadata=metadata or {}
        )
        self._sources[name] = source
        return source
    
    def get_sorted_sources(self, market: str = None) -> List[DataSource]:
        """获取排序后的数据源列表"""
        sources = [
            s for s in self._sources.values()
            if s.enabled and not s.circuit_breaker_open
        ]
        
        # 按市场过滤
        if market:
            sources = [
                s for s in sources
                if s.metadata.get("market") in (None, market)
            ]
        
        # 检查熔断恢复
        for source in sources:
            if source.circuit_breaker_open:
                if source.circuit_breaker_open_time:
                    elapsed = (datetime.now() - source.circuit_breaker_open_time).total_seconds()
                    if elapsed > self._circuit_breaker_timeout:
                        source.circuit_breaker_open = False
                        source.circuit_breaker_open_time = None
        
        # 排序：优先级 > 健康度 > 权重
        sources.sort(
            key=lambda s: (
                -s.priority,
                -s.health_score,
                -s.weight
            )
        )
        
        return sources
    
    def select_source(self, market: str = None) -> Optional[DataSource]:
        """选择最优数据源"""
        sources = self.get_sorted_sources(market)
        if not sources:
            return None
        
        # 加权随机选择（前3个）
        top_sources = sources[:3]
        total_weight = sum(s.weight * s.health_score for s in top_sources)
        
        if total_weight == 0:
            return top_sources[0]
        
        r = random.uniform(0, total_weight)
        current = 0
        for source in top_sources:
            current += source.weight * source.health_score
            if current >= r:
                return source
        
        return top_sources[0]
    
    def execute_with_fallback(
        self,
        func: Callable,
        source_name: str,
        *args,
        **kwargs
    ) -> Any:
        """执行函数，带自动回退"""
        self._global_stats["total_calls"] += 1
        
        source = self._sources.get(source_name)
        if not source or not source.enabled:
            raise ValueError(f"Source not found or disabled: {source_name}")
        
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            response_time = (time.time() - start_time) * 1000
            source.record_success(response_time)
            return result
            
        except Exception as e:
            source.record_failure()
            
            # 检查是否需要熔断
            if source.success_rate < (1 - self._circuit_breaker_threshold):
                if not source.circuit_breaker_open:
                    source.circuit_breaker_open = True
                    source.circuit_breaker_open_time = datetime.now()
                    self._global_stats["circuit_breaker_triggers"] += 1
            
            # 尝试回退
            self._global_stats["fallback_count"] += 1
            
            # 获取备用数据源
            fallback_sources = [
                s for s in self.get_sorted_sources()
                if s.name != source_name and s.enabled
            ]
            
            for fallback_source in fallback_sources:
                try:
                    fallback_func = kwargs.get(f"fallback_{fallback_source.name}")
                    if fallback_func:
                        start_time = time.time()
                        result = fallback_func(*args, **kwargs)
                        response_time = (time.time() - start_time) * 1000
                        fallback_source.record_success(response_time)
                        return result
                except Exception:
                    fallback_source.record_failure()
                    continue
            
            # 所有回退都失败
            raise e
    
    def get_source_stats(self, source_name: str) -> Optional[Dict[str, Any]]:
        """获取数据源统计"""
        source = self._sources.get(source_name)
        if not source:
            return None
        
        return {
            "name": source.name,
            "priority": source.priority,
            "health_score": source.health_score,
            "success_rate": source.success_rate,
            "total_calls": source.total_calls,
            "success_count": source.success_count,
            "failure_count": source.failure_count,
            "avg_response_time": source.avg_response_time,
            "circuit_breaker_open": source.circuit_breaker_open,
            "last_success": source.last_success,
            "last_failure": source.last_failure
        }
    
    def get_global_stats(self) -> Dict[str, Any]:
        """获取全局统计"""
        return {
            **self._global_stats,
            "source_count": len(self._sources),
            "active_sources": len([s for s in self._sources.values() if s.enabled]),
            "circuit_breaker_open_count": len(
                [s for s in self._sources.values() if s.circuit_breaker_open]
            )
        }
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        return {
            "timestamp": datetime.now().isoformat(),
            "global_stats": self.get_global_stats(),
            "sources": [
                self.get_source_stats(name)
                for name in self._sources
            ]
        }


# 默认数据源配置
DEFAULT_SOURCES = {
    "cn": [
        {"name": "pytdx", "priority": 3, "weight": 1.0, "market": "cn"},
        {"name": "akshare", "priority": 2, "weight": 0.8, "market": "cn"},
        {"name": "yfinance_cn", "priority": 1, "weight": 0.5, "market": "cn"},
    ],
    "us": [
        {"name": "yfinance", "priority": 3, "weight": 1.0, "market": "us"},
        {"name": "alpha_vantage", "priority": 2, "weight": 0.7, "market": "us"},
        {"name": "polygon", "priority": 1, "weight": 0.5, "market": "us"},
    ]
}


# 单例
_fallback_manager: Optional[SmartFallbackManager] = None


def get_fallback_manager() -> SmartFallbackManager:
    """获取或创建回退管理器单例"""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = SmartFallbackManager()
        
        # 注册默认数据源
        for market, sources in DEFAULT_SOURCES.items():
            for source_config in sources:
                _fallback_manager.register_source(**source_config)
    
    return _fallback_manager
