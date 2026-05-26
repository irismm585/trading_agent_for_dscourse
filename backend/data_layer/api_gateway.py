"""API Gateway - API 网关和限流保护

提供统一的数据 API 网关，支持请求限流、熔断、统计和成本控制。
"""

from __future__ import annotations

import time
import threading
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from functools import wraps
import uuid


@dataclass
class RateLimitConfig:
    """限流配置"""
    requests_per_second: int = 10
    burst: int = 20
    window_seconds: int = 60
    max_requests_per_window: int = 600


@dataclass
class CircuitBreakerConfig:
    """熔断配置"""
    failure_threshold: float = 0.5
    recovery_timeout: int = 30
    half_open_max_calls: int = 5


@dataclass
class APIStats:
    """API 统计"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0.0
    rate_limited_calls: int = 0
    circuit_breaker_triggers: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls


class TokenBucket:
    """令牌桶限流算法"""
    
    def __init__(self, rate: int, burst: int):
        """初始化令牌桶
        
        Args:
            rate: 每秒生成的令牌数
            burst: 最大令牌数
        """
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """消耗令牌
        
        Args:
            tokens: 需要消耗的令牌数
            
        Returns:
            是否成功
        """
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            
            # 补充令牌
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


class SlidingWindow:
    """滑动窗口限流算法"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        """初始化滑动窗口
        
        Args:
            max_requests: 窗口内最大请求数
            window_seconds: 窗口大小（秒）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque = deque()
        self._lock = threading.Lock()
    
    def allow(self) -> bool:
        """检查是否允许请求
        
        Returns:
            是否允许
        """
        with self._lock:
            now = time.time()
            
            # 移除过期的请求
            while self.requests and (now - self.requests[0] > self.window_seconds):
                self.requests.popleft()
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False


class CircuitBreaker:
    """熔断器"""
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(self, config: CircuitBreakerConfig = None):
        """初始化熔断器"""
        self.config = config or CircuitBreakerConfig()
        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self._lock = threading.Lock()
    
    def allow_request(self) -> bool:
        """检查是否允许请求"""
        with self._lock:
            if self.state == self.CLOSED:
                return True
            
            if self.state == self.OPEN:
                now = time.time()
                if now - self.last_failure_time > self.config.recovery_timeout:
                    self.state = self.HALF_OPEN
                    self.success_count = 0
                    return True
                return False
            
            if self.state == self.HALF_OPEN:
                return self.success_count < self.config.half_open_max_calls
            
            return False
    
    def record_success(self):
        """记录成功"""
        with self._lock:
            if self.state == self.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.half_open_max_calls:
                    self.state = self.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
    
    def record_failure(self):
        """记录失败"""
        with self._lock:
            self.failure_count += 1
            
            if self.state == self.CLOSED:
                if self.failure_count >= 5:
                    self.state = self.OPEN
                    self.last_failure_time = time.time()
            elif self.state == self.HALF_OPEN:
                self.state = self.OPEN
                self.last_failure_time = time.time()
                self.success_count = 0


