"""Quality Monitor - 数据质量监控仪表盘

提供数据质量监控、告警、历史趋势分析功能。
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import deque
from pathlib import Path


@dataclass
class QualityMetric:
    """质量指标"""
    name: str
    value: float
    threshold: float
    unit: str = ""
    status: str = "normal"  # normal, warning, critical
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "threshold": self.threshold,
            "unit": self.unit,
            "status": self.status,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class DataSourceHealth:
    """数据源健康状态"""
    name: str
    status: str  # healthy, degraded, down
    availability: float  # 0-1
    latency_ms: float
    error_rate: float
    last_check: datetime
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "availability": self.availability,
            "latency_ms": self.latency_ms,
            "error_rate": self.error_rate,
            "last_check": self.last_check.isoformat(),
            "message": self.message
        }


@dataclass
class Alert:
    """告警信息"""
    id: str
    level: str  # info, warning, critical
    title: str
    message: str
    source: str
    timestamp: datetime
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged
        }


class QualityMonitor:
    """数据质量监控器"""
    
    def __init__(self, max_history: int = 1000, storage_path: str = None):
        """初始化监控器
        
        Args:
            max_history: 最大历史记录数
            storage_path: 持久化存储路径
        """
        self._metrics: Dict[str, deque] = {}
        self._source_health: Dict[str, DataSourceHealth] = {}
        self._alerts: List[Alert] = []
        self._max_history = max_history
        self._storage_path = Path(storage_path) if storage_path else None
        self._alert_callbacks: List[Callable] = []
        self._thresholds = {
            "data_completeness": 0.95,  # 95% 完整性
            "data_accuracy": 0.98,    # 98% 准确性
            "data_timeliness": 300,   # 5 分钟及时性
            "error_rate": 0.05,       # 5% 错误率
            "latency_ms": 5000,       # 5 秒延迟
        }
        
        self._load_history()
    
    def _load_history(self):
        """加载历史数据"""
        if self._storage_path and self._storage_path.exists():
            try:
                with open(self._storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 恢复告警
                    for alert_data in data.get("alerts", []):
                        alert = Alert(
                            id=alert_data["id"],
                            level=alert_data["level"],
                            title=alert_data["title"],
                            message=alert_data["message"],
                            source=alert_data["source"],
                            timestamp=datetime.fromisoformat(alert_data["timestamp"]),
                            acknowledged=alert_data.get("acknowledged", False)
                        )
                        self._alerts.append(alert)
            except Exception:
                pass
    
    def _save_history(self):
        """保存历史数据"""
        if self._storage_path:
            try:
                self._storage_path.parent.mkdir(parents=True, exist_ok=True)
                data = {
                    "alerts": [a.to_dict() for a in self._alerts[-100:]],
                    "timestamp": datetime.now().isoformat()
                }
                with open(self._storage_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
    
    def record_metric(
        self,
        name: str,
        value: float,
        threshold: float = None,
        unit: str = ""
    ) -> QualityMetric:
        """记录质量指标
        
        Args:
            name: 指标名称
            value: 指标值
            threshold: 阈值（如果为 None 使用默认阈值）
            unit: 单位
            
        Returns:
            质量指标对象
        """
        if threshold is None:
            threshold = self._thresholds.get(name, 0.9)
        
        # 确定状态
        status = "normal"
        if name in ["latency_ms", "error_rate"]:
            # 越小越好
            if value > threshold * 1.5:
                status = "critical"
            elif value > threshold:
                status = "warning"
        else:
            # 越大越好
            if value < threshold * 0.8:
                status = "critical"
            elif value < threshold:
                status = "warning"
        
        metric = QualityMetric(
            name=name,
            value=value,
            threshold=threshold,
            unit=unit,
            status=status
        )
        
        # 存储历史
        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=self._max_history)
        self._metrics[name].append(metric)
        
        # 检查是否需要告警
        if status != "normal":
            self._check_and_alert(metric)
        
        return metric
    
    def update_source_health(
        self,
        name: str,
        availability: float,
        latency_ms: float,
        error_rate: float,
        message: str = ""
    ) -> DataSourceHealth:
        """更新数据源健康状态
        
        Args:
            name: 数据源名称
            availability: 可用性 (0-1)
            latency_ms: 延迟（毫秒）
            error_rate: 错误率 (0-1)
            message: 附加消息
            
        Returns:
            数据源健康状态
        """
        # 确定状态
        status = "healthy"
        if availability < 0.7 or error_rate > 0.2 or latency_ms > 10000:
            status = "down"
        elif availability < 0.9 or error_rate > 0.1 or latency_ms > 5000:
            status = "degraded"
        
        health = DataSourceHealth(
            name=name,
            status=status,
            availability=availability,
            latency_ms=latency_ms,
            error_rate=error_rate,
            last_check=datetime.now(),
            message=message
        )
        
        self._source_health[name] = health
        
        # 检查告警
        if status != "healthy":
            self._create_alert(
                level="warning" if status == "degraded" else "critical",
                title=f"数据源 {name} 状态异常",
                message=f"状态: {status}, 可用性: {availability:.1%}, 延迟: {latency_ms:.0f}ms, 错误率: {error_rate:.1%}",
                source=name
            )
        
        return health
    
    def _check_and_alert(self, metric: QualityMetric):
        """检查并创建告警"""
        level = "warning" if metric.status == "warning" else "critical"
        self._create_alert(
            level=level,
            title=f"指标异常: {metric.name}",
            message=f"当前值: {metric.value}{metric.unit}, 阈值: {metric.threshold}{metric.unit}",
            source="metric"
        )
    
    def _create_alert(
        self,
        level: str,
        title: str,
        message: str,
        source: str
    ) -> Alert:
        """创建告警"""
        alert = Alert(
            id=f"alert_{int(time.time() * 1000)}",
            level=level,
            title=title,
            message=message,
            source=source,
            timestamp=datetime.now()
        )
        
        self._alerts.append(alert)
        
        # 限制告警数量
        if len(self._alerts) > 1000:
            self._alerts = self._alerts[-1000:]
        
        # 触发回调
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass
        
        self._save_history()
        
        return alert
    
    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """添加告警回调"""
        self._alert_callbacks.append(callback)
    
    def get_dashboard(self) -> Dict[str, Any]:
        """获取仪表盘数据
        
        Returns:
            完整的仪表盘数据
        """
        now = datetime.now()
        
        # 计算总体健康度
        total_sources = len(self._source_health)
        healthy_sources = sum(
            1 for h in self._source_health.values()
            if h.status == "healthy"
        )
        overall_health = healthy_sources / total_sources if total_sources > 0 else 1.0
        
        # 获取最近的指标
        latest_metrics = {}
        for name, metrics in self._metrics.items():
            if metrics:
                latest_metrics[name] = metrics[-1].to_dict()
        
        # 获取活跃告警
        active_alerts = [
            a.to_dict() for a in self._alerts[-50:]
            if not a.acknowledged
        ]
        
        # 获取历史趋势（最近24小时）
        trend_data = {}
        for name, metrics in self._metrics.items():
            recent = [
                m.to_dict() for m in metrics
                if (now - m.timestamp).total_seconds() < 86400
            ]
            if recent:
                trend_data[name] = recent
        
        return {
            "timestamp": now.isoformat(),
            "overall_health": overall_health,
            "overall_status": (
                "healthy" if overall_health >= 0.9
                else "degraded" if overall_health >= 0.7
                else "critical"
            ),
            "source_count": total_sources,
            "healthy_sources": healthy_sources,
            "sources": [
                h.to_dict() for h in self._source_health.values()
            ],
            "metrics": latest_metrics,
            "active_alerts": active_alerts,
            "alert_count": len(active_alerts),
            "trends": trend_data
        }
    
    def get_alerts(
        self,
        level: str = None,
        acknowledged: bool = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取告警列表
        
        Args:
            level: 按级别过滤
            acknowledged: 按确认状态过滤
            limit: 返回数量限制
            
        Returns:
            告警列表
        """
        alerts = self._alerts
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        
        return [a.to_dict() for a in alerts[-limit:]]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警
        
        Args:
            alert_id: 告警 ID
            
        Returns:
            是否成功
        """
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                self._save_history()
                return True
        return False
    
    def set_threshold(self, name: str, value: float):
        """设置阈值"""
        self._thresholds[name] = value
    
    def get_thresholds(self) -> Dict[str, float]:
        """获取所有阈值"""
        return dict(self._thresholds)


# 单例
_monitor_instance: Optional[QualityMonitor] = None


def get_quality_monitor(
    max_history: int = 1000,
    storage_path: str = None
) -> QualityMonitor:
    """获取或创建监控器单例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = QualityMonitor(
            max_history=max_history,
            storage_path=storage_path
        )
    return _monitor_instance