class APIGateway:
    """API 网关"""
    
    def __init__(
        self,
        rate_limit_config: RateLimitConfig = None,
        circuit_breaker_config: CircuitBreakerConfig = None
    ):
        """初始化 API 网关"""
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        
        # 限流组件
        self._token_bucket = TokenBucket(
            rate=self.rate_limit_config.requests_per_second,
            burst=self.rate_limit_config.burst
        )
        self._sliding_window = SlidingWindow(
            max_requests=self.rate_limit_config.max_requests_per_window,
            window_seconds=self.rate_limit_config.window_seconds
        )
        
        # 熔断器
        self._circuit_breaker = CircuitBreaker(self.circuit_breaker_config)
        
        # 统计
        self._stats = APIStats()
        self._endpoint_stats: Dict[str, APIStats] = {}
        
        # 成本追踪
        self._cost_tracker: Dict[str, float] = {}
        self._daily_cost: Dict[str, float] = {}
        self._cost_limit: float = float('inf')
        
        # 锁
        self._lock = threading.Lock()
    
    def check_rate_limit(self) -> bool:
        """检查限流
        
        Returns:
            是否允许请求
        """
        # 检查令牌桶
        if not self._token_bucket.consume():
            return False
        
        # 检查滑动窗口
        if not self._sliding_window.allow():
            return False
        
        return True
    
    def check_circuit_breaker(self) -> bool:
        """检查熔断器
        
        Returns:
            是否允许请求
        """
        return self._circuit_breaker.allow_request()
    
    def wrap(
        self,
        endpoint: str = "default",
        cost: float = 0.0
    ) -> Callable:
        """装饰器：包装 API 调用
        
        Args:
            endpoint: 端点名称
            cost: 调用成本
            
        Returns:
            装饰器函数
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 检查限流
                if not self.check_rate_limit():
                    self._stats.rate_limited_calls += 1
                    raise RateLimitError("Rate limit exceeded")
                
                # 检查熔断器
                if not self.check_circuit_breaker():
                    self._stats.circuit_breaker_triggers += 1
                    raise CircuitBreakerError("Circuit breaker is open")
                
                # 检查成本限制
                if self._check_cost_limit(endpoint, cost):
                    raise CostLimitError("Daily cost limit exceeded")
                
                # 执行调用
                start_time = time.time()
                
                try:
                    result = func(*args, **kwargs)
                    
                    # 记录成功
                    duration_ms = (time.time() - start_time) * 1000
                    
                    self._record_success(endpoint, duration_ms, cost)
                    self._circuit_breaker.record_success()
                    
                    return result
                    
                except Exception as e:
                    # 记录失败
                    self._record_failure(endpoint)
                    self._circuit_breaker.record_failure()
                    raise
            
            return wrapper
        return decorator
    
    def _record_success(
        self,
        endpoint: str,
        duration_ms: float,
        cost: float
    ):
        """记录成功调用"""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.total_latency_ms += duration_ms
            
            if endpoint not in self._endpoint_stats:
                self._endpoint_stats[endpoint] = APIStats()
            
            self._endpoint_stats[endpoint].total_calls += 1
            self._endpoint_stats[endpoint].successful_calls += 1
            self._endpoint_stats[endpoint].total_latency_ms += duration_ms
            
            # 记录成本
            today = datetime.now().strftime("%Y-%m-%d")
            if today not in self._daily_cost:
                self._daily_cost[today] = 0.0
            self._daily_cost[today] += cost
            self._cost_tracker[endpoint] = self._cost_tracker.get(endpoint, 0) + cost
    
    def _record_failure(self, endpoint: str):
        """记录失败调用"""
        with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            
            if endpoint not in self._endpoint_stats:
                self._endpoint_stats[endpoint] = APIStats()
            
            self._endpoint_stats[endpoint].total_calls += 1
            self._endpoint_stats[endpoint].failed_calls += 1
    
    def _check_cost_limit(self, endpoint: str, cost: float) -> bool:
        """检查成本限制"""
        today = datetime.now().strftime("%Y-%m-%d")
        current_cost = self._daily_cost.get(today, 0)
        return (current_cost + cost) > self._cost_limit
    
    def set_cost_limit(self, limit: float):
        """设置成本限制"""
        self._cost_limit = limit
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "timestamp": datetime.now().isoformat(),
            "global": {
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "success_rate": self._stats.success_rate,
                "avg_latency_ms": self._stats.avg_latency_ms,
                "rate_limited_calls": self._stats.rate_limited_calls,
                "circuit_breaker_triggers": self._stats.circuit_breaker_triggers,
            },
            "endpoints": {
                name: {
                    "total_calls": stats.total_calls,
                    "successful_calls": stats.successful_calls,
                    "failed_calls": stats.failed_calls,
                    "success_rate": stats.success_rate,
                    "avg_latency_ms": stats.avg_latency_ms,
                }
                for name, stats in self._endpoint_stats.items()
            },
            "cost": {
                "today": self._daily_cost.get(datetime.now().strftime("%Y-%m-%d"), 0),
                "total": sum(self._cost_tracker.values()),
                "limit": self._cost_limit,
            },
            "circuit_breaker": {
                "state": self._circuit_breaker.state,
                "failure_count": self._circuit_breaker.failure_count,
            },
        }
    
    def reset_stats(self):
        """重置统计"""
        with self._lock:
            self._stats = APIStats()
            self._endpoint_stats = {}
    
    def get_dashboard(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        stats = self.get_stats()
        
        return {
            **stats,
            "health_status": (
                "healthy" if stats["global"]["success_rate"] >= 0.95
                else "degraded" if stats["global"]["success_rate"] >= 0.8
                else "critical"
            ),
            "alerts": self._get_alerts(stats),
        }
    
    def _get_alerts(self, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取告警"""
        alerts = []
        
        if stats["global"]["success_rate"] < 0.95:
            alerts.append({
                "level": "warning",
                "message": f"Success rate is low: {stats['global']['success_rate']:.1%}",
            })
        
        if stats["global"]["rate_limited_calls"] > 100:
            alerts.append({
                "level": "warning",
                "message": f"High rate limiting: {stats['global']['rate_limited_calls']} calls",
            })
        
        if stats["circuit_breaker"]["state"] != "closed":
            alerts.append({
                "level": "critical",
                "message": f"Circuit breaker is {stats['circuit_breaker']['state']}",
            })
        
        return alerts


class RateLimitError(Exception):
    """限流错误"""
    pass


class CircuitBreakerError(Exception):
    """熔断错误"""
    pass


class CostLimitError(Exception):
    """成本限制错误"""
    pass


# 单例
_gateway_instance: Optional[APIGateway] = None


def get_api_gateway(
    rate_limit_config: RateLimitConfig = None) -> APIGateway:
    """获取或创建 API 网关单例"""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = APIGateway(rate_limit_config=rate_limit_config)
    return _gateway_instance
